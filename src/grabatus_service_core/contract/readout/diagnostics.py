"""Diagnostic: a quality metric with its threshold and its meaning."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from grabatus_service_core.contract.readout.enums import DiagnosticStatus, QualityStatus

_FROZEN = ConfigDict(extra="forbid", frozen=True)


class Diagnostic(BaseModel):
    """One quality check, already judged against its threshold."""

    model_config = _FROZEN

    name: str = Field(min_length=1, max_length=120)
    value: float
    threshold: str = Field(min_length=1, max_length=64)
    status: DiagnosticStatus
    meaning: str = Field(min_length=1, max_length=500)


class OverallQuality(BaseModel):
    """The single verdict on whether this result can be trusted."""

    model_config = _FROZEN

    status: QualityStatus
    summary: str = Field(min_length=1, max_length=1000)
