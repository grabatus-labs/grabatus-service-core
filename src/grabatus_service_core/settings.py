"""Library settings (pydantic-settings).

Reads ``GBT_*`` and ``SERVICE_SECRET_KEY`` env vars. Defaults are
secure-by-default; production overrides via Cloud Run env vars or, for
secrets, Secret Manager mounts.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from grabatus_service_core.receiver.registry import ServiceRegistry


class RuntimeMode(StrEnum):
    """Selects the pipeline branch a process executes."""

    RECEIVER = "receiver"
    WORKER = "worker"
    MONOLITH = "monolith"


_DEFAULT_ALLOWED_SCHEMES: frozenset[str] = frozenset({"gs", "bigquery", "secret"})


class Settings(BaseSettings):
    """Process-wide configuration parsed from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="GBT_",
        case_sensitive=False,
        extra="ignore",
    )

    runtime_mode: Annotated[RuntimeMode, Field(alias="GBT_RUNTIME_MODE")]
    env: Annotated[Literal["local", "staging", "production"], Field(alias="GBT_ENV")]
    request_timeout_seconds: int = Field(default=540, ge=1, le=3600)
    http_timeout_seconds: int = Field(default=30, ge=1, le=300)
    webhook_timeout_seconds: int = Field(default=15, ge=1, le=120)
    compute_timeout_seconds: int = Field(default=480, ge=1, le=3600)
    allowed_schemes: Annotated[frozenset[str], NoDecode] = Field(
        default=_DEFAULT_ALLOWED_SCHEMES,
    )
    allowed_hosts: Annotated[frozenset[str], NoDecode] = Field(default=frozenset())
    service_registry: Annotated[ServiceRegistry, NoDecode] = Field(
        default_factory=lambda: ServiceRegistry(by_name={}),
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    trace_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    worker_job_name: str | None = Field(default=None)
    service_secret_key: Annotated[SecretStr, Field(alias="SERVICE_SECRET_KEY")]

    @field_validator("allowed_schemes", "allowed_hosts", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return frozenset(item.strip() for item in value.split(",") if item.strip())
        return value

    @field_validator("service_registry", mode="before")
    @classmethod
    def _parse_service_registry(cls, value: object) -> object:
        if isinstance(value, str):
            return ServiceRegistry.from_env_string(value)
        return value
