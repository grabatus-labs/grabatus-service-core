"""ServiceKnowledge: what the service is, independent of any single run.

Static per service version, embedded verbatim into every readout. It is
what lets an LLM answer "what is this and who is it for" without
inventing the context around the numbers.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from grabatus_service_core.contract.readout.enums import ITEM_MAX_LENGTH, MAX_ITEMS

_FROZEN = ConfigDict(extra="forbid", frozen=True)

_MAX_WORKFLOW_STEPS = 12
_MAX_COLUMNS = 64

# Each bullet is one short, human-written line — not a place to smuggle a
# large payload as a single tuple item.
_Bullet = Annotated[str, StringConstraints(max_length=ITEM_MAX_LENGTH)]


class Persona(BaseModel):
    """Who uses the service, and what hurts today."""

    model_config = _FROZEN

    role: str = Field(min_length=1, max_length=200)
    pains: tuple[str, ...] = Field(min_length=1, max_length=MAX_ITEMS)


class WorkflowStep(BaseModel):
    """One step of using the service, paired with what the LLM should say."""

    model_config = _FROZEN

    order: int = Field(ge=1, le=_MAX_WORKFLOW_STEPS)
    what_the_user_does: str = Field(min_length=1, max_length=500)
    what_the_llm_should_say: str = Field(min_length=1, max_length=1000)


class InputRequirement(BaseModel):
    """One column the service reads, in business terms."""

    model_config = _FROZEN

    column: str = Field(min_length=1, max_length=64)
    required: bool
    business_meaning: str = Field(min_length=1, max_length=500)
    example: str = Field(min_length=1, max_length=200)


class InterpretationRule(BaseModel):
    """Situation -> meaning -> recommendation. Turns a number into a decision."""

    model_config = _FROZEN

    observed_situation: str = Field(min_length=1, max_length=300)
    what_it_means: str = Field(min_length=1, max_length=500)
    what_to_recommend: str = Field(min_length=1, max_length=500)


class Misreading(BaseModel):
    """A wrong reading seen in the field, and its correction."""

    model_config = _FROZEN

    wrong_reading: str = Field(min_length=1, max_length=500)
    correction: str = Field(min_length=1, max_length=500)


class Term(BaseModel):
    """A technical term and how to say it to the client."""

    model_config = _FROZEN

    technical_term: str = Field(min_length=1, max_length=120)
    client_language: str = Field(min_length=1, max_length=300)


class ServiceKnowledge(BaseModel):
    """Everything an LLM needs to know about the service itself."""

    model_config = _FROZEN

    one_liner: str = Field(min_length=1, max_length=280)
    what_it_does: str = Field(min_length=1, max_length=2000)
    problem_solved: str = Field(min_length=1, max_length=1000)

    when_to_use: tuple[_Bullet, ...] = Field(min_length=1, max_length=MAX_ITEMS)
    when_not_to_use: tuple[_Bullet, ...] = Field(min_length=1, max_length=MAX_ITEMS)

    personas: tuple[Persona, ...] = Field(min_length=1, max_length=MAX_ITEMS)
    workflow: tuple[WorkflowStep, ...] = Field(min_length=1, max_length=_MAX_WORKFLOW_STEPS)
    input_requirements: tuple[InputRequirement, ...] = Field(min_length=1, max_length=_MAX_COLUMNS)

    interpretation_playbook: tuple[InterpretationRule, ...] = Field(
        min_length=1, max_length=MAX_ITEMS
    )
    common_misreadings: tuple[Misreading, ...] = Field(default=(), max_length=MAX_ITEMS)
    glossary: tuple[Term, ...] = Field(min_length=1, max_length=MAX_ITEMS)
    limitations: tuple[_Bullet, ...] = Field(min_length=1, max_length=MAX_ITEMS)

    @field_validator("workflow")
    @classmethod
    def _orders_are_contiguous_from_one(
        cls, steps: tuple[WorkflowStep, ...]
    ) -> tuple[WorkflowStep, ...]:
        """A workflow the LLM reads out of order is a workflow it gets wrong."""
        orders = [step.order for step in steps]
        if orders != list(range(1, len(orders) + 1)):
            raise ValueError(f"workflow orders must be contiguous from 1, got {orders!r}")
        return steps
