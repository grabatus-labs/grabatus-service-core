"""ServiceKnowledge refuses to describe a service incompletely."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.knowledge import (
    InputRequirement,
    InterpretationRule,
    Misreading,
    Persona,
    ServiceKnowledge,
    Term,
    WorkflowStep,
)


def _knowledge(**overrides: object) -> ServiceKnowledge:
    payload: dict[str, object] = {
        "one_liner": "Descobre quais produtos são comprados juntos.",
        "what_it_does": "Minera regras de associação e ranqueia por impacto financeiro.",
        "problem_solved": "O gerente monta combo por intuição.",
        "when_to_use": ("Definir planograma",),
        "when_not_to_use": ("Medir efeito causal de promoção — use teste A/B",),
        "personas": (Persona(role="Gerente comercial", pains=("Não distingo afinidade real",)),),
        "workflow": (
            WorkflowStep(
                order=1,
                what_the_user_does="Sobe a planilha de transações",
                what_the_llm_should_say="Confirmo que transaction_id e sku são obrigatórios.",
            ),
        ),
        "input_requirements": (
            InputRequirement(
                column="transaction_id",
                required=True,
                business_meaning="Identifica uma compra.",
                example="TX-000481",
            ),
        ),
        "interpretation_playbook": (
            InterpretationRule(
                observed_situation="Lift alto e addressable baixo",
                what_it_means="Afinidade real em volume pequeno.",
                what_to_recommend="Testar em uma loja antes de mexer na rede.",
            ),
        ),
        "common_misreadings": (
            Misreading(
                wrong_reading="Confiança de 73% significa causa.",
                correction="É frequência observada, não causa.",
            ),
        ),
        "glossary": (
            Term(technical_term="lift", client_language="quantas vezes mais que o acaso"),
        ),
        "limitations": ("Não mede canibalização.",),
    }
    payload.update(overrides)
    return ServiceKnowledge(**payload)  # type: ignore[arg-type]


def test_complete_knowledge_validates() -> None:
    assert _knowledge().one_liner.startswith("Descobre")


def test_knowledge_is_frozen() -> None:
    knowledge = _knowledge()
    with pytest.raises(ValidationError):
        knowledge.one_liner = "outro"  # type: ignore[misc]


def test_knowledge_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        _knowledge(pricing_tier="premium")


@pytest.mark.parametrize(
    "empty_field",
    [
        "when_to_use",
        "when_not_to_use",
        "personas",
        "workflow",
        "input_requirements",
        "interpretation_playbook",
        "glossary",
        "limitations",
    ],
)
def test_mandatory_sections_reject_empty(empty_field: str) -> None:
    """An empty section is a service that cannot be explained."""
    with pytest.raises(ValidationError):
        _knowledge(**{empty_field: ()})


def test_common_misreadings_may_be_empty() -> None:
    """The only optional section: a new service has seen no misreading yet."""
    assert _knowledge(common_misreadings=()).common_misreadings == ()


def test_workflow_order_must_start_at_one() -> None:
    step = WorkflowStep(order=2, what_the_user_does="a", what_the_llm_should_say="b")
    with pytest.raises(ValidationError, match="contiguous"):
        _knowledge(workflow=(step,))


def test_workflow_order_must_be_contiguous() -> None:
    steps = (
        WorkflowStep(order=1, what_the_user_does="a", what_the_llm_should_say="b"),
        WorkflowStep(order=3, what_the_user_does="c", what_the_llm_should_say="d"),
    )
    with pytest.raises(ValidationError, match="contiguous"):
        _knowledge(workflow=steps)


def test_workflow_error_names_the_offending_orders() -> None:
    steps = (WorkflowStep(order=7, what_the_user_does="a", what_the_llm_should_say="b"),)
    with pytest.raises(ValidationError, match=r"\[7\]"):
        _knowledge(workflow=steps)


def test_persona_rejects_empty_pains() -> None:
    with pytest.raises(ValidationError):
        Persona(role="Gerente", pains=())


def test_workflow_step_rejects_zero_order() -> None:
    with pytest.raises(ValidationError):
        WorkflowStep(order=0, what_the_user_does="a", what_the_llm_should_say="b")


@pytest.mark.parametrize("bullet_field", ["when_to_use", "when_not_to_use", "limitations"])
def test_bullet_lists_reject_an_oversized_single_item(bullet_field: str) -> None:
    """A tuple's own max_length bounds item *count*, never item *length* —
    without a per-item bound, a single huge string validates as "one
    bullet" and raw data enters the readout through this side door."""
    with pytest.raises(ValidationError):
        _knowledge(**{bullet_field: ("x" * 2_000_000,)})
