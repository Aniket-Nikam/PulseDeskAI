"""
PulseDesk Backend — FastAPI Application Entry Point
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.db.session import init_db
from app.api.v1 import api_router

setup_logging()
log = get_logger("main")

# Ensure screenshot directory exists
os.makedirs(settings.SCREENSHOT_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("pulsedesk_starting")
    await init_db()
    log.info("database_ready")
    yield
    log.info("pulsedesk_shutdown")


app = FastAPI(
    title="PulseDesk API",
    description="Employee Activity Monitoring System",
    version="4.0.0",
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
    allow_methods=["*"],
    allow_headers=["*"],
)

# All API routes under /api/v1
app.include_router(api_router, prefix="/api/v1")

# Join portal served at root /join (no /api/v1 prefix so employees can access it easily)
from app.api.v1.routes.join_portal import router as join_portal_router
app.include_router(join_portal_router)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": [
                {"field": ".".join(str(l) for l in e["loc"]), "message": e["msg"]}
                for e in exc.errors()
            ],
        },
    )


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    log.error("unhandled_exception", path=str(request.url), error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "4.0.0"}
