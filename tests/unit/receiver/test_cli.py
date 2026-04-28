"""cli.main: bootstraps adapters, builds the receiver FastAPI app, hands to uvicorn."""

from __future__ import annotations

from typing import Any

import pytest

from grabatus_service_core.receiver.cli import main
from grabatus_service_core.testing import InMemoryJobDispatcher, NullObservability


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "shared-receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.setenv("GBT_SERVICE_REGISTRY", "forecast:fc")
    monkeypatch.setenv("GBT_GCP_PROJECT", "grabatus")
    monkeypatch.setenv("GBT_GCP_REGION", "us-east1")
    monkeypatch.setenv("GBT_BUCKET_PREFIX", "gbt-storage")


def test_main_reads_settings_and_runs_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("PORT", "8080")

    captured: dict[str, Any] = {}

    def _fake_run(app: Any, *, host: str, port: int) -> None:
        captured["app"] = app
        captured["host"] = host
        captured["port"] = port

    # Stub the heavy adapters so we don't hit GCP.
    monkeypatch.setattr(
        "grabatus_service_core.receiver.cli.CloudRunJobsDispatcher",
        lambda **kwargs: InMemoryJobDispatcher(),
    )
    monkeypatch.setattr(
        "grabatus_service_core.receiver.cli.setup_opentelemetry",
        lambda **kwargs: type("_Handle", (), {"tracer": object(), "meter": object()})(),
    )
    monkeypatch.setattr(
        "grabatus_service_core.receiver.cli.OpenTelemetryObservability",
        lambda **kwargs: NullObservability(),
    )
    monkeypatch.setattr("uvicorn.run", _fake_run)

    main()

    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 8080
    assert captured["app"].title == "grabatus-service-core"


def test_main_defaults_port_to_8080_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("PORT", raising=False)

    captured: dict[str, Any] = {}

    def _fake_run(app: Any, *, host: str, port: int) -> None:
        captured["port"] = port

    monkeypatch.setattr(
        "grabatus_service_core.receiver.cli.CloudRunJobsDispatcher",
        lambda **kwargs: InMemoryJobDispatcher(),
    )
    monkeypatch.setattr(
        "grabatus_service_core.receiver.cli.setup_opentelemetry",
        lambda **kwargs: type("_Handle", (), {"tracer": object(), "meter": object()})(),
    )
    monkeypatch.setattr(
        "grabatus_service_core.receiver.cli.OpenTelemetryObservability",
        lambda **kwargs: NullObservability(),
    )
    monkeypatch.setattr("uvicorn.run", _fake_run)

    main()

    assert captured["port"] == 8080


def test_main_raises_when_gcp_project_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "shared-receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.setenv("GBT_SERVICE_REGISTRY", "forecast:fc")
    monkeypatch.delenv("GBT_GCP_PROJECT", raising=False)

    with pytest.raises(ValueError, match=r"GBT_GCP_PROJECT"):
        main()
