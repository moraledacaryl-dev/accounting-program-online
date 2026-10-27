from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, get_ident
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from app.api.channel_reconciliation import PayoutReconcileBatch, reconcile_payout_batch
from app.db.database import SessionLocal, engine
from app.models.channel_payout_reconciliation import ChannelPayoutBookingLink
from app.models.entities import (
    Booking, BookingChannel, ChannelPayout, FinancialAccount, JournalEntry, MoneyTransaction, PayrollPeriod, PayrollPeriodLine,
    PurchaseOrder, PurchaseRequest, PurchaseRequestLine, Receivable, Supplier,
)
from app.schemas.cashflow import MoneyTransactionCreate, ReceivableCollectPayload, ReceivableCreate
from app.schemas.common import RecordSettlementCreate
from app.models.entities import Record, RecordSettlement
from app.models.mutation_idempotency import MutationIdempotency
from app.services.record_settlement_atomicity_service import (
    SettlementConflict, create_record_settlement_idempotent,
)
from app.services.cashflow_service import (
    collect_receivable,
    create_money_transaction,
    create_receivable,
    ensure_default_financial_accounts,
)
from app.services.payroll_period_service import post_payroll_period
from app.services.procurement_service import create_purchase_order_from_request


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


def test_postgresql_concurrent_channel_payout_has_actionable_stale_result():
    marker = uuid4().hex[:12]
    with SessionLocal() as db:
        channel = BookingChannel(code=f'RACE-{marker}', name=f'Race channel {marker}', is_active=True)
        db.add(channel)
        db.flush()
        booking = Booking(guest_name=f'Synthetic race {marker}', channel_id=channel.id,
                          status='confirmed', check_in='2026-10-01', check_out='2026-10-02',
                          gross_amount=100)
        db.add(booking)
        db.commit()
        channel_id, booking_id = channel.id, booking.id

    payload = PayoutReconcileBatch(
        channel_id=channel_id, actual_payout_date='2026-10-28',
        auto_post_accounting=False,
        items=[{'booking_id': booking_id, 'expected_amount': '100.00', 'actual_amount': '100.00'}],
    )
    first_inserted, second_read_link = Event(), Event()
    thread_ids = {}

    def observe_statement(_connection, _cursor, statement, _parameters, _context, _many):
        sql = statement.lower()
        ident = get_ident()
        if ident == thread_ids.get('first') and sql.lstrip().startswith('insert into channel_payouts'):
            first_inserted.set()
            second_read_link.wait(timeout=1.5)
        elif ident == thread_ids.get('second') and 'from channel_payout_booking_links' in sql:
            second_read_link.set()

    def submit(label):
        thread_ids[label] = get_ident()
        with SessionLocal() as db:
            return reconcile_payout_batch(payload, db=db, user=None)

    event.listen(engine, 'after_cursor_execute', observe_statement)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(submit, 'first')
            assert first_inserted.wait(timeout=10)
            second = pool.submit(submit, 'second')
            first_result = first.result(timeout=20)
            with pytest.raises(HTTPException) as stale:
                second.result(timeout=20)
    finally:
        event.remove(engine, 'after_cursor_execute', observe_statement)

    assert first_result['booking_count'] == 1
    assert stale.value.status_code == 409
    assert 'already marked paid' in stale.value.detail
    with SessionLocal() as db:
        assert db.query(ChannelPayoutBookingLink).filter_by(booking_id=booking_id).count() == 1
        assert db.query(ChannelPayout).filter_by(channel_id=channel_id).count() == 1


def test_postgresql_concurrent_cash_out_cannot_double_spend_balance():
    marker = uuid4().hex[:12]
    with SessionLocal() as db:
        ensure_default_financial_accounts(db)
        account = FinancialAccount(
            name=f'Pass66 cash race {marker}',
            code=f'P66C-{marker}',
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


def test_postgresql_concurrent_pr_conversion_creates_one_po():
    marker = uuid4().hex[:10]
    with SessionLocal() as db:
        supplier = Supplier(name=f'Pass66 supplier {marker}', code=f'P66S-{marker}', is_active=True)
        db.add(supplier)
        db.flush()
        pr = PurchaseRequest(
            request_no=f'P66PR-{marker}', request_date='2026-08-29', supplier_id=supplier.id,
            status='approved', requested_by='pass66-ci', approved_by='pass66-ci',
        )
        db.add(pr)
        db.flush()
        db.add(PurchaseRequestLine(
            purchase_request_id=pr.id, description='Concurrent conversion', quantity=2,
            unit='pc', estimated_unit_cost=100, sort_order=0,
        ))
        db.commit()
        pr_id = pr.id

    def convert():
        with SessionLocal() as db:
            try:
                return create_purchase_order_from_request(db, pr_id, username='pass66-ci')
            except Exception:
                db.rollback()
                raise

    results = _run_concurrently(convert, convert)
    assert [kind for kind, _ in results].count('ok') == 2
    ids = {value['id'] for kind, value in results if kind == 'ok'}
    assert len(ids) == 1

    with SessionLocal() as db:
        pr = db.get(PurchaseRequest, pr_id)
        assert pr.status == 'converted_to_po'
        assert db.query(PurchaseOrder).filter(PurchaseOrder.purchase_request_id == pr_id).count() == 1


def test_postgresql_concurrent_payroll_posting_creates_one_journal():
    marker = uuid4().hex[:10]
    with SessionLocal() as db:
        period = PayrollPeriod(
            name=f'Pass66 payroll {marker}', period_start='2026-08-01', period_end='2026-08-15',
            release_date='2026-08-16', status='reviewed', source_type='manual',
        )
        db.add(period)
        db.flush()
        db.add(PayrollPeriodLine(
            payroll_period_id=period.id, employee_name='Pass66 Employee', department='Test',
            gross_pay=1000, net_pay=900, deductions=100, employer_contribution=50,
        ))
        db.commit()
        period_id = period.id

    def post():
        with SessionLocal() as db:
            try:
                return post_payroll_period(db, period_id, username='pass66-ci', post_date='2026-08-29')
            except Exception:
                db.rollback()
                raise

    results = _run_concurrently(post, post)
    assert [kind for kind, _ in results].count('ok') == 2
    journal_ids = {value['journal']['id'] for kind, value in results if kind == 'ok'}
    assert len(journal_ids) == 1

    with SessionLocal() as db:
        period = db.get(PayrollPeriod, period_id)
        assert period.status == 'posted'
        assert period.generated_journal_entry_id in journal_ids
        assert db.query(JournalEntry).filter(JournalEntry.reference_no == f'PPR-{period_id}').count() == 1


def _seed_record_for_settlement_race(marker: str) -> int:
    with SessionLocal() as db:
        row = Record(
            module_slug='events', module_name='Events',
            category='Rental', bucket='Rental', item='Venue',
            name=f'Group2 settlement race {marker}', amount=100,
            direction='income', payment_method='on_account',
            workflow_status='approved', transaction_date='2026-10-01',
        )
        db.add(row)
        db.commit()
        return row.id


def _concurrent_record_settlement(record_id: int, *, key: str, ref: str, amount: float = 75):
    def run():
        with SessionLocal() as db:
            return create_record_settlement_idempotent(
                db,
                RecordSettlementCreate(
                    record_id=record_id, settlement_date='2026-10-20',
                    amount=amount, payment_method='bank_transfer', reference_no=ref,
                ),
                idempotency_key=key, username='group2-postgresql',
            )
    return run


def test_postgresql_concurrent_record_settlements_cannot_overpay():
    marker = uuid4().hex[:14]
    rid = _seed_record_for_settlement_race(marker)
    results = _run_concurrently(
        _concurrent_record_settlement(rid, key=f'{marker}-settlement-a', ref=f'{marker}-a'),
        _concurrent_record_settlement(rid, key=f'{marker}-settlement-b', ref=f'{marker}-b'),
    )
    assert [kind for kind, _ in results].count('ok') == 1
    assert [kind for kind, _ in results].count('error') == 1
    assert isinstance(next(value for kind, value in results if kind == 'error'), SettlementConflict)
    with SessionLocal() as db:
        rows = db.query(RecordSettlement).filter(RecordSettlement.record_id == rid).all()
        assert len(rows) == 1
        assert float(rows[0].amount) == 75
        assert db.query(MutationIdempotency).filter(
            MutationIdempotency.scope == f'record_settlement:create:{rid}',
        ).count() == 1


def test_postgresql_same_key_concurrent_settlement_replays_one_result():
    marker = uuid4().hex[:14]
    rid = _seed_record_for_settlement_race(marker)
    request = _concurrent_record_settlement(rid, key=f'{marker}-same-key', ref=f'{marker}-ref', amount=50)
    results = _run_concurrently(request, request)
    assert [kind for kind, _ in results].count('ok') == 2
    payloads = [value for _, value in results]
    assert sorted(x[3] for x in payloads) == [False, True]
    assert payloads[0][0].id == payloads[1][0].id
    with SessionLocal() as db:
        assert db.query(RecordSettlement).filter(RecordSettlement.record_id == rid).count() == 1
        assert db.query(MutationIdempotency).filter(
            MutationIdempotency.scope == f'record_settlement:create:{rid}',
        ).count() == 1
