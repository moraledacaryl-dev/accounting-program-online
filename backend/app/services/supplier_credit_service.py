from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.business_clock import business_today
from app.models.entities import Payable
from app.models.payable_adjustments import SupplierCredit, SupplierCreditApplication
from app.schemas.cashflow import SupplierCreditApplyPayload
from app.services.audit_service import record_audit
from app.services.bir_service import ensure_date_unlocked
from app.services.cashflow_service import _serialize_payable, _update_payable_balance


TOLERANCE = 0.0001


class SupplierCreditIdempotencyConflict(ValueError):
    pass


def _money(value) -> float:
    try:
        return round(float(value or 0), 4)
    except (TypeError, ValueError):
        return 0.0


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
        'amount': _money(row.amount),
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
        'amount': _money(row.amount),
        'applied_amount': _money(row.applied_amount),
        'balance_available': _money(row.balance_available),
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
    amount = _money(payload.amount)
    payable_id = int(payload.payable_id)

    existing = (
        db.query(SupplierCreditApplication)
        .filter(SupplierCreditApplication.idempotency_key == key)
        .first()
    )
    if existing:
        same_request = (
            int(existing.supplier_credit_id) == int(credit_id)
            and int(existing.payable_id) == payable_id
            and abs(_money(existing.amount) - amount) <= TOLERANCE
            and str(existing.application_date or '') == date
            and str(existing.notes or '') == str(payload.notes or '')
        )
        if not same_request:
            raise SupplierCreditIdempotencyConflict(
                'Idempotency-Key was already used with a different supplier-credit application.'
            )
        return _replay_result(db, existing)

    if amount <= TOLERANCE:
        raise ValueError('Supplier credit application amount must be greater than zero.')

    # Lock credit first, then payable. All credit applications use this order.
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

    available = max(_money(credit.balance_available), 0.0)
    balance_due = max(_money(payable.balance_due), 0.0)
    if available <= TOLERANCE or (credit.status or '').strip().lower() == 'applied':
        raise ValueError('Supplier credit has no remaining balance.')
    if balance_due <= TOLERANCE:
        raise ValueError('Payable has no remaining balance.')
    if amount - available > TOLERANCE:
        raise ValueError('Application amount cannot exceed supplier credit balance.')
    if amount - balance_due > TOLERANCE:
        raise ValueError('Application amount cannot exceed payable balance.')

    ensure_date_unlocked(
        db,
        date,
        scope='bir',
        action='apply supplier credit in locked period',
    )

    before_credit = {
        'applied_amount': _money(credit.applied_amount),
        'balance_available': available,
        'status': credit.status,
    }
    before_payable = {
        'gross_amount': _money(payable.gross_amount),
        'amount_paid': _money(payable.amount_paid),
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
    db.flush()

    credit.applied_amount = _money(_money(credit.applied_amount) + amount)
    credit.balance_available = _money(max(0.0, available - amount))
    if credit.balance_available <= TOLERANCE:
        credit.balance_available = 0.0
        credit.status = 'applied'
    else:
        credit.status = 'partially_applied'
    db.add(credit)

    # Supplier credits are non-cash reductions of the payable's gross liability.
    # This matches purchase-return adjustments and keeps amount_paid cash-derived.
    payable.gross_amount = _money(max(_money(payable.amount_paid), _money(payable.gross_amount) - amount))
    db.add(payable)
    _update_payable_balance(db, payable.id)
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
            'applied_amount': _money(credit.applied_amount),
            'balance_available': _money(credit.balance_available),
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
            'gross_amount': _money(payable.gross_amount),
            'amount_paid': _money(payable.amount_paid),
            'balance_due': _money(payable.balance_due),
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
