from unittest.mock import MagicMock, patch

from app.api.integrations_pos_review import cashflow, order, order_void, reconciliation, room_charge, transfer


def _capture(callable_, payload):
    db = MagicMock()
    with patch('app.api.integrations_pos_review.create_review_item') as create:
        create.side_effect = lambda _db, review: review.model_dump()
        return callable_(payload, db, MagicMock())


def test_cash_collection_maps_to_reviewable_cash_in():
    result = _capture(cashflow, {
        'direction': 'in',
        'amount': 1250,
        'financial_account_id': 7,
        'reference_no': 'OR-1001',
        'transaction_date': '2026-07-16',
        'payment_method': 'cash',
    })
    assert result['source_app'] == 'pos'
    assert result['financial_effect'] == 'cash_in'
    assert result['amount'] == 1250
    assert result['proposed_account_id'] == 7
    assert result['idempotency_key'] == 'pos:cashflow_transaction:OR-1001'


def test_refund_maps_to_reviewable_cash_out():
    result = _capture(cashflow, {
        'direction': 'out',
        'amount': 300,
        'financial_account_id': 7,
        'external_id': 'refund-payment:42',
        'category': 'POS Refund',
    })
    assert result['financial_effect'] == 'cash_out'
    assert result['amount'] == 300


def test_positive_room_charge_maps_to_receivable():
    result = _capture(room_charge, {
        'source_id': 55,
        'gross_amount': 780,
        'counterparty_name': 'Guest One',
        'transaction_date': '2026-07-16',
    })
    assert result['financial_effect'] == 'receivable'
    assert result['amount'] == 780
    assert result['proposed_links']['counterparty_name'] == 'Guest One'


def test_reference_events_include_typed_targets():
    transfer_result = _capture(transfer, {
        'reference_no': 'TR-9',
        'from_account_id': 1,
        'to_account_id': 2,
        'amount': 500,
    })
    order_result = _capture(order, {
        'order_no': 'POS-100',
        'order_date': '2026-07-16',
        'lines': [{'quantity': 2, 'unit_price': 100, 'discount_amount': 10}],
    })
    close_result = _capture(reconciliation, {
        'reconciliation_date': '2026-07-16',
        'shift_name': 'SHIFT-1',
        'actual_counted': 2000,
    })
    assert transfer_result['proposed_links']['target_type'] == 'pos_cash_transfer'
    assert order_result['amount'] == 190
    assert order_result['proposed_links']['target_type'] == 'pos_order'
    assert close_result['proposed_links']['target_type'] == 'pos_register_reconciliation'


def test_order_void_payload_maps_to_linked_reference():
    result = _capture(order_void, {
        'order_no': 'POS-100',
        'order_uuid': 'order-uuid-100',
        'business_date': '2026-07-17',
        'reason': 'Guest cancellation',
        'external_id': 'order-uuid-100',
    })

    assert result['source_app'] == 'pos'
    assert result['source_entity_type'] == 'order_voided'
    assert result['financial_effect'] == 'reference_only'
    assert result['idempotency_key'] == 'pos:order_voided:order-uuid-100'
    assert result['proposed_links']['target_type'] == 'pos_order_void'
    assert result['proposed_links']['order_no'] == 'POS-100'
    assert result['proposed_links']['reason'] == 'Guest cancellation'
