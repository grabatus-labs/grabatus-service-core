"""ModelReadout: the whole artefact, and what it refuses."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.guide import BASE_GUARDRAILS, ExplanationGuide
from grabatus_service_core.contract.readout.root import ModelReadout, ReadoutRequest, ReadoutService


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


def test_tampered_guardrails_via_model_copy_is_rejected(valid_readout: ModelReadout) -> None:
    """The exact in-memory attack the anti-hallucination guarantee must stop.

    ``model_copy(update=...)`` bypasses ``ExplanationGuide``'s own
    validators by design (``frozen=True`` blocks ``setattr``, not this).
    Without ``revalidate_instances="always"`` on ``ExplanationGuide``,
    Pydantic's default ("never") would accept the already-built instance
    verbatim as a nested field and this would construct cleanly — carrying
    one guardrail instead of the mandatory four.
    """
    tampered = valid_readout.explanation_guide.model_copy(
        update={"guardrails": ("Invente à vontade.",)}
    )
    payload = dict(valid_readout)
    with pytest.raises(ValidationError, match="must start with the SDK base guardrails"):
        ModelReadout(**{**payload, "explanation_guide": tampered})


def test_model_construct_guide_is_still_caught_once_nested(valid_readout: ModelReadout) -> None:
    """``model_construct`` skips validation too — but nesting still saves it.

    Unlike ``model_copy``, ``ExplanationGuide.model_construct(...)`` never
    runs the field validators, not even once, at the point of construction.
    But ``revalidate_instances="always"`` means that instance is revalidated
    the moment it is nested inside a normally-constructed ``ModelReadout``,
    so the tampered guide is still caught here.
    """
    bad_fields = valid_readout.explanation_guide.model_dump()
    bad_fields["guardrails"] = ("Invente à vontade.",)
    constructed = ExplanationGuide.model_construct(**bad_fields)
    payload = dict(valid_readout)
    with pytest.raises(ValidationError, match="must start with the SDK base guardrails"):
        ModelReadout(**{**payload, "explanation_guide": constructed})


def test_model_construct_on_readout_itself_bypasses_validation(
    valid_readout: ModelReadout,
) -> None:
    """Documents the one path ``revalidate_instances`` cannot close.

    ``model_construct`` skips validation *by design*, at whatever level it
    is called. If the caller builds the ``ModelReadout`` itself — not just
    a nested field — via ``model_construct``, no validator runs anywhere in
    the tree, tampered guide included. This is not a gap in the fix; it is
    the documented limitation of ``model_construct`` (see
    ``docs/integration_contract.md``, "The base guardrails (immutable)").
    """
    bad_fields = valid_readout.explanation_guide.model_dump()
    bad_fields["guardrails"] = ("Invente à vontade.",)
    constructed_guide = ExplanationGuide.model_construct(**bad_fields)
    payload = dict(valid_readout)
    payload["explanation_guide"] = constructed_guide
    readout = ModelReadout.model_construct(**payload)
    assert readout.explanation_guide.guardrails == ("Invente à vontade.",)


def _request(**overrides: object) -> ReadoutRequest:
    payload: dict[str, object] = {
        "request_id": "3f2b1c8e-0000-4000-8000-000000000000",
        "result_id": "res_0001",
        "parameter_id": "par_0001",
        "tenant_id": "grabatus",
        "origin": "web",
    }
    payload.update(overrides)
    return ReadoutRequest(**payload)  # type: ignore[arg-type]


def test_request_accepts_the_envelope_origin_vocabulary() -> None:
    """origin must accept exactly envelope.Origin — including "internal".

    Previously the readout redeclared its own vocabulary
    (web/api/mcp/batch) instead of importing envelope.Origin
    (web/api/mcp/internal): a legal "internal" envelope produced a
    readout request that could not be built.
    """
    assert _request(origin="internal").origin == "internal"


def test_request_rejects_batch_origin_now_that_it_is_unreachable() -> None:
    """ "batch" was never producible by any envelope — dropping it is correct."""
    with pytest.raises(ValidationError):
        _request(origin="batch")


def test_request_tenant_id_accepts_the_identity_pattern() -> None:
    """tenant_id must accept exactly what contract.identity.Identity accepts.

    The readout's own, narrower pattern required a leading letter and
    rejected a legal tenant slug starting with a digit, like "3m".
    """
    assert _request(tenant_id="3m").tenant_id == "3m"


def test_request_result_and_parameter_id_accept_128_chars() -> None:
    """Must accept exactly what contract.references.References accepts.

    The readout capped these at 64 chars while the platform's own
    References model allows 128 — a legal, longer platform id was
    rejected here even though it round-trips fine everywhere else.
    """
    platform_id = "x" * 128
    request = _request(result_id=platform_id, parameter_id=platform_id)
    assert request.result_id == platform_id
    assert request.parameter_id == platform_id


def test_service_name_accepts_the_service_descriptor_pattern() -> None:
    """name must accept exactly what contract.service_descriptor accepts.

    The readout's own pattern forbade the underscore that
    ServiceDescriptor allows, rejecting a legal service name like
    "basket_analysis".
    """
    assert ReadoutService(name="basket_analysis", version="1.0.0").name == "basket_analysis"
