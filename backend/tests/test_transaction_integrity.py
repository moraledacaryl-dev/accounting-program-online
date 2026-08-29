from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.purchase_requests import add_purchase_request
from app.api.stock import add_item, add_movement
from app.db.database import Base
from app.models.entities import InventoryBatch, InventoryItem, PurchaseRequest, StockMovement
from app.schemas.common import InventoryItemCreate, StockMovementCreate
from app.schemas.procurement import PurchaseRequestCreate, PurchaseRequestLineInput


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def test_purchase_request_create_returns_serialized_record_without_duplicate_commit():
    db = make_session()
    payload = PurchaseRequestCreate(
        department='Kitchen',
        status='submitted',
        lines=[
            PurchaseRequestLineInput(
                description='Cooking oil',
                quantity=2,
                unit='bottle',
                estimated_unit_cost=150,
            )
        ],
    )

    result = add_purchase_request(
        payload=payload,
        db=db,
        user=SimpleNamespace(username='auditor'),
    )

    assert result['id']
    assert result['estimated_total'] == 300
    assert result['lines'][0]['quantity'] == 2
    assert db.query(PurchaseRequest).count() == 1


def test_opening_inventory_is_preserved_when_later_stock_is_received():
    db = make_session()
    user = SimpleNamespace(username='auditor')

    item = add_item(
        payload=InventoryItemCreate(
            name='Audit Rice',
            unit='kg',
            quantity_on_hand=2,
            average_cost=50,
        ),
        db=db,
        user=user,
    )

    assert float(item.quantity_on_hand) == 2
    assert db.query(InventoryBatch).filter(InventoryBatch.item_id == item.id).count() == 1
    assert db.query(StockMovement).filter(StockMovement.item_id == item.id).count() == 1

    add_movement(
        payload=StockMovementCreate(
            item_id=item.id,
            movement_type='in',
            quantity=10,
            unit_cost=60,
            reason='Receiving test',
            module_slug='procurement',
        ),
        db=db,
        user=user,
    )

    db.refresh(item)
    open_quantity = sum(
        float(batch.quantity_remaining)
        for batch in db.query(InventoryBatch).filter(
            InventoryBatch.item_id == item.id,
            InventoryBatch.is_closed == False,
        ).all()
    )
    assert float(item.quantity_on_hand) == 12
    assert open_quantity == 12
    assert db.query(StockMovement).filter(StockMovement.item_id == item.id).count() == 2
