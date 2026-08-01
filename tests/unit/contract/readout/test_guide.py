"""The base guardrails survive any service's customisation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.guide import (
    BASE_GUARDRAILS,
    ExplanationGuide,
    build_explanation_guide,
)


def _guide(**overrides: object) -> ExplanationGuide:
    payload: dict[str, object] = {
        "audience": "gerente comercial sem formação estatística",
        "summary_for_llm": "Três combos concentram 60% da oportunidade estimada.",
        "what_was_solved": "Quais combos valem virar ação de gôndola.",
        "must_not_claim": ("que a associação prova causa",),
        "recommended_narrative_order": ("rule_001",),
        "guardrails": BASE_GUARDRAILS,
    }
    payload.update(overrides)
    return ExplanationGuide(**payload)  # type: ignore[arg-type]


def test_base_has_exactly_four_rules() -> None:
    assert len(BASE_GUARDRAILS) == 4


def test_base_covers_the_four_mandates() -> None:
    joined = " ".join(BASE_GUARDRAILS).lower()
    assert "não extrapole" in joined
    assert "não sabe" in joined
    assert "grabatus" in joined
    assert "não recalcule" in joined
    assert "sugestão de melhoria" in joined


def test_guide_accepts_the_exact_base() -> None:
    assert _guide().guardrails == BASE_GUARDRAILS


def test_guide_accepts_base_plus_service_rules() -> None:
    extended = (*BASE_GUARDRAILS, "Nunca cite um SKU ausente de findings[].")
    assert _guide(guardrails=extended).guardrails[-1].startswith("Nunca cite")


def test_guide_rejects_a_dropped_base_rule() -> None:
    with pytest.raises(ValidationError, match="must start with the SDK base guardrails"):
        _guide(guardrails=BASE_GUARDRAILS[:3])


def test_guide_rejects_a_rewritten_base_rule() -> None:
    tampered = ("Pode estimar quando fizer sentido.", *BASE_GUARDRAILS[1:])
    with pytest.raises(ValidationError, match="must start with the SDK base guardrails"):
        _guide(guardrails=tampered)


def test_guide_rejects_reordered_base_rules() -> None:
    reordered = (BASE_GUARDRAILS[1], BASE_GUARDRAILS[0], *BASE_GUARDRAILS[2:])
    with pytest.raises(ValidationError, match="must start with the SDK base guardrails"):
        _guide(guardrails=reordered)


def test_guide_rejects_service_rules_before_the_base() -> None:
    """Prefix, not membership — order carries meaning for a reader."""
    prefixed = ("Regra do serviço primeiro.", *BASE_GUARDRAILS)
    with pytest.raises(ValidationError, match="must start with the SDK base guardrails"):
        _guide(guardrails=prefixed)


def test_guide_rejects_a_non_sequence_guardrails_value() -> None:
    """A malformed payload must fail as a Pydantic error, not a raw TypeError."""
    with pytest.raises(ValidationError, match="must be a sequence of strings"):
        _guide(guardrails=None)


def test_builder_fills_the_base_automatically() -> None:
    guide = build_explanation_guide(
        audience="gerente comercial",
        summary_for_llm="Resumo.",
        what_was_solved="A dor endereçada.",
        must_not_claim=("que prova causa",),
    )
    assert guide.guardrails == BASE_GUARDRAILS


def test_builder_appends_service_rules_after_the_base() -> None:
    guide = build_explanation_guide(
        audience="gerente comercial",
        summary_for_llm="Resumo.",
        what_was_solved="A dor endereçada.",
        must_not_claim=("que prova causa",),
        additional_guardrails=("Nunca cite um SKU ausente de findings[].",),
    )
    assert guide.guardrails[:4] == BASE_GUARDRAILS
    assert guide.guardrails[4].startswith("Nunca cite")


def test_must_not_claim_is_mandatory_and_non_empty() -> None:
    """The difference between a result and an overclaim."""
    with pytest.raises(ValidationError):
        _guide(must_not_claim=())


def test_recommended_narrative_order_may_be_empty() -> None:
    assert _guide(recommended_narrative_order=()).recommended_narrative_order == ()


def test_guide_is_frozen() -> None:
    guide = _guide()
    with pytest.raises(ValidationError):
        guide.audience = "outro"  # type: ignore[misc]
