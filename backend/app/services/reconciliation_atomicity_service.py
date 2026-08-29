from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from app.models.entities import CashReconciliation, CashReconciliationLine, FinancialAccount
from app.schemas.cashflow import CashReconciliationCreate
from app.services.bir_service import ensure_date_unlocked
from app.services.cashflow_service import (
    _account_day_expected_values,
    _as_float,
    _normalize_reconciliation_status,
    _safe_date,
    _serialize_reconciliation,
    ensure_default_financial_accounts,
)


def create_cash_reconciliation_uncommitted(
    db: Session,
    payload: CashReconciliationCreate,
    *,
    username: str | None = None,
) -> dict:
    """Create/update a reconciliation without committing.

    Pass 68 uses this boundary so the reconciliation and its Operations outbox
    event are persisted atomically by the API request's single commit.
    """
    ensure_default_financial_accounts(db)

    account = db.get(FinancialAccount, int(payload.financial_account_id))
    if not account:
        raise ValueError('financial_account_id not found.')

    recon_date = _safe_date(payload.reconciliation_date)
    ensure_date_unlocked(
        db,
        recon_date,
        scope='bir',
        action='create cash reconciliation in locked period',
    )

    opening_balance, expected_in, expected_out, expected_closing = _account_day_expected_values(
        db,
        account.id,
        recon_date,
    )
    actual_counted = _as_float(payload.actual_counted)
    variance = round(actual_counted - expected_closing, 4)
    shift_name = (payload.shift_name or '').strip() or None

    row = (
        db.query(CashReconciliation)
        .filter(
            CashReconciliation.financial_account_id == account.id,
            CashReconciliation.reconciliation_date == recon_date,
            CashReconciliation.shift_name == shift_name,
        )
        .first()
    )
    if not row:
        row = CashReconciliation(
            financial_account_id=account.id,
            reconciliation_date=recon_date,
            shift_name=shift_name,
        )
    else:
        for line in list(row.lines or []):
            db.delete(line)

    recon_status = _normalize_reconciliation_status(payload.status)
    if recon_status == 'closed' and abs(variance) >= 0.01 and not (payload.notes or '').strip():
        raise ValueError('Variance note is required when closing with non-zero variance.')

    row.opening_balance = opening_balance
    row.expected_in = expected_in
    row.expected_out = expected_out
    row.expected_closing = expected_closing
    row.actual_counted = actual_counted
    row.variance = variance
    row.status = recon_status
    row.counted_by = payload.counted_by or username
    row.approved_by = username if row.status in {'reviewed', 'closed'} else row.approved_by
    row.posted_at = recon_date if row.status in {'reviewed', 'closed'} else row.posted_at
    row.closed_at = recon_date if row.status == 'closed' else None
    row.locked_at = recon_date if row.status == 'closed' else None
    row.notes = payload.notes
    db.add(row)
    db.flush()

    for idx, line in enumerate(payload.lines or []):
        db.add(
            CashReconciliationLine(
                cash_reconciliation_id=row.id,
                line_label=(line.line_label or '').strip() or f'line_{idx + 1}',
                amount=_as_float(line.amount),
                notes=line.notes,
                sort_order=int(line.sort_order if line.sort_order is not None else idx),
            )
        )
    db.flush()

    stored = (
        db.query(CashReconciliation)
        .options(
            selectinload(CashReconciliation.financial_account),
            selectinload(CashReconciliation.lines),
        )
        .filter(CashReconciliation.id == row.id)
        .populate_existing()
        .first()
    )
    return _serialize_reconciliation(stored)
