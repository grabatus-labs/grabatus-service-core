"""Tests for the Settings (pydantic-settings) model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

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
