from typing import Optional, List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.db.session import get_db
from app.models import Employee, Department, Device, DeviceStatus, WorkSession, DailySummary
from app.schemas import (
    EmployeeCreate, EmployeeUpdate, EmployeeOut,
    DepartmentCreate, DepartmentOut,
)
from app.api.v1.routes.auth import get_current_admin
from app.services.online_tracker import is_employee_online
from app.core.logging import get_logger

router = APIRouter(tags=["employees"])
log = get_logger("employees")


# ─── Departments ─────────────────────────────────────────────────────────────

@router.post("/departments", response_model=DepartmentOut, status_code=201)
async def create_department(
    payload: DepartmentCreate,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Department).where(Department.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Department name already exists")

    dept = Department(**payload.model_dump())
    db.add(dept)
    await db.commit()
    await db.refresh(dept)
    return DepartmentOut(id=dept.id, name=dept.name, description=dept.description,
                         created_at=dept.created_at, employee_count=0)


@router.get("/departments", response_model=List[DepartmentOut])
async def list_departments(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Department, func.count(Employee.id).label("employee_count"))
        .outerjoin(Employee, and_(Employee.department_id == Department.id, Employee.is_active == True))
        .group_by(Department.id)
        .order_by(Department.name)
    )
    rows = result.all()
    return [
        DepartmentOut(
            id=dept.id, name=dept.name, description=dept.description,
            created_at=dept.created_at, employee_count=count,
        )
        for dept, count in rows
    ]


@router.delete("/departments/{dept_id}", status_code=204)
async def delete_department(
    dept_id: uuid.UUID,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Department).where(Department.id == dept_id))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    await db.delete(dept)
    await db.commit()


# ─── Employees ────────────────────────────────────────────────────────────────

@router.post("/employees", response_model=EmployeeOut, status_code=201)
async def create_employee(
    payload: EmployeeCreate,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Employee).where(Employee.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Employee email already registered")

    if payload.department_id:
        dept_result = await db.execute(select(Department).where(Department.id == payload.department_id))
        if not dept_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Department not found")

    employee = Employee(**payload.model_dump())
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    log.info("employee_created", employee_id=str(employee.id), by=str(admin.id))
    return await _employee_out(employee, db)


@router.get("/employees", response_model=List[EmployeeOut])
async def list_employees(
    department_id: Optional[uuid.UUID] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Employee)
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    if is_active is not None:
        stmt = stmt.where(Employee.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            Employee.full_name.ilike(pattern) | Employee.email.ilike(pattern)
        )
    stmt = stmt.order_by(Employee.full_name)

    result = await db.execute(stmt)
    employees = result.scalars().all()
    return [await _employee_out(e, db) for e in employees]


@router.get("/employees/{employee_id}", response_model=EmployeeOut)
async def get_employee(
    employee_id: uuid.UUID,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return await _employee_out(employee, db)


@router.patch("/employees/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: uuid.UUID,
    payload: EmployeeUpdate,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(employee, field, value)

    await db.commit()
    await db.refresh(employee)
    return await _employee_out(employee, db)


@router.delete("/employees/{employee_id}", status_code=204)
async def deactivate_employee(
    employee_id: uuid.UUID,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    employee.is_active = False
    await db.commit()


# ─── Helper ──────────────────────────────────────────────────────────────────

async def _employee_out(employee: Employee, db: AsyncSession) -> EmployeeOut:
    dept_name = None
    if employee.department_id:
        dept_result = await db.execute(
            select(Department.name).where(Department.id == employee.department_id)
        )
        dept_name = dept_result.scalar_one_or_none()

    device_count_result = await db.execute(
        select(func.count(Device.id)).where(
            Device.employee_id == employee.id,
            Device.status == DeviceStatus.approved,
        )
    )
    device_count = device_count_result.scalar() or 0
    online = await is_employee_online(employee.id, db)

    return EmployeeOut(
        id=employee.id,
        email=employee.email,
        full_name=employee.full_name,
        department_id=employee.department_id,
        department_name=dept_name,
        job_title=employee.job_title,
        timezone=employee.timezone,
        work_start_hour=employee.work_start_hour,
        work_end_hour=employee.work_end_hour,
        is_active=employee.is_active,
        created_at=employee.created_at,
        device_count=device_count,
        is_online=online,
    )
