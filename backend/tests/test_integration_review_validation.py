from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.schemas.integration_review import IntegrationReviewCreate, IntegrationReviewDecision
from app.services.integration_review_service import (
    _staff_payroll_revision_of,
    _staff_payroll_superseded_paid_ids,
    validate_review_payload,
)


def _payload(**overrides):
    values = {
        'source_app': 'pos',
        'source_event_id': 'sale-1001',
        'source_entity_type': 'sale',
        'source_entity_id': '1001',
        'source_revision': 1,
        'financial_effect': 'journal_only',
        'amount': 100,
        'currency': 'PHP',
        'proposed_journal': {
            'lines': [
                {'account_code': '1000', 'account_name': 'Cash', 'debit': 100, 'credit': 0},
                {'account_code': '4000', 'account_name': 'Revenue', 'debit': 0, 'credit': 100},
            ]
        },
        'proposed_links': {},
        'payload': {},
    }
    values.update(overrides)
    return IntegrationReviewCreate(**values)


def test_balanced_journal_is_valid():
    result = validate_review_payload(MagicMock(), _payload())
    assert result['valid'] is True
    assert result['errors'] == []


def test_unbalanced_journal_is_rejected():
    payload = _payload(proposed_journal={
        'lines': [
            {'account_code': '1000', 'debit': 100, 'credit': 0},
            {'account_code': '4000', 'debit': 0, 'credit': 90},
        ]
    })
    result = validate_review_payload(MagicMock(), payload)
    assert result['valid'] is False
    assert any('balance' in error.lower() for error in result['errors'])


def test_payable_requires_supplier():
    payload = _payload(
        financial_effect='payable',
        proposed_journal=None,
        proposed_links={},
    )
    result = validate_review_payload(MagicMock(), payload)
    assert result['valid'] is False
    assert any('supplier_name' in error for error in result['errors'])


def test_reference_requires_typed_target():
    payload = _payload(
        financial_effect='reference_only',
        amount=0,
        proposed_journal=None,
        proposed_links={},
    )
    result = validate_review_payload(MagicMock(), payload)
    assert result['valid'] is False
    assert any('target_type' in error for error in result['errors'])


def test_invalid_revision_and_currency_are_rejected():
    payload = _payload(source_revision=0, currency='PESO')
    result = validate_review_payload(MagicMock(), payload)
    assert result['valid'] is False
    assert any('source_revision' in error for error in result['errors'])
    assert any('currency' in error for error in result['errors'])


def test_cash_out_without_source_owned_account_is_reviewable():
    payload = _payload(
        source_app='staff',
        source_event_id='payroll-run:11:Paid',
        source_entity_type='Payroll Run',
        source_entity_id='11',
        financial_effect='cash_out',
        amount=92176.70,
        proposed_account_id=None,
        proposed_journal=None,
        proposed_links={
            'category': 'Payroll',
            'subcategory': 'Net Pay',
            'payment_method': 'bank_transfer',
            'counterparty_name': 'Employees',
        },
    )
    result = validate_review_payload(MagicMock(), payload)
    assert result['valid'] is True
    assert result['errors'] == []
    assert any('actual financial account' in warning for warning in result['warnings'])


def test_integration_decision_accepts_positive_actual_amount_paid():
    decision = IntegrationReviewDecision(actual_amount_paid=6891.00)
    assert decision.actual_amount_paid == 6891.00


def test_integration_decision_rejects_nonpositive_actual_amount_paid():
    with pytest.raises(ValidationError):
        IntegrationReviewDecision(actual_amount_paid=0)


def _review_row(entity_id: str, event_id: str, payload: dict):
    return SimpleNamespace(
        source_app='staff',
        source_entity_id=entity_id,
        source_event_id=event_id,
        payload_json=__import__('json').dumps(payload),
    )


def test_paid_revision_identifies_original_run_as_superseded():
    original = _review_row('4', 'payroll-run:4:Paid', {'run': {'id': 4}})
    revision = _review_row(
        '5',
        'payroll-run:5:Paid',
        {'run': {'id': 5, 'revision_of_run_id': 4}},
    )
    assert _staff_payroll_revision_of(original) is None
    assert _staff_payroll_revision_of(revision) == 4
    assert _staff_payroll_superseded_paid_ids([original, revision]) == {'4'}


def test_nested_paid_revision_payload_is_supported():
    revision = _review_row(
        '8',
        'payroll-run:8:Paid',
        {'payload': {'run': {'id': 8, 'revision_of_run_id': 7}}},
    )
    assert _staff_payroll_revision_of(revision) == 7


def test_non_paid_staff_event_does_not_supersede_payment():
    approved = _review_row(
        '5',
        'payroll-run:5:Approved',
        {'run': {'id': 5, 'revision_of_run_id': 4}},
    )
    assert _staff_payroll_revision_of(approved) is None
