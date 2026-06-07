import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.entities import FinancialAccount, InventoryItem, MenuItem, MenuPromotion, MoneyTransaction, Payable, PurchaseOrder, PurchaseOrderLine, Receivable, ReceivableAdjustment, SaleOrder, StockMovement, Supplier
from app.schemas.cashflow import MoneyTransactionCreate, ReceivableCreate
from app.schemas.common import SaleOrderCreate
from app.schemas.procurement import ProcurementStatusAction, ReceivingCreate
from app.services.cashflow_service import create_money_transaction, create_receivable, ensure_default_financial_accounts
from app.services.procurement_service import create_receiving_record, set_receiving_status
from app.services.restaurant_service import create_sale_order


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def create_room_charge_receivable(db, *, source_id=101, amount=100, external_id=None):
    return create_receivable(db, ReceivableCreate(
        source_type='pos_room_charge',
        source_id=source_id,
        counterparty_name='Room 201',
        gross_amount=amount,
        external_source='dedicated_pos_cloud',
        external_id=external_id or f'room-charge:charge-{source_id}',
    ))


def test_room_charge_receiver_is_idempotent_and_applies_linked_reversal():
    db = make_session()
    charge = create_room_charge_receivable(db, source_id=101, amount=100)
    replay = create_room_charge_receivable(db, source_id=101, amount=100)
    assert replay['id'] == charge['id']
    assert db.query(Receivable).count() == 1

    adjusted = create_receivable(db, ReceivableCreate(
        source_type='pos_room_charge_reversal',
        source_id=102,
        counterparty_name='Room 201',
        gross_amount=-40,
        external_source='dedicated_pos_cloud',
        external_id='room-charge:refund-102',
        reverses_source_type='pos_room_charge',
        reverses_source_id=101,
    ))
    replay_adjustment = create_receivable(db, ReceivableCreate(
        source_type='pos_room_charge_reversal',
        source_id=102,
        counterparty_name='Room 201',
        gross_amount=-40,
        external_source='dedicated_pos_cloud',
        external_id='room-charge:refund-102',
        reverses_source_type='pos_room_charge',
        reverses_source_id=101,
    ))
    assert adjusted['balance_due'] == 60
    assert replay_adjustment['balance_due'] == 60
    assert db.query(ReceivableAdjustment).count() == 1


def test_room_charge_reversal_validation_rejects_bad_negative_receivables():
    db = make_session()
    create_room_charge_receivable(db, source_id=201, amount=100)

    with pytest.raises(ValueError, match='reverses_source_type and reverses_source_id'):
        create_receivable(db, ReceivableCreate(
            source_type='pos_room_charge_reversal',
            source_id=202,
            counterparty_name='Room 201',
            gross_amount=-20,
            external_source='dedicated_pos_cloud',
            external_id='room-charge:refund-202',
        ))

    with pytest.raises(ValueError, match='only allowed for POS room-charge reversals'):
        create_receivable(db, ReceivableCreate(
            source_type='pos_refund',
            source_id=203,
            counterparty_name='Room 201',
            gross_amount=-20,
            external_source='dedicated_pos_cloud',
            external_id='room-charge:refund-203',
            reverses_source_type='pos_room_charge',
            reverses_source_id=201,
        ))

    with pytest.raises(ValueError, match='only allowed for POS room-charge reversals'):
        create_receivable(db, ReceivableCreate(
            source_type='pos_room_charge_reversal',
            source_id=204,
            counterparty_name='Room 201',
            gross_amount=-20,
            external_source='dedicated_pos_cloud',
            external_id='room-charge:refund-204',
            reverses_source_type='manual_adjustment',
            reverses_source_id=201,
        ))

    with pytest.raises(ValueError, match='Original receivable'):
        create_receivable(db, ReceivableCreate(
            source_type='pos_room_charge_reversal',
            source_id=205,
            counterparty_name='Room 999',
            gross_amount=-20,
            external_source='dedicated_pos_cloud',
            external_id='room-charge:refund-205',
            reverses_source_type='pos_room_charge',
            reverses_source_id=999,
        ))

    with pytest.raises(ValueError, match='exceeds the remaining balance'):
        create_receivable(db, ReceivableCreate(
            source_type='pos_room_charge_reversal',
            source_id=206,
            counterparty_name='Room 201',
            gross_amount=-120,
            external_source='dedicated_pos_cloud',
            external_id='room-charge:refund-206',
            reverses_source_type='pos_room_charge',
            reverses_source_id=201,
        ))

    with pytest.raises(ValueError, match='gross_amount must be greater than zero'):
        create_receivable(db, ReceivableCreate(
            source_type='pos_room_charge',
            source_id=207,
            counterparty_name='Room 201',
            gross_amount=0,
            external_source='dedicated_pos_cloud',
            external_id='room-charge:charge-207',
        ))


def test_room_charge_reversal_supports_full_and_partial_balances():
    db = make_session()
    create_room_charge_receivable(db, source_id=301, amount=100)

    partial = create_receivable(db, ReceivableCreate(
        source_type='pos_room_charge_reversal',
        source_id=302,
        counterparty_name='Room 301',
        gross_amount=-25,
        external_source='dedicated_pos_cloud',
        external_id='room-charge:refund-302',
        reverses_source_type='pos_room_charge',
        reverses_source_id=301,
    ))
    assert partial['balance_due'] == 75

    full_remaining = create_receivable(db, ReceivableCreate(
        source_type='pos_room_charge_reversal',
        source_id=303,
        counterparty_name='Room 301',
        gross_amount=-75,
        external_source='dedicated_pos_cloud',
        external_id='room-charge:refund-303',
        reverses_source_type='pos_room_charge',
        reverses_source_id=301,
    ))
    replay = create_receivable(db, ReceivableCreate(
        source_type='pos_room_charge_reversal',
        source_id=303,
        counterparty_name='Room 301',
        gross_amount=-75,
        external_source='dedicated_pos_cloud',
        external_id='room-charge:refund-303',
        reverses_source_type='pos_room_charge',
        reverses_source_id=301,
    ))

    assert full_remaining['balance_due'] == 0
    assert full_remaining['status'] == 'settled'
    assert full_remaining['adjustments_total'] == -100
    assert full_remaining['adjustments_count'] == 2
    assert full_remaining['latest_adjustment_source_type'] == 'pos_room_charge_reversal'
    assert replay['balance_due'] == 0
    assert db.query(ReceivableAdjustment).count() == 2


def test_pos_money_settlement_receiver_is_idempotent():
    db = make_session()
    ensure_default_financial_accounts(db)
    account = db.query(FinancialAccount).filter(FinancialAccount.code == 'BNK-01').one()
    payload = MoneyTransactionCreate(
        direction='in',
        financial_account_id=account.id,
        amount=250,
        payment_method='gcash',
        external_source='dedicated_pos_cloud',
        external_id='payment:gcash:101',
    )
    first = create_money_transaction(db, payload)
    replay = create_money_transaction(db, payload)
    db.refresh(account)
    assert replay['id'] == first['id']
    assert db.query(MoneyTransaction).count() == 1
    assert account.current_balance == 250


def test_pos_sale_replay_does_not_duplicate_or_reapply_accounting_promotion():
    db = make_session()
    item = MenuItem(name='Burger', module_slug='restaurant', category='Meals', price=100, is_active=True)
    db.add(item)
    db.flush()
    db.add(MenuPromotion(name='Accounting Promo', applies_to='menu_item', menu_item_id=item.id, promo_type='percent_off', promo_value=10, is_active=True))
    db.commit()
    payload = SaleOrderCreate(
        order_no='POS-001',
        order_date='2026-06-01',
        strict_inventory=False,
        external_source='dedicated_pos_cloud',
        external_id='order-uuid-001',
        lines=[{'menu_item_id': item.id, 'quantity': 1, 'unit_price': 100, 'discount_amount': 0}],
    )
    first = create_sale_order(db, payload)
    replay = create_sale_order(db, payload)
    assert replay.id == first.id
    assert first.net_amount == 100
    assert db.query(SaleOrder).count() == 1


def test_posted_receiving_reversal_restores_stock_po_and_unpaid_bill():
    db = make_session()
    supplier = Supplier(name='Supplier A', code='SUP-A', is_active=True)
    item = InventoryItem(name='Eggs', unit='pcs')
    db.add_all([supplier, item])
    db.commit()
    db.refresh(supplier)
    db.refresh(item)
    po = PurchaseOrder(po_no='PO-001', po_date='2026-06-01', supplier_id=supplier.id, status='issued', total_amount=50)
    db.add(po)
    db.flush()
    po_line = PurchaseOrderLine(purchase_order_id=po.id, inventory_item_id=item.id, description='Eggs', quantity_ordered=5, quantity_received=0, unit='pcs', unit_cost=10, line_total=50)
    db.add(po_line)
    db.commit()
    db.refresh(po)
    db.refresh(po_line)

    receiving = create_receiving_record(db, ReceivingCreate(
        receiving_no='RCV-001',
        receiving_date='2026-06-01',
        supplier_id=supplier.id,
        purchase_order_id=po.id,
        status='posted',
        post_to_stock=True,
        auto_create_payable=True,
        lines=[{'purchase_order_line_id': po_line.id, 'inventory_item_id': item.id, 'quantity_received': 5, 'unit_cost': 10}],
    ), username='tester')
    db.refresh(item)
    db.refresh(po_line)
    assert item.quantity_on_hand == 5
    assert po_line.quantity_received == 5
    assert db.query(Payable).filter(Payable.source_type == 'receiving').one().balance_due == 50

    reversed_row = set_receiving_status(db, receiving['id'], ProcurementStatusAction(status='reversed', notes='Supplier return'), username='tester')
    db.refresh(item)
    db.refresh(po_line)
    db.refresh(po)
    payable = db.query(Payable).filter(Payable.source_type == 'receiving').one()
    assert reversed_row['status'] == 'reversed'
    assert item.quantity_on_hand == 0
    assert po_line.quantity_received == 0
    assert po.status == 'issued'
    assert payable.status == 'cancelled'
    assert payable.balance_due == 0
    assert db.query(StockMovement).filter(StockMovement.reason == 'receiving_reversal').count() == 1
