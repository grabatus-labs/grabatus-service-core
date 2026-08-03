"""Every bounded collection must actually reject the item past its bound.

A `max_length` nobody tests is a `max_length` a refactor can drop without
a single test turning red. Only `input_digests` had this coverage.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.enums import MAX_ITEMS
from grabatus_service_core.contract.readout.knowledge import Persona
from grabatus_service_core.contract.readout.provenance import InputDigest, Reproducibility

_MAX_PROVENANCE_ITEMS = 20
_MAX_ROLE_LENGTH = 32
_SHA = "a" * 64


def _reproducibility(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "random_seed": None,
        "compute_duration_seconds": 1.0,
        "input_digests": [{"role": "transactions", "sha256": _SHA}],
        "library_versions": {"mlxtend": "0.23.1"},
    }
    return payload | overrides


def _libraries(count: int) -> dict[str, str]:
    return {f"lib_{index}": "1.0.0" for index in range(count)}


def test_library_versions_rejects_the_item_past_the_bound() -> None:
    payload = _reproducibility(library_versions=_libraries(_MAX_PROVENANCE_ITEMS + 1))

    with pytest.raises(ValidationError, match="library_versions"):
        Reproducibility.model_validate(payload)


def test_library_versions_accepts_exactly_the_bound() -> None:
    """A bound one item too tight breaks services the schema calls legal."""
    payload = _reproducibility(library_versions=_libraries(_MAX_PROVENANCE_ITEMS))

    parsed = Reproducibility.model_validate(payload)

    assert len(parsed.library_versions) == _MAX_PROVENANCE_ITEMS


def test_input_digest_role_rejects_the_character_past_the_bound() -> None:
    with pytest.raises(ValidationError, match="role"):
        InputDigest.model_validate({"role": "r" * (_MAX_ROLE_LENGTH + 1), "sha256": _SHA})


def test_input_digest_role_accepts_exactly_the_bound() -> None:
    at_bound = "r" * _MAX_ROLE_LENGTH

    assert InputDigest.model_validate({"role": at_bound, "sha256": _SHA}).role == at_bound


def test_a_max_items_collection_rejects_the_item_past_the_bound() -> None:
    """`Persona.pains` stands for every `max_length=MAX_ITEMS` field in knowledge.py."""
    with pytest.raises(ValidationError, match="pains"):
        Persona.model_validate({"role": "Gerente", "pains": ["dor"] * (MAX_ITEMS + 1)})


def test_a_max_items_collection_accepts_exactly_the_bound() -> None:
    parsed = Persona.model_validate({"role": "Gerente", "pains": ["dor"] * MAX_ITEMS})

    assert len(parsed.pains) == MAX_ITEMS
