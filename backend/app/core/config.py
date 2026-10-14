"""Runtime configuration. Every value comes from environment variables (prefix BCW_),
so the same image runs unchanged in every datacenter."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BCW_", env_file=".env", extra="ignore")

    # Identity of this deployment, stamped on every log line and session update.
    datacenter: str = "local"

    # Session + workflow state. "memory" is for local development and tests only.
    session_store: Literal["memory", "mongo"] = "memory"
    mongodb_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_db: str = "bc_workflows"
    # Sessions and their workflow state are kept for 30 days after the last step.
    session_ttl_seconds: int = 30 * 24 * 60 * 60

    # OBCV integration.
    obcv_mode: Literal["mock"] = "mock"
    obcv_mock_delay_ms: int = 1500
    obcv_wait_timeout_seconds: float = 30.0

    # Link shown on "Follow the standard procedure" screens.
    bc_team_url: str = "https://example.invalid/banker-connection"

    # When true, requests without a bearer token are rejected.
    auth_required: bool = False

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    log_level: str = "INFO"
