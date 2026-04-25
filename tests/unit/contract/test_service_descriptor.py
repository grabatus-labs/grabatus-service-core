"""Tests for the ServiceDescriptor schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.service_descriptor import ServiceDescriptor


def test_service_descriptor_accepts_valid_name_and_semver() -> None:
    desc = ServiceDescriptor.model_validate({"name": "forecast", "version": "1.2.0"})

    assert desc.name == "forecast"
    assert desc.version == "1.2.0"


@pytest.mark.parametrize(
    "name",
    ["Forecast", "forecast service", "forecast.v1", "forecast/v1", ""],
)
def test_service_descriptor_rejects_invalid_names(name: str) -> None:
    with pytest.raises(ValidationError, match="name"):
        ServiceDescriptor.model_validate({"name": name, "version": "1.0.0"})


@pytest.mark.parametrize(
    "name",
    ["forecast", "ab-test", "linear_optimization", "bayesian-mcmc-v2"],
)
def test_service_descriptor_accepts_valid_slugs(name: str) -> None:
    desc = ServiceDescriptor.model_validate({"name": name, "version": "1.0.0"})

    assert desc.name == name


@pytest.mark.parametrize(
    "version",
    ["1", "1.0", "v1.0.0", "1.0.0-alpha", "1.0.0+sha", "1.0.0.0"],
)
def test_service_descriptor_rejects_non_semver(version: str) -> None:
    with pytest.raises(ValidationError, match="version"):
        ServiceDescriptor.model_validate({"name": "forecast", "version": version})


@pytest.mark.parametrize("version", ["0.0.1", "1.0.0", "10.20.30"])
def test_service_descriptor_accepts_valid_semver(version: str) -> None:
    desc = ServiceDescriptor.model_validate({"name": "forecast", "version": version})

    assert desc.version == version


def test_service_descriptor_is_frozen() -> None:
    desc = ServiceDescriptor.model_validate({"name": "forecast", "version": "1.0.0"})

    with pytest.raises(ValidationError, match="frozen"):
        desc.name = "other"  # type: ignore[misc]
