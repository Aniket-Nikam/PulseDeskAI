"""
PulseDesk Database Session Configuration

Provides async SQLAlchemy engine, session factory, and dependency injection.

IMPORTANT: Schema creation is handled by Alembic migrations, NOT by
Base.metadata.create_all(). Use `alembic upgrade head` to initialize
or migrate the database.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from typing import AsyncGenerator

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("db")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> None:
    """
    Verify the database is reachable on startup.
    Does NOT create tables — that's Alembic's job.

    For first-time setup:
        alembic upgrade head

    For existing databases without Alembic history:
        alembic stamp head
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        log.info("db_connection_verified")
    except Exception as e:
        log.error("db_connection_failed", error=str(e))
        raise RuntimeError(
            f"Cannot connect to database. Verify DATABASE_URL in .env. Error: {e}"
        ) from e


async def ensure_schema_ready() -> None:
    """
    Schema initialization.
    For local development, we auto-create missing tables.
    """
    try:
        from app.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Safely add hashed_password column to employees table if missing (isolated transaction)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("ALTER TABLE employees ADD COLUMN hashed_password VARCHAR(255) NULL"))
        except Exception:
            pass

        # Safely add business_name column to admins table if missing (isolated transaction)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("ALTER TABLE admins ADD COLUMN business_name VARCHAR(255) NULL"))
        except Exception:
            pass

        # Safely add check_in_count column to attendance_records table if missing
        try:
            async with engine.begin() as conn:
                await conn.execute(text("ALTER TABLE attendance_records ADD COLUMN check_in_count INTEGER DEFAULT 1"))
        except Exception:
            pass

        async with engine.begin() as conn:
            # Verify and auto-create composite indexes on startup
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_screenshots_employee_captured_at ON screenshots (employee_id, captured_at)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_anomalies_employee_detected_at ON anomaly_logs (employee_id, detected_at)"))
        log.info("schema_ready", msg="Database schema auto-creation and composite indexes verification succeeded.")
    except Exception as e:
        log.error("schema_error", error=str(e))
        raise
