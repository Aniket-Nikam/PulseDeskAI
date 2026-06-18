import json
import os
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_current_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.dirname(os.path.dirname(_current_dir))
_env_file_path = os.path.join(_backend_dir, ".env")


class Settings(BaseSettings):
    APP_NAME: str = "PulseDesk"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ALLOW_ADMIN_CLI_RESET: bool = False

    DATABASE_URL: str
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    FRONTEND_URL: str = ""
    TOKEN_ISSUER: str = "pulsedesk"
    TOKEN_AUDIENCE: str = "pulsedesk-admin"
    ALGORITHM: str = "HS256"
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    DEVICE_TOKEN_SECRET: str = ""
    ALLOW_INSECURE_DEFAULTS: bool = True
    ACCESS_COOKIE_NAME: str = "pulsedesk_access"
    REFRESH_COOKIE_NAME: str = "pulsedesk_refresh"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"  # lax | strict | none
    COOKIE_DOMAIN: str = ""
    COOKIE_PATH: str = "/"

    # AI
    AI_ENABLED: bool = True
    GROQ_API_KEY: str = ""
    GROQ_PRIMARY_MODEL: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_VISION_MODEL: str = "llama-4-scout-17b-16e-instruct"
    AI_REQUEST_TIMEOUT_SECONDS: int = 20
    AI_SCREENSHOT_ANALYSIS_ENABLED: bool = False

    # Screenshots
    SCREENSHOT_DIR: str = "./screenshots"
    SCREENSHOT_MAX_SIZE_KB: int = 200
    SCREENSHOT_QUERY_TOKEN_ENABLED: bool = True

    # Agent request integrity
    AGENT_SIGNATURE_REQUIRED: bool = True
    AGENT_SIGNATURE_TOLERANCE_SECONDS: int = 300
    AGENT_SIGNATURE_REPLAY_CACHE_SECONDS: int = 600

    # Logging
    LOG_LEVEL: str = "INFO"

    # CORS / trusted hosts
    CORS_ORIGINS: str = '["http://localhost:5173","http://localhost:3000"]'
    CORS_ALLOW_METHODS: str = '["GET","POST","PATCH","PUT","DELETE","OPTIONS"]'
    CORS_ALLOW_HEADERS: str = '["Authorization","Content-Type","Accept"]'
    TRUSTED_HOSTS: str = '["localhost","127.0.0.1"]'

    # Other settings
    HEARTBEAT_TIMEOUT_SECONDS: int = 120
    IDLE_THRESHOLD_SECONDS: int = 300
    BATCH_SIZE_LIMIT: int = 200
    RATE_LIMIT_PER_MINUTE: int = 120
    AUTH_LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    AUTH_REFRESH_RATE_LIMIT_PER_MINUTE: int = 30
    ENROLLMENT_RATE_LIMIT_PER_MINUTE: int = 20
    JOIN_VERIFY_RATE_LIMIT_PER_MINUTE: int = 12
    JOIN_DOWNLOAD_RATE_LIMIT_PER_MINUTE: int = 15
    AGENT_UPLOAD_RATE_LIMIT_PER_MINUTE: int = 120
    ENROLLMENT_LINK_TTL_HOURS: int = 24
    JOIN_CODE_TTL_HOURS: int = 48
    JOIN_DOWNLOAD_TOKEN_TTL_MINUTES: int = 20

    model_config = SettingsConfigDict(
        env_file=_env_file_path,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @staticmethod
    def _parse_json_list(raw: Any, fallback: list[str]) -> list[str]:
        try:
            if isinstance(raw, str):
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, list) else fallback
            if isinstance(raw, list):
                return raw
        except (json.JSONDecodeError, TypeError):
            pass
        return fallback

    @field_validator(
        "DEBUG",
        "AI_ENABLED",
        "AI_SCREENSHOT_ANALYSIS_ENABLED",
        "ALLOW_INSECURE_DEFAULTS",
        "COOKIE_SECURE",
        "SCREENSHOT_QUERY_TOKEN_ENABLED",
        "AGENT_SIGNATURE_REQUIRED",
        "ALLOW_ADMIN_CLI_RESET",
        mode="before",
    )
    @classmethod
    def parse_bool_flags(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = value.strip().lower()
            truthy = {"1", "true", "yes", "on", "dev", "development", "debug"}
            falsy = {"0", "false", "no", "off", "prod", "production", "release"}
            if normalized in truthy:
                return True
            if normalized in falsy:
                return False
        return value

    @field_validator("SECRET_KEY", "DEVICE_TOKEN_SECRET", mode="after")
    @classmethod
    def validate_sensitive_secret(cls, value: str, info):
        secret = (value or "").strip()
        if len(secret) < 32:
            raise ValueError(f"{info.field_name} must be at least 32 characters")
        lowered = secret.lower()
        if "change-this" in lowered or "changeme" in lowered or "replace-with" in lowered:
            raise ValueError(f"{info.field_name} must not use default placeholder values")
        return secret

    @field_validator("COOKIE_SAMESITE", mode="after")
    @classmethod
    def validate_cookie_samesite(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("COOKIE_SAMESITE must be one of: lax, strict, none")
        return normalized

    @field_validator("GROQ_MODEL", mode="after")
    @classmethod
    def resolve_groq_model(cls, value: str, info) -> str:
        primary = (info.data.get("GROQ_PRIMARY_MODEL") or "").strip()
        return primary or value

    @property
    def cors_origins_list(self) -> list[str]:
        origins = self._parse_json_list(self.CORS_ORIGINS, ["http://localhost:5173"])
        if "*" in origins:
            raise ValueError("CORS_ORIGINS must not contain '*' when credentials are enabled")
        return origins

    @property
    def cors_allow_methods_list(self) -> list[str]:
        return self._parse_json_list(self.CORS_ALLOW_METHODS, ["GET", "POST", "PATCH", "DELETE", "OPTIONS"])

    @property
    def cors_allow_headers_list(self) -> list[str]:
        return self._parse_json_list(self.CORS_ALLOW_HEADERS, ["Authorization", "Content-Type", "Accept"])

    @property
    def trusted_hosts_list(self) -> list[str]:
        hosts = self._parse_json_list(self.TRUSTED_HOSTS, ["localhost", "127.0.0.1"])
        if "*" in hosts and not self.ALLOW_INSECURE_DEFAULTS:
            raise ValueError("TRUSTED_HOSTS must not contain '*' unless ALLOW_INSECURE_DEFAULTS is true")
        return hosts

    @property
    def csrf_origin_allowlist(self) -> list[str]:
        return [origin.rstrip("/") for origin in self.cors_origins_list]

    @property
    def require_origin_check_for_cookie_auth(self) -> bool:
        return True

    @property
    def cookie_security_valid(self) -> bool:
        if self.COOKIE_SAMESITE == "none" and not self.COOKIE_SECURE:
            raise ValueError("COOKIE_SECURE must be true when COOKIE_SAMESITE is 'none'")
        if not self.COOKIE_SECURE and not (self.DEBUG or self.ALLOW_INSECURE_DEFAULTS):
            raise ValueError("COOKIE_SECURE must be true unless DEBUG or ALLOW_INSECURE_DEFAULTS is enabled")
        return True



settings = Settings()
