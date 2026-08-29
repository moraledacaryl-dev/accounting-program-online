from __future__ import annotations

import inspect

from app.services import event_service, payroll_period_service, procurement_service
from app.services import cashflow_service


def test_pass66_composite_transaction_contracts():
    assert 'commit: bool = True' in inspect.getsource(cashflow_service.create_money_transaction)
    assert 'commit: bool = True' in inspect.getsource(cashflow_service.create_receivable)
    assert 'commit: bool = True' in inspect.getsource(cashflow_service.create_payable)
    assert 'commit: bool = True' in inspect.getsource(procurement_service.create_purchase_order)
    assert 'commit=False' in inspect.getsource(procurement_service.create_purchase_order_from_request)
    assert '.with_for_update()' in inspect.getsource(procurement_service.create_purchase_order_from_request)
    assert '.with_for_update()' in inspect.getsource(procurement_service.set_receiving_status)
    assert '.with_for_update()' in inspect.getsource(payroll_period_service.post_payroll_period)
    assert '_lock_event(' in inspect.getsource(event_service.record_event_payment)
    assert 'commit=False' in inspect.getsource(event_service.record_event_payment)
