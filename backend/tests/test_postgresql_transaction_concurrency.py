from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from app.db.database import SessionLocal, engine
from app.models.entities import FinancialAccount, MoneyTransaction, Receivable
from app.schemas.cashflow import MoneyTransactionCreate, ReceivableCollectPayload, ReceivableCreate
from app.services.cashflow_service import (
    collect_receivable,
    create_money_transaction,
    create_receivable,
    ensure_default_financial_accounts,
)


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
            except Exception as exc:  # outcome is asserted by each test
                results.append(('error', exc))
        return results


def test_postgresql_concurrent_cash_out_cannot_double_spend_balance():
    marker = uuid4().hex[:12]
    with SessionLocal() as db:
        ensure_default_financial_accounts(db)
        account = FinancialAccount(
            name=f'Pass66 cash race {marker}',
            code=f'P66C-{marker}',
            account_type='bank',
            subtype='ci',
            currency='PHP',
            is_active=True,
            requires_daily_reconciliation=False,
            reconciliation_mode='none',
            requires_physical_count=False,
            variance_tolerance=0,
            approval_required_on_variance=False,
            opening_balance=100,
            current_balance=100,
            department='finance',
        )
        db.add(account)
        db.commit()
        account_id = account.id

    def withdraw(external_id):
        def run():
            with SessionLocal() as db:
                try:
                    return create_money_transaction(
                        db,
                        MoneyTransactionCreate(
                            transaction_date='2026-08-29',
                            direction='out',
                            financial_account_id=account_id,
                            amount=80,
                            payment_method='cash',
                            allow_overdraw=False,
                            external_source='pass66_cash_race',
                            external_id=external_id,
                        ),
                        username='pass66-ci',
                    )
                except Exception:
                    db.rollback()
                    raise
        return run

    results = _run_concurrently(
        withdraw(f'{marker}-a'),
        withdraw(f'{marker}-b'),
    )

    assert [kind for kind, _ in results].count('ok') == 1
    assert [kind for kind, _ in results].count('error') == 1
    error = next(value for kind, value in results if kind == 'error')
    assert isinstance(error, ValueError)
    assert 'Insufficient account balance' in str(error)

    with SessionLocal() as db:
        account = db.get(FinancialAccount, account_id)
        assert float(account.current_balance or 0) == 20
        assert db.query(MoneyTransaction).filter(
            MoneyTransaction.external_source == 'pass66_cash_race',
            MoneyTransaction.external_id.in_([f'{marker}-a', f'{marker}-b']),
        ).count() == 1


def test_postgresql_concurrent_receivable_collection_cannot_overcollect():
    marker = uuid4().hex[:12]
    with SessionLocal() as db:
        account = FinancialAccount(
            name=f'Pass66 AR race {marker}',
            code=f'P66R-{marker}',
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
                source_type='pass66_ci',
                source_id=None,
                counterparty_name=f'Pass66 AR Client {marker}',
                receivable_type='other',
                transaction_date='2026-08-29',
                gross_amount=100,
                amount_collected=0,
                external_source='pass66_ar_race',
                external_id=marker,
            ),
        )
        receivable_id = receivable['id']

    def collect(reference):
        def run():
            with SessionLocal() as db:
                try:
                    return collect_receivable(
                        db,
                        receivable_id,
                        ReceivableCollectPayload(
                            amount=80,
                            collection_date='2026-08-29',
                            financial_account_id=account_id,
                            payment_method='bank_transfer',
                            reference_no=reference,
                            module='finance',
                            category='Receivables',
                            auto_post_accounting=False,
                        ),
                        username='pass66-ci',
                    )
                except Exception:
                    db.rollback()
                    raise
        return run

    results = _run_concurrently(
        collect(f'P66-{marker}-A'),
        collect(f'P66-{marker}-B'),
    )

    assert [kind for kind, _ in results].count('ok') == 1
    assert [kind for kind, _ in results].count('error') == 1
    error = next(value for kind, value in results if kind == 'error')
    assert isinstance(error, ValueError)
    assert 'cannot exceed receivable balance' in str(error)

    with SessionLocal() as db:
        receivable = db.get(Receivable, receivable_id)
        account = db.get(FinancialAccount, account_id)
        assert float(receivable.amount_collected or 0) == 80
        assert float(receivable.balance_due or 0) == 20
        assert float(account.current_balance or 0) == 80
        assert db.query(MoneyTransaction).filter(
            MoneyTransaction.receivable_id == receivable_id
        ).count() == 1
