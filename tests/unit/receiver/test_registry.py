"""Verify ServiceRegistry resolution + frozenness + parsing."""

import pytest

from grabatus_service_core.errors import UnknownServiceError
from grabatus_service_core.receiver.registry import ServiceRegistry


def test_resolve_returns_worker_job_name_for_known_service() -> None:
    registry = ServiceRegistry(by_name={"forecast": "grabatus-forecasting-worker"})
    assert registry.resolve("forecast") == "grabatus-forecasting-worker"


def test_resolve_raises_unknown_service_error_for_missing_name() -> None:
    registry = ServiceRegistry(by_name={"forecast": "fc-worker"})
    with pytest.raises(UnknownServiceError) as exc_info:
        registry.resolve("ghost")
    assert "ghost" in str(exc_info.value)
    assert "forecast" in str(exc_info.value)  # known services listed for diagnostics


def test_resolve_on_empty_registry_raises_unknown_service_error() -> None:
    registry = ServiceRegistry(by_name={})
    with pytest.raises(UnknownServiceError):
        registry.resolve("anything")


def test_registry_resolves_one_of_multiple_services() -> None:
    registry = ServiceRegistry(
        by_name={
            "forecast": "fc-worker",
            "abtest": "ab-worker",
            "optimize": "opt-worker",
        },
    )
    assert registry.resolve("abtest") == "ab-worker"


def test_from_env_string_single_entry() -> None:
    registry = ServiceRegistry.from_env_string("forecast:fc-worker")
    assert registry.resolve("forecast") == "fc-worker"


def test_from_env_string_multiple_entries() -> None:
    registry = ServiceRegistry.from_env_string("forecast:fc-worker,abtest:ab-worker")
    assert registry.resolve("forecast") == "fc-worker"
    assert registry.resolve("abtest") == "ab-worker"


def test_from_env_string_strips_whitespace() -> None:
    registry = ServiceRegistry.from_env_string(" forecast : fc-worker , abtest : ab-worker ")
    assert registry.resolve("forecast") == "fc-worker"
    assert registry.resolve("abtest") == "ab-worker"


def test_from_env_string_empty_string_yields_empty_registry() -> None:
    registry = ServiceRegistry.from_env_string("")
    assert registry.by_name == {}


def test_from_env_string_rejects_entry_without_colon() -> None:
    with pytest.raises(ValueError, match=r"expected 'name:worker'"):
        ServiceRegistry.from_env_string("forecast")


def test_from_env_string_rejects_duplicate_service_name() -> None:
    with pytest.raises(ValueError, match=r"duplicate service name"):
        ServiceRegistry.from_env_string("forecast:fc1,forecast:fc2")


def test_from_env_string_rejects_empty_worker_name() -> None:
    with pytest.raises(ValueError, match=r"empty"):
        ServiceRegistry.from_env_string("forecast:")


def test_registry_by_name_is_immutable() -> None:
    """Mutating the source dict after construction must not affect the registry."""
    source = {"forecast": "fc-worker"}
    registry = ServiceRegistry(by_name=source)
    source["forecast"] = "tampered"
    assert registry.resolve("forecast") == "fc-worker"


def test_registry_dataclass_is_frozen() -> None:
    registry = ServiceRegistry(by_name={"forecast": "fc-worker"})
    with pytest.raises((AttributeError, TypeError)):
        registry.by_name = {}  # type: ignore[misc]
