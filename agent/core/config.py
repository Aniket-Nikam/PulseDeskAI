import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AgentConfig:
    server_url: str
    employee_email: str
    sample_interval: int
    batch_interval: int
    heartbeat_interval: int
    idle_threshold: int
    screenshot_enabled: bool
    offline_db_path: str
    log_level: str

    @classmethod
    def from_env(cls) -> "AgentConfig":
        def safe_int(key: str, default: int) -> int:
            try:
                return int(os.getenv(key, str(default)))
            except ValueError:
                return default

        server_url = os.getenv("SERVER_URL", "").strip().rstrip("/")
        if not server_url and os.getenv("ALLOW_LOCALHOST_DEFAULT", "false").lower() == "true":
            server_url = "http://localhost:8000"
            
        return cls(
            server_url=server_url,
            employee_email=os.getenv("EMPLOYEE_EMAIL", ""),
            sample_interval=safe_int("SAMPLE_INTERVAL_SECONDS", 30),
            batch_interval=safe_int("BATCH_INTERVAL_SECONDS", 30),
            heartbeat_interval=safe_int("HEARTBEAT_INTERVAL_SECONDS", 60),
            idle_threshold=safe_int("IDLE_THRESHOLD_SECONDS", 300),
            screenshot_enabled=os.getenv("SCREENSHOT_ENABLED", "false").lower() == "true",
            offline_db_path=os.getenv("OFFLINE_DB_PATH", "./pulsedesk_queue.db"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


config = AgentConfig.from_env()
