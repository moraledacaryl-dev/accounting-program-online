from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.entities import AttendanceEntry, Employee, PayrollPeriod
from app.schemas.common import EmployeeCreate, EmployeeUpdate, AttendanceCreate
from app.api.deps import require_permissions

router = APIRouter()


class AttendanceBulkCreate(BaseModel):
    entries: list[AttendanceCreate]


def _serialize_attendance(row: AttendanceEntry) -> dict:
    return {
        'id': row.id,
        'employee_id': row.employee_id,
        'work_date': row.work_date,
        'time_in': row.time_in,
        'time_out': row.time_out,
        'late_minutes': float(row.late_minutes or 0),
        'undertime_minutes': float(row.undertime_minutes or 0),
        'overtime_hours': float(row.overtime_hours or 0),
        'night_diff_hours': float(row.night_diff_hours or 0),
        'day_type': row.day_type,
        'is_absent': bool(row.is_absent),
        'leave_type': row.leave_type,
        'notes': row.notes,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get('/employees')
def employees(db: Session = Depends(get_db), user=Depends(require_permissions('employees.view'))):
    return db.query(Employee).order_by(Employee.full_name.asc()).all()

@router.post('/employees')
def add_employee(payload: EmployeeCreate, db: Session = Depends(get_db), user=Depends(require_permissions('employees.manage'))):
    obj = Employee(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.put('/employees/{employee_id}')
def edit_employee(employee_id: int, payload: EmployeeUpdate, db: Session = Depends(get_db), user=Depends(require_permissions('employees.manage'))):
    obj = db.get(Employee, employee_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Employee not found')
    for k,v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.delete('/employees/{employee_id}')
def delete_employee(employee_id: int, db: Session = Depends(get_db), user=Depends(require_permissions('employees.manage'))):
    obj = db.get(Employee, employee_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Employee not found')
    db.delete(obj); db.commit()
    return {'ok': True}

@router.get('/attendance')
def attendance(
    db: Session = Depends(get_db),
    user=Depends(require_permissions('attendance.view')),
    employee_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    payroll_period_id: int | None = None,
):
    query = db.query(AttendanceEntry)
    if employee_id:
        query = query.filter(AttendanceEntry.employee_id == int(employee_id))
    if payroll_period_id:
        period = db.get(PayrollPeriod, int(payroll_period_id))
        if period:
            start_date = start_date or period.period_start
            end_date = end_date or period.period_end
    if start_date:
        query = query.filter(AttendanceEntry.work_date >= start_date)
    if end_date:
        query = query.filter(AttendanceEntry.work_date <= end_date)
    rows = query.order_by(AttendanceEntry.work_date.desc(), AttendanceEntry.id.desc()).all()
    return [_serialize_attendance(row) for row in rows]

@router.post('/attendance')
def add_attendance(payload: AttendanceCreate, db: Session = Depends(get_db), user=Depends(require_permissions('attendance.manage'))):
    obj = AttendanceEntry(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return _serialize_attendance(obj)


@router.put('/attendance/{attendance_id}')
def edit_attendance(
    attendance_id: int,
    payload: AttendanceCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('attendance.manage')),
):
    obj = db.get(AttendanceEntry, attendance_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Attendance not found')
    for key, value in payload.model_dump().items():
        setattr(obj, key, value)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _serialize_attendance(obj)


@router.post('/attendance/bulk')
def add_attendance_bulk(
    payload: AttendanceBulkCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('attendance.manage')),
):
    created = []
    for entry in payload.entries:
        obj = AttendanceEntry(**entry.model_dump())
        db.add(obj)
        created.append(obj)
    db.commit()
    for obj in created:
        db.refresh(obj)
    return {
        'created_count': len(created),
        'rows': [_serialize_attendance(row) for row in created],
    }


@router.post('/attendance/import')
def import_attendance_bulk(
    payload: AttendanceBulkCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('attendance.manage')),
):
    return add_attendance_bulk(payload, db=db, user=user)

@router.delete('/attendance/{attendance_id}')
def delete_attendance(attendance_id: int, db: Session = Depends(get_db), user=Depends(require_permissions('attendance.manage'))):
    obj = db.get(AttendanceEntry, attendance_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Attendance not found')
    db.delete(obj); db.commit()
    return {'ok': True}
