"""
PulseDesk Backend — FastAPI Application Entry Point

Production-grade features:
- Request tracking with unique IDs for debugging
- Comprehensive error handling with structured responses
- Security headers for XSS, clickjacking, CSRF protection
- CORS with origin validation
- Rate limiting on sensitive endpoints
"""
import os
import uuid
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.exceptions import ServiceError
from app.db.session import check_db_connection, ensure_schema_ready
from app.api.v1 import api_router
from app.api.v1.routes.join_portal import router as join_portal_router
from app.core.security import is_private_or_local_origin

setup_logging()
log = get_logger("main")
_ = settings.cookie_security_valid

# Ensure screenshot directory exists
os.makedirs(settings.SCREENSHOT_DIR, exist_ok=True)


class RequestIdMiddleware:
    """Add unique request ID to each request for tracing and debugging."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request_id = str(uuid.uuid4())
            scope["request_id"] = request_id
            
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.append((b"x-request-id", request_id.encode()))
                    message["headers"] = headers
                await send(message)
            
            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)


def _extract_origin(value: str) -> str:
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    return value.rstrip("/")


def _is_allowed_origin(value: str) -> bool:
    origin = _extract_origin(value)
    if not origin:
        return False
    allowed = set(settings.csrf_origin_allowlist)
    return origin in allowed or is_private_or_local_origin(origin)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("pulsedesk_starting", version="5.0.0")
    await check_db_connection()
    await ensure_schema_ready()
    log.info("database_ready")

    # Seed default blocklist rules on first startup
    from app.db.session import AsyncSessionLocal
    from app.services.blocklist_store import seed_default_rules
    async with AsyncSessionLocal() as db:
        seeded = await seed_default_rules(db)
        if seeded:
            log.info(f"blocklist_defaults_seeded: {seeded} rules")

    # Start break alert checker
    from app.services.break_alert_service import start_break_alert_checker
    start_break_alert_checker()

    # Start screenshot retention cleanup task
    from app.services.screenshot_cleanup_service import start_screenshot_cleanup_task
    start_screenshot_cleanup_task()

    # Start weekly summary scheduler
    from app.services.weekly_summary_service import start_weekly_summary_scheduler
    start_weekly_summary_scheduler()

    # Start in-memory screenshot AI worker task
    from app.services.screenshot_ai import start_screenshot_ai_worker
    import asyncio
    asyncio.create_task(start_screenshot_ai_worker())

    yield
    log.info("pulsedesk_shutdown")


class CacheRequestBodyMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if "/api/v1/agent" in path or "/api/v1/consent" in path or "/api/v1/blocker" in path:
                body = b""
                more_body = True
                while more_body:
                    message = await receive()
                    body += message.get("body", b"")
                    more_body = message.get("more_body", False)

                async def cached_receive():
                    return {"type": "http.request", "body": body, "more_body": False}

                await self.app(scope, cached_receive, send)
                return

        await self.app(scope, receive, send)


app = FastAPI(
    title="PulseDesk API",
    description="Employee Activity Monitoring System (Production-grade)",
    version="5.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Request ID tracking middleware (first for maximum coverage)
app.add_middleware(RequestIdMiddleware)

# Request Caching for agent authentication
app.add_middleware(CacheRequestBodyMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=settings.cors_allow_methods_list,
    allow_headers=settings.cors_allow_headers_list,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.trusted_hosts_list,
)

# All API routes under /api/v1
app.include_router(api_router, prefix="/api/v1")

# Join portal served at root /join (no /api/v1 prefix so employees can access it easily)
app.include_router(join_portal_router)


# ── Exception Handlers ────────────────────────────────────────────────────────

@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    """Translate service-layer errors to structured HTTP responses."""
    request_id = request.scope.get("request_id", "unknown")
    log.warning(
        "service_error",
        request_id=request_id,
        path=str(request.url.path),
        status=exc.status_code,
        detail=exc.detail,
        **exc.context,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "request_id": request_id,
            "status": exc.status_code,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors with detailed field information."""
    request_id = request.scope.get("request_id", "unknown")
    log.info(
        "validation_error",
        request_id=request_id,
        path=str(request.url.path),
        error_count=len(exc.errors()),
    )
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "request_id": request_id,
            "status": 422,
            "errors": [
                {
                    "field": ".".join(str(loc_part) for loc_part in e["loc"]),
                    "message": e["msg"],
                    "type": e["type"],
                }
                for e in exc.errors()
            ],
        },
    )



@app.middleware("http")
async def csrf_guard_middleware(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/v1/"):
        auth_header = request.headers.get("authorization", "").strip()
        has_auth_cookie = bool(
            request.cookies.get(settings.ACCESS_COOKIE_NAME) or request.cookies.get(settings.REFRESH_COOKIE_NAME)
        )
        if settings.require_origin_check_for_cookie_auth and has_auth_cookie and not auth_header:
            origin = request.headers.get("origin") or request.headers.get("referer") or ""
            if not origin or not _is_allowed_origin(origin):
                return JSONResponse(status_code=403, content={"detail": "Cross-site request blocked"})
    return await call_next(request)



@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    # Security headers (production standards)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self), microphone=(), camera=()"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' ws: wss:;"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    # HSTS for HTTPS environments
    if settings.COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    
    return response


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and return safe error responses."""
    request_id = request.scope.get("request_id", "unknown")
    log.error(
        "unhandled_exception",
        request_id=request_id,
        path=str(request.url.path),
        method=request.method,
        error_type=type(exc).__name__,
        error_message=str(exc)[:200],  # Limit message length
        error_detail=repr(exc)[:500],
    )
    # Return generic message to client (don't leak internal errors)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred. Please contact support with the request ID if the problem persists.",
            "request_id": request_id,
            "status": 500,
        },
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "5.0.0"}
