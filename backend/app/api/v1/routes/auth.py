from datetime import datetime, timezone, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models import Admin, UserRole
from app.schemas import AdminLogin, TokenResponse, RefreshTokenRequest, AdminOut, AdminCreate
from app.core.security import (
    verify_password, hash_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.core.logging import get_logger
from jose import JWTError

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)
log = get_logger("auth")


async def get_current_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: AsyncSession = Depends(get_db),
) -> Admin:
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        admin_id = payload.get("sub")
        if not admin_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail="Token expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(Admin).where(Admin.id == admin_id, Admin.is_active == True)
    )
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=401, detail="Admin account not found or deactivated")
    return admin


def require_role(*roles: UserRole):
    async def checker(current_admin: Admin = Depends(get_current_admin)):
        if current_admin.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_admin
    return checker


@router.post("/login", response_model=TokenResponse)
async def login(payload: AdminLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Admin).where(Admin.email == payload.email))
    admin = result.scalar_one_or_none()

    if not admin or not verify_password(payload.password, admin.hashed_password):
        log.warning("failed_login", email=payload.email)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not admin.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated")

    admin.last_login = datetime.now(timezone.utc)
    await db.commit()

    token_data = {"sub": str(admin.id), "role": admin.role}
    log.info("admin_logged_in", admin_id=str(admin.id), email=admin.email)

    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        admin_id=admin.id,
        full_name=admin.full_name,
        role=admin.role,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except JWTError:
        raise HTTPException(status_code=401, detail="Refresh token expired or invalid")

    admin_id = data.get("sub")
    result = await db.execute(
        select(Admin).where(Admin.id == admin_id, Admin.is_active == True)
    )
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=401, detail="Admin not found")

    token_data = {"sub": str(admin.id), "role": admin.role}
    log.info("token_refreshed", admin_id=str(admin.id))

    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        admin_id=admin.id,
        full_name=admin.full_name,
        role=admin.role,
    )


@router.get("/me", response_model=AdminOut)
async def get_me(current_admin: Admin = Depends(get_current_admin)):
    """Returns current admin profile. Used by frontend on startup to validate session."""
    return current_admin


@router.post("/admins", response_model=AdminOut, status_code=201)
async def create_admin(
    payload: AdminCreate,
    current_admin: Admin = Depends(require_role(UserRole.super_admin)),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Admin).where(Admin.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    admin = Admin(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


@router.post("/change-password", status_code=200)
async def change_password(
    payload: dict,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    current_pw = payload.get("current_password", "")
    new_pw = payload.get("new_password", "")

    if not verify_password(current_pw, current_admin.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(new_pw) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    current_admin.hashed_password = hash_password(new_pw)
    await db.commit()
    return {"message": "Password changed successfully"}
