"""DataProvenance: what went into the fit, and what did not.

Three note lists, deliberately distinct: ``filters_applied`` is what the
service removed on purpose, ``known_gaps`` is what was missing at the
source, and ``quality_flags`` is what the service had to assume in order
to run at all. Collapsing them into one field would hide which of the
three a given caveat came from — and that is exactly what the client
needs to know to judge the number.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from grabatus_service_core.contract.readout.enums import ITEM_MAX_LENGTH, MAX_ITEMS

_FROZEN = ConfigDict(extra="forbid", frozen=True)

# Each note is one short, human-written line — not a place to smuggle a
# 1.9 MB payload as a single tuple item (the tuple's own max_length bounds
# item *count*, not item *length*).
_Note = Annotated[str, StringConstraints(max_length=ITEM_MAX_LENGTH)]


class PeriodCovered(BaseModel):
    """Inclusive date range the observations span."""

    model_config = _FROZEN

    start: date
    end: date

    @model_validator(mode="after")
    def _end_not_before_start(self) -> Self:
        if self.end < self.start:
            raise ValueError(f"end={self.end!r} precedes start={self.start!r}")
        return self


class EntitySummary(BaseModel):
    """How many distinct things of a given kind were analysed."""

    model_config = _FROZEN

    label: str = Field(min_length=1, max_length=64)
    count: int = Field(ge=0)


class DataProvenance(BaseModel):
    """Shape and quality of the data behind the result."""

    model_config = _FROZEN

    observation_count: int = Field(gt=0)
    granularity: str = Field(min_length=1, max_length=64)
    period_covered: PeriodCovered | None = None
    entities: tuple[EntitySummary, ...] = Field(min_length=1, max_length=MAX_ITEMS)
    filters_applied: tuple[_Note, ...] = Field(default=(), max_length=MAX_ITEMS)
    known_gaps: tuple[_Note, ...] = Field(default=(), max_length=MAX_ITEMS)
    quality_flags: tuple[_Note, ...] = Field(default=(), max_length=MAX_ITEMS)
