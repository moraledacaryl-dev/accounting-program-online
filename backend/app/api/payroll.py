from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from app.db.database import get_db
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
        gross_components = (
            float(values.get('basic_pay') or 0)
            + float(values.get('overtime_pay') or 0)
            + float(values.get('night_diff_pay') or 0)
            + float(values.get('holiday_pay') or 0)
            + float(values.get('allowances') or 0)
        )
        gross_pay = float(values.get('gross_pay') or 0)
        if gross_pay == 0 and gross_components > 0:
            gross_pay = gross_components

        statutory_deductions = (
            float(values.get('sss_employee') or 0)
            + float(values.get('philhealth_employee') or 0)
            + float(values.get('pagibig_employee') or 0)
        )
        other_deductions = float(values.get('other_deductions') or 0)
        total_deductions = round(statutory_deductions + other_deductions, 2)

        values['gross_pay'] = round(gross_pay, 2)
        values['total_deductions'] = total_deductions
        values['net_pay'] = round(gross_pay - total_deductions, 2)

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
