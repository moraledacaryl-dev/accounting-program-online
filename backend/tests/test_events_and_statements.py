from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.reports import _build_close_readiness, _build_financial_statements
from app.db.database import Base
from app.models.entities import EventPayment, FinancialAccount, JournalEntry, JournalLine, MoneyTransaction, Receivable
from app.schemas.events import EventActionPayload, EventBookingPayload, EventLinePayload, EventPaymentPayload
from app.services.cashflow_service import ensure_default_financial_accounts
from app.services.event_service import confirm_event, create_event, record_event_payment


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def journal_amount(db, reference_no, account_code, side):
    entry = db.query(JournalEntry).filter(JournalEntry.reference_no == reference_no).one()
    return sum(float(getattr(line, side) or 0) for line in db.query(JournalLine).filter(
        JournalLine.journal_entry_id == entry.id,
        JournalLine.account_code == account_code,
    ).all())


def test_event_confirmation_and_payment_posts_ar_without_duplicate_revenue():
    db = make_session()
    ensure_default_financial_accounts(db)
    account = db.query(FinancialAccount).filter(FinancialAccount.code == 'BNK-01').one()

    event = create_event(
        db,
        EventBookingPayload(
            event_name='June Garden Wedding',
            client_name='Santos Family',
            event_date='2026-06-12',
            venue='Garden',
            deposit_required=2000,
            deposit_due_date='2026-06-05',
            lines=[
                EventLinePayload(line_type='package', description='Wedding package', quantity=1, unit_price=5000),
            ],
        ),
        username='tester',
    )

    confirmed = confirm_event(db, event['id'], EventActionPayload(action_date='2026-06-01'), username='tester')
    assert confirmed['status'] == 'confirmed'
    assert confirmed['total_amount'] == 5000
    assert confirmed['balance_due'] == 5000
    assert confirmed['record_id']
    assert confirmed['receivable_id']
    assert journal_amount(db, f"REC-{confirmed['record_id']}", '1100', 'debit') == 5000
    assert journal_amount(db, f"REC-{confirmed['record_id']}", '4014', 'credit') == 5000

    paid = record_event_payment(
        db,
        event['id'],
        EventPaymentPayload(
            payment_date='2026-06-03',
            amount=2000,
            financial_account_id=account.id,
            payment_method='bank_transfer',
            reference_no='DEP-001',
        ),
        username='tester',
    )

    receivable = db.get(Receivable, confirmed['receivable_id'])
    db.refresh(account)
    assert paid['deposit_paid'] == 2000
    assert paid['balance_due'] == 3000
    assert receivable.amount_collected == 2000
    assert receivable.balance_due == 3000
    assert account.current_balance == 2000
    assert db.query(EventPayment).count() == 1
    assert db.query(MoneyTransaction).count() == 1

    payment = db.query(EventPayment).one()
    assert journal_amount(db, f'EVTPAY-{payment.id}', '1020', 'debit') == 2000
    assert journal_amount(db, f'EVTPAY-{payment.id}', '1100', 'credit') == 2000
    assert journal_amount(db, f"REC-{confirmed['record_id']}", '4014', 'credit') == 5000

    statements = _build_financial_statements(db, start_date='2026-06-01', end_date='2026-06-30', as_of_date='2026-06-30')
    assert statements['profit_and_loss']['totals']['revenue'] == 5000
    assert statements['profit_and_loss']['totals']['net_income'] == 5000
    assert statements['cash_flow']['totals']['net_cash_flow'] == 2000
    assert statements['balance_sheet']['totals']['assets'] == 5000
    assert statements['balance_sheet']['totals']['equity'] == 5000
    assert statements['balance_sheet']['totals']['balance_check'] == 0
    assert statements['trial_balance']['totals']['is_balanced'] is True


def test_close_readiness_blocks_on_drafts_and_unreconciled_cash():
    readiness = _build_close_readiness({
        'draft_records': 2,
        'unreconciled_cashflow_accounts': 1,
        'unposted_payroll_periods': 0,
        'low_stock_items': 4,
        'ar_over_30_days': 0,
        'ap_over_30_days': 0,
    })
    assert readiness['status'] == 'blocked'
    assert readiness['can_close'] is False
    assert readiness['critical_count'] == 2
    assert readiness['score'] < 70

    ready = _build_close_readiness({})
    assert ready['status'] == 'ready'
    assert ready['can_close'] is True
