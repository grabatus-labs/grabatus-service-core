"""make_opaque_contract: factory used by downstream service tests."""

from __future__ import annotations

from grabatus_service_core.receiver.registry import ServiceRegistry
from grabatus_service_core.testing import (
    InMemoryServiceRegistry,
    make_opaque_contract,
)


def test_make_opaque_contract_default_is_a_valid_contract() -> None:
    contract = make_opaque_contract()
    assert contract.service.name == "sample"  # default from make_service_descriptor
    # parameters default to an empty mapping
    assert contract.parameters.model_dump() == {}


def test_make_opaque_contract_accepts_parameters_dict() -> None:
    contract = make_opaque_contract(parameters={"x": 1})
    assert contract.parameters.model_dump() == {"x": 1}


def test_make_opaque_contract_accepts_service_name_override() -> None:
    contract = make_opaque_contract(service_name="forecast")
    assert contract.service.name == "forecast"


def test_make_opaque_contract_accepts_both_parameters_and_service_name() -> None:
    contract = make_opaque_contract(parameters={"x": 1}, service_name="abtest")
    assert contract.service.name == "abtest"
    assert contract.parameters.model_dump() == {"x": 1}


def test_in_memory_service_registry_is_alias_for_service_registry() -> None:
    assert InMemoryServiceRegistry is ServiceRegistry


def test_in_memory_service_registry_round_trips() -> None:
    registry = InMemoryServiceRegistry(by_name={"forecast": "fc"})
    assert registry.resolve("forecast") == "fc"
