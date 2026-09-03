from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from app.db.database import SessionLocal, engine
from app.models.entities import AccountTransfer, FinancialAccount
from app.schemas.cashflow import AccountTransferCreate, CashflowActionPayload
from app.services.cashflow_service import create_transfer
from app.services.transfer_mutation_service import approve_transfer


pytestmark = pytest.mark.skipif(
    engine.dialect.name != 'postgresql',
    reason='PostgreSQL CI lane only',
)


def test_postgresql_concurrent_transfer_approval_applies_balance_once():
    marker = uuid4().hex[:10]
    with SessionLocal() as db:
        from_account = FinancialAccount(
            name=f'Pass85 from {marker}',
            code=f'P85F-{marker}',
            account_type='cash_drawer',
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
        to_account = FinancialAccount(
            name=f'Pass85 to {marker}',
            code=f'P85T-{marker}',
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
        db.add_all([from_account, to_account])
        db.commit()
        from_id = from_account.id
        to_id = to_account.id

        transfer = create_transfer(
            db,
            AccountTransferCreate(
                transfer_date='2026-09-03',
                from_account_id=from_id,
                to_account_id=to_id,
                amount=80,
                status='draft',
                allow_overdraw=False,
                auto_post_accounting=False,
                external_source='pass85_transfer_race',
                external_id=marker,
            ),
            username='pass85-ci',
        )
        transfer_id = transfer['id']

    barrier = Barrier(2)

    def approve():
        barrier.wait(timeout=10)
        with SessionLocal() as db:
            try:
                return approve_transfer(
                    db,
                    transfer_id,
                    CashflowActionPayload(action_date='2026-09-03'),
                    username='pass85-ci',
                )
            except Exception:
                db.rollback()
                raise

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(approve), pool.submit(approve)]
        results = [future.result(timeout=20) for future in futures]

    assert len(results) == 2

    with SessionLocal() as db:
        transfer = db.get(AccountTransfer, transfer_id)
        from_account = db.get(FinancialAccount, from_id)
        to_account = db.get(FinancialAccount, to_id)
        assert transfer.status == 'approved'
        assert float(from_account.current_balance or 0) == 20
        assert float(to_account.current_balance or 0) == 80
