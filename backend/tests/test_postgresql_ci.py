from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.database import SessionLocal, engine
from app.models.entities import FinancialAccount, MenuItem, MoneyTransaction, Payable, SaleOrder
from app.models.mutation_idempotency import MutationIdempotency
from app.schemas.cashflow import MoneyTransactionCreate, PayableCreate, PayablePayPayload
from app.schemas.common import SaleOrderCreate
from app.services.auth_security_service import (
    clear_login_failures,
    login_failure_key,
    recent_login_failure_count,
    record_login_failure,
)
from app.services.cashflow_service import create_money_transaction, ensure_default_financial_accounts
from app.services.payable_atomicity_service import (
    create_payable_idempotent,
    pay_payable_idempotent,
)
from app.services.restaurant_service import create_sale_order


pytestmark = pytest.mark.skipif(
    engine.dialect.name != 'postgresql',
    reason='PostgreSQL CI lane only',
)


def test_postgresql_migration_head_and_auth_security_tables_exist():
    with engine.connect() as connection:
        head = connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
        assert head == '0008_operations_outbox'

        tables = set(
            connection.execute(
                text(
                    "SELECT tablename FROM pg_catalog.pg_tables "
                    "WHERE schemaname = 'public'"
                )
            ).scalars()
        )

    assert 'auth_login_failures' in tables
    assert 'revoked_access_tokens' in tables
    assert 'mutation_idempotency' in tables
    assert 'operations_outbox_events' in tables
    assert 'money_transactions' in tables
    assert 'sale_orders' in tables


def test_postgresql_money_transaction_idempotency_and_balance_update():
    external_id = f'pass62-money-{uuid4()}'

    with SessionLocal() as db:
        ensure_default_financial_accounts(db)
        account = db.query(FinancialAccount).filter(FinancialAccount.code == 'BNK-01').one()
        opening_balance = float(account.current_balance or 0)

        payload = MoneyTransactionCreate(
            direction='in',
            financial_account_id=account.id,
            amount=250,
            payment_method='gcash',
            external_source='pass62_postgresql_ci',
            external_id=external_id,
        )

        first = create_money_transaction(db, payload)
        replay = create_money_transaction(db, payload)
        db.refresh(account)

        assert replay['id'] == first['id']
        assert db.query(MoneyTransaction).filter(MoneyTransaction.external_id == external_id).count() == 1
        assert float(account.current_balance or 0) == opening_balance + 250


def test_postgresql_pos_sale_replay_is_idempotent():
    marker = uuid4().hex[:12]
    external_id = f'pass62-sale-{marker}'

    with SessionLocal() as db:
        item = MenuItem(
            name=f'Pass 62 PostgreSQL Item {marker}',
            module_slug='restaurant',
            category='CI',
            price=125,
            is_active=True,
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        payload = SaleOrderCreate(
            order_no=f'P62-{marker}',
            order_date='2026-08-26',
            strict_inventory=False,
            external_source='dedicated_pos_cloud',
            external_id=external_id,
            lines=[
                {
                    'menu_item_id': item.id,
                    'quantity': 1,
                    'unit_price': 125,
                    'discount_amount': 0,
                }
            ],
        )

        first = create_sale_order(db, payload)
        replay = create_sale_order(db, payload)

        assert replay.id == first.id
        assert db.query(SaleOrder).filter(SaleOrder.external_id == external_id).count() == 1
        assert float(first.net_amount or 0) == 125


def test_postgresql_shared_login_failure_state_survives_sessions():
    key_hash = login_failure_key('203.0.113.62', f'pass62-{uuid4()}')

    with SessionLocal() as first_session:
        record_login_failure(first_session, key_hash)
        assert recent_login_failure_count(first_session, key_hash) == 1

    with SessionLocal() as second_session:
        assert recent_login_failure_count(second_session, key_hash) == 1
        clear_login_failures(second_session, key_hash)

    with SessionLocal() as third_session:
        assert recent_login_failure_count(third_session, key_hash) == 0


def test_postgresql_payable_create_and_payment_replays_are_idempotent_and_atomic():
    marker = uuid4().hex[:12]
    create_key = f'pass64-create-{marker}'
    payment_key = f'pass64-payment-{marker}'

    with SessionLocal() as db:
        account = FinancialAccount(
            name=f'Pass 64 PostgreSQL Bank {marker}',
            code=f'P64-{marker}',
            account_type='bank',
            subtype='ci',
            currency='PHP',
            is_active=True,
            requires_daily_reconciliation=False,
            reconciliation_mode='none',
            requires_physical_count=False,
            variance_tolerance=0,
            approval_required_on_variance=False,
            opening_balance=1000,
            current_balance=1000,
            department='finance',
        )
        db.add(account)
        db.commit()
        db.refresh(account)

        create_payload = PayableCreate(
            supplier_name=f'Pass 64 PostgreSQL Supplier {marker}',
            bill_date='2026-08-27',
            due_date='2026-09-27',
            gross_amount=600,
        )
        first, replayed = create_payable_idempotent(db, create_payload, create_key)
        assert replayed is False
        db.commit()

        replay, replayed = create_payable_idempotent(db, create_payload, create_key)
        assert replayed is True
        db.commit()
        assert replay['id'] == first['id']
        assert db.query(Payable).filter(Payable.id == first['id']).count() == 1

        payment_payload = PayablePayPayload(
            amount=200,
            payment_date='2026-08-27',
            financial_account_id=account.id,
            payment_method='bank_transfer',
        )
        paid, replayed = pay_payable_idempotent(
            db,
            first['id'],
            payment_payload,
            payment_key,
            username='pass64-ci',
        )
        assert replayed is False
        db.commit()

        paid_replay, replayed = pay_payable_idempotent(
            db,
            first['id'],
            payment_payload,
            payment_key,
            username='pass64-ci',
        )
        assert replayed is True
        db.commit()

        db.refresh(account)
        stored = db.get(Payable, first['id'])

        assert paid_replay['transaction']['id'] == paid['transaction']['id']
        assert float(stored.amount_paid or 0) == 200
        assert float(stored.balance_due or 0) == 400
        assert float(account.current_balance or 0) == 800
        assert db.query(MoneyTransaction).filter(MoneyTransaction.payable_id == first['id']).count() == 1
        assert db.query(MutationIdempotency).filter(
            MutationIdempotency.idempotency_key.in_([create_key, payment_key])
        ).count() == 2
