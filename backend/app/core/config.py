from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
import json


class Settings(BaseSettings):
    APP_NAME: str = "PulseDesk"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    FRONTEND_URL: str = "http://localhost:5173"

    # Groq AI
    GROQ_API_KEY: str = ""
    GROQ_PRIMARY_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_FALLBACK_MODEL: str = "llama-3.1-8b-instant"

    # Screenshots
    SCREENSHOT_DIR: str = "./screenshots"
    SCREENSHOT_MAX_SIZE_KB: int = 200

    # Logging
    LOG_LEVEL: str = "INFO"

    # CORS - store as string
    CORS_ORIGINS: str = '["http://localhost:5173","http://localhost:3000"]'

    # Other settings
    HEARTBEAT_TIMEOUT_SECONDS: int = 120
    IDLE_THRESHOLD_SECONDS: int = 300
    BATCH_SIZE_LIMIT: int = 200
    RATE_LIMIT_PER_MINUTE: int = 120
    ALGORITHM: str = "HS256"
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    DEVICE_TOKEN_SECRET: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def cors_origins_list(self):
        """Parse CORS_ORIGINS into a list of strings."""
        try:
            # Handle both string JSON and already-parsed list
            if isinstance(self.CORS_ORIGINS, str):
                return json.loads(self.CORS_ORIGINS)
            elif isinstance(self.CORS_ORIGINS, list):
                return self.CORS_ORIGINS
        except (json.JSONDecodeError, TypeError):
            pass
        # Fallback
        return ["http://localhost:5173"]


settings = Settings()