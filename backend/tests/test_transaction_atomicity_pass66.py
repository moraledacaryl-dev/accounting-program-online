from __future__ import annotations

import inspect

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.entities import (
    EventPayment, FinancialAccount, InventoryItem, JournalEntry, MoneyTransaction,
    Payable, PurchaseOrder, PurchaseRequest, ReceivingRecord, StockMovement, Supplier, Receivable,
)
from app.schemas.events import EventActionPayload, EventBookingPayload, EventLinePayload, EventPaymentPayload
from app.services import event_service, procurement_service
from app.schemas.procurement import (
    ProcurementStatusAction, PurchaseRequestCreate, PurchaseRequestLineInput,
    ReceivingCreate, ReceivingLineInput,
)
from app.services.cashflow_service import ensure_default_financial_accounts
from app.services.event_service import confirm_event, create_event, record_event_payment


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def test_event_payment_late_failure_rolls_back_cash_receivable_and_payment(monkeypatch):
    db = make_session()
    ensure_default_financial_accounts(db)
    account = db.query(FinancialAccount).filter(FinancialAccount.code == 'BNK-01').one()

    event = create_event(
        db,
        EventBookingPayload(
            event_name='Pass 66 Atomic Event',
            client_name='Atomicity Client',
            event_date='2026-08-29',
            lines=[
                EventLinePayload(
                    line_type='package',
                    description='Atomicity package',
                    quantity=1,
                    unit_price=5000,
                )
            ],
        ),
        username='pass66',
    )
    confirmed = confirm_event(
        db,
        event['id'],
        EventActionPayload(action_date='2026-08-29'),
        username='pass66',
    )

    receivable_id = confirmed['receivable_id']
    receivable = db.get(Receivable, receivable_id)
    opening_account = float(account.current_balance or 0)
    opening_collected = float(receivable.amount_collected or 0)
    opening_due = float(receivable.balance_due or 0)

    def fail_after_collection(*args, **kwargs):
        raise RuntimeError('pass66 late event journal failure')

    monkeypatch.setattr(event_service, '_post_event_payment_journal', fail_after_collection)

    with pytest.raises(RuntimeError, match='pass66 late event journal failure'):
        record_event_payment(
            db,
            event['id'],
            EventPaymentPayload(
                payment_date='2026-08-29',
                amount=2000,
                financial_account_id=account.id,
                payment_method='bank_transfer',
                reference_no='PASS66-FAIL',
            ),
            username='pass66',
        )

    db.rollback()
    db.expire_all()

    account_after = db.get(FinancialAccount, account.id)
    receivable_after = db.get(Receivable, receivable_id)

    assert float(account_after.current_balance or 0) == opening_account
    assert float(receivable_after.amount_collected or 0) == opening_collected
    assert float(receivable_after.balance_due or 0) == opening_due
    assert db.query(EventPayment).count() == 0
    assert db.query(MoneyTransaction).filter(MoneyTransaction.receivable_id == receivable_id).count() == 0
    assert db.query(JournalEntry).filter(JournalEntry.reference_no.like('EVTPAY-%')).count() == 0


def test_nested_financial_helpers_are_explicitly_non_committing_in_composite_workflows():
    event_payment_source = inspect.getsource(event_service.record_event_payment)
    event_receivable_source = inspect.getsource(event_service._sync_event_receivable)
    receiving_source = inspect.getsource(procurement_service._maybe_create_payable_from_receiving)

    assert 'confirm_event(' in event_payment_source and 'commit=False' in event_payment_source
    assert 'collect_receivable(' in event_payment_source and 'commit=False' in event_payment_source
    assert 'create_receivable(' in event_receivable_source and 'commit=False' in event_receivable_source
    assert 'create_payable(' in receiving_source and 'commit=False' in receiving_source


def test_receiving_late_failure_rolls_back_stock_effects(monkeypatch):
    db = make_session()
    item = InventoryItem(
        name='Pass66 rollback item', module_name='Inventory', category_name='Test',
        subcategory_name='Atomicity', unit='pc', quantity_on_hand=10,
        reorder_level=0, average_cost=5,
    )
    db.add(item)
    db.commit()

    receiving = procurement_service.create_receiving_record(
        db,
        ReceivingCreate(
            receiving_no='PASS66-RCV-ROLLBACK',
            receiving_date='2026-08-29',
            status='draft',
            lines=[ReceivingLineInput(
                inventory_item_id=item.id,
                description='rollback line',
                quantity_received=3,
                unit='pc',
                unit_cost=5,
            )],
        ),
        username='pass66',
    )

    def fail_after_stock(*args, **kwargs):
        raise RuntimeError('pass66 receiving late failure')

    monkeypatch.setattr(procurement_service, '_maybe_create_payable_from_receiving', fail_after_stock)
    with pytest.raises(RuntimeError, match='pass66 receiving late failure'):
        procurement_service.set_receiving_status(
            db,
            receiving['id'],
            ProcurementStatusAction(status='posted', auto_create_payable=True),
            username='pass66',
        )

    db.rollback()
    db.expire_all()
    refreshed_item = db.get(InventoryItem, item.id)
    refreshed_receiving = db.get(ReceivingRecord, receiving['id'])
    assert refreshed_receiving.status == 'draft'
    assert float(refreshed_item.quantity_on_hand or 0) == 10
    assert db.query(StockMovement).filter(StockMovement.receiving_record_id == receiving['id']).count() == 0
    assert db.query(Payable).filter(Payable.source_type == 'receiving', Payable.source_id == receiving['id']).count() == 0


def test_purchase_request_conversion_late_failure_rolls_back_po(monkeypatch):
    db = make_session()
    supplier = Supplier(name='Pass66 rollback supplier', code='P66-RB-SUP', is_active=True)
    db.add(supplier)
    db.commit()

    request = procurement_service.create_purchase_request(
        db,
        PurchaseRequestCreate(
            request_no='PASS66-PR-ROLLBACK',
            request_date='2026-08-29',
            supplier_id=supplier.id,
            status='approved',
            lines=[PurchaseRequestLineInput(
                description='rollback purchase', quantity=2, unit='pc', estimated_unit_cost=100,
            )],
        ),
        username='pass66',
    )

    original = procurement_service.create_purchase_order

    def create_then_fail(*args, **kwargs):
        kwargs['commit'] = False
        original(*args, **kwargs)
        raise RuntimeError('pass66 conversion late failure')

    monkeypatch.setattr(procurement_service, 'create_purchase_order', create_then_fail)
    with pytest.raises(RuntimeError, match='pass66 conversion late failure'):
        procurement_service.create_purchase_order_from_request(db, request['id'], username='pass66')

    db.rollback()
    db.expire_all()
    pr = db.get(PurchaseRequest, request['id'])
    assert pr.status == 'approved'
    assert db.query(PurchaseOrder).filter(PurchaseOrder.purchase_request_id == pr.id).count() == 0


def test_workflow_roots_are_locked_and_pr_conversion_is_non_committing():
    procurement_source = inspect.getsource(procurement_service.create_purchase_order_from_request)
    receiving_source = inspect.getsource(procurement_service.set_receiving_status)
    event_source = inspect.getsource(event_service.record_event_payment)

    assert '.with_for_update()' in procurement_source
    assert 'commit=False' in procurement_source
    assert '.with_for_update()' in receiving_source
    assert '_lock_event(' in event_source
