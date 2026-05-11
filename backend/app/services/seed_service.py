import json
from sqlalchemy.orm import Session
from app.models.entities import MasterValue, Employee, InventoryItem, Asset, Booking, ChannelPayout, TaxonomyNode, MenuItem
from app.services.auth_service import ensure_admin_user
from app.services.taxonomy_service import load_taxonomy_file, load_module_index
from app.services.fifo_service import create_inbound_movement

def seed_demo_data(db: Session):
    ensure_admin_user(db)
    if db.query(TaxonomyNode).count() == 0:
        taxonomy = load_taxonomy_file()
        module_index = load_module_index()
        reverse = {v: k for k, v in module_index.items()}
        for module_name, categories in taxonomy.items():
            module_slug = reverse.get(module_name, module_name.lower().replace(' ', '-'))
            for category, buckets in categories.items():
                for bucket, items in buckets.items():
                    for item in items:
                        db.add(TaxonomyNode(module_slug=module_slug, module_name=module_name, category=category, bucket=bucket, item=item, is_active=True))
        db.commit()
    if db.query(Employee).count() == 0:
        db.add_all([
            Employee(full_name='Ann Erica Clarin', department='Front Office', job_title='Receptionist', employment_profile='Regular', compensation_type='Monthly', rate=12676, daily_rate=487.54, hourly_rate=60.94),
            Employee(full_name='Rollan Aranas Enriquez', department='Front Office', job_title='Front Desk Officer', employment_profile='Regular', compensation_type='Monthly', rate=12676, daily_rate=487.54, hourly_rate=60.94),
        ])
        db.commit()
    if db.query(InventoryItem).count() == 0:
        eggs = InventoryItem(name='Eggs', category_name='Raw Materials', subcategory_name='Staples', unit='pcs', reorder_level=30)
        chicken = InventoryItem(name='Chicken', category_name='Raw Materials', subcategory_name='Proteins', unit='kg', reorder_level=3)
        coffee = InventoryItem(name='Coffee Beans', category_name='Beverages', subcategory_name='Coffee Ingredients', unit='g', reorder_level=500)
        db.add_all([eggs, chicken, coffee]); db.commit(); db.refresh(eggs); db.refresh(chicken); db.refresh(coffee)
        create_inbound_movement(db, eggs, 120, 8, 'Purchase', 'inventory', 'SEED-EGGS', 'Demo seed', '2026-04-01', 'Supplier A')
        create_inbound_movement(db, chicken, 12, 240, 'Purchase', 'inventory', 'SEED-CHICKEN', 'Demo seed', '2026-04-01', 'Supplier A')
        create_inbound_movement(db, coffee, 3000, 0.9, 'Purchase', 'inventory', 'SEED-COFFEE', 'Demo seed', '2026-04-01', 'Supplier B')
    if db.query(Asset).count() == 0:
        db.add_all([
            Asset(name='Deluxe King Bed', asset_class='Furniture', location='Room 1', acquisition_cost=18000, useful_life_months=84),
            Asset(name='Chest Freezer', asset_class='Equipment', location='Kitchen', acquisition_cost=22000, useful_life_months=60),
        ])
    if db.query(Booking).count() == 0:
        db.add(Booking(guest_name='Sample Guest', room_name='Deluxe King', room_type='Deluxe', channel='Agoda', status='confirmed', gross_amount=4500, deposit_amount=1000, breakfast_included=2))
    if db.query(ChannelPayout).count() == 0:
        db.add(ChannelPayout(channel='Agoda', booking_ref='AGD-001', gross_amount=4500, commission_amount=675, net_amount=3825, status='pending'))
    if db.query(MenuItem).count() == 0:
        db.add_all([
            MenuItem(name='Tocilog', module_slug='breakfast', category='Breakfast Meals', price=149),
            MenuItem(name='Carbonara', module_slug='restaurant', category='Pasta', price=289),
        ])
    default_masters = {
        'payment_methods': ['Cash', 'GCash', 'Bank Transfer', 'Card', 'OTA Payout'],
        'units': ['pcs', 'packs', 'sets', 'g', 'kg', 'mL', 'L'],
        'workflow_status': ['draft', 'pending_review', 'approved', 'posted', 'archived'],
        'bir_status': ['internal_only', 'ready_for_bir', 'needs_review', 'posted_to_bir'],
        'roles': ['admin', 'owner', 'manager', 'accountant', 'staff'],
    }
    existing = {(m.group_name, m.value) for m in db.query(MasterValue).all()}
    for group, values in default_masters.items():
        for value in values:
            if (group, value) not in existing:
                db.add(MasterValue(group_name=group, value=value, code=value.lower().replace(' ', '_')))
    db.commit()
    return {'ok': True}
