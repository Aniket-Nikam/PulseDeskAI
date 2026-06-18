"""Reset an admin password using environment variables.

Required env:
  DATABASE_URL
  RESET_ADMIN_EMAIL
  RESET_ADMIN_PASSWORD
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def reset_password() -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings
    from app.core.security import hash_password

    # Enforce security check - must opt-in via ALLOW_ADMIN_CLI_RESET
    if not settings.ALLOW_ADMIN_CLI_RESET:
        print("[-] Error: CLI admin password reset is disabled.")
        print("    To enable this utility, set ALLOW_ADMIN_CLI_RESET=True in your environment or .env file.")
        sys.exit(1)

    database_url = os.getenv("DATABASE_URL", "").strip()
    admin_email = os.getenv("RESET_ADMIN_EMAIL", "").strip().lower()
    new_password = os.getenv("RESET_ADMIN_PASSWORD", "")

    if not database_url or not admin_email or not new_password:
        raise RuntimeError("DATABASE_URL, RESET_ADMIN_EMAIL, and RESET_ADMIN_PASSWORD are required")
    if len(new_password) < 12:
        raise RuntimeError("RESET_ADMIN_PASSWORD must be at least 12 characters")

    # Interactive prompt (unless explicitly running non-interactively, e.g. in tests/automation)
    non_interactive = os.getenv("RESET_ADMIN_NON_INTERACTIVE", "").strip().lower() in ("true", "1", "yes")
    if not non_interactive and sys.stdin.isatty():
        try:
            confirm = input(f"Are you sure you want to reset the password for '{admin_email}'? Type 'CONFIRM' to proceed: ")
            if confirm.strip() != "CONFIRM":
                print("[-] Password reset cancelled.")
                return
        except KeyboardInterrupt:
            print("\n[-] Password reset cancelled.")
            return

    new_hash = hash_password(new_password)
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        result = await conn.execute(
            text("UPDATE admins SET hashed_password = :pw WHERE email = :email"),
            {"pw": new_hash, "email": admin_email},
        )
        print(f"Updated rows: {result.rowcount}")
        if result.rowcount == 0:
            print("No admin found for the given email.")
        else:
            print(f"[OK] Password reset completed for: {admin_email}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(reset_password())
