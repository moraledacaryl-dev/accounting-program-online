from unittest.mock import MagicMock

from app.schemas.integration_review import IntegrationReviewCreate
from app.services.integration_review_service import validate_review_payload


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
