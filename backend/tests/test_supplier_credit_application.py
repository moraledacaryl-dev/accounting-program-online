import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.entities import AuditEvent, MoneyTransaction, Payable
from app.models.payable_adjustments import SupplierCredit, SupplierCreditApplication
from app.schemas.cashflow import PayableCreate
from app.schemas.supplier_credits import SupplierCreditApplyPayload
from app.services.subledger_edit_guard import ensure_payable_edit_preserves_settlement
from app.services.supplier_credit_service import (
    SupplierCreditIdempotencyConflict,
    apply_supplier_credit,
)


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def make_credit(db, *, supplier='Supplier One', amount=100):
    row = SupplierCredit(
        supplier_name=supplier,
        purchase_order_id='po-1',
        credit_date='2026-09-10',
        amount=amount,
        applied_amount=0,
        balance_available=amount,
        status='open',
        source_app='inventory',
        source_event_id=f'return-{supplier}-{amount}',
        notes='test credit',
    )
    db.add(row)
    db.flush()
    return row


def make_payable(db, *, supplier='Supplier One', gross=150, paid=20):
    row = Payable(
        supplier_name=supplier,
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
    db.add(row)
    db.flush()
    return row


def apply(db, credit, payable, amount, key='supplier-credit-test-001'):
    return apply_supplier_credit(
        db,
        credit.id,
        SupplierCreditApplyPayload(
            payable_id=payable.id,
            amount=amount,
            application_date='2026-09-10',
            notes='Apply return credit',
        ),
        key,
        username='reviewer',
    )


def test_full_credit_application_reduces_liability_without_cash(monkeypatch):
    db = make_session()
    monkeypatch.setattr('app.services.supplier_credit_service.ensure_date_unlocked', lambda *args, **kwargs: None)
    credit = make_credit(db, amount=100)
    payable = make_payable(db, gross=150, paid=20)

    before_cash = db.query(MoneyTransaction).count()
    result = apply(db, credit, payable, 100)
    db.commit()

    db.refresh(credit)
    db.refresh(payable)
    assert result['replayed'] is False
    assert payable.gross_amount == 50
    assert payable.amount_paid == 20
    assert payable.balance_due == 30
    assert payable.status == 'partial'
    assert credit.applied_amount == 100
    assert credit.balance_available == 0
    assert credit.status == 'applied'
    assert db.query(SupplierCreditApplication).count() == 1
    assert db.query(MoneyTransaction).count() == before_cash
    assert db.query(AuditEvent).filter(AuditEvent.action == 'supplier_credit.applied').count() == 1
    assert db.query(AuditEvent).filter(AuditEvent.action == 'supplier_credit.applied_to_payable').count() == 1


def test_partial_credit_application_preserves_remaining_credit(monkeypatch):
    db = make_session()
    monkeypatch.setattr('app.services.supplier_credit_service.ensure_date_unlocked', lambda *args, **kwargs: None)
    credit = make_credit(db, amount=100)
    payable = make_payable(db, gross=80, paid=0)

    apply(db, credit, payable, 25)
    db.commit()
    db.refresh(credit)
    db.refresh(payable)

    assert payable.gross_amount == 55
    assert payable.balance_due == 55
    assert payable.status == 'open'
    assert credit.applied_amount == 25
    assert credit.balance_available == 75
    assert credit.status == 'partially_applied'


def test_same_idempotency_key_replays_without_second_reduction(monkeypatch):
    db = make_session()
    monkeypatch.setattr('app.services.supplier_credit_service.ensure_date_unlocked', lambda *args, **kwargs: None)
    credit = make_credit(db, amount=100)
    payable = make_payable(db, gross=150, paid=20)

    first = apply(db, credit, payable, 40, 'supplier-credit-replay-001')
    db.commit()
    replay = apply(db, credit, payable, 40, 'supplier-credit-replay-001')
    db.commit()

    db.refresh(credit)
    db.refresh(payable)
    assert first['replayed'] is False
    assert replay['replayed'] is True
    assert payable.gross_amount == 110
    assert payable.balance_due == 90
    assert credit.applied_amount == 40
    assert credit.balance_available == 60
    assert db.query(SupplierCreditApplication).count() == 1


def test_idempotency_key_reuse_with_different_request_is_conflict(monkeypatch):
    db = make_session()
    monkeypatch.setattr('app.services.supplier_credit_service.ensure_date_unlocked', lambda *args, **kwargs: None)
    credit = make_credit(db, amount=100)
    payable = make_payable(db, gross=150, paid=0)
    apply(db, credit, payable, 30, 'supplier-credit-conflict-001')
    db.commit()

    with pytest.raises(SupplierCreditIdempotencyConflict, match='different supplier-credit application'):
        apply(db, credit, payable, 35, 'supplier-credit-conflict-001')


def test_wrong_supplier_and_overapplication_are_rejected_without_mutation(monkeypatch):
    db = make_session()
    monkeypatch.setattr('app.services.supplier_credit_service.ensure_date_unlocked', lambda *args, **kwargs: None)
    credit = make_credit(db, supplier='Supplier One', amount=50)
    other = make_payable(db, supplier='Supplier Two', gross=100, paid=0)

    with pytest.raises(ValueError, match='same supplier'):
        apply(db, credit, other, 10, 'supplier-credit-wrong-001')
    db.rollback()

    db = make_session()
    monkeypatch.setattr('app.services.supplier_credit_service.ensure_date_unlocked', lambda *args, **kwargs: None)
    credit = make_credit(db, amount=50)
    payable = make_payable(db, gross=100, paid=0)
    with pytest.raises(ValueError, match='cannot exceed supplier credit balance'):
        apply(db, credit, payable, 60, 'supplier-credit-over-credit-001')
    db.rollback()

    db = make_session()
    monkeypatch.setattr('app.services.supplier_credit_service.ensure_date_unlocked', lambda *args, **kwargs: None)
    credit = make_credit(db, amount=100)
    payable = make_payable(db, gross=30, paid=0)
    with pytest.raises(ValueError, match='cannot exceed payable balance'):
        apply(db, credit, payable, 40, 'supplier-credit-over-payable-001')
    db.rollback()


def test_adjusted_payable_gross_cannot_be_overwritten_manually(monkeypatch):
    db = make_session()
    monkeypatch.setattr('app.services.supplier_credit_service.ensure_date_unlocked', lambda *args, **kwargs: None)
    credit = make_credit(db, amount=50)
    payable = make_payable(db, gross=100, paid=0)
    apply(db, credit, payable, 25, 'supplier-credit-edit-001')
    db.commit()
    db.refresh(payable)

    changed = PayableCreate(
        supplier_name=payable.supplier_name,
        payable_type=payable.payable_type,
        bill_date=payable.bill_date,
        due_date=payable.due_date,
        gross_amount=80,
        amount_paid=payable.amount_paid,
        status=payable.status,
        notes=payable.notes,
        bir_include=payable.bir_include,
    )
    with pytest.raises(ValueError, match='adjustment-derived'):
        ensure_payable_edit_preserves_settlement(db, payable.id, changed)

    unchanged = changed.model_copy(update={'gross_amount': payable.gross_amount, 'notes': 'metadata edit'})
    ensure_payable_edit_preserves_settlement(db, payable.id, unchanged)
