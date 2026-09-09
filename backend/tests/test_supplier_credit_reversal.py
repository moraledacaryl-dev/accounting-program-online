import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.entities import AuditEvent, MoneyTransaction, Payable
from app.models.payable_adjustments import (
    SupplierCredit,
    SupplierCreditApplication,
    SupplierCreditApplicationReversal,
)
from app.schemas.supplier_credits import SupplierCreditApplyPayload, SupplierCreditReversePayload
from app.services.supplier_credit_reversal_service import (
    SupplierCreditReversalIdempotencyConflict,
    list_supplier_credits_with_reversals,
    reverse_supplier_credit_application,
)
from app.services.supplier_credit_service import apply_supplier_credit


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def make_records(db, *, credit_amount=100, gross=150, paid=20):
    credit = SupplierCredit(
        supplier_name='Supplier One',
        purchase_order_id='po-1',
        credit_date='2026-09-10',
        amount=credit_amount,
        applied_amount=0,
        balance_available=credit_amount,
        status='open',
        source_app='inventory',
        source_event_id='return-reversal-test',
        notes='test credit',
    )
    payable = Payable(
        supplier_name='Supplier One',
        payable_type='supplier_bill',
        bill_date='2026-09-10',
        due_date='2026-09-30',
        gross_amount=gross,
        amount_paid=paid,
        balance_due=gross - paid,
        status='partial' if paid else 'open',
        posted_at='2026-09-10',
        closed_at=None,
        notes='test payable',
        bir_include=False,
    )
    db.add_all([credit, payable])
    db.flush()
    return credit, payable


def apply_credit(db, credit, payable, amount=40):
    result = apply_supplier_credit(
        db,
        credit.id,
        SupplierCreditApplyPayload(
            payable_id=payable.id,
            amount=amount,
            application_date='2026-09-10',
            notes='original application',
        ),
        'supplier-credit-reversal-apply-001',
        username='reviewer',
    )
    db.flush()
    return db.get(SupplierCreditApplication, result['application']['id'])


def reverse(db, application, *, key='supplier-credit-reverse-001', reason='Wrong bill selected'):
    return reverse_supplier_credit_application(
        db,
        application.id,
        SupplierCreditReversePayload(
            reversal_date='2026-09-10',
            reason=reason,
        ),
        key,
        username='reviewer',
    )


def unlock(monkeypatch):
    monkeypatch.setattr('app.services.supplier_credit_service.ensure_date_unlocked', lambda *args, **kwargs: None)
    monkeypatch.setattr('app.services.supplier_credit_reversal_service.ensure_date_unlocked', lambda *args, **kwargs: None)


def test_reversal_restores_credit_and_payable_without_cash(monkeypatch):
    db = make_session()
    unlock(monkeypatch)
    credit, payable = make_records(db)
    application = apply_credit(db, credit, payable, 40)
    db.commit()
    before_cash = db.query(MoneyTransaction).count()

    result = reverse(db, application)
    db.commit()
    db.refresh(credit)
    db.refresh(payable)

    assert result['replayed'] is False
    assert credit.applied_amount == 0
    assert credit.balance_available == 100
    assert credit.status == 'open'
    assert payable.gross_amount == 150
    assert payable.amount_paid == 20
    assert payable.balance_due == 130
    assert payable.status == 'partial'
    assert db.query(MoneyTransaction).count() == before_cash
    assert db.query(SupplierCreditApplication).count() == 1
    assert db.query(SupplierCreditApplicationReversal).count() == 1
    assert db.query(AuditEvent).filter(AuditEvent.action == 'supplier_credit.application_reversed').count() == 1


def test_reversal_after_later_cash_payment_preserves_payment(monkeypatch):
    db = make_session()
    unlock(monkeypatch)
    credit, payable = make_records(db, gross=150, paid=20)
    application = apply_credit(db, credit, payable, 40)
    db.commit()

    payable.amount_paid = 50
    payable.balance_due = payable.gross_amount - payable.amount_paid
    payable.status = 'partial'
    db.commit()

    reverse(db, application, key='supplier-credit-reverse-payment-001')
    db.commit()
    db.refresh(payable)

    assert payable.gross_amount == 150
    assert payable.amount_paid == 50
    assert payable.balance_due == 100
    assert payable.status == 'partial'


def test_same_reversal_key_replays_without_second_restoration(monkeypatch):
    db = make_session()
    unlock(monkeypatch)
    credit, payable = make_records(db)
    application = apply_credit(db, credit, payable, 40)
    db.commit()

    first = reverse(db, application, key='supplier-credit-reverse-replay-001')
    db.commit()
    replay = reverse(db, application, key='supplier-credit-reverse-replay-001')
    db.commit()
    db.refresh(credit)
    db.refresh(payable)

    assert first['replayed'] is False
    assert replay['replayed'] is True
    assert credit.balance_available == 100
    assert payable.gross_amount == 150
    assert db.query(SupplierCreditApplicationReversal).count() == 1


def test_second_reversal_and_key_reuse_conflict(monkeypatch):
    db = make_session()
    unlock(monkeypatch)
    credit, payable = make_records(db)
    application = apply_credit(db, credit, payable, 40)
    db.commit()
    reverse(db, application, key='supplier-credit-reverse-first-001')
    db.commit()

    with pytest.raises(ValueError, match='already been reversed'):
        reverse(db, application, key='supplier-credit-reverse-second-001')

    db2 = make_session()
    unlock(monkeypatch)
    credit1, payable1 = make_records(db2)
    application1 = apply_credit(db2, credit1, payable1, 20)
    db2.commit()
    reverse(db2, application1, key='supplier-credit-reverse-conflict-001')
    db2.commit()

    credit2 = SupplierCredit(
        supplier_name='Supplier Two', purchase_order_id='po-2', credit_date='2026-09-10',
        amount=30, applied_amount=0, balance_available=30, status='open', source_app='inventory',
        source_event_id='return-reversal-test-two', notes='test credit two',
    )
    payable2 = Payable(
        supplier_name='Supplier Two', payable_type='supplier_bill', bill_date='2026-09-10',
        due_date='2026-09-30', gross_amount=60, amount_paid=0, balance_due=60, status='open',
        posted_at='2026-09-10', closed_at=None, notes='test payable two', bir_include=False,
    )
    db2.add_all([credit2, payable2])
    db2.flush()
    application2 = apply_supplier_credit(
        db2,
        credit2.id,
        SupplierCreditApplyPayload(payable_id=payable2.id, amount=10, application_date='2026-09-10'),
        'supplier-credit-reversal-apply-002',
        username='reviewer',
    )
    db2.commit()

    with pytest.raises(SupplierCreditReversalIdempotencyConflict, match='different supplier-credit reversal'):
        reverse_supplier_credit_application(
            db2,
            application2['application']['id'],
            SupplierCreditReversePayload(reversal_date='2026-09-10', reason='Wrong bill selected'),
            'supplier-credit-reverse-conflict-001',
            username='reviewer',
        )


def test_locked_reversal_date_is_rejected(monkeypatch):
    db = make_session()
    monkeypatch.setattr('app.services.supplier_credit_service.ensure_date_unlocked', lambda *args, **kwargs: None)
    credit, payable = make_records(db)
    application = apply_credit(db, credit, payable, 40)
    db.commit()

    def locked(*args, **kwargs):
        raise ValueError('locked period')

    monkeypatch.setattr('app.services.supplier_credit_reversal_service.ensure_date_unlocked', locked)
    with pytest.raises(ValueError, match='locked period'):
        reverse(db, application, key='supplier-credit-reverse-locked-001')
    db.rollback()
    assert db.query(SupplierCreditApplicationReversal).count() == 0


def test_credit_listing_marks_reversed_application(monkeypatch):
    db = make_session()
    unlock(monkeypatch)
    credit, payable = make_records(db)
    application = apply_credit(db, credit, payable, 40)
    db.commit()
    reverse(db, application, key='supplier-credit-reverse-list-001')
    db.commit()

    rows = list_supplier_credits_with_reversals(db)
    stored_application = rows[0]['applications'][0]
    assert stored_application['is_reversed'] is True
    assert stored_application['reversal']['reason'] == 'Wrong bill selected'
