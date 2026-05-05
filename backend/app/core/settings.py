from __future__ import annotations

import json

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IMS_", env_file=".env", extra="ignore")

    env: str = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://ims:ims@localhost:5432/ims"
    redis_url: str = "redis://localhost:6379/0"
    redis_max_retries: int = 5
    redis_retry_base_delay_ms: int = 200
    redis_connect_timeout_seconds: float = 2.0
    # Must be > BRPOP timeout used by workers to avoid read timeouts.
    redis_socket_timeout_seconds: float = 15.0

    # Accept either CSV (recommended) or JSON list string.
    # Example CSV: "http://localhost:5173,http://localhost:3000"
    # Example JSON: '["http://localhost:5173"]'
    cors_origins: str = "http://localhost:5173"

    ingest_rate_limit_per_sec: int = 2000
    signal_queue_max_length: int = 50000
    debounce_window_seconds: int = 10
    metrics_print_interval_seconds: int = 5
    dashboard_cache_ttl_seconds: int = 5
    incident_cache_ttl_seconds: int = 30

    # JSON map, e.g. {"P0":"combined","P1":"slack","P2":"email"}
    alert_strategy_map_json: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        s = self.cors_origins.strip()
        if not s:
            return []
        if s.startswith("["):
            parsed = json.loads(s)
            if not isinstance(parsed, list):
                raise ValueError("IMS_CORS_ORIGINS JSON must be a list")
            return [str(x).strip() for x in parsed if str(x).strip()]
        return [part.strip() for part in s.split(",") if part.strip()]


settings = Settings()

