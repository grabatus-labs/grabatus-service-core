"""ArtifactDescription is a data dictionary, not prose."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.artifacts import (
    ArtifactDescription,
    FieldDescription,
)


def _field(**overrides: object) -> FieldDescription:
    payload: dict[str, object] = {
        "name": "lift",
        "type": "number",
        "unit": None,
        "interval_level": None,
        "meaning": "Razão entre a frequência conjunta observada e a esperada sob independência.",
        "read_as": "Quantas vezes mais provável que o acaso.",
    }
    payload.update(overrides)
    return FieldDescription(**payload)  # type: ignore[arg-type]


def _artifact(**overrides: object) -> ArtifactDescription:
    payload: dict[str, object] = {
        "role": "rules_json",
        "uri": "gs://gbt-storage-grabatus/user_999/rules.json",
        "format": "json",
        "description": "Regras de associação ranqueadas por impacto financeiro.",
        "fields": (_field(),),
    }
    payload.update(overrides)
    return ArtifactDescription(**payload)  # type: ignore[arg-type]


def test_complete_artifact_validates() -> None:
    assert _artifact().role == "rules_json"


def test_role_follows_the_contract_role_pattern() -> None:
    """Same pattern as InputSpec/OutputSpec roles in contract/io_spec.py."""
    with pytest.raises(ValidationError):
        _artifact(role="Rules JSON")


def test_fields_are_mandatory() -> None:
    """An artefact with no field dictionary is opaque again."""
    with pytest.raises(ValidationError):
        _artifact(fields=())


def test_interval_level_must_be_a_probability() -> None:
    with pytest.raises(ValidationError):
        _field(interval_level=1.5)


def test_interval_level_accepts_a_valid_probability() -> None:
    """0.9 is inside the open interval; 0 and 1 are not valid interval levels.

    Asserting only the accepted value would pass even if the gt/lt bounds
    were dropped entirely, so the boundary rejections are pinned here too.
    """
    assert _field(interval_level=0.9).interval_level == 0.9
    with pytest.raises(ValidationError):
        _field(interval_level=0.0)
    with pytest.raises(ValidationError):
        _field(interval_level=1.0)


def test_field_type_is_a_closed_vocabulary() -> None:
    with pytest.raises(ValidationError):
        _field(type="dataframe")


def test_read_as_is_mandatory() -> None:
    """`meaning` is technical; `read_as` is the sentence the client hears."""
    with pytest.raises(ValidationError):
        _field(read_as="")


def test_artifact_is_frozen() -> None:
    artifact = _artifact()
    with pytest.raises(ValidationError):
        artifact.role = "outro"  # type: ignore[misc]
