"""
Employee & Department Service Layer

All business logic for employee/department CRUD. Route handlers delegate here.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ConflictError
from app.core.logging import get_logger
from app.models import (
    Employee, Department, Device, DeviceStatus, WorkSession, ActivityEvent,
    AppUsageDaily, AnomalyLog, ScreenshotPolicy, Screenshot, DailySummary,
    ActionItem, AdminAuditLog
)
from app.schemas import EmployeeCreate, EmployeeUpdate, EmployeeOut, DepartmentCreate, DepartmentOut
from app.services.online_tracker import is_employee_online

log = get_logger("employee_service")


# ─── Department Operations ────────────────────────────────────────────────────

async def create_department(payload: DepartmentCreate, db: AsyncSession) -> DepartmentOut:
    existing = await db.execute(select(Department).where(Department.name == payload.name))
    if existing.scalar_one_or_none():
        raise ConflictError("Department name already exists")

    dept = Department(**payload.model_dump())
    db.add(dept)
    await db.commit()
    await db.refresh(dept)
    return DepartmentOut(
        id=dept.id, name=dept.name, description=dept.description,
        created_at=dept.created_at, employee_count=0,
    )


async def list_departments(db: AsyncSession) -> list[DepartmentOut]:
    result = await db.execute(
        select(Department, func.count(Employee.id).label("employee_count"))
        .outerjoin(Employee, and_(Employee.department_id == Department.id, Employee.is_active))
        .group_by(Department.id)
        .order_by(Department.name)
    )
    return [
        DepartmentOut(
            id=dept.id, name=dept.name, description=dept.description,
            created_at=dept.created_at, employee_count=count,
        )
        for dept, count in result.all()
    ]


async def delete_department(dept_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(select(Department).where(Department.id == dept_id))
    dept = result.scalar_one_or_none()
    if not dept:
        raise NotFoundError("Department not found")
    await db.delete(dept)
    await db.commit()


# ─── Employee Operations ──────────────────────────────────────────────────────

async def build_employee_out(employee: Employee, db: AsyncSession) -> EmployeeOut:
    """Build a full EmployeeOut response with computed fields."""
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


async def create_employee(payload: EmployeeCreate, db: AsyncSession) -> EmployeeOut:
    existing = await db.execute(select(Employee).where(Employee.email == payload.email))
    if existing.scalar_one_or_none():
        raise ConflictError("Employee email already registered")

    if payload.department_id:
        dept_result = await db.execute(select(Department).where(Department.id == payload.department_id))
        if not dept_result.scalar_one_or_none():
            raise NotFoundError("Department not found")

    employee = Employee(**payload.model_dump())
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    log.info("employee_created", employee_id=str(employee.id))
    return await build_employee_out(employee, db)


async def get_employee(employee_id: uuid.UUID, db: AsyncSession) -> EmployeeOut:
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise NotFoundError("Employee not found")
    return await build_employee_out(employee, db)


async def list_employees(
    db: AsyncSession,
    *,
    department_id: Optional[uuid.UUID] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
) -> list[EmployeeOut]:
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
    return [await build_employee_out(e, db) for e in employees]


async def update_employee(
    employee_id: uuid.UUID,
    payload: EmployeeUpdate,
    db: AsyncSession,
) -> EmployeeOut:
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise NotFoundError("Employee not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(employee, field, value)

    await db.commit()
    await db.refresh(employee)
    return await build_employee_out(employee, db)


async def deactivate_employee(employee_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise NotFoundError("Employee not found")
    employee.is_active = False
    await db.commit()


async def delete_employee_permanently(employee_id: uuid.UUID, db: AsyncSession) -> None:
    from sqlalchemy import delete
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise NotFoundError("Employee not found")

    # Manually cascade delete all related records
    await db.execute(delete(AdminAuditLog).where(AdminAuditLog.target_employee_id == employee_id))
    await db.execute(delete(ActionItem).where(ActionItem.employee_id == employee_id))
    await db.execute(delete(AnomalyLog).where(AnomalyLog.employee_id == employee_id))
    await db.execute(delete(Screenshot).where(Screenshot.employee_id == employee_id))
    await db.execute(delete(ScreenshotPolicy).where(ScreenshotPolicy.employee_id == employee_id))
    await db.execute(delete(ActivityEvent).where(ActivityEvent.employee_id == employee_id))
    await db.execute(delete(WorkSession).where(WorkSession.employee_id == employee_id))
    await db.execute(delete(AppUsageDaily).where(AppUsageDaily.employee_id == employee_id))
    await db.execute(delete(DailySummary).where(DailySummary.employee_id == employee_id))
    await db.execute(delete(Device).where(Device.employee_id == employee_id))
    await db.execute(delete(Employee).where(Employee.id == employee_id))
    
    await db.commit()

