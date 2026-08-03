"""The context must hand the backend its own output destinations.

Without them the readout's ``artifacts[].uri`` has no honest source, and
the gate is satisfiable only by a hardcoded constant — the defect issue
#16 describes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from grabatus_service_core.errors import UnknownOutputRoleError
from grabatus_service_core.testing import make_compute_context, make_contract, make_output_spec

if TYPE_CHECKING:
    from grabatus_service_core.ports.compute_context import ComputeContext

_FORECAST_URI = "gs://gbt-storage-grabatus/user_999/forecast.json"
_READOUT_URI = "gs://gbt-storage-grabatus/user_999/readout.json"


class _NoParameters(BaseModel):
    """Stands in for a service's parameter model; the context never reads it."""


def _context_with(*roles_and_uris: tuple[str, str]) -> ComputeContext:
    contract = make_contract(
        parameters=_NoParameters(),
        outputs=[make_output_spec(role=role, destination_uri=uri) for role, uri in roles_and_uris],
    )
    return make_compute_context(contract=contract)


def test_the_backend_reads_its_destination_from_the_contract() -> None:
    context = _context_with(("forecast_json", _FORECAST_URI))

    assert context.artifact_uri("forecast_json") == _FORECAST_URI


def test_every_declared_output_is_reachable() -> None:
    """A service writing two artefacts must be able to describe both."""
    context = _context_with(("forecast_json", _FORECAST_URI), ("model_readout", _READOUT_URI))

    assert context.artifact_uri("model_readout") == _READOUT_URI


def test_an_undeclared_role_fails_instead_of_returning_a_plausible_uri() -> None:
    context = _context_with(("forecast_json", _FORECAST_URI))

    with pytest.raises(UnknownOutputRoleError, match="typo_json"):
        context.artifact_uri("typo_json")


def test_the_failure_names_the_roles_that_do_exist() -> None:
    """Without them the service cannot tell a typo from a missing output."""
    context = _context_with(("forecast_json", _FORECAST_URI))

    with pytest.raises(UnknownOutputRoleError, match="forecast_json"):
        context.artifact_uri("typo_json")


def test_the_destinations_cannot_be_rewritten_through_the_context() -> None:
    """A backend that could edit the map could redirect its own readout."""
    context = _context_with(("forecast_json", _FORECAST_URI))

    with pytest.raises(TypeError):
        context.output_uris["forecast_json"] = "gs://elsewhere/x.json"  # type: ignore[index]
