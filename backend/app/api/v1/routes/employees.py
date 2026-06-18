"""
PulseDesk Employee & Department Routes

Thin route handlers that delegate to the employee service layer.
"""

from typing import Optional, List
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas import (
    EmployeeCreate, EmployeeUpdate, EmployeeOut, EmployeePasswordReset,
    DepartmentCreate, DepartmentOut,
)
from app.api.v1.routes.auth import require_admin_read, require_admin_write
from app.core.audit import log_admin_action
from app.services import employee_service

router = APIRouter(tags=["employees"])


# ─── Departments ─────────────────────────────────────────────────────────────

@router.post("/departments", response_model=DepartmentOut, status_code=201)
async def create_department(
    payload: DepartmentCreate,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    result = await employee_service.create_department(payload, db)
    log_admin_action("department_created", admin_id=str(admin.id), department_id=str(result.id))
    return result


@router.get("/departments", response_model=List[DepartmentOut])
async def list_departments(
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    return await employee_service.list_departments(db)


@router.delete("/departments/{dept_id}", status_code=204)
async def delete_department(
    dept_id: uuid.UUID,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    await employee_service.delete_department(dept_id, db)
    log_admin_action("department_deleted", admin_id=str(admin.id), department_id=str(dept_id))


# ─── Employees ────────────────────────────────────────────────────────────────

@router.post("/employees", response_model=EmployeeOut, status_code=201)
async def create_employee(
    payload: EmployeeCreate,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    result = await employee_service.create_employee(payload, db)
    log_admin_action("employee_created", admin_id=str(admin.id), employee_id=str(result.id))
    return result


@router.get("/employees", response_model=List[EmployeeOut])
async def list_employees(
    department_id: Optional[uuid.UUID] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    return await employee_service.list_employees(
        db, department_id=department_id, is_active=is_active, search=search,
    )


@router.get("/employees/{employee_id}", response_model=EmployeeOut)
async def get_employee(
    employee_id: uuid.UUID,
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    return await employee_service.get_employee(employee_id, db)


@router.patch("/employees/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: uuid.UUID,
    payload: EmployeeUpdate,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    result = await employee_service.update_employee(employee_id, payload, db)
    log_admin_action("employee_updated", admin_id=str(admin.id), employee_id=str(employee_id))
    return result


@router.delete("/employees/{employee_id}/permanent", status_code=204)
async def delete_employee_permanently(
    employee_id: uuid.UUID,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    await employee_service.delete_employee_permanently(employee_id, db)
    log_admin_action("employee_permanently_deleted", admin_id=str(admin.id), employee_id=str(employee_id))


@router.delete("/employees/{employee_id}", status_code=204)
async def deactivate_employee(
    employee_id: uuid.UUID,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    await employee_service.deactivate_employee(employee_id, db)
    log_admin_action("employee_deactivated", admin_id=str(admin.id), employee_id=str(employee_id))


@router.post("/employees/{employee_id}/reset-password", status_code=200)
async def reset_employee_password(
    employee_id: uuid.UUID,
    payload: EmployeePasswordReset,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    from app.models import Employee
    from sqlalchemy import select
    from fastapi import HTTPException
    from app.core.security import hash_password
    
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    employee.hashed_password = hash_password(payload.new_password)
    await db.commit()
    log_admin_action("employee_password_reset", admin_id=str(admin.id), employee_id=str(employee_id))
    return {"status": "success"}
