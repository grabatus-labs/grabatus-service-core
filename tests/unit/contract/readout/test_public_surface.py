"""The closed vocabularies must be reachable without importing private modules.

A service annotating ``def _family_for(kind: str) -> ModelFamily`` under
``mypy --strict`` has three options: import the facade, reach into
``readout.enums``, or redeclare the vocabulary. The third is the drift the
snapshot test exists to prevent, so the first has to work.
"""

from __future__ import annotations

import pytest

from grabatus_service_core import contract
from grabatus_service_core.contract import readout

_CLOSED_VOCABULARIES = [
    "Confidence",
    "DiagnosticStatus",
    "Direction",
    "FieldType",
    "HyperparameterValue",
    "ModelFamily",
    "Origin",
    "Paradigm",
    "QualityStatus",
    "Severity",
    "UncertaintyKind",
]


@pytest.mark.parametrize("name", _CLOSED_VOCABULARIES)
def test_every_closed_vocabulary_is_exported(name: str) -> None:
    assert name in readout.__all__
    assert getattr(readout, name) is not None


def test_the_readout_subpackage_is_reachable_from_the_contract_facade() -> None:
    """One canonical path, so services do not invent a second one."""
    assert "readout" in contract.__all__
    assert contract.readout is readout
