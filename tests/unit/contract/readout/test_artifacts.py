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


def test_meaning_is_mandatory() -> None:
    """`meaning` is technical; `read_as` is the sentence the client hears."""
    with pytest.raises(ValidationError):
        _field(meaning="")


@pytest.mark.parametrize("required_field", ["meaning", "read_as"])
def test_required_text_fields_cannot_be_omitted(required_field: str) -> None:
    """Proves absence of the key, not just an empty string.

    ``_field()`` always supplies both keys, so a default value smuggled in
    via ``Field(default="", ...)`` would slip past every other test here —
    the empty-string checks above validate a value that is present, and
    Pydantic v2 does not revalidate a default when the key is missing. This
    builds the payload directly, without the key, and goes through the
    model to prove the field cannot simply be dropped.
    """
    payload: dict[str, object] = {
        "name": "lift",
        "type": "number",
        "unit": None,
        "interval_level": None,
        "meaning": "Razão entre a frequência conjunta observada e a esperada sob independência.",
        "read_as": "Quantas vezes mais provável que o acaso.",
    }
    del payload[required_field]
    with pytest.raises(ValidationError):
        FieldDescription.model_validate(payload)


def test_artifact_is_frozen() -> None:
    artifact = _artifact()
    with pytest.raises(ValidationError):
        artifact.role = "outro"  # type: ignore[misc]


def test_uri_rejects_the_data_scheme() -> None:
    """`data:` embeds its payload directly in the URI -- the cleanest way
    to smuggle a large sample into a readout that carries no raw arrays."""
    with pytest.raises(ValidationError):
        _artifact(uri="data:application/json;base64," + "A" * 400_000)


def test_uri_rejects_the_inline_scheme() -> None:
    """`inline://` is the same smuggling shape as `data:` -- it embeds its
    payload directly in the URI too, even though InputSpec/OutputSpec
    accept `inline` as a legitimate input/output *format*."""
    with pytest.raises(ValidationError):
        _artifact(uri="inline://base64," + "A" * 400_000)


def test_uri_accepts_the_gs_and_bigquery_schemes() -> None:
    """The two schemes an artifact -- a file the service already wrote --
    is actually expected to live under."""
    assert _artifact(uri="gs://gbt-storage-grabatus/user_999/rules.json").uri is not None
    assert _artifact(uri="bigquery://project/dataset/table").uri is not None


def test_uri_rejects_an_oversized_value() -> None:
    with pytest.raises(ValidationError):
        _artifact(uri="gs://gbt-storage-grabatus/" + "a" * 3000)
