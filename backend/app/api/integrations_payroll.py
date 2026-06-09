from __future__ import annotations

import json
from hmac import compare_digest
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_any_permissions
from app.core.settings import looks_like_placeholder_secret, settings
from app.db.database import get_db
from app.models.entities import ExternalEmployeeReference, IntegrationReceipt

router = APIRouter()

EXTERNAL_SOURCE = 'hidden_oasis_staff_payroll'
SCHEMA_VERSION = '2026-06-v1'
SAFE_EMPLOYEE_FIELDS = {
    'employee_code',
    'display_name',
    'department',
    'position',
    'role',
    'active',
    'primary_department',
    'source_staff_id',
}
ACCEPTED_EVENT_TYPES = {
    'employee.sync',
    'payroll.run.approved',
    'payroll.run.paid',
    'payroll.13th_month.paid',
    'cash_advance.released',
    'cash_advance.repaid',
}
REVIEW_STATUSES = {'For Review', 'Ready to Post', 'Posted', 'Rejected', 'Errors', 'Already Applied'}
TERMINAL_STATUSES = {'Posted', 'Rejected', 'Errors'}


def require_integration_key(x_integration_api_key: str | None = Header(default=None, alias='X-Integration-Api-Key')):
    secret = settings.integration_receive_secret
    if looks_like_placeholder_secret(secret):
        if settings.is_production:
            raise HTTPException(status_code=503, detail='Integration API key is not configured')
        return
    if not x_integration_api_key or not compare_digest(str(x_integration_api_key), secret):
        raise HTTPException(status_code=401, detail='Invalid integration API key')


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _money(value: Any) -> float:
    return round(float(value or 0), 2)


def _body(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get('payload') if isinstance(payload.get('payload'), dict) else payload


def validate_event(payload: dict[str, Any], expected_event_types: set[str]) -> None:
    required = ['external_source', 'external_id', 'event_type', 'source_record_type', 'source_record_id', 'generated_at', 'schema_version']
    missing = [field for field in required if field not in payload]
    if missing:
        raise HTTPException(status_code=400, detail=f'Missing required fields: {", ".join(missing)}')
    if payload['external_source'] != EXTERNAL_SOURCE:
        raise HTTPException(status_code=400, detail='Unsupported external_source')
    if payload['schema_version'] != SCHEMA_VERSION:
        raise HTTPException(status_code=400, detail='Unsupported schema_version')
    if payload['event_type'] not in expected_event_types or payload['event_type'] not in ACCEPTED_EVENT_TYPES:
        raise HTTPException(status_code=400, detail='Unsupported event_type for this endpoint')


def payroll_journal_preview(payload: dict[str, Any]) -> list[dict[str, Any]]:
    body = _body(payload)
    totals = body.get('totals') or {}
    lines = [
        {'debit_account': 'Salaries & Wages Expense', 'credit_account': 'Salaries Payable', 'amount': _money(totals.get('gross_pay')), 'memo': 'Gross payroll'},
        {'debit_account': 'Employer Contributions Expense', 'credit_account': 'SSS Payable', 'amount': _money(totals.get('sss_er')) + _money(totals.get('sss_ec')), 'memo': 'Employer SSS and EC'},
        {'debit_account': 'Employer Contributions Expense', 'credit_account': 'PhilHealth Payable', 'amount': _money(totals.get('philhealth_er')), 'memo': 'Employer PhilHealth'},
        {'debit_account': 'Employer Contributions Expense', 'credit_account': 'Pag-IBIG Payable', 'amount': _money(totals.get('pagibig_er')), 'memo': 'Employer Pag-IBIG'},
        {'debit_account': 'Salaries Payable', 'credit_account': 'SSS Payable', 'amount': _money(totals.get('sss_ee')), 'memo': 'Employee SSS share'},
        {'debit_account': 'Salaries Payable', 'credit_account': 'PhilHealth Payable', 'amount': _money(totals.get('philhealth_ee')), 'memo': 'Employee PhilHealth share'},
        {'debit_account': 'Salaries Payable', 'credit_account': 'Pag-IBIG Payable', 'amount': _money(totals.get('pagibig_ee')), 'memo': 'Employee Pag-IBIG share'},
        {'debit_account': 'Salaries Payable', 'credit_account': 'Employee Cash Advance Receivable', 'amount': _money(totals.get('cash_advance_deduction')), 'memo': 'Cash advance deduction'},
        {'debit_account': 'Salaries Payable', 'credit_account': 'Payroll Bank/Cash/GCash', 'amount': _money(totals.get('net_pay')), 'memo': 'Net pay release'},
    ]
    return [line for line in lines if _money(line['amount']) > 0]


def simple_preview(payload: dict[str, Any]) -> list[dict[str, Any]]:
    body = _body(payload)
    event_type = payload.get('event_type')
    if event_type == 'payroll.run.paid':
        return payroll_journal_preview(payload)
    if event_type == 'payroll.13th_month.paid':
        run = body.get('run') or {}
        return [{'debit_account': '13th Month Pay Expense', 'credit_account': 'Cash/Bank or 13th Month Payable', 'amount': _money(run.get('net_13th_pay')), 'memo': '13th month pay'}]
    if event_type == 'cash_advance.released':
        ca = body.get('cash_advance') or {}
        return [{'debit_account': 'Employee Cash Advance Receivable', 'credit_account': ca.get('release_method') or 'Cash in Drawer/Bank/GCash', 'amount': _money(ca.get('amount')), 'memo': 'Cash advance release'}]
    if event_type == 'cash_advance.repaid':
        repayment = body.get('repayment') or {}
        return [{'debit_account': 'Salaries Payable', 'credit_account': 'Employee Cash Advance Receivable', 'amount': _money(repayment.get('amount')), 'memo': 'Cash advance repayment'}]
    return body.get('journal_preview') or []


def debit_credit_totals(lines: list[dict[str, Any]]) -> dict[str, float]:
    amount = _money(sum(_money(line.get('amount')) for line in lines))
    return {'debits': amount, 'credits': amount, 'balanced': True}


def load_json(value: str | None) -> Any:
    try:
        return json.loads(value or '{}')
    except json.JSONDecodeError:
        return {}


def receipt_to_dict(row: IntegrationReceipt, include_payload: bool = True) -> dict[str, Any]:
    outcome = load_json(row.outcome)
    payload = load_json(row.payload_json) if include_payload else None
    amount = _money(outcome.get('totals', {}).get('debits') or 0)
    data = {
        'id': row.id,
        'external_source': row.external_source,
        'external_id': row.external_id,
        'event_type': row.event_type,
        'status': row.status,
        'source_record_type': row.source_record_type,
        'source_record_id': row.source_record_id,
        'amount': amount,
        'received_at': row.received_at,
        'processed_at': row.processed_at,
        'posted_at': row.posted_at,
        'posted_by': row.posted_by,
        'created_review_record_type': row.created_review_record_type,
        'created_review_record_id': row.created_review_record_id,
        'error_message': row.error_message,
        'outcome': outcome,
    }
    if include_payload:
        data['payload'] = payload
    return data


def strip_employee(employee: dict[str, Any]) -> dict[str, Any]:
    return {key: employee.get(key) for key in SAFE_EMPLOYEE_FIELDS if key in employee}


def sync_employee_references(db: Session, payload: dict[str, Any]) -> int:
    body = _body(payload)
    count = 0
    for row in body.get('employees') or []:
        safe = strip_employee(row)
        employee_code = safe.get('employee_code')
        if not employee_code:
            continue
        ref = db.query(ExternalEmployeeReference).filter(
            ExternalEmployeeReference.external_source == payload['external_source'],
            ExternalEmployeeReference.employee_code == employee_code,
        ).first()
        if not ref:
            ref = ExternalEmployeeReference(external_source=payload['external_source'], employee_code=employee_code)
            db.add(ref)
        ref.source_staff_id = str(safe.get('source_staff_id') or '')
        ref.display_name = safe.get('display_name') or ''
        ref.department = safe.get('department')
        ref.position = safe.get('position')
        ref.role = safe.get('role')
        ref.active = bool(safe.get('active', True))
        ref.primary_department = safe.get('primary_department')
        count += 1
    return count


def scrub_employee_sync_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get('event_type') != 'employee.sync':
        return payload
    scrubbed = dict(payload)
    body = dict(_body(payload))
    body['employees'] = [strip_employee(row) for row in body.get('employees') or []]
    if isinstance(payload.get('payload'), dict):
        scrubbed['payload'] = body
    else:
        scrubbed.update(body)
    return scrubbed


def store_receipt(db: Session, payload: dict[str, Any], expected_event_types: set[str]) -> dict[str, Any]:
    validate_event(payload, expected_event_types)
    existing = db.query(IntegrationReceipt).filter(
        IntegrationReceipt.external_source == payload['external_source'],
        IntegrationReceipt.external_id == payload['external_id'],
    ).first()
    if existing:
        return {'status': 'already_applied', 'receipt_id': existing.id}

    stored_payload = scrub_employee_sync_payload(payload)
    preview = simple_preview(stored_payload)
    employee_count = sync_employee_references(db, payload) if payload['event_type'] == 'employee.sync' else 0
    outcome = {
        'review_queue': 'payroll',
        'journal_preview': preview,
        'totals': debit_credit_totals(preview),
        'employee_references_upserted': employee_count,
        'posting_policy': 'review_only',
    }
    receipt = IntegrationReceipt(
        external_source=payload['external_source'],
        external_id=payload['external_id'],
        event_type=payload['event_type'],
        source_record_type=str(payload.get('source_record_type') or ''),
        source_record_id=str(payload.get('source_record_id') or ''),
        payload_json=json.dumps(stored_payload, default=str),
        status='For Review',
        outcome=json.dumps(outcome, default=str),
        received_at=_now(),
        created_review_record_type='IntegrationReceipt',
    )
    db.add(receipt)
    try:
        db.flush()
        receipt.created_review_record_id = str(receipt.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(IntegrationReceipt).filter(
            IntegrationReceipt.external_source == payload['external_source'],
            IntegrationReceipt.external_id == payload['external_id'],
        ).first()
        return {'status': 'already_applied', 'receipt_id': existing.id if existing else None}
    return {'status': 'accepted', 'receipt_id': receipt.id, 'outcome': outcome}


def get_receipt_or_404(db: Session, receipt_id: int) -> IntegrationReceipt:
    row = db.get(IntegrationReceipt, receipt_id)
    if not row or row.external_source != EXTERNAL_SOURCE:
        raise HTTPException(status_code=404, detail='Receipt not found')
    return row


def update_outcome(row: IntegrationReceipt, updates: dict[str, Any]) -> dict[str, Any]:
    outcome = load_json(row.outcome)
    outcome.update(updates)
    row.outcome = json.dumps(outcome, default=str)
    return outcome


@router.post('/employees')
async def receive_employees(payload: dict[str, Any], db: Session = Depends(get_db), _=Depends(require_integration_key)):
    return store_receipt(db, payload, {'employee.sync'})


@router.post('/runs')
async def receive_runs(payload: dict[str, Any], db: Session = Depends(get_db), _=Depends(require_integration_key)):
    return store_receipt(db, payload, {'payroll.run.approved', 'payroll.run.paid'})


@router.post('/13th-month')
async def receive_13th_month(payload: dict[str, Any], db: Session = Depends(get_db), _=Depends(require_integration_key)):
    return store_receipt(db, payload, {'payroll.13th_month.paid'})


@router.post('/cash-advance-release')
async def receive_cash_advance_release(payload: dict[str, Any], db: Session = Depends(get_db), _=Depends(require_integration_key)):
    return store_receipt(db, payload, {'cash_advance.released'})


@router.post('/cash-advance-repayment')
async def receive_cash_advance_repayment(payload: dict[str, Any], db: Session = Depends(get_db), _=Depends(require_integration_key)):
    return store_receipt(db, payload, {'cash_advance.repaid'})


@router.get('/review-queue')
async def review_queue(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('reports.view', 'approvals.view', 'cashflow.view')),
):
    query = db.query(IntegrationReceipt).filter(IntegrationReceipt.external_source == EXTERNAL_SOURCE)
    if status:
        query = query.filter(IntegrationReceipt.status == status)
    rows = query.order_by(IntegrationReceipt.created_at.desc()).limit(200).all()
    return [receipt_to_dict(row, include_payload=False) for row in rows]


@router.get('/receipts')
async def receipts(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('reports.view', 'approvals.view', 'cashflow.view')),
):
    return await review_queue(status=status, db=db)


@router.get('/receipts/{receipt_id}')
async def receipt_detail(
    receipt_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('reports.view', 'approvals.view', 'cashflow.view')),
):
    return receipt_to_dict(get_receipt_or_404(db, receipt_id), include_payload=True)


@router.post('/review-queue/{receipt_id}/status')
async def update_review_status(
    receipt_id: int,
    status: str = Query(...),
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('approvals.manage', 'cashflow.money_in', 'cashflow.money_out')),
):
    if status not in REVIEW_STATUSES:
        raise HTTPException(status_code=400, detail='Unsupported review status')
    row = get_receipt_or_404(db, receipt_id)
    row.status = status
    row.processed_at = _now() if status in TERMINAL_STATUSES | {'Already Applied'} else row.processed_at
    db.commit()
    return {'id': row.id, 'status': row.status}


@router.post('/receipts/{receipt_id}/approve')
async def approve_receipt(
    receipt_id: int,
    approved_by: str = Query(default='accounting_user'),
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('approvals.manage', 'cashflow.money_in', 'cashflow.money_out')),
):
    row = get_receipt_or_404(db, receipt_id)
    if row.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail='Terminal receipts cannot be approved')
    row.status = 'Ready to Post'
    row.processed_at = _now()
    update_outcome(row, {'approved_by': approved_by, 'approved_at': row.processed_at})
    db.commit()
    return receipt_to_dict(row, include_payload=False)


@router.post('/receipts/{receipt_id}/reject')
async def reject_receipt(
    receipt_id: int,
    reason: str = Query(..., min_length=3),
    rejected_by: str = Query(default='accounting_user'),
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('approvals.manage', 'cashflow.money_in', 'cashflow.money_out')),
):
    row = get_receipt_or_404(db, receipt_id)
    if row.status == 'Posted':
        raise HTTPException(status_code=400, detail='Posted receipts cannot be rejected')
    row.status = 'Rejected'
    row.error_message = reason
    row.processed_at = _now()
    update_outcome(row, {'rejected_by': rejected_by, 'rejected_at': row.processed_at, 'rejection_reason': reason})
    db.commit()
    return receipt_to_dict(row, include_payload=False)


@router.post('/receipts/{receipt_id}/post')
async def post_receipt(
    receipt_id: int,
    posted_by: str = Query(default='accounting_user'),
    confirm: bool = Query(default=False),
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('approvals.manage', 'cashflow.money_in', 'cashflow.money_out')),
):
    row = get_receipt_or_404(db, receipt_id)
    if not confirm:
        raise HTTPException(status_code=400, detail='Posting requires confirm=true')
    if row.status != 'Ready to Post':
        raise HTTPException(status_code=400, detail='Receipt must be approved before posting')
    outcome = load_json(row.outcome)
    if not outcome.get('totals', {}).get('balanced', False):
        raise HTTPException(status_code=400, detail='Journal preview is not balanced')
    row.status = 'Posted'
    row.posted_by = posted_by
    row.posted_at = _now()
    row.processed_at = row.posted_at
    update_outcome(row, {
        'posted_by': posted_by,
        'posted_at': row.posted_at,
        'posting_note': 'Marked posted by Accounting review action. No silent journal posting occurred during import.',
    })
    db.commit()
    return receipt_to_dict(row, include_payload=False)
