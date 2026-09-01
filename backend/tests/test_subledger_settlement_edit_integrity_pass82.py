from types import SimpleNamespace

import pytest

from app.models.entities import Payable, Receivable
from app.services.subledger_edit_guard import (
    ensure_payable_edit_preserves_settlement,
    ensure_receivable_edit_preserves_settlement,
)


class FakeDb:
    def __init__(self, receivable=None, payable=None):
        self.receivable = receivable
        self.payable = payable

    def get(self, model, row_id):
        if model is Receivable:
            return self.receivable
        if model is Payable:
            return self.payable
        return None


def test_receivable_edit_cannot_fabricate_collection_history():
    row = SimpleNamespace(
        id=1,
        gross_amount=1000.0,
        amount_collected=250.0,
        status='partial',
    )
    payload = SimpleNamespace(gross_amount=1000.0, amount_collected=900.0)

    with pytest.raises(ValueError, match='transaction-derived'):
        ensure_receivable_edit_preserves_settlement(FakeDb(receivable=row), 1, payload)


def test_payable_edit_cannot_fabricate_payment_history():
    row = SimpleNamespace(
        id=2,
        gross_amount=1000.0,
        amount_paid=300.0,
        status='partial',
    )
    payload = SimpleNamespace(gross_amount=1000.0, amount_paid=900.0)

    with pytest.raises(ValueError, match='transaction-derived'):
        ensure_payable_edit_preserves_settlement(FakeDb(payable=row), 2, payload)


def test_written_off_subledgers_require_explicit_reopen_before_edit():
    receivable = SimpleNamespace(id=1, gross_amount=1000.0, amount_collected=250.0, status='written_off')
    payable = SimpleNamespace(id=2, gross_amount=1000.0, amount_paid=300.0, status='written_off')

    with pytest.raises(ValueError, match='Reopen the receivable'):
        ensure_receivable_edit_preserves_settlement(
            FakeDb(receivable=receivable),
            1,
            SimpleNamespace(gross_amount=1000.0, amount_collected=250.0),
        )

    with pytest.raises(ValueError, match='Reopen the payable'):
        ensure_payable_edit_preserves_settlement(
            FakeDb(payable=payable),
            2,
            SimpleNamespace(gross_amount=1000.0, amount_paid=300.0),
        )


def test_settled_gross_change_requires_explicit_reopen():
    receivable = SimpleNamespace(id=1, gross_amount=1000.0, amount_collected=1000.0, status='settled')
    payable = SimpleNamespace(id=2, gross_amount=1000.0, amount_paid=1000.0, status='settled')

    with pytest.raises(ValueError, match='Reopen the receivable'):
        ensure_receivable_edit_preserves_settlement(
            FakeDb(receivable=receivable),
            1,
            SimpleNamespace(gross_amount=1200.0, amount_collected=1000.0),
        )

    with pytest.raises(ValueError, match='Reopen the payable'):
        ensure_payable_edit_preserves_settlement(
            FakeDb(payable=payable),
            2,
            SimpleNamespace(gross_amount=1200.0, amount_paid=1000.0),
        )


def test_metadata_edit_with_unchanged_settlement_is_allowed():
    receivable = SimpleNamespace(id=1, gross_amount=1000.0, amount_collected=250.0, status='partial')
    payable = SimpleNamespace(id=2, gross_amount=1000.0, amount_paid=300.0, status='partial')

    ensure_receivable_edit_preserves_settlement(
        FakeDb(receivable=receivable),
        1,
        SimpleNamespace(gross_amount=1000.0, amount_collected=250.0),
    )
    ensure_payable_edit_preserves_settlement(
        FakeDb(payable=payable),
        2,
        SimpleNamespace(gross_amount=1000.0, amount_paid=300.0),
    )


def test_routes_call_pass82_guards():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    receivables = (root / 'app/api/receivables.py').read_text()
    payables = (root / 'app/api/payables.py').read_text()

    assert 'ensure_receivable_edit_preserves_settlement(db, receivable_id, payload)' in receivables
    assert 'ensure_payable_edit_preserves_settlement(db, payable_id, payload)' in payables
