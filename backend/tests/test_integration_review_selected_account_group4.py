"""Group 4: reviewer-selected accounts are revalidated without posting money.

Synthetic in-memory account lookup only. No production records or journal writes.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.integration_review_service import _current_validation


def _review(proposed_account_id=11):
    return SimpleNamespace(
        source_app='pos', source_event_id='synthetic-cash-refund',
        source_entity_type='refund', source_entity_id='12',
        source_revision=1, financial_effect='cash_out',
        amount=150.0, currency='PHP', proposed_account_id=proposed_account_id,
        proposed_journal_json='{}', proposed_links_json='{}', payload_json='{}',
    )


def _db(accounts):
    db = MagicMock()

    def filter_account(expression):
        # SQLAlchemy's comparison contains the concrete selected integer ID.
        identifier = int(expression.right.value)
        return SimpleNamespace(first=lambda: accounts.get(identifier))

    db.query.return_value.filter.side_effect = filter_account
    return db


def test_reviewer_can_select_a_valid_replacement_for_a_stale_inactive_proposal():
    accounts = {
        11: SimpleNamespace(id=11, account_type='cash_drawer', is_active=False, currency='PHP'),
        22: SimpleNamespace(id=22, account_type='ewallet', is_active=True, currency='PHP'),
    }
    row = _review()
    db = _db(accounts)
    historical_check = _current_validation(db, row)
    assert not historical_check['valid']
    assert any('inactive' in e.lower() for e in historical_check['errors'])

    reviewer_check = _current_validation(db, row, selected_account_id=22)
    assert reviewer_check['valid']
    assert reviewer_check['errors'] == []
    # This is a validation-only operation: the retained proposal remains unchanged.
    assert row.proposed_account_id == 11
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    ('account_type', 'is_active', 'currency', 'message'),
    [
        ('expense', True, 'PHP', 'not a cash'),
        ('bank', False, 'PHP', 'inactive'),
        ('bank', True, 'USD', 'currency'),
    ],
)
def test_invalid_reviewer_override_cannot_pass_financial_validation(
    account_type, is_active, currency, message,
):
    account = SimpleNamespace(id=22, account_type=account_type, is_active=is_active, currency=currency)
    db = _db({22: account})
    result = _current_validation(db, _review(), selected_account_id=22)
    assert not result['valid']
    assert any(message in error.lower() for error in result['errors'])
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_missing_source_proposal_does_not_create_an_automatic_account_choice():
    row = _review(proposed_account_id=None)
    account = SimpleNamespace(id=22, account_type='bank', is_active=True, currency='PHP')
    db = _db({22: account})
    original = _current_validation(db, row)
    assert original['valid']
    assert any('select the actual' in warning.lower() for warning in original['warnings'])
    assert _current_validation(db, row, selected_account_id=22)['valid']
    assert row.proposed_account_id is None
