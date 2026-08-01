"""ModelReadout: the whole artefact, and what it refuses."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.guide import BASE_GUARDRAILS
from grabatus_service_core.contract.readout.root import ModelReadout


def test_valid_readout_round_trips(valid_readout: ModelReadout) -> None:
    raw = valid_readout.model_dump_json()
    rebuilt = ModelReadout.model_validate_json(raw)
    assert rebuilt.service.name == "grabatus-basketanalysis"


def test_readout_embeds_the_service_documentation(valid_readout: ModelReadout) -> None:
    """Self-contained: the LLM needs nothing else to explain this.

    Checks a specific, non-guessable fact carried by ``service_knowledge``
    (not just any truthy string), and proves the field is mandatory: a
    readout missing it entirely must be rejected, not silently accepted
    with an empty explanation of the service.
    """
    assert valid_readout.service_knowledge.glossary[0].technical_term == "lift"
    assert valid_readout.service_knowledge.limitations == ("Não mede canibalização.",)

    payload = valid_readout.model_dump(mode="json")
    del payload["service_knowledge"]
    with pytest.raises(ValidationError, match="service_knowledge"):
        ModelReadout.model_validate(payload)


def test_readout_carries_the_base_guardrails(valid_readout: ModelReadout) -> None:
    """Not just "at least 4 rules" — the exact SDK wording, in order.

    A count-only check would pass even if the four rules were replaced by
    four unrelated strings. Comparing against ``BASE_GUARDRAILS`` itself
    catches that.
    """
    guardrails = valid_readout.explanation_guide.guardrails
    assert guardrails[: len(BASE_GUARDRAILS)] == BASE_GUARDRAILS
    assert len(guardrails) >= len(BASE_GUARDRAILS)


def test_unknown_top_level_field_is_rejected(valid_readout: ModelReadout) -> None:
    payload = valid_readout.model_dump(mode="json")
    payload["raw_samples"] = [1, 2, 3]
    with pytest.raises(ValidationError):
        ModelReadout.model_validate(payload)


def test_service_version_must_be_semver(valid_readout: ModelReadout) -> None:
    payload = valid_readout.model_dump(mode="json")
    payload["service"]["version"] = "1.0"
    with pytest.raises(ValidationError):
        ModelReadout.model_validate(payload)


def test_readout_version_is_pinned(valid_readout: ModelReadout) -> None:
    payload = valid_readout.model_dump(mode="json")
    payload["readout_version"] = "2.0"
    with pytest.raises(ValidationError):
        ModelReadout.model_validate(payload)


def test_generated_at_must_be_timezone_aware(valid_readout: ModelReadout) -> None:
    """A naive timestamp is ambiguous across the platform's regions."""
    payload = valid_readout.model_dump(mode="json")
    payload["generated_at"] = "2026-07-31T14:03:11"
    with pytest.raises(ValidationError, match="timezone"):
        ModelReadout.model_validate(payload)


def test_findings_may_be_empty(valid_readout: ModelReadout) -> None:
    """Zero findings is a legitimate outcome — and must stay explainable.

    Two distinct code paths are checked: an explicit empty list (goes
    through validation) and the key missing altogether (falls back to the
    field default). Pydantic v2 does not re-validate a default on
    omission, so only exercising the explicit case would miss a mutation
    that turned ``findings`` into a required field with no default.
    """
    payload = valid_readout.model_dump(mode="json")
    payload["findings"] = []
    assert ModelReadout.model_validate(payload).findings == ()

    del payload["findings"]
    assert ModelReadout.model_validate(payload).findings == ()


def test_artifacts_are_mandatory(valid_readout: ModelReadout) -> None:
    payload = valid_readout.model_dump(mode="json")
    payload["artifacts"] = []
    with pytest.raises(ValidationError):
        ModelReadout.model_validate(payload)


def test_serialisation_preserves_accents(valid_readout: ModelReadout) -> None:
    raw = json.loads(valid_readout.model_dump_json())
    assert "não" in raw["explanation_guide"]["guardrails"][0]


def test_readout_is_frozen(valid_readout: ModelReadout) -> None:
    with pytest.raises(ValidationError):
        valid_readout.readout_version = "9.9"  # type: ignore[misc]
