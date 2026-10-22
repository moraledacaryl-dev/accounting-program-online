"""Group 2: a reviewed cash proposal is not authority to use a noncash account.

Synthetic DB mocks only; no integration acceptance, postings or private rows.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.integration_review_service import (
    _cash_posting_account,
    validate_review_payload,
)


def _db(account):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = account
    return db


def _receipt(account_id=21):
    return {
        'source_app': 'staff',
        'source_event_id': 'synthetic:payroll',
        'source_entity_type': 'payroll',
        'source_revision': 1,
        'financial_effect': 'cash_out',
        'amount': 100.00,
        'currency': 'PHP',
        'proposed_account_id': account_id,
        'proposed_links': {},
    }


@pytest.mark.parametrize("account_type", ["expense", "revenue", "", None, "liability"])
def test_nonmonetary_account_rejected_at_intake_and_acceptance(account_type):
    account = SimpleNamespace(id=21, is_active=True, account_type=account_type, currency="PHP")
    result = validate_review_payload(_db(account), _receipt())
    assert not result["valid"]
    assert any("not a cash" in error.lower() for error in result["errors"])
    with pytest.raises(ValueError, match="monetary"):
        _cash_posting_account(_db(account), 21, "PHP")


@pytest.mark.parametrize("account_type", ["cash_drawer", "petty_cash", "safe", "bank", "ewallet"])
def test_supported_cash_types_remain_available_for_independent_human_review(account_type):
    account = SimpleNamespace(id=21, is_active=True, account_type=account_type, currency="PHP")
    assert validate_review_payload(_db(account), _receipt())["valid"]
    assert _cash_posting_account(_db(account), 21, "PHP") is account


def test_missing_inactive_or_wrong_currency_fails_closed_without_posting():
    with pytest.raises(ValueError, match="active"):
        _cash_posting_account(_db(None), 21, "PHP")
    inactive = SimpleNamespace(id=21, is_active=False, account_type="bank", currency="PHP")
    with pytest.raises(ValueError, match="active"):
        _cash_posting_account(_db(inactive), 21, "PHP")
    wrong_currency = SimpleNamespace(id=21, is_active=True, account_type="bank", currency="USD")
    with pytest.raises(ValueError, match="currency"):
        _cash_posting_account(_db(wrong_currency), 21, "PHP")


def test_missing_proposal_is_reviewable_but_cannot_be_accepted_without_account():
    assert validate_review_payload(_db(None), _receipt(None))["valid"]
    with pytest.raises(ValueError, match="active"):
        _cash_posting_account(_db(None), None, "PHP")
