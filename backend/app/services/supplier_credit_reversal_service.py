from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.business_clock import business_today
from app.models.entities import Payable
from app.models.payable_adjustments import (
    SupplierCredit,
    SupplierCreditApplication,
    SupplierCreditApplicationReversal,
)
from app.schemas.supplier_credits import SupplierCreditReversePayload
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
from app.services.supplier_credit_service import list_supplier_credits


class SupplierCreditReversalIdempotencyConflict(ValueError):
    pass


def _normalize_key(value: str | None) -> str:
    key = (value or '').strip()
    if len(key) < 8:
        raise ValueError('Idempotency-Key must contain at least 8 characters.')
    if len(key) > 180:
        raise ValueError('Idempotency-Key must not exceed 180 characters.')
    return key


def _reversal_date(value: str | None) -> str:
    return (value or '').strip() or business_today()


def _serialize_reversal(row: SupplierCreditApplicationReversal) -> dict:
    return {
        'id': row.id,
        'application_id': row.application_id,
        'reversal_date': row.reversal_date,
        'amount': serialize_money(row.amount),
        'idempotency_key': row.idempotency_key,
        'reason': row.reason,
        'reversed_by': row.reversed_by,
        'created_at': row.created_at.isoformat() if row.created_at else None,
    }


def list_supplier_credits_with_reversals(
    db: Session,
    *,
    status: str | None = None,
    supplier_name: str | None = None,
    limit: int = 300,
) -> list[dict]:
    credits = list_supplier_credits(
        db,
        status=status,
        supplier_name=supplier_name,
        limit=limit,
    )
    application_ids = [
        int(application['id'])
        for credit in credits
        for application in credit.get('applications', [])
    ]
    if not application_ids:
        return credits

    reversals = (
        db.query(SupplierCreditApplicationReversal)
        .filter(SupplierCreditApplicationReversal.application_id.in_(application_ids))
        .all()
    )
    by_application = {int(row.application_id): _serialize_reversal(row) for row in reversals}
    for credit in credits:
        for application in credit.get('applications', []):
            application['reversal'] = by_application.get(int(application['id']))
            application['is_reversed'] = application['reversal'] is not None
    return credits


def _same_request(
    row: SupplierCreditApplicationReversal,
    *,
    application_id: int,
    reversal_date: str,
    reason: str,
) -> bool:
    return (
        int(row.application_id) == int(application_id)
        and str(row.reversal_date or '') == reversal_date
        and str(row.reason or '') == reason
    )


def _replay_result(
    db: Session,
    reversal: SupplierCreditApplicationReversal,
) -> dict:
    application = db.get(SupplierCreditApplication, int(reversal.application_id))
    if not application:
        raise SupplierCreditReversalIdempotencyConflict(
            'Idempotent supplier-credit reversal application no longer exists.'
        )
    credit = db.get(SupplierCredit, int(application.supplier_credit_id))
    payable = db.get(Payable, int(application.payable_id))
    if not credit or not payable:
        raise SupplierCreditReversalIdempotencyConflict(
            'Idempotent supplier-credit reversal result no longer exists.'
        )
    return {
        'reversal': _serialize_reversal(reversal),
        'application_id': application.id,
        'supplier_credit_id': credit.id,
        'supplier_credit': {
            'id': credit.id,
            'applied_amount': serialize_money(credit.applied_amount),
            'balance_available': serialize_money(credit.balance_available),
            'status': credit.status,
        },
        'payable': _serialize_payable(payable),
        'replayed': True,
    }


def reverse_supplier_credit_application(
    db: Session,
    application_id: int,
    payload: SupplierCreditReversePayload,
    idempotency_key: str | None,
    *,
    username: str | None = None,
    user=None,
) -> dict:
    key = _normalize_key(idempotency_key)
    date = _reversal_date(payload.reversal_date)
    reason = (payload.reason or '').strip()
    if len(reason) < 3:
        raise ValueError('Reversal reason must contain at least 3 characters.')

    key_match = (
        db.query(SupplierCreditApplicationReversal)
        .filter(SupplierCreditApplicationReversal.idempotency_key == key)
        .first()
    )
    if key_match:
        if not _same_request(
            key_match,
            application_id=application_id,
            reversal_date=date,
            reason=reason,
        ):
            raise SupplierCreditReversalIdempotencyConflict(
                'Idempotency-Key was already used with a different supplier-credit reversal.'
            )
        return _replay_result(db, key_match)

    application = (
        db.query(SupplierCreditApplication)
        .filter(SupplierCreditApplication.id == int(application_id))
        .populate_existing()
        .with_for_update()
        .first()
    )
    if not application:
        raise ValueError('Supplier credit application not found.')

    existing = (
        db.query(SupplierCreditApplicationReversal)
        .filter(SupplierCreditApplicationReversal.application_id == application.id)
        .first()
    )
    if existing:
        if existing.idempotency_key == key and _same_request(
            existing,
            application_id=application.id,
            reversal_date=date,
            reason=reason,
        ):
            return _replay_result(db, existing)
        raise ValueError('Supplier credit application has already been reversed.')

    credit = (
        db.query(SupplierCredit)
        .filter(SupplierCredit.id == int(application.supplier_credit_id))
        .populate_existing()
        .with_for_update()
        .first()
    )
    payable = (
        db.query(Payable)
        .filter(Payable.id == int(application.payable_id))
        .populate_existing()
        .with_for_update()
        .first()
    )
    if not credit or not payable:
        raise ValueError('Supplier credit application references missing financial records.')

    amount = normalize_money(application.amount)
    if amount <= MONEY_TOLERANCE:
        raise ValueError('Supplier credit application has no reversible amount.')
    if normalize_money(credit.applied_amount) + MONEY_TOLERANCE < amount:
        raise ValueError('Supplier credit applied balance is inconsistent with this application.')

    ensure_date_unlocked(
        db,
        date,
        scope='bir',
        action='reverse supplier credit application in locked period',
    )

    before_credit = {
        'applied_amount': normalize_money(credit.applied_amount),
        'balance_available': normalize_money(credit.balance_available),
        'status': credit.status,
    }
    before_payable = {
        'gross_amount': normalize_money(payable.gross_amount),
        'amount_paid': normalize_money(payable.amount_paid),
        'balance_due': normalize_money(payable.balance_due),
        'status': payable.status,
    }

    reversal = SupplierCreditApplicationReversal(
        application_id=application.id,
        reversal_date=date,
        amount=amount,
        idempotency_key=key,
        reason=reason,
        reversed_by=username,
    )
    db.add(reversal)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        winner = (
            db.query(SupplierCreditApplicationReversal)
            .filter(SupplierCreditApplicationReversal.idempotency_key == key)
            .first()
        )
        if winner and _same_request(
            winner,
            application_id=application.id,
            reversal_date=date,
            reason=reason,
        ):
            return _replay_result(db, winner)
        by_application = (
            db.query(SupplierCreditApplicationReversal)
            .filter(SupplierCreditApplicationReversal.application_id == application.id)
            .first()
        )
        if by_application:
            raise ValueError('Supplier credit application has already been reversed.')
        raise SupplierCreditReversalIdempotencyConflict(
            'Idempotency-Key was already used with a different supplier-credit reversal.'
        )

    credit.applied_amount = normalize_money(max(ZERO, normalize_money(credit.applied_amount) - amount))
    credit.balance_available = normalize_money(
        min(normalize_money(credit.amount), normalize_money(credit.balance_available) + amount)
    )
    if credit.applied_amount <= MONEY_TOLERANCE:
        credit.applied_amount = ZERO
        credit.status = 'open'
    else:
        credit.status = 'partially_applied'
    db.add(credit)

    payable.gross_amount = normalize_money(normalize_money(payable.gross_amount) + amount)
    db.add(payable)
    update_payable_balance_exact(db, payable.id)
    db.flush()

    record_audit(
        db,
        entity_type='supplier_credit_application',
        entity_id=application.id,
        action='supplier_credit.application_reversed',
        user=user,
        before={
            'supplier_credit_id': application.supplier_credit_id,
            'payable_id': application.payable_id,
            'application_date': application.application_date,
            'amount': amount,
        },
        after={
            'reversal_id': reversal.id,
            'reversal_date': date,
            'amount': amount,
            'reason': reason,
        },
        source_app='accounting',
        correlation_id=f'supplier-credit-application:{application.id}:reversal:{reversal.id}',
    )
    record_audit(
        db,
        entity_type='supplier_credit',
        entity_id=credit.id,
        action='supplier_credit.application_reversal_restored_credit',
        user=user,
        before=before_credit,
        after={
            'applied_amount': normalize_money(credit.applied_amount),
            'balance_available': normalize_money(credit.balance_available),
            'status': credit.status,
        },
        source_app='accounting',
        correlation_id=f'supplier-credit-application:{application.id}:reversal:{reversal.id}',
    )
    record_audit(
        db,
        entity_type='payable',
        entity_id=payable.id,
        action='supplier_credit.application_reversal_restored_payable',
        user=user,
        before=before_payable,
        after={
            'gross_amount': normalize_money(payable.gross_amount),
            'amount_paid': normalize_money(payable.amount_paid),
            'balance_due': normalize_money(payable.balance_due),
            'status': payable.status,
        },
        source_app='accounting',
        correlation_id=f'supplier-credit-application:{application.id}:reversal:{reversal.id}',
    )

    return {
        'reversal': _serialize_reversal(reversal),
        'application_id': application.id,
        'supplier_credit_id': credit.id,
        'supplier_credit': {
            'id': credit.id,
            'applied_amount': serialize_money(credit.applied_amount),
            'balance_available': serialize_money(credit.balance_available),
            'status': credit.status,
        },
        'payable': _serialize_payable(payable),
        'replayed': False,
    }
