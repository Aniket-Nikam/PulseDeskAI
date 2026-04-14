"""
PulseDesk Backend — FastAPI Application Entry Point
"""
import os
from contextlib import asynccontextmanager

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

setup_logging()
log = get_logger("main")

# Ensure screenshot directory exists
os.makedirs(settings.SCREENSHOT_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("pulsedesk_starting", version="5.0.0")
    await check_db_connection()
    await ensure_schema_ready()
    log.info("database_ready")
    yield
    log.info("pulsedesk_shutdown")


app = FastAPI(
    title="PulseDesk API",
    description="Employee Activity Monitoring System",
    version="5.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

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
    log.warning(
        "service_error",
        path=str(request.url.path),
        status=exc.status_code,
        detail=exc.detail,
        **exc.context,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": [
                {"field": ".".join(str(loc_part) for loc_part in e["loc"]), "message": e["msg"]}
                for e in exc.errors()
            ],
        },
    )


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    log.error("unhandled_exception", path=str(request.url.path), error_type=type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "5.0.0"}
