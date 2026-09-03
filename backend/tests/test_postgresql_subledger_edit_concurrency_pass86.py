from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from app.db.database import SessionLocal, engine
from app.models.entities import FinancialAccount, MoneyTransaction, Receivable
from app.schemas.cashflow import ReceivableCollectPayload, ReceivableCreate
from app.services.cashflow_service import collect_receivable, create_receivable
from app.services.subledger_edit_service import update_receivable_safely


pytestmark = pytest.mark.skipif(
    engine.dialect.name != 'postgresql',
    reason='PostgreSQL CI lane only',
)


def _run_concurrently(first, second):
    barrier = Barrier(2)

    def wrapped(fn):
        barrier.wait(timeout=10)
        return fn()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(wrapped, fn) for fn in (first, second)]
        results = []
        for future in futures:
            try:
                results.append(('ok', future.result(timeout=20)))
            except Exception as exc:
                results.append(('error', exc))
        return results


def test_postgresql_receivable_edit_serializes_with_collection():
    marker = uuid4().hex[:12]
    with SessionLocal() as db:
        account = FinancialAccount(
            name=f'Pass86 AR account {marker}',
            code=f'P86-{marker}',
            account_type='bank',
            subtype='ci',
            currency='PHP',
            is_active=True,
            requires_daily_reconciliation=False,
            reconciliation_mode='none',
            requires_physical_count=False,
            variance_tolerance=0,
            approval_required_on_variance=False,
            opening_balance=0,
            current_balance=0,
            department='finance',
        )
        db.add(account)
        db.commit()
        account_id = account.id

        receivable = create_receivable(
            db,
            ReceivableCreate(
                source_type='pass86_ci',
                counterparty_name=f'Pass86 Client {marker}',
                receivable_type='other',
                transaction_date='2026-09-03',
                gross_amount=100,
                amount_collected=0,
                status='open',
            ),
        )
        receivable_id = receivable['id']

    def edit():
        with SessionLocal() as db:
            try:
                return update_receivable_safely(
                    db,
                    receivable_id,
                    ReceivableCreate(
                        source_type='pass86_ci',
                        counterparty_name=f'Pass86 Client {marker}',
                        receivable_type='other',
                        transaction_date='2026-09-03',
                        gross_amount=50,
                        amount_collected=0,
                        status='open',
                    ),
                )
            except Exception:
                db.rollback()
                raise

    def collect():
        with SessionLocal() as db:
            try:
                return collect_receivable(
                    db,
                    receivable_id,
                    ReceivableCollectPayload(
                        amount=80,
                        collection_date='2026-09-03',
                        financial_account_id=account_id,
                        payment_method='bank_transfer',
                        reference_no=f'P86-{marker}',
                        module='finance',
                        category='Receivables',
                        auto_post_accounting=False,
                    ),
                    username='pass86-ci',
                )
            except Exception:
                db.rollback()
                raise

    results = _run_concurrently(edit, collect)

    assert [kind for kind, _ in results].count('ok') == 1
    assert [kind for kind, _ in results].count('error') == 1

    with SessionLocal() as db:
        receivable = db.get(Receivable, receivable_id)
        account = db.get(FinancialAccount, account_id)
        linked = db.query(MoneyTransaction).filter(MoneyTransaction.receivable_id == receivable_id).all()

        collected = float(receivable.amount_collected or 0)
        gross = float(receivable.gross_amount or 0)
        balance = float(receivable.balance_due or 0)
        account_balance = float(account.current_balance or 0)

        assert gross >= collected
        assert balance == pytest.approx(gross - collected)
        assert account_balance == pytest.approx(collected)
        assert len(linked) in {0, 1}
