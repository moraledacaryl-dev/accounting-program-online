from types import SimpleNamespace

import pytest

from app.models.entities import Payable, Receivable
from app.schemas.cashflow import CashflowActionPayload
from app.services import settlement_reversal_service as service


class FakeDb:
    def __init__(self, model, row):
        self.model = model
        self.row = row

    def get(self, model, row_id):
        if model is self.model and int(row_id) == int(self.row.id):
            return self.row
        return None


def payload():
    return CashflowActionPayload(action_date='2026-09-02', reason='correction')


def test_written_off_receivable_must_be_reopened_before_collection_reversal(monkeypatch):
    row = SimpleNamespace(id=1, status='written_off')
    called = False

    def unsafe(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(service, 'reverse_receivable_collection', unsafe)

    with pytest.raises(ValueError, match='Reopen the written-off receivable'):
        service.reverse_receivable_collection_with_state_guard(
            FakeDb(Receivable, row), 1, 10, payload(), username='staff'
        )

    assert called is False


def test_written_off_payable_must_be_reopened_before_payment_reversal(monkeypatch):
    row = SimpleNamespace(id=2, status='written_off')
    called = False

    def unsafe(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(service, 'reverse_payable_payment', unsafe)

    with pytest.raises(ValueError, match='Reopen the written-off payable'):
        service.reverse_payable_payment_with_state_guard(
            FakeDb(Payable, row), 2, 20, payload(), username='staff'
        )

    assert called is False


def test_open_receivable_reversal_delegates(monkeypatch):
    row = SimpleNamespace(id=3, status='partial')
    expected = {'ok': True}

    monkeypatch.setattr(
        service,
        'reverse_receivable_collection',
        lambda db, rid, tid, action, username=None: expected,
    )

    assert service.reverse_receivable_collection_with_state_guard(
        FakeDb(Receivable, row), 3, 30, payload(), username='staff'
    ) is expected


def test_open_payable_reversal_delegates(monkeypatch):
    row = SimpleNamespace(id=4, status='partial')
    expected = {'ok': True}

    monkeypatch.setattr(
        service,
        'reverse_payable_payment',
        lambda db, pid, tid, action, username=None: expected,
    )

    assert service.reverse_payable_payment_with_state_guard(
        FakeDb(Payable, row), 4, 40, payload(), username='staff'
    ) is expected


def test_api_routes_use_guarded_reversal_service():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    receivables = (root / 'app/api/receivables.py').read_text()
    payables = (root / 'app/api/payables.py').read_text()

    assert 'reverse_receivable_collection_with_state_guard(' in receivables
    assert 'reverse_payable_payment_with_state_guard(' in payables
    assert 'return reverse_receivable_collection(' not in receivables
    assert 'return reverse_payable_payment(' not in payables
