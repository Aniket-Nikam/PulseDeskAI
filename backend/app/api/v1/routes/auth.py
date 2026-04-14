from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
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
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.core.audit import log_admin_action
from jose import JWTError

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)
log = get_logger("auth")


def _set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
) -> None:
    cookie_domain = settings.COOKIE_DOMAIN or None
    from typing import Literal, cast
    samesite_str = settings.COOKIE_SAMESITE
    samesite = cast(Literal["lax", "strict", "none"] | None, samesite_str if samesite_str in ("lax", "strict", "none") else None)

    response.set_cookie(
        key=settings.ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite=samesite,
        domain=cookie_domain,
        path=settings.COOKIE_PATH,
        max_age=int(settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60),
    )
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite=samesite,
        domain=cookie_domain,
        path=settings.COOKIE_PATH,
        max_age=int(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600),
    )


def _clear_auth_cookies(response: Response) -> None:
    cookie_domain = settings.COOKIE_DOMAIN or None
    from typing import Literal, cast
    samesite_str = settings.COOKIE_SAMESITE
    samesite = cast(Literal["lax", "strict", "none"] | None, samesite_str if samesite_str in ("lax", "strict", "none") else None)
    response.delete_cookie(
        key=settings.ACCESS_COOKIE_NAME,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite=samesite,
        domain=cookie_domain,
        path=settings.COOKIE_PATH,
    )
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite=samesite,
        domain=cookie_domain,
        path=settings.COOKIE_PATH,
    )


def _token_from_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    *,
    cookie_name: str,
) -> str | None:
    if credentials and credentials.credentials:
        return credentials.credentials
    cookie_token = request.cookies.get(cookie_name)
    return cookie_token or None


async def get_current_admin(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: AsyncSession = Depends(get_db),
) -> Admin:
    token = _token_from_request(request, credentials, cookie_name=settings.ACCESS_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        admin_id = payload.get("sub")
        if not admin_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Token expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(Admin).where(Admin.id == admin_id, Admin.is_active)
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


require_admin_read = require_role(UserRole.super_admin, UserRole.admin, UserRole.manager)
require_admin_write = require_role(UserRole.super_admin, UserRole.admin)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: AdminLogin,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    enforce_rate_limit(
        request,
        key_prefix="auth_login",
        limit=settings.AUTH_LOGIN_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
    )

    email = payload.email.strip().lower()
    result = await db.execute(select(Admin).where(Admin.email == email))
    admin = result.scalar_one_or_none()

    if not admin or not verify_password(payload.password, admin.hashed_password):
        log.warning("failed_login", email=email)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not admin.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated")

    admin.last_login = datetime.now(timezone.utc)
    await db.commit()

    role = admin.role.value if hasattr(admin.role, "value") else str(admin.role)
    token_data = {"sub": str(admin.id), "role": role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    _set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)

    log.info("admin_logged_in", admin_id=str(admin.id))
    log_admin_action("auth_login", admin_id=str(admin.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        admin_id=admin.id,
        full_name=admin.full_name,
        role=admin.role,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    payload: RefreshTokenRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    enforce_rate_limit(
        request,
        key_prefix="auth_refresh",
        limit=settings.AUTH_REFRESH_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        include_auth_fingerprint=True,
    )

    incoming_refresh = payload.refresh_token if payload else ""
    refresh_token_value = incoming_refresh or request.cookies.get(settings.REFRESH_COOKIE_NAME, "")
    if not refresh_token_value:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    try:
        data = decode_token(refresh_token_value)
        if data.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except JWTError:
        raise HTTPException(status_code=401, detail="Refresh token expired or invalid")

    admin_id = data.get("sub")
    result = await db.execute(
        select(Admin).where(Admin.id == admin_id, Admin.is_active)
    )
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=401, detail="Admin not found")

    role = admin.role.value if hasattr(admin.role, "value") else str(admin.role)
    token_data = {"sub": str(admin.id), "role": role}
    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)
    _set_auth_cookies(response, access_token=new_access_token, refresh_token=new_refresh_token)
    log.info("token_refreshed", admin_id=str(admin.id))

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        admin_id=admin.id,
        full_name=admin.full_name,
        role=admin.role,
    )


@router.post("/logout", status_code=200)
async def logout(request: Request, response: Response):
    admin_id = "unknown"
    access_cookie = request.cookies.get(settings.ACCESS_COOKIE_NAME, "")
    if access_cookie:
        try:
            payload = decode_token(access_cookie)
            admin_id = str(payload.get("sub") or "unknown")
        except JWTError:
            admin_id = "unknown"
    _clear_auth_cookies(response)
    log_admin_action("auth_logout", admin_id=admin_id)
    return {"message": "Logged out"}


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
    log_admin_action(
        "admin_created",
        admin_id=str(current_admin.id),
        created_admin_id=str(admin.id),
        created_admin_role=str(admin.role.value if hasattr(admin.role, "value") else admin.role),
    )
    return admin


@router.post("/change-password", status_code=200)
async def change_password(
    payload: ChangePasswordRequest,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    current_pw = payload.current_password
    new_pw = payload.new_password

    if not verify_password(current_pw, current_admin.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if new_pw == current_pw:
        raise HTTPException(status_code=400, detail="New password must be different from current password")

    current_admin.hashed_password = hash_password(new_pw)
    await db.commit()
    log_admin_action("password_changed", admin_id=str(current_admin.id))
    return {"message": "Password changed successfully"}
