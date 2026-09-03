from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from app.db.database import SessionLocal, engine
from app.models.entities import FinancialAccount, MoneyTransaction
from app.schemas.cashflow import CashflowActionPayload, MoneyTransactionCreate
from app.services.cashflow_service import create_money_transaction
from app.services.money_transaction_mutation_service import cancel_money_transaction


pytestmark = pytest.mark.skipif(
    engine.dialect.name != 'postgresql',
    reason='PostgreSQL CI lane only',
)


def test_postgresql_concurrent_money_transaction_cancel_reverses_effect_once():
    marker = uuid4().hex[:10]
    with SessionLocal() as db:
        account = FinancialAccount(
            name=f'Pass87 account {marker}',
            code=f'P87-{marker}',
            account_type='cash_drawer',
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

        tx = create_money_transaction(
            db,
            MoneyTransactionCreate(
                transaction_date='2026-09-03',
                direction='in',
                financial_account_id=account_id,
                amount=100,
                payment_method='cash',
                status='posted',
                allow_overdraw=False,
                auto_post_accounting=False,
                external_source='pass87_cancel_race',
                external_id=marker,
            ),
            username='pass87-ci',
        )
        tx_id = tx['id']

    barrier = Barrier(2)

    def cancel():
        barrier.wait(timeout=10)
        with SessionLocal() as db:
            try:
                return cancel_money_transaction(
                    db,
                    tx_id,
                    CashflowActionPayload(action_date='2026-09-03'),
                    username='pass87-ci',
                )
            except Exception:
                db.rollback()
                raise

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(cancel), pool.submit(cancel)]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(('ok', future.result(timeout=20)))
            except Exception as exc:
                outcomes.append(('error', exc))

    assert [kind for kind, _ in outcomes].count('ok') == 1
    assert [kind for kind, _ in outcomes].count('error') == 1
    error = next(value for kind, value in outcomes if kind == 'error')
    assert isinstance(error, ValueError)
    assert 'already cancelled' in str(error)

    with SessionLocal() as db:
        tx = db.get(MoneyTransaction, tx_id)
        account = db.get(FinancialAccount, account_id)
        assert tx.status == 'cancelled'
        assert float(account.current_balance or 0) == 0
