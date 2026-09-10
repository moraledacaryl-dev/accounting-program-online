from __future__ import annotations

from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.business_clock import business_today
from app.models.entities import Payable
from app.models.payable_adjustments import SupplierCredit, SupplierCreditApplication
from app.schemas.supplier_credits import SupplierCreditApplyPayload
from app.services.audit_service import record_audit
from app.services.bir_service import ensure_date_unlocked
from app.services.cashflow_service import _serialize_payable
from app.services.exact_money_service import (
    MONEY_TOLERANCE,
    ZERO,
    normalize_money,
    serialize_money,
    update_payable_balance_exact,
)


class SupplierCreditIdempotencyConflict(ValueError):
    pass


def _normalize_name(value: str | None) -> str:
    return ' '.join((value or '').strip().casefold().split())


def _application_date(value: str | None) -> str:
    return (value or '').strip() or business_today()


def _normalize_key(value: str | None) -> str:
    key = (value or '').strip()
    if len(key) < 8:
        raise ValueError('Idempotency-Key must contain at least 8 characters.')
    if len(key) > 180:
        raise ValueError('Idempotency-Key must not exceed 180 characters.')
    return key


def _serialize_application(row: SupplierCreditApplication) -> dict:
    return {
        'id': row.id,
        'supplier_credit_id': row.supplier_credit_id,
        'payable_id': row.payable_id,
        'application_date': row.application_date,
        'amount': serialize_money(row.amount),
        'idempotency_key': row.idempotency_key,
        'notes': row.notes,
        'created_by': row.created_by,
        'created_at': row.created_at.isoformat() if row.created_at else None,
    }


def _serialize_credit(db: Session, row: SupplierCredit) -> dict:
    applications = (
        db.query(SupplierCreditApplication)
        .filter(SupplierCreditApplication.supplier_credit_id == row.id)
        .order_by(SupplierCreditApplication.id.asc())
        .all()
    )
    return {
        'id': row.id,
        'supplier_name': row.supplier_name,
        'purchase_order_id': row.purchase_order_id,
        'credit_date': row.credit_date,
        'amount': serialize_money(row.amount),
        'applied_amount': serialize_money(row.applied_amount),
        'balance_available': serialize_money(row.balance_available),
        'status': row.status,
        'source_app': row.source_app,
        'source_event_id': row.source_event_id,
        'notes': row.notes,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'applications': [_serialize_application(item) for item in applications],
    }


def list_supplier_credits(
    db: Session,
    *,
    status: str | None = None,
    supplier_name: str | None = None,
    limit: int = 300,
) -> list[dict]:
    query = db.query(SupplierCredit)
    if status:
        query = query.filter(SupplierCredit.status == status.strip().lower())
    if supplier_name:
        query = query.filter(SupplierCredit.supplier_name.ilike(f'%{supplier_name.strip()}%'))
    rows = query.order_by(SupplierCredit.id.desc()).limit(int(limit)).all()
    return [_serialize_credit(db, row) for row in rows]


def _same_application_request(
    row: SupplierCreditApplication,
    *,
    credit_id: int,
    payable_id: int,
    amount: Decimal,
    application_date: str,
    notes: str | None,
) -> bool:
    return (
        int(row.supplier_credit_id) == int(credit_id)
        and int(row.payable_id) == int(payable_id)
        and abs(normalize_money(row.amount) - amount) <= MONEY_TOLERANCE
        and str(row.application_date or '') == application_date
        and str(row.notes or '') == str(notes or '')
    )


def _replay_result(db: Session, application: SupplierCreditApplication) -> dict:
    credit = db.get(SupplierCredit, int(application.supplier_credit_id))
    payable = db.get(Payable, int(application.payable_id))
    if not credit or not payable:
        raise SupplierCreditIdempotencyConflict(
            'Idempotent supplier-credit result no longer exists.'
        )
    return {
        'application': _serialize_application(application),
        'supplier_credit': _serialize_credit(db, credit),
        'payable': _serialize_payable(payable),
        'replayed': True,
    }


def apply_supplier_credit(
    db: Session,
    credit_id: int,
    payload: SupplierCreditApplyPayload,
    idempotency_key: str | None,
    *,
    username: str | None = None,
    user=None,
) -> dict:
    key = _normalize_key(idempotency_key)
    date = _application_date(payload.application_date)
    amount = normalize_money(payload.amount)
    payable_id = int(payload.payable_id)

    existing = (
        db.query(SupplierCreditApplication)
        .filter(SupplierCreditApplication.idempotency_key == key)
        .first()
    )
    if existing:
        if not _same_application_request(
            existing,
            credit_id=credit_id,
            payable_id=payable_id,
            amount=amount,
            application_date=date,
            notes=payload.notes,
        ):
            raise SupplierCreditIdempotencyConflict(
                'Idempotency-Key was already used with a different supplier-credit application.'
            )
        return _replay_result(db, existing)

    if amount <= MONEY_TOLERANCE:
        raise ValueError('Supplier credit application amount must be greater than zero.')

    credit = (
        db.query(SupplierCredit)
        .filter(SupplierCredit.id == int(credit_id))
        .populate_existing()
        .with_for_update()
        .first()
    )
    if not credit:
        raise ValueError('Supplier credit not found.')

    payable = (
        db.query(Payable)
        .filter(Payable.id == payable_id)
        .populate_existing()
        .with_for_update()
        .first()
    )
    if not payable:
        raise ValueError('Payable not found.')

    if _normalize_name(credit.supplier_name) != _normalize_name(payable.supplier_name):
        raise ValueError('Supplier credit can only be applied to a payable for the same supplier.')

    available = max(normalize_money(credit.balance_available), ZERO)
    balance_due = max(normalize_money(payable.balance_due), ZERO)
    if available <= MONEY_TOLERANCE or (credit.status or '').strip().lower() == 'applied':
        raise ValueError('Supplier credit has no remaining balance.')
    if balance_due <= MONEY_TOLERANCE:
        raise ValueError('Payable has no remaining balance.')
    if amount - available > MONEY_TOLERANCE:
        raise ValueError('Application amount cannot exceed supplier credit balance.')
    if amount - balance_due > MONEY_TOLERANCE:
        raise ValueError('Application amount cannot exceed payable balance.')

    ensure_date_unlocked(
        db,
        date,
        scope='bir',
        action='apply supplier credit in locked period',
    )

    before_credit = {
        'applied_amount': normalize_money(credit.applied_amount),
        'balance_available': available,
        'status': credit.status,
    }
    before_payable = {
        'gross_amount': normalize_money(payable.gross_amount),
        'amount_paid': normalize_money(payable.amount_paid),
        'balance_due': balance_due,
        'status': payable.status,
    }

    application = SupplierCreditApplication(
        supplier_credit_id=credit.id,
        payable_id=payable.id,
        application_date=date,
        amount=amount,
        idempotency_key=key,
        notes=payload.notes,
        created_by=username,
    )
    db.add(application)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        winner = (
            db.query(SupplierCreditApplication)
            .filter(SupplierCreditApplication.idempotency_key == key)
            .first()
        )
        if not winner:
            raise
        if not _same_application_request(
            winner,
            credit_id=credit_id,
            payable_id=payable_id,
            amount=amount,
            application_date=date,
            notes=payload.notes,
        ):
            raise SupplierCreditIdempotencyConflict(
                'Idempotency-Key was already used with a different supplier-credit application.'
            )
        return _replay_result(db, winner)

    credit.applied_amount = normalize_money(normalize_money(credit.applied_amount) + amount)
    credit.balance_available = normalize_money(max(ZERO, available - amount))
    if credit.balance_available <= MONEY_TOLERANCE:
        credit.balance_available = ZERO
        credit.status = 'applied'
    else:
        credit.status = 'partially_applied'
    db.add(credit)

    payable.gross_amount = normalize_money(
        max(normalize_money(payable.amount_paid), normalize_money(payable.gross_amount) - amount)
    )
    db.add(payable)
    update_payable_balance_exact(db, payable.id)
    db.flush()

    record_audit(
        db,
        entity_type='supplier_credit',
        entity_id=credit.id,
        action='supplier_credit.applied',
        user=user,
        before=before_credit,
        after={
            'application_id': application.id,
            'payable_id': payable.id,
            'amount': amount,
            'applied_amount': normalize_money(credit.applied_amount),
            'balance_available': normalize_money(credit.balance_available),
            'status': credit.status,
        },
        source_app='accounting',
        correlation_id=f'supplier-credit:{credit.id}:application:{application.id}',
    )
    record_audit(
        db,
        entity_type='payable',
        entity_id=payable.id,
        action='supplier_credit.applied_to_payable',
        user=user,
        before=before_payable,
        after={
            'supplier_credit_id': credit.id,
            'application_id': application.id,
            'amount': amount,
            'gross_amount': normalize_money(payable.gross_amount),
            'amount_paid': normalize_money(payable.amount_paid),
            'balance_due': normalize_money(payable.balance_due),
            'status': payable.status,
        },
        source_app='accounting',
        correlation_id=f'supplier-credit:{credit.id}:application:{application.id}',
    )

    return {
        'application': _serialize_application(application),
        'supplier_credit': _serialize_credit(db, credit),
        'payable': _serialize_payable(payable),
        'replayed': False,
    }
