from __future__ import annotations
from datetime import datetime
from calendar import monthrange
from sqlalchemy.orm import Session
from app.models.entities import Employee, AttendanceEntry, PayrollRun, PayrollLine, JournalEntry, JournalLine
from app.services.bir_service import ensure_date_unlocked

REGULAR_OT_MULTIPLIER = 1.25
RESTDAY_MULTIPLIER = 1.30
HOLIDAY_MULTIPLIER = 2.00
NIGHT_DIFF_RATE = 0.10
PHILHEALTH_RATE = 0.04  # editable in code/admin later
PHILHEALTH_SALARY_CAP = 100000.0

def hours_between(time_in: str | None, time_out: str | None) -> float:
    if not time_in or not time_out:
        return 0.0
    t1 = datetime.strptime(time_in, "%H:%M")
    t2 = datetime.strptime(time_out, "%H:%M")
    diff = (t2 - t1).total_seconds() / 3600
    if diff < 0:
        diff += 24
    return max(diff, 0.0)

def compute_sss_2025(gross: float):
    # Effective Jan 2025 SSS contribution schedule from official SSS table.
    msc = min(max(round(gross / 500.0) * 500.0, 5000.0), 35000.0)
    # ER+EE under regular SS; simplified: total 15% split 10% employer, 5% employee for SS portion approximation
    # EC handled in employer side via coarse mapping.
    ee = round(msc * 0.05, 2)
    er = round(msc * 0.10, 2)
    ec = 10.0 if msc < 15000 else 30.0
    er_total = round(er + ec, 2)
    return ee, er_total

def compute_philhealth(gross: float):
    basis = min(max(gross, 10000.0), PHILHEALTH_SALARY_CAP)
    total = round(basis * PHILHEALTH_RATE, 2)
    half = round(total / 2.0, 2)
    return half, total - half

def compute_pagibig(gross: float):
    basis = min(gross, 5000.0)
    ee_rate = 0.01 if gross <= 1500 else 0.02
    ee = round(basis * ee_rate, 2)
    er = round(basis * 0.02, 2)
    return ee, er

def compute_employee_line(emp: Employee, attendances: list[AttendanceEntry], include_allowances: bool = True):
    total_hours = 0.0
    basic_pay = 0.0
    overtime_pay = 0.0
    night_diff_pay = 0.0
    holiday_pay = 0.0
    for a in attendances:
        worked_hours = 0.0 if a.is_absent else max(hours_between(a.time_in, a.time_out) - (float(a.late_minutes or 0) + float(a.undertime_minutes or 0)) / 60.0, 0.0)
        total_hours += worked_hours
        base_hourly = float(emp.hourly_rate or 0)
        if emp.compensation_type.lower() == 'monthly':
            # 26-day divisor typical in payroll systems, 8 hrs/day
            base_daily = float(emp.rate or 0) / 26.0 if emp.rate else 0.0
            base_hourly = base_daily / 8.0
            paid_hours = min(max(worked_hours, 0.0), 8.0)
            basic_pay += base_daily * (paid_hours / 8.0) if paid_hours > 0 and not a.is_absent else 0.0
        elif emp.compensation_type.lower() == 'daily':
            base_daily = float(emp.daily_rate or emp.rate or 0)
            base_hourly = base_daily / 8.0 if base_daily else 0.0
            paid_hours = min(max(worked_hours, 0.0), 8.0)
            basic_pay += base_daily * (paid_hours / 8.0) if paid_hours > 0 and not a.is_absent else 0.0
        else:
            base_hourly = float(emp.hourly_rate or emp.rate or 0)
            basic_pay += worked_hours * base_hourly

        ot_hours = float(a.overtime_hours or 0)
        nd_hours = float(a.night_diff_hours or 0)
        day_type = (a.day_type or 'regular_day').lower()
        ot_mult = REGULAR_OT_MULTIPLIER
        day_mult = 1.0
        if day_type == 'rest_day':
            day_mult = RESTDAY_MULTIPLIER
            ot_mult = RESTDAY_MULTIPLIER * REGULAR_OT_MULTIPLIER
        elif day_type == 'holiday':
            day_mult = HOLIDAY_MULTIPLIER
            ot_mult = HOLIDAY_MULTIPLIER * REGULAR_OT_MULTIPLIER

        holiday_component = 0.0
        if day_type == 'holiday' and worked_hours > 0:
            if emp.compensation_type.lower() in {'monthly', 'daily'}:
                base_daily = float(emp.daily_rate or emp.rate or 0)
                if emp.compensation_type.lower() == 'monthly':
                    base_daily = float(emp.rate or 0) / 26.0 if emp.rate else 0.0
                holiday_component = max((day_mult - 1.0) * base_daily, 0.0)
            else:
                holiday_component = max((day_mult - 1.0) * worked_hours * base_hourly, 0.0)
        holiday_pay += holiday_component

        overtime_pay += ot_hours * base_hourly * ot_mult
        night_diff_pay += nd_hours * base_hourly * NIGHT_DIFF_RATE

    allowances = (float(emp.meal_allowance or 0) + float(emp.transport_allowance or 0)) if include_allowances else 0.0
    gross = round(basic_pay + overtime_pay + night_diff_pay + holiday_pay + allowances, 2)
    sss_ee, sss_er = compute_sss_2025(gross)
    ph_ee, ph_er = compute_philhealth(gross)
    pi_ee, pi_er = compute_pagibig(gross)
    other_deductions = 0.0
    deductions = round(sss_ee + ph_ee + pi_ee + other_deductions, 2)
    net = round(gross - deductions, 2)
    return {
        'employee_id': emp.id,
        'employee_name': emp.full_name,
        'department': emp.department,
        'hours_worked': round(total_hours, 2),
        'basic_pay': round(basic_pay, 2),
        'overtime_pay': round(overtime_pay, 2),
        'night_diff_pay': round(night_diff_pay, 2),
        'holiday_pay': round(holiday_pay, 2),
        'allowances': round(allowances, 2),
        'gross_pay': gross,
        'sss_employee': sss_ee,
        'philhealth_employee': ph_ee,
        'pagibig_employee': pi_ee,
        'other_deductions': other_deductions,
        'total_deductions': deductions,
        'net_pay': net,
        'sss_employer': sss_er,
        'philhealth_employer': ph_er,
        'pagibig_employer': pi_er,
    }

def generate_payroll_run(db: Session, name: str, period_start: str, period_end: str, release_date: str | None = None, include_allowances: bool = True):
    ensure_date_unlocked(db, period_start, scope='bir', action='generate payroll run in locked period')
    ensure_date_unlocked(db, period_end, scope='bir', action='generate payroll run in locked period')
    emps = db.query(Employee).filter(Employee.is_active == True).order_by(Employee.full_name.asc()).all()
    run = PayrollRun(name=name, period_start=period_start, period_end=period_end, release_date=release_date, status='draft')
    db.add(run)
    db.flush()
    for emp in emps:
        atts = db.query(AttendanceEntry).filter(
            AttendanceEntry.employee_id == emp.id,
            AttendanceEntry.work_date >= period_start,
            AttendanceEntry.work_date <= period_end,
        ).order_by(AttendanceEntry.work_date.asc()).all()
        line_data = compute_employee_line(emp, atts, include_allowances)
        db.add(PayrollLine(payroll_run_id=run.id, **line_data))
    db.commit()
    db.refresh(run)
    return run

def autopost_payroll_run(db: Session, run: PayrollRun):
    ensure_date_unlocked(db, run.period_end, scope='bir', action='post payroll run to journal')
    if run.generated_journal_entry_id:
        return db.get(JournalEntry, run.generated_journal_entry_id)
    gross = sum(float(l.gross_pay or 0) for l in run.lines)
    sss_er = sum(float(l.sss_employer or 0) for l in run.lines)
    ph_er = sum(float(l.philhealth_employer or 0) for l in run.lines)
    pi_er = sum(float(l.pagibig_employer or 0) for l in run.lines)
    other_deds = sum(float(l.other_deductions or 0) for l in run.lines)
    net = sum(float(l.net_pay or 0) for l in run.lines)

    je = JournalEntry(entry_date=run.period_end, reference_no=f"PAY-{run.id}", description=f"Payroll run {run.name}", source_module='payroll', status='posted')
    db.add(je)
    db.flush()
    lines = [
        JournalLine(journal_entry_id=je.id, account_code='5000', account_name='Salaries and Wages Expense', debit=round(gross,2), credit=0),
        JournalLine(journal_entry_id=je.id, account_code='5010', account_name='Employer Government Contributions Expense', debit=round(sss_er+ph_er+pi_er,2), credit=0),
        JournalLine(journal_entry_id=je.id, account_code='2100', account_name='Payroll Payable', debit=0, credit=round(net,2)),
        JournalLine(journal_entry_id=je.id, account_code='2110', account_name='SSS Payable', debit=0, credit=round(sum(float(l.sss_employee or 0) for l in run.lines)+sss_er,2)),
        JournalLine(journal_entry_id=je.id, account_code='2120', account_name='PhilHealth Payable', debit=0, credit=round(sum(float(l.philhealth_employee or 0) for l in run.lines)+ph_er,2)),
        JournalLine(journal_entry_id=je.id, account_code='2130', account_name='Pag-IBIG Payable', debit=0, credit=round(sum(float(l.pagibig_employee or 0) for l in run.lines)+pi_er,2)),
    ]
    if round(other_deds, 2) > 0:
        lines.append(
            JournalLine(
                journal_entry_id=je.id,
                account_code='2140',
                account_name='Other Payroll Deductions Payable',
                debit=0,
                credit=round(other_deds, 2),
            )
        )
    for l in lines:
        db.add(l)
    run.generated_journal_entry_id = je.id
    run.status = 'posted'
    db.add(run)
    db.commit()
    db.refresh(je)
    return je
