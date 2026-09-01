from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.entities import MoneyTransaction, Payable, Receivable
from app.services.settlement_reversal_guard import ensure_linked_settlement_mutable


ROOT = Path(__file__).resolve().parents[2]


class FakeDb:
    def __init__(self, *, receivable=None, payable=None):
        self.receivable = receivable
        self.payable = payable

    def get(self, model, row_id):
        if model is Receivable:
            return self.receivable
        if model is Payable:
            return self.payable
        return None


def _tx(**kwargs):
    values = {
        'status': 'posted',
        'receivable_id': None,
        'payable_id': None,
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_written_off_receivable_blocks_posted_collection_mutation():
    db = FakeDb(receivable=SimpleNamespace(id=10, status='written_off'))
    tx = _tx(receivable_id=10)

    with pytest.raises(ValueError, match='Reopen the receivable'):
        ensure_linked_settlement_mutable(db, tx)


def test_written_off_payable_blocks_posted_payment_mutation():
    db = FakeDb(payable=SimpleNamespace(id=20, status='written_off'))
    tx = _tx(payable_id=20)

    with pytest.raises(ValueError, match='Reopen the payable'):
        ensure_linked_settlement_mutable(db, tx)


def test_reopened_parent_allows_settlement_mutation():
    receivable_db = FakeDb(receivable=SimpleNamespace(id=10, status='partial'))
    payable_db = FakeDb(payable=SimpleNamespace(id=20, status='open'))

    ensure_linked_settlement_mutable(receivable_db, _tx(receivable_id=10))
    ensure_linked_settlement_mutable(payable_db, _tx(payable_id=20))


def test_non_posting_transaction_does_not_need_parent_reopen():
    db = FakeDb(receivable=SimpleNamespace(id=10, status='written_off'))
    ensure_linked_settlement_mutable(db, _tx(status='draft', receivable_id=10))


def test_public_mutation_routes_all_use_guard():
    cashflow = (ROOT / 'backend/app/api/cashflow.py').read_text()
    receivables = (ROOT / 'backend/app/api/receivables.py').read_text()
    payables = (ROOT / 'backend/app/api/payables.py').read_text()

    # Generic edit, cancel, and reverse each guard the currently stored transaction.
    assert cashflow.count('ensure_linked_settlement_mutable(db, current)') >= 3

    # Dedicated AR/AP reversal routes also guard the linked settlement.
    assert 'ensure_linked_settlement_mutable(db, tx)' in receivables
    assert 'ensure_linked_settlement_mutable(db, tx)' in payables


def test_guard_contract_mentions_explicit_reopen():
    source = (ROOT / 'backend/app/services/settlement_reversal_guard.py').read_text()
    assert 'written_off' in source
    assert 'Reopen the receivable' in source
    assert 'Reopen the payable' in source
