from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api import payables, receivables
from app.services.subledger_creation_guard import (
    ensure_payable_starts_unsettled,
    ensure_receivable_starts_unsettled,
)


ROOT = Path(__file__).resolve().parents[2]


def _payload(**values):
    defaults = {
        'amount_collected': 0,
        'amount_paid': 0,
        'status': 'open',
    }
    defaults.update(values)
    return SimpleNamespace(**defaults)


def test_receivable_creation_requires_unsettled_open_state():
    ensure_receivable_starts_unsettled(_payload(amount_collected=0, status='open'))

    with pytest.raises(ValueError, match='amount_collected = 0'):
        ensure_receivable_starts_unsettled(_payload(amount_collected=125, status='open'))

    with pytest.raises(ValueError, match='must start open'):
        ensure_receivable_starts_unsettled(_payload(amount_collected=0, status='partial'))


def test_payable_creation_requires_unsettled_open_state():
    ensure_payable_starts_unsettled(_payload(amount_paid=0, status='open'))

    with pytest.raises(ValueError, match='amount_paid = 0'):
        ensure_payable_starts_unsettled(_payload(amount_paid=125, status='open'))

    with pytest.raises(ValueError, match='must start open'):
        ensure_payable_starts_unsettled(_payload(amount_paid=0, status='settled'))


def test_receivable_route_guards_before_business_write():
    source = Path(receivables.__file__).read_text()
    guard = source.index('ensure_receivable_starts_unsettled(payload)')
    write = source.index('return create_receivable(db, payload)')
    assert guard < write


def test_payable_route_guards_before_idempotency_reservation_and_write():
    source = Path(payables.__file__).read_text()
    guard = source.index('ensure_payable_starts_unsettled(payload)')
    write = source.index('create_payable_idempotent(db, payload, idempotency_key)')
    assert guard < write


def test_frontend_creation_has_no_opening_settlement_controls():
    receivable_page = (
        ROOT / 'frontend/app/cashflow/receivables/page.js'
    ).read_text()
    payable_page = (
        ROOT / 'frontend/app/cashflow/payables/page.js'
    ).read_text()

    assert 'Already Collected' not in receivable_page
    assert 'Already Paid' not in payable_page

    assert "amount_collected: editingId ? Number(form.amount_collected || 0) : 0" in receivable_page
    assert "status: editingId ? form.status : 'open'" in receivable_page
    assert 'Collected to Date' in receivable_page
    assert 'readOnly value={form.amount_collected}' in receivable_page

    assert "amount_paid: editingId ? Number(form.amount_paid || 0) : 0" in payable_page
    assert "status: editingId ? form.status : 'open'" in payable_page
    assert 'Paid to Date' in payable_page
    assert 'readOnly value={form.amount_paid}' in payable_page
