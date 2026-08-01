"""ExplanationGuide: how to narrate the result, and what never to claim.

The four base guardrails belong to the SDK. They are a module constant
rather than a default value, and a prefix validator rejects any readout
whose guardrails do not begin with them — so a service can add domain
rules but has no mechanism to weaken the guarantee.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

BASE_GUARDRAILS: Final[tuple[str, ...]] = (
    "Responda apenas com o que este documento afirma. Não extrapole, não "
    "estime e não complete lacunas com conhecimento geral sobre o setor.",
    "Se a pergunta não puder ser respondida com este documento, diga que "
    "não sabe e ofereça o contato da Grabatus. Nunca produza um número que "
    "não esteja escrito aqui.",
    "Não recalcule nada a partir de dados brutos. Os números deste "
    "documento já são o resultado final da análise.",
    "Sempre que encontrar uma lacuna — algo que o cliente pediu e este "
    "documento não responde — registre uma sugestão de melhoria no canal "
    "da Grabatus, descrevendo o que faltou.",
)

_MAX_GUARDRAILS = 20
_MAX_CLAIMS = 20
_MAX_NARRATIVE_STEPS = 20


class ExplanationGuide(BaseModel):
    """Narration instructions for whichever LLM presents this result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    audience: str = Field(min_length=1, max_length=200)
    summary_for_llm: str = Field(min_length=1, max_length=2000)
    what_was_solved: str = Field(min_length=1, max_length=1000)
    recommended_narrative_order: tuple[str, ...] = Field(
        default=(), max_length=_MAX_NARRATIVE_STEPS
    )
    must_not_claim: tuple[str, ...] = Field(min_length=1, max_length=_MAX_CLAIMS)
    guardrails: tuple[str, ...] = Field(max_length=_MAX_GUARDRAILS)

    @field_validator("guardrails")
    @classmethod
    def _starts_with_the_base(cls, rules: tuple[str, ...]) -> tuple[str, ...]:
        """Prefix, not membership: order and wording both carry meaning.

        The base length is enforced here rather than via ``Field(min_length=...)``
        so that a too-short ``guardrails`` tuple fails with this same
        prefix-violation message instead of Pydantic's generic "too short".
        """
        prefix = rules[: len(BASE_GUARDRAILS)]
        if prefix != BASE_GUARDRAILS:
            raise ValueError(f"guardrails must start with the SDK base guardrails, got {prefix!r}")
        return rules


def build_explanation_guide(
    *,
    audience: str,
    summary_for_llm: str,
    what_was_solved: str,
    must_not_claim: tuple[str, ...],
    recommended_narrative_order: tuple[str, ...] = (),
    additional_guardrails: tuple[str, ...] = (),
) -> ExplanationGuide:
    """Assemble the guide with the base guardrails already in place.

    Services call this rather than constructing ``ExplanationGuide``
    directly, so the easy path is also the correct one.
    """
    return ExplanationGuide(
        audience=audience,
        summary_for_llm=summary_for_llm,
        what_was_solved=what_was_solved,
        recommended_narrative_order=recommended_narrative_order,
        must_not_claim=must_not_claim,
        guardrails=(*BASE_GUARDRAILS, *additional_guardrails),
    )
