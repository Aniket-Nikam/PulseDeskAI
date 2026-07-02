import warnings
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import secrets
import hmac
import uuid

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("security")

# Suppress passlib's bcrypt version warning (cosmetic only, not a real error)
warnings.filterwarnings("ignore", ".*error reading bcrypt version.*")
warnings.filterwarnings("ignore", ".*trapped.*")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _prehash(password: str) -> str:
    """Pre-hash password with SHA-256 to avoid bcrypt's 72-byte limit.
    
    bcrypt 5.0+ raises ValueError for passwords > 72 bytes instead of
    silently truncating. Pre-hashing with SHA-256 produces a fixed 44-byte
    base64 string, always under the limit. This is the same approach used
    by Django and other major frameworks.
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def hash_password(password: str) -> str:
    return pwd_context.hash(_prehash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(_prehash(plain_password), hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update(
        {
            "exp": expire,
            "iat": now,
            "nbf": now,
            "jti": str(uuid.uuid4()),
            "iss": settings.TOKEN_ISSUER,
            "aud": settings.TOKEN_AUDIENCE,
            "type": "access",
        }
    )
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update(
        {
            "exp": expire,
            "iat": now,
            "nbf": now,
            "jti": str(uuid.uuid4()),
            "iss": settings.TOKEN_ISSUER,
            "aud": settings.TOKEN_AUDIENCE,
            "type": "refresh",
        }
    )
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        audience=settings.TOKEN_AUDIENCE,
        issuer=settings.TOKEN_ISSUER,
    )


def generate_device_token(device_id: str, employee_id: str) -> str:
    """Generate a stable HMAC device token for agent authentication."""
    payload = f"{device_id}:{employee_id}"
    return hmac.new(
        settings.DEVICE_TOKEN_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def hash_device_token(device_token: str) -> str:
    """Hash a raw device token before database storage."""
    return hashlib.sha256(f"pulsedesk-device-token:{device_token}".encode("utf-8")).hexdigest()


def device_token_lookup_values(device_token: str) -> list[str]:
    """
    Return lookup candidates for hashed-token storage with legacy fallback.

    New devices store only hash_device_token(raw_token). Older installations may
    still have plaintext token rows; keeping this fallback avoids forcing every
    deployed agent to re-enroll immediately.
    """
    token = (device_token or "").strip()
    if not token:
        return []
    hashed = hash_device_token(token)
    return [hashed] if hashed == token else [hashed, token]


def generate_enrollment_code() -> str:
    """Short human-readable enrollment code shown on device."""
    return secrets.token_hex(3).upper()


def generate_one_time_token(num_bytes: int = 24) -> str:
    return secrets.token_urlsafe(num_bytes)


def is_private_or_local_origin(origin: str) -> bool:
    """Check if the origin refers to localhost or a private LAN IP address."""
    if not origin:
        return False
    origin = origin.strip().rstrip("/")
    try:
        from urllib.parse import urlparse
        import re
        parsed = urlparse(origin)
        hostname = parsed.hostname
        if not hostname:
            if "://" not in origin:
                parsed = urlparse("http://" + origin)
                hostname = parsed.hostname
            if not hostname:
                return False
        
        hostname = hostname.lower()
        if hostname == "localhost" or hostname == "127.0.0.1" or hostname == "::1":
            return True
        
        # Check common developer tunnel hostnames
        if settings.ALLOW_INSECURE_DEFAULTS and (
            hostname.endswith(".localtunnel.me")
            or hostname.endswith(".ngrok.io")
            or hostname.endswith(".ngrok-free.app")
            or hostname.endswith(".trycloudflare.com")
        ):
            return True

        # Check private IP ranges
        if re.match(r"^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$", hostname):
            return True
        if re.match(r"^192\.168\.\d{1,3}\.\d{1,3}$", hostname):
            return True
        match = re.match(r"^172\.(\d{1,3})\.\d{1,3}\.\d{1,3}$", hostname)
        if match:
            second_octet = int(match.group(1))
            if 16 <= second_octet <= 31:
                return True
                
        if hostname.endswith(".local"):
            return True
    except Exception:
        pass
    return False


async def check_admin_can_view_employee(
    admin_id: uuid.UUID,
    admin_role: str,
    employee_id: uuid.UUID,
    db,
) -> bool:
    """
    Production-grade privacy control: Verify admin can access employee data.
    
    Access rules:
    - super_admin: Can view all employees
    - admin: Can view all employees (organization-level)
    - manager: Can view only employees in the same department (future: assigned dept)
    
    Args:
        admin_id: The admin's UUID
        admin_role: The admin's role (super_admin, admin, manager)
        employee_id: The employee whose data is being requested
        db: Database session
        
    Returns:
        True if access is allowed, False otherwise
    """
    from app.models import UserRole
    
    # Super admin can access everything
    if admin_role == UserRole.super_admin.value:
        log.debug("access_allowed", admin_id=str(admin_id), employee_id=str(employee_id), reason="super_admin")
        return True
    
    # Organization admins can access all employees
    if admin_role == UserRole.admin.value:
        log.debug("access_allowed", admin_id=str(admin_id), employee_id=str(employee_id), reason="org_admin")
        return True
    
    # Managers can only access employees in their department
    if admin_role == UserRole.manager.value:
        from sqlalchemy import select
        from app.models import Employee
        
        # Get employee's department
        result = await db.execute(select(Employee).where(Employee.id == employee_id))
        employee = result.scalar_one_or_none()
        
        if not employee:
            log.warning("access_denied", admin_id=str(admin_id), employee_id=str(employee_id), reason="employee_not_found")
            return False
        
        # TODO: When manager's department is stored in Admin table, add:
        # result_admin = await db.execute(select(Admin).where(Admin.id == admin_id))
        # admin = result_admin.scalar_one_or_none()
        # if admin.managed_department_id == employee.department_id:
        #     return True
        
        # For now: all managers can access all employees (change when dept assignment is added)
        log.debug("access_allowed", admin_id=str(admin_id), employee_id=str(employee_id), reason="manager_access")
        return True
    
    log.warning("access_denied", admin_id=str(admin_id), employee_id=str(employee_id), reason="unknown_role", role=admin_role)
    return False

