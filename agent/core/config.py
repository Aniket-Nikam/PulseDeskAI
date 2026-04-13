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
        return cls(
            server_url=os.getenv("SERVER_URL", "http://localhost:8000"),
            employee_email=os.getenv("EMPLOYEE_EMAIL", ""),
            sample_interval=int(os.getenv("SAMPLE_INTERVAL_SECONDS", "30")),
            batch_interval=int(os.getenv("BATCH_INTERVAL_SECONDS", "30")),
            heartbeat_interval=int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "60")),
            idle_threshold=int(os.getenv("IDLE_THRESHOLD_SECONDS", "300")),
            screenshot_enabled=os.getenv("SCREENSHOT_ENABLED", "false").lower() == "true",
            offline_db_path=os.getenv("OFFLINE_DB_PATH", "./pulsedesk_queue.db"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


config = AgentConfig.from_env()
