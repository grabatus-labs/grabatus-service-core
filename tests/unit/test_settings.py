"""Tests for the Settings (pydantic-settings) model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.receiver.registry import ServiceRegistry
from grabatus_service_core.settings import RuntimeMode, Settings


def test_settings_required_fields_raise_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("GBT_RUNTIME_MODE", "GBT_ENV", "SERVICE_SECRET_KEY"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "shhh")

    settings = Settings()

    assert settings.runtime_mode is RuntimeMode.MONOLITH
    assert settings.env == "local"
    assert settings.service_secret_key.get_secret_value() == "shhh"


def test_settings_default_timeouts_match_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "x")

    settings = Settings()

    assert settings.request_timeout_seconds == 540
    assert settings.http_timeout_seconds == 30
    assert settings.webhook_timeout_seconds == 15
    assert settings.compute_timeout_seconds == 480


def test_settings_default_allowed_schemes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "x")

    settings = Settings()

    assert settings.allowed_schemes == frozenset({"gs", "bigquery", "secret"})


def test_settings_parses_csv_env_into_frozenset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "production")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "x")
    monkeypatch.setenv("GBT_ALLOWED_SCHEMES", "gs,https")

    settings = Settings()

    assert settings.allowed_schemes == frozenset({"gs", "https"})


def test_settings_rejects_invalid_runtime_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "fancy")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "x")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_trace_sample_rate_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "x")
    monkeypatch.setenv("GBT_TRACE_SAMPLE_RATE", "1.5")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_parses_service_registry_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.setenv("GBT_SERVICE_REGISTRY", "forecast:fc-worker,abtest:ab-worker")

    settings = Settings()

    assert settings.service_registry.resolve("forecast") == "fc-worker"
    assert settings.service_registry.resolve("abtest") == "ab-worker"


def test_settings_default_service_registry_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.delenv("GBT_SERVICE_REGISTRY", raising=False)

    settings = Settings()

    assert settings.service_registry.by_name == {}


def test_settings_rejects_malformed_registry_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.setenv("GBT_SERVICE_REGISTRY", "not-a-pair")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_accepts_already_constructed_service_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validator mode='before': programmatic construction passes through unchanged."""
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.delenv("GBT_SERVICE_REGISTRY", raising=False)

    settings = Settings(service_registry=ServiceRegistry(by_name={"x": "y"}))
    assert settings.service_registry.resolve("x") == "y"


def test_settings_reads_gcp_project_and_region(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "shared-receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.setenv("GBT_GCP_PROJECT", "grabatus")
    monkeypatch.setenv("GBT_GCP_REGION", "us-east1")
    monkeypatch.setenv("GBT_BUCKET_PREFIX", "gbt-storage")

    settings = Settings()

    assert settings.gcp_project == "grabatus"
    assert settings.gcp_region == "us-east1"
    assert settings.bucket_prefix == "gbt-storage"


def test_settings_default_gcp_project_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.delenv("GBT_GCP_PROJECT", raising=False)

    settings = Settings()

    assert settings.gcp_project is None
    assert settings.gcp_region == "us-east1"  # default
    assert settings.bucket_prefix == "gbt-storage"  # default
