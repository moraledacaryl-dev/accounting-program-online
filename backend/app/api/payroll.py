from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from app.db.database import get_db
from app.db.monetary_precision import centavos, decimal_money
from app.models.entities import PayrollRun
from app.schemas.common import PayrollRunCreate, PayrollGeneratePayload
from app.services.payroll_service import generate_payroll_run, autopost_payroll_run
from app.api.deps import require_any_permissions, require_permissions
from app.services.bir_service import ensure_date_unlocked

router = APIRouter()

@router.get('/runs')
def runs(db: Session = Depends(get_db), user=Depends(require_permissions('payroll_periods.view'))):
    return db.query(PayrollRun).options(selectinload(PayrollRun.lines)).order_by(PayrollRun.id.desc()).all()

@router.post('/runs')
def create_run(payload: PayrollRunCreate, db: Session = Depends(get_db), user=Depends(require_permissions('payroll_periods.manage'))):
    try:
        ensure_date_unlocked(db, payload.period_start, scope='bir', action='create payroll run in locked period')
        ensure_date_unlocked(db, payload.period_end, scope='bir', action='create payroll run in locked period')
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    run = PayrollRun(name=payload.name, period_start=payload.period_start, period_end=payload.period_end, release_date=payload.release_date, status=payload.status, notes=payload.notes)
    db.add(run); db.flush()
    from app.models.entities import PayrollLine
    for line in payload.lines:
        values = line.model_dump()
        gross_components = sum((
            decimal_money(values.get('basic_pay')),
            decimal_money(values.get('overtime_pay')),
            decimal_money(values.get('night_diff_pay')),
            decimal_money(values.get('holiday_pay')),
            decimal_money(values.get('allowances')),
        ), Decimal('0'))
        gross_pay = decimal_money(values.get('gross_pay'))
        if gross_pay == 0 and gross_components > 0:
            gross_pay = gross_components

        statutory_deductions = sum((
            decimal_money(values.get('sss_employee')),
            decimal_money(values.get('philhealth_employee')),
            decimal_money(values.get('pagibig_employee')),
        ), Decimal('0'))
        other_deductions = decimal_money(values.get('other_deductions'))
        total_deductions = centavos(statutory_deductions + other_deductions)

        values['gross_pay'] = centavos(gross_pay)
        values['total_deductions'] = total_deductions
        values['net_pay'] = centavos(gross_pay - total_deductions)

        db.add(PayrollLine(payroll_run_id=run.id, **values))
    db.commit(); db.refresh(run)
    return run

@router.post('/runs/generate')
def generate(payload: PayrollGeneratePayload, db: Session = Depends(get_db), user=Depends(require_permissions('payroll_periods.manage'))):
    try:
        return generate_payroll_run(db, payload.name, payload.period_start, payload.period_end, payload.release_date, payload.include_allowances)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post('/runs/{run_id}/post')
def post_run(run_id: int, db: Session = Depends(get_db), user=Depends(require_any_permissions('payroll_periods.manage', 'journals.post'))):
    run = db.get(PayrollRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail='Payroll run not found')
    try:
        return autopost_payroll_run(db, run)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
