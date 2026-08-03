"""ModelReadout: documentation and result travelling together."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from grabatus_service_core.contract.base import MAX_SERVICE_OUTPUTS
from grabatus_service_core.contract.duplicates import duplicated
from grabatus_service_core.contract.envelope import Origin
from grabatus_service_core.contract.readout.artifacts import ArtifactDescription
from grabatus_service_core.contract.readout.caveats import Caveat
from grabatus_service_core.contract.readout.data import DataProvenance
from grabatus_service_core.contract.readout.diagnostics import Diagnostic, OverallQuality
from grabatus_service_core.contract.readout.enums import READOUT_VERSION
from grabatus_service_core.contract.readout.findings import Finding
from grabatus_service_core.contract.readout.guide import ExplanationGuide
from grabatus_service_core.contract.readout.knowledge import ServiceKnowledge
from grabatus_service_core.contract.readout.model import ModelDescription
from grabatus_service_core.contract.readout.provenance import Reproducibility

# Origin is imported, not redeclared, from envelope.py — this used to be a
# second, independent Literal here (web/api/mcp/batch) that diverged from
# the envelope's own vocabulary (web/api/mcp/internal). Re-exported so
# `from .root import Origin` (used by readout/__init__.py) keeps working.
__all__ = [
    "ModelReadout",
    "Origin",
    "ReadoutRequest",
    "ReadoutService",
]

_FROZEN = ConfigDict(extra="forbid", frozen=True)

# Deliberately NOT named _FROZEN: every other module in this package uses
# that name for the plain config above, and the same name holding a
# different value is worse than either convention alone.
# `protected_namespaces=()` because the field is named `model`, which
# collides with Pydantic's reserved `model_` prefix warning. The field
# name is published contract — the config yields, not the name.
_FROZEN_WITH_MODEL_FIELD = ConfigDict(
    extra="forbid",
    frozen=True,
    protected_namespaces=(),
)

_SEMVER = r"^\d+\.\d+\.\d+$"

# Copied from contract.identity.Identity.tenant_id (`_TENANT_SLUG_PATTERN`,
# private to that module): a readout's tenant_id must accept exactly the
# tenants an envelope can legally carry. The narrower `^[a-z][a-z0-9-]*$`
# used here previously rejected legal tenants like "3m".
_TENANT_ID_PATTERN = r"^[a-z0-9-]+$"

# Copied from contract.service_descriptor.ServiceDescriptor.name
# (`_SERVICE_SLUG_PATTERN`, private to that module): a readout's
# service.name must accept exactly what a service descriptor can legally
# carry, including the underscore ServiceDescriptor allows and this
# pattern previously did not (e.g. "basket_analysis").
_SERVICE_NAME_PATTERN = r"^[a-z][a-z0-9_-]*$"

# Matches contract.references.References: parameter_id/result_id are
# platform-opaque ids up to 128 chars, not the 64 this used to enforce.
_MAX_PLATFORM_ID_LENGTH = 128

# One artefact description per artefact the service wrote. The readout
# occupies an output slot but never describes itself, so the ceiling is
# the contract's output budget minus that slot — derived, because the
# hand-written 11 was unreachable by two.
_MAX_ARTIFACTS = MAX_SERVICE_OUTPUTS
_MAX_FINDINGS = 50
_MAX_DIAGNOSTICS = 30
_MAX_CAVEATS = 20


class ReadoutRequest(BaseModel):
    """Which request produced this readout."""

    model_config = _FROZEN

    request_id: str = Field(min_length=1, max_length=64)
    result_id: str = Field(min_length=1, max_length=_MAX_PLATFORM_ID_LENGTH)
    parameter_id: str = Field(min_length=1, max_length=_MAX_PLATFORM_ID_LENGTH)
    tenant_id: str = Field(min_length=1, max_length=64, pattern=_TENANT_ID_PATTERN)
    origin: Origin


class ReadoutService(BaseModel):
    """Which service, at which version, produced this readout."""

    model_config = _FROZEN

    name: str = Field(min_length=1, max_length=64, pattern=_SERVICE_NAME_PATTERN)
    version: str = Field(pattern=_SEMVER)


class ModelReadout(BaseModel):
    """The artefact an LLM reads to explain a result without inventing.

    Carries conclusions, never raw arrays. Every collection here is
    bounded — nothing in this document may grow with the input size.
    """

    model_config = _FROZEN_WITH_MODEL_FIELD

    readout_version: Literal["1.0"] = READOUT_VERSION
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

    @model_validator(mode="after")
    def _finding_ids_are_unique(self) -> Self:
        """Two findings under one id make every reference to it ambiguous."""
        repeated = duplicated(finding.id for finding in self.findings)
        if repeated:
            raise ValueError(f"finding ids must be unique, got duplicates={repeated!r}")
        return self

    @model_validator(mode="after")
    def _artifact_roles_are_unique(self) -> Self:
        """One role, one artefact — the same rule the contract's outputs follow."""
        repeated = duplicated(artifact.role for artifact in self.artifacts)
        if repeated:
            raise ValueError(f"artifact roles must be unique, got duplicates={repeated!r}")
        return self

    @model_validator(mode="after")
    def _narrative_order_names_real_findings(self) -> Self:
        """The order is normative: every step names a ``Finding.id``.

        A dangling reference hands the LLM an instruction it can only obey
        by inventing the finding — the exact outcome the guardrails forbid.
        The document would contradict itself and the LLM would pick.
        """
        known = {finding.id for finding in self.findings}
        dangling = sorted(set(self.explanation_guide.recommended_narrative_order) - known)
        if dangling:
            raise ValueError(
                f"recommended_narrative_order names findings that do not exist: {dangling!r}; "
                f"known finding ids={sorted(known)!r}",
            )
        return self
