from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, selectinload

from app.models.entities import JournalEntry, JournalLine, PayrollImportBatch, PayrollPeriod, PayrollPeriodLine
from app.schemas.payroll_periods import PayrollImportCreate, PayrollPeriodCreate, PayrollPeriodLineInput, PayrollPeriodUpdate
from app.services.bir_service import ensure_date_unlocked


def _today() -> str:
    return datetime.utcnow().strftime('%Y-%m-%d')


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except Exception:
        return float(default)


def _serialize_line(row: PayrollPeriodLine) -> dict:
    return {
        'id': row.id,
        'payroll_period_id': row.payroll_period_id,
        'employee_id': row.employee_id,
        'employee_name': row.employee_name,
        'department': row.department,
        'regular_hours': float(row.regular_hours or 0),
        'overtime_hours': float(row.overtime_hours or 0),
        'regular_holiday_hours': float(row.regular_holiday_hours or 0),
        'special_holiday_hours': float(row.special_holiday_hours or 0),
        'night_diff_hours': float(row.night_diff_hours or 0),
        'regular_amount': float(row.regular_amount or 0),
        'overtime_amount': float(row.overtime_amount or 0),
        'holiday_amount': float(row.holiday_amount or 0),
        'night_diff_amount': float(row.night_diff_amount or 0),
        'allowances': float(row.allowances or 0),
        'deductions': float(row.deductions or 0),
        'employer_contribution': float(row.employer_contribution or 0),
        'gross_pay': float(row.gross_pay or 0),
        'net_pay': float(row.net_pay or 0),
        'notes': row.notes,
    }


def _serialize_import(row: PayrollImportBatch) -> dict:
    return {
        'id': row.id,
        'payroll_period_id': row.payroll_period_id,
        'file_name': row.file_name,
        'imported_by': row.imported_by,
        'row_count': int(row.row_count or 0),
        'status': row.status,
        'notes': row.notes,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _period_totals(period: PayrollPeriod) -> dict:
    lines = period.lines or []
    gross_total = sum(float(row.gross_pay or 0) for row in lines)
    net_total = sum(float(row.net_pay or 0) for row in lines)
    deductions_total = sum(float(row.deductions or 0) for row in lines)
    employer_total = sum(float(row.employer_contribution or 0) for row in lines)
    return {
        'gross_total': round(gross_total, 4),
        'net_total': round(net_total, 4),
        'deductions_total': round(deductions_total, 4),
        'employer_contribution_total': round(employer_total, 4),
    }


def _serialize_period(row: PayrollPeriod) -> dict:
    lines = sorted(row.lines or [], key=lambda x: (x.employee_name or '', x.id))
    imports = sorted(row.imports or [], key=lambda x: x.id, reverse=True)
    totals = _period_totals(row)
    return {
        'id': row.id,
        'name': row.name,
        'period_start': row.period_start,
        'period_end': row.period_end,
        'release_date': row.release_date,
        'status': row.status,
        'source_type': row.source_type,
        'notes': row.notes,
        'generated_journal_entry_id': row.generated_journal_entry_id,
        'line_count': len(lines),
        **totals,
        'lines': [_serialize_line(line) for line in lines],
        'imports': [_serialize_import(batch) for batch in imports],
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _assert_no_overlap(db: Session, period_start: str | None, period_end: str | None, exclude_period_id: int | None = None):
    start = _norm(period_start)
    end = _norm(period_end)
    if not start or not end:
        return
    if end < start:
        raise ValueError('period_end cannot be earlier than period_start.')

    query = db.query(PayrollPeriod).filter(PayrollPeriod.period_start.isnot(None), PayrollPeriod.period_end.isnot(None))
    if exclude_period_id:
        query = query.filter(PayrollPeriod.id != int(exclude_period_id))
    existing = query.all()
    for row in existing:
        row_start = _norm(row.period_start)
        row_end = _norm(row.period_end)
        if not row_start or not row_end:
            continue
        overlap = not (end < row_start or start > row_end)
        if overlap:
            raise ValueError(
                f'Payroll period overlaps with existing period #{row.id} ({row.name}) from {row_start} to {row_end}.'
            )


def _coalesce_gross(line: PayrollPeriodLineInput) -> float:
    gross = _to_float(line.gross_pay, None)
    if gross is not None and gross != 0:
        return max(0.0, gross)
    computed = (
        _to_float(line.regular_amount)
        + _to_float(line.overtime_amount)
        + _to_float(line.holiday_amount)
        + _to_float(line.night_diff_amount)
        + _to_float(line.allowances)
    )
    return max(0.0, computed)


def _coalesce_net(line: PayrollPeriodLineInput, gross: float) -> float:
    net = _to_float(line.net_pay, None)
    if net is not None and net != 0:
        return max(0.0, net)
    return max(0.0, gross - _to_float(line.deductions))


def _apply_lines(db: Session, period: PayrollPeriod, lines: list[PayrollPeriodLineInput]):
    for old in list(period.lines or []):
        db.delete(old)
    for line in lines or []:
        employee_name = _norm(line.employee_name)
        if not employee_name:
            raise ValueError('employee_name is required per payroll line.')
        gross = _coalesce_gross(line)
        net = _coalesce_net(line, gross)
        db.add(
            PayrollPeriodLine(
                payroll_period_id=period.id,
                employee_id=line.employee_id,
                employee_name=employee_name,
                department=_norm(line.department),
                regular_hours=max(0.0, _to_float(line.regular_hours)),
                overtime_hours=max(0.0, _to_float(line.overtime_hours)),
                regular_holiday_hours=max(0.0, _to_float(line.regular_holiday_hours)),
                special_holiday_hours=max(0.0, _to_float(line.special_holiday_hours)),
                night_diff_hours=max(0.0, _to_float(line.night_diff_hours)),
                regular_amount=max(0.0, _to_float(line.regular_amount)),
                overtime_amount=max(0.0, _to_float(line.overtime_amount)),
                holiday_amount=max(0.0, _to_float(line.holiday_amount)),
                night_diff_amount=max(0.0, _to_float(line.night_diff_amount)),
                allowances=max(0.0, _to_float(line.allowances)),
                deductions=max(0.0, _to_float(line.deductions)),
                employer_contribution=max(0.0, _to_float(line.employer_contribution)),
                gross_pay=round(gross, 4),
                net_pay=round(net, 4),
                notes=line.notes,
            )
        )


def list_payroll_periods(db: Session, *, status: str | None = None, limit: int = 200):
    query = db.query(PayrollPeriod).options(selectinload(PayrollPeriod.lines), selectinload(PayrollPeriod.imports))
    if status:
        query = query.filter(PayrollPeriod.status == status)
    rows = query.order_by(PayrollPeriod.id.desc()).limit(max(1, min(int(limit or 200), 1000))).all()
    return [_serialize_period(row) for row in rows]


def get_payroll_period(db: Session, period_id: int):
    row = (
        db.query(PayrollPeriod)
        .options(selectinload(PayrollPeriod.lines), selectinload(PayrollPeriod.imports))
        .filter(PayrollPeriod.id == int(period_id))
        .first()
    )
    if not row:
        raise ValueError('Payroll period not found.')
    return _serialize_period(row)


def create_payroll_period(db: Session, payload: PayrollPeriodCreate):
    _assert_no_overlap(db, payload.period_start, payload.period_end, exclude_period_id=None)
    row = PayrollPeriod(
        name=_norm(payload.name) or f'Payroll Period {_today()}',
        period_start=_norm(payload.period_start),
        period_end=_norm(payload.period_end),
        release_date=_norm(payload.release_date),
        status=_norm(payload.status) or 'draft',
        source_type=_norm(payload.source_type) or 'manual',
        notes=payload.notes,
    )
    db.add(row)
    db.flush()
    _apply_lines(db, row, payload.lines or [])
    db.commit()
    row = (
        db.query(PayrollPeriod)
        .options(selectinload(PayrollPeriod.lines), selectinload(PayrollPeriod.imports))
        .filter(PayrollPeriod.id == row.id)
        .first()
    )
    return _serialize_period(row)


def update_payroll_period(db: Session, period_id: int, payload: PayrollPeriodUpdate):
    row = db.get(PayrollPeriod, int(period_id))
    if not row:
        raise ValueError('Payroll period not found.')
    data = payload.model_dump(exclude_unset=True)
    if row.status == 'posted':
        allowed_keys = {'notes'}
        changed_keys = {key for key in data.keys() if key not in allowed_keys}
        if changed_keys:
            raise ValueError('Posted payroll periods can only update notes. Reopen policy is required for structural edits.')

    next_period_start = _norm(data.get('period_start')) if 'period_start' in data else _norm(row.period_start)
    next_period_end = _norm(data.get('period_end')) if 'period_end' in data else _norm(row.period_end)
    _assert_no_overlap(db, next_period_start, next_period_end, exclude_period_id=row.id)

    for key in ('name', 'period_start', 'period_end', 'release_date', 'status', 'source_type', 'notes'):
        if key in data:
            value = data.get(key)
            if isinstance(value, str):
                value = _norm(value)
            setattr(row, key, value)
    db.add(row)
    db.flush()
    if 'lines' in data and data.get('lines') is not None:
        if row.status == 'posted':
            raise ValueError('Posted payroll periods cannot update lines directly.')
        _apply_lines(db, row, data.get('lines') or [])
    db.commit()
    row = (
        db.query(PayrollPeriod)
        .options(selectinload(PayrollPeriod.lines), selectinload(PayrollPeriod.imports))
        .filter(PayrollPeriod.id == row.id)
        .first()
    )
    return _serialize_period(row)


def delete_payroll_period(db: Session, period_id: int):
    row = db.get(PayrollPeriod, int(period_id))
    if not row:
        raise ValueError('Payroll period not found.')
    if row.status == 'posted' or row.generated_journal_entry_id:
        raise ValueError('Posted payroll periods cannot be deleted.')
    db.delete(row)
    db.commit()
    return {'ok': True}


def import_payroll_lines(db: Session, payload: PayrollImportCreate, username: str | None = None):
    period = None
    if payload.payroll_period_id:
        period = db.get(PayrollPeriod, int(payload.payroll_period_id))
        if not period:
            raise ValueError('payroll_period_id not found.')
        if period.status == 'posted':
            raise ValueError('Cannot import lines to a posted payroll period.')
    if period is None:
        period = PayrollPeriod(
            name=f'Imported {payload.file_name}',
            period_start=None,
            period_end=None,
            release_date=None,
            status='draft',
            source_type='import',
            notes='Auto-created from payroll import batch',
        )
        db.add(period)
        db.flush()
    _apply_lines(db, period, payload.lines or [])
    batch = PayrollImportBatch(
        payroll_period_id=period.id,
        file_name=payload.file_name,
        imported_by=username,
        row_count=len(payload.lines or []),
        status=_norm(payload.status) or 'imported',
        notes=payload.notes,
    )
    db.add(batch)
    db.commit()
    return {
        'batch': _serialize_import(batch),
        'period': get_payroll_period(db, period.id),
    }


def post_payroll_period(db: Session, period_id: int, username: str | None = None, post_date: str | None = None):
    period = (
        db.query(PayrollPeriod)
        .options(selectinload(PayrollPeriod.lines))
        .filter(PayrollPeriod.id == int(period_id))
        .first()
    )
    if not period:
        raise ValueError('Payroll period not found.')
    if period.generated_journal_entry_id:
        journal = db.get(JournalEntry, int(period.generated_journal_entry_id))
        if journal:
            return {'journal': {'id': journal.id, 'reference_no': journal.reference_no}, 'period': get_payroll_period(db, period.id)}
    if not (period.lines or []):
        raise ValueError('Payroll period has no lines.')

    tx_date = _norm(post_date) or _norm(period.period_end) or _today()
    ensure_date_unlocked(db, tx_date, scope='bir', action='post payroll period in locked period')

    totals = _period_totals(period)
    gross_total = float(totals['gross_total'])
    net_total = float(totals['net_total'])
    deductions_total = float(totals['deductions_total'])
    employer_total = float(totals['employer_contribution_total'])

    journal = JournalEntry(
        entry_date=tx_date,
        reference_no=f'PPR-{period.id}',
        description=f'Payroll period posting: {period.name}',
        source_module='payroll',
        status='posted',
        locked=False,
    )
    db.add(journal)
    db.flush()

    lines = [
        JournalLine(journal_entry_id=journal.id, account_code='5000', account_name='Salaries and Wages Expense', debit=round(gross_total, 2), credit=0),
        JournalLine(journal_entry_id=journal.id, account_code='5010', account_name='Employer Contributions Expense', debit=round(employer_total, 2), credit=0),
        JournalLine(journal_entry_id=journal.id, account_code='2100', account_name='Payroll Payable', debit=0, credit=round(net_total, 2)),
    ]
    if deductions_total > 0:
        lines.append(
            JournalLine(
                journal_entry_id=journal.id,
                account_code='2140',
                account_name='Payroll Deductions Payable',
                debit=0,
                credit=round(deductions_total, 2),
            )
        )
    for line in lines:
        db.add(line)

    period.generated_journal_entry_id = journal.id
    period.status = 'posted'
    if username:
        period.notes = f'{period.notes or ""}\nPosted by {username} on {tx_date}'.strip()
    db.add(period)
    db.commit()
    return {
        'journal': {
            'id': journal.id,
            'reference_no': journal.reference_no,
            'entry_date': journal.entry_date,
        },
        'period': get_payroll_period(db, period.id),
    }
