from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.subledger_creation_guard import (
    ensure_public_payable_creation_unsettled,
    ensure_public_receivable_creation_unsettled,
)


ROOT = Path(__file__).resolve().parents[1]


def test_public_receivable_creation_requires_zero_settlement():
    ensure_public_receivable_creation_unsettled(SimpleNamespace(amount_collected=0))
    with pytest.raises(ValueError, match='must start with amount_collected=0'):
        ensure_public_receivable_creation_unsettled(SimpleNamespace(amount_collected=10))


def test_public_payable_creation_requires_zero_settlement():
    ensure_public_payable_creation_unsettled(SimpleNamespace(amount_paid=0))
    with pytest.raises(ValueError, match='must start with amount_paid=0'):
        ensure_public_payable_creation_unsettled(SimpleNamespace(amount_paid=10))


def test_public_api_routes_apply_creation_guards_before_services():
    receivables = (ROOT / 'app/api/receivables.py').read_text()
    payables = (ROOT / 'app/api/payables.py').read_text()

    assert 'ensure_public_receivable_creation_unsettled(payload)' in receivables
    assert receivables.index('ensure_public_receivable_creation_unsettled(payload)') < receivables.index('return create_receivable(db, payload)')

    assert 'ensure_public_payable_creation_unsettled(payload)' in payables
    assert payables.index('ensure_public_payable_creation_unsettled(payload)') < payables.index('create_payable_idempotent(db, payload, idempotency_key)')


def test_guard_messages_require_ledger_backed_settlement_workflows():
    guard = (ROOT / 'app/services/subledger_creation_guard.py').read_text()
    assert 'Use the Collect workflow' in guard
    assert 'Use the Pay workflow' in guard
    assert 'financial account' in guard
