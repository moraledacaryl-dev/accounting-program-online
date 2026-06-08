import pytest
import json
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.integrations_payroll import store_receipt
from app.db.database import Base
from app.models.entities import ExternalEmployeeReference, IntegrationReceipt


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def envelope(event_type, external_id='event-1', payload=None):
    return {
        'external_source': 'hidden_oasis_staff_payroll',
        'external_id': external_id,
        'event_type': event_type,
        'source_record_type': 'Payroll Run',
        'source_record_id': 1,
        'generated_at': '2026-06-08T10:00:00',
        'schema_version': '2026-06-v1',
        'payload': payload or {},
    }


def payroll_payload(external_id='payroll-1'):
    return envelope('payroll.run.paid', external_id, {
        'totals': {
            'gross_pay': 1000,
            'sss_er': 80,
            'sss_ec': 10,
            'philhealth_er': 50,
            'pagibig_er': 20,
            'sss_ee': 70,
            'philhealth_ee': 50,
            'pagibig_ee': 20,
            'cash_advance_deduction': 100,
            'net_pay': 760,
        }
    })


def test_payroll_import_creates_review_receipt_and_balanced_preview():
    db = make_session()
    result = store_receipt(db, payroll_payload(), {'payroll.run.paid'})
    receipt = db.get(IntegrationReceipt, result['receipt_id'])
    assert result['status'] == 'accepted'
    assert receipt.status == 'For Review'
    assert result['outcome']['posting_policy'] == 'review_only'
    assert result['outcome']['totals']['balanced'] is True
    assert any(line['credit_account'] == 'Payroll Bank/Cash/GCash' for line in result['outcome']['journal_preview'])


def test_duplicate_payroll_import_is_idempotent():
    db = make_session()
    first = store_receipt(db, payroll_payload('dupe-1'), {'payroll.run.paid'})
    second = store_receipt(db, payroll_payload('dupe-1'), {'payroll.run.paid'})
    assert second['status'] == 'already_applied'
    assert second['receipt_id'] == first['receipt_id']
    assert db.query(IntegrationReceipt).count() == 1


def test_invalid_payload_is_rejected():
    db = make_session()
    payload = payroll_payload()
    payload.pop('external_id')
    with pytest.raises(HTTPException):
        store_receipt(db, payload, {'payroll.run.paid'})


def test_employee_sync_strips_sensitive_fields():
    db = make_session()
    payload = envelope('employee.sync', 'emp-sync-1', {
        'employees': [{
            'employee_code': 'EMP-001',
            'display_name': 'Safe Name',
            'department': 'Admin',
            'position': 'Clerk',
            'role': 'Regular',
            'active': True,
            'primary_department': 'Admin',
            'source_staff_id': 7,
            'hourly_rate': 999,
            'sss_number': 'secret',
        }]
    })
    result = store_receipt(db, payload, {'employee.sync'})
    ref = db.query(ExternalEmployeeReference).one()
    receipt = db.get(IntegrationReceipt, result['receipt_id'])
    assert result['outcome']['employee_references_upserted'] == 1
    assert ref.employee_code == 'EMP-001'
    assert not hasattr(ref, 'hourly_rate')
    assert 'hourly_rate' not in json.dumps(json.loads(receipt.payload_json))
    assert 'sss_number' not in json.dumps(json.loads(receipt.payload_json))


def test_cash_advance_and_13th_month_preview_are_review_only():
    db = make_session()
    release = envelope('cash_advance.released', 'ca-release-1', {'cash_advance': {'amount': 500, 'release_method': 'GCash'}})
    thirteenth = envelope('payroll.13th_month.paid', '13th-1', {'run': {'net_13th_pay': 1200}})
    release_result = store_receipt(db, release, {'cash_advance.released'})
    thirteenth_result = store_receipt(db, thirteenth, {'payroll.13th_month.paid'})
    assert release_result['outcome']['journal_preview'][0]['debit_account'] == 'Employee Cash Advance Receivable'
    assert thirteenth_result['outcome']['journal_preview'][0]['debit_account'] == '13th Month Pay Expense'
    assert db.query(IntegrationReceipt).count() == 2
