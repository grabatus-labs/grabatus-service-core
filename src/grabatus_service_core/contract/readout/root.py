"""ModelReadout: documentation and result travelling together."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from grabatus_service_core.contract.readout.artifacts import ArtifactDescription
from grabatus_service_core.contract.readout.caveats import Caveat
from grabatus_service_core.contract.readout.data import DataProvenance
from grabatus_service_core.contract.readout.diagnostics import Diagnostic, OverallQuality
from grabatus_service_core.contract.readout.findings import Finding
from grabatus_service_core.contract.readout.guide import ExplanationGuide
from grabatus_service_core.contract.readout.knowledge import ServiceKnowledge
from grabatus_service_core.contract.readout.model import ModelDescription
from grabatus_service_core.contract.readout.provenance import Reproducibility

# `protected_namespaces=()` because the field is named `model`, which
# collides with Pydantic's reserved `model_` prefix warning. The field
# name is published contract — the config yields, not the name.
_FROZEN = ConfigDict(extra="forbid", frozen=True, protected_namespaces=())

_SEMVER = r"^\d+\.\d+\.\d+$"
_SLUG = r"^[a-z][a-z0-9-]*$"

_MAX_ARTIFACTS = 11
_MAX_FINDINGS = 50
_MAX_DIAGNOSTICS = 30
_MAX_CAVEATS = 20

Origin = Literal["web", "api", "mcp", "batch"]


class ReadoutRequest(BaseModel):
    """Which request produced this readout."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1, max_length=64)
    result_id: str = Field(min_length=1, max_length=64)
    parameter_id: str = Field(min_length=1, max_length=64)
    tenant_id: str = Field(min_length=1, max_length=64, pattern=_SLUG)
    origin: Origin


class ReadoutService(BaseModel):
    """Which service, at which version, produced this readout."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=64, pattern=_SLUG)
    version: str = Field(pattern=_SEMVER)


class ModelReadout(BaseModel):
    """The artefact an LLM reads to explain a result without inventing.

    Carries conclusions, never raw arrays. Every collection here is
    bounded — nothing in this document may grow with the input size.
    """

    model_config = _FROZEN

    readout_version: Literal["1.0"] = "1.0"
    generated_at: datetime

    request: ReadoutRequest
    service: ReadoutService
    service_knowledge: ServiceKnowledge

    model: ModelDescription
    data: DataProvenance
    artifacts: tuple[ArtifactDescription, ...] = Field(min_length=1, max_length=_MAX_ARTIFACTS)

    findings: tuple[Finding, ...] = Field(default=(), max_length=_MAX_FINDINGS)
    diagnostics: tuple[Diagnostic, ...] = Field(default=(), max_length=_MAX_DIAGNOSTICS)
    overall_quality: OverallQuality
    caveats: tuple[Caveat, ...] = Field(default=(), max_length=_MAX_CAVEATS)

    explanation_guide: ExplanationGuide
    reproducibility: Reproducibility

    @model_validator(mode="after")
    def _generated_at_is_aware(self) -> Self:
        """A naive timestamp is ambiguous across the platform's regions."""
        if self.generated_at.tzinfo is None:
            raise ValueError(f"generated_at must carry a timezone, got {self.generated_at!r}")
        return self
