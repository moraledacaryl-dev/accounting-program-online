import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.entities import Payable
from app.models.payable_adjustments import PayableAdjustment, SupplierCredit
from app.schemas.integration_review import IntegrationReviewCreate, IntegrationReviewDecision
from app.services.integration_review_service import accept_item, create_review_item, validate_review_payload


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def receive(db, event_id: str, po_id: str, amount: float = 100):
    item = create_review_item(
        db,
        IntegrationReviewCreate(
            source_app='inventory',
            source_event_id=event_id,
            source_entity_type='goods_receipt',
            source_entity_id=event_id,
            financial_effect='payable',
            amount=amount,
            proposed_links={
                'supplier_id': 'sup-1',
                'supplier_name': 'Supplier One',
                'purchase_order_id': po_id,
                'invoice_number': event_id,
            },
            payload={
                'event_type': 'procurement.goods_received',
                'data': {'purchase_order_id': po_id},
            },
            idempotency_key=f'receipt:{event_id}',
        ),
    )
    return accept_item(
        db,
        item['id'],
        IntegrationReviewDecision(transaction_date='2026-09-10'),
        'reviewer',
    )


def purchase_return(db, event_id: str, po_id: str, amount: float):
    payload = IntegrationReviewCreate(
        source_app='inventory',
        source_event_id=event_id,
        source_entity_type='purchase_return',
        source_entity_id=event_id,
        financial_effect='payable_adjustment',
        amount=amount,
        proposed_links={
            'target_type': 'purchase_return',
            'target_id': event_id,
            'supplier_id': 'sup-1',
            'supplier_name': 'Supplier One',
            'purchase_order_id': po_id,
            'return_number': event_id,
        },
        payload={
            'event_type': 'procurement.purchase_return.posted',
            'data': {'purchase_order_id': po_id, 'total': str(amount)},
        },
        idempotency_key=f'return:{event_id}',
    )
    created = create_review_item(db, payload)
    return created, payload


def test_payable_adjustment_validation_requires_inventory_supplier_and_po():
    db = make_session()
    valid = IntegrationReviewCreate(
        source_app='inventory',
        source_event_id='ret-1',
        source_entity_type='purchase_return',
        source_entity_id='ret-1',
        financial_effect='payable_adjustment',
        amount=25,
        proposed_links={'supplier_name': 'Supplier One', 'purchase_order_id': 'po-1'},
    )
    assert validate_review_payload(db, valid)['valid'] is True

    bad = valid.model_copy(update={'proposed_links': {'supplier_name': 'Supplier One'}})
    result = validate_review_payload(db, bad)
    assert result['valid'] is False
    assert 'Payable adjustments require proposed_links.purchase_order_id.' in result['errors']


def test_purchase_return_reduces_unpaid_payable_and_is_replay_safe():
    db = make_session()
    receipt = receive(db, 'grn-1', 'po-1', 100)
    payable_id = receipt['accepted_payable_id']

    created, _ = purchase_return(db, 'ret-1', 'po-1', 40)
    accepted = accept_item(
        db,
        created['id'],
        IntegrationReviewDecision(transaction_date='2026-09-10'),
        'reviewer',
    )
    replay = accept_item(
        db,
        created['id'],
        IntegrationReviewDecision(transaction_date='2026-09-10'),
        'reviewer',
    )

    payable = db.get(Payable, payable_id)
    assert payable.gross_amount == 60
    assert payable.balance_due == 60
    assert payable.status == 'open'
    assert db.query(PayableAdjustment).count() == 1
    assert db.query(SupplierCredit).count() == 0
    assert accepted['validation']['payable_adjustment']['allocated_amount'] == 40
    assert replay['status'] == 'accepted'
    assert db.query(PayableAdjustment).count() == 1


def test_return_over_paid_balance_creates_explicit_supplier_credit():
    db = make_session()
    receipt = receive(db, 'grn-2', 'po-2', 100)
    payable = db.get(Payable, receipt['accepted_payable_id'])
    payable.amount_paid = 70
    payable.balance_due = 30
    payable.status = 'partial'
    db.commit()

    created, _ = purchase_return(db, 'ret-2', 'po-2', 50)
    accepted = accept_item(
        db,
        created['id'],
        IntegrationReviewDecision(transaction_date='2026-09-10'),
        'reviewer',
    )

    db.refresh(payable)
    credit = db.query(SupplierCredit).one()
    assert payable.gross_amount == 70
    assert payable.amount_paid == 70
    assert payable.balance_due == 0
    assert payable.status == 'settled'
    assert db.query(PayableAdjustment).one().amount == 30
    assert credit.amount == 20
    assert credit.balance_available == 20
    assert credit.status == 'open'
    assert accepted['validation']['payable_adjustment']['allocated_amount'] == 30
    assert accepted['validation']['payable_adjustment']['supplier_credit_amount'] == 20


def test_return_allocates_across_multiple_receipt_payables_oldest_first():
    db = make_session()
    first = receive(db, 'grn-3a', 'po-3', 60)
    second = receive(db, 'grn-3b', 'po-3', 40)

    created, _ = purchase_return(db, 'ret-3', 'po-3', 80)
    accept_item(
        db,
        created['id'],
        IntegrationReviewDecision(transaction_date='2026-09-10'),
        'reviewer',
    )

    first_payable = db.get(Payable, first['accepted_payable_id'])
    second_payable = db.get(Payable, second['accepted_payable_id'])
    assert first_payable.balance_due == 0
    assert first_payable.status == 'settled'
    assert second_payable.balance_due == 20
    assert second_payable.status == 'open'
    assert [row.amount for row in db.query(PayableAdjustment).order_by(PayableAdjustment.id).all()] == [60, 20]
    assert db.query(SupplierCredit).count() == 0


def test_return_cannot_be_accepted_before_matching_receipt_payable():
    db = make_session()
    created, _ = purchase_return(db, 'ret-4', 'po-4', 10)
    with pytest.raises(ValueError, match='No accepted goods-receipt payable exists'):
        accept_item(
            db,
            created['id'],
            IntegrationReviewDecision(transaction_date='2026-09-10'),
            'reviewer',
        )
    db.rollback()
    assert db.query(PayableAdjustment).count() == 0
    assert db.query(SupplierCredit).count() == 0
