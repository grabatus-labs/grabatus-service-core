"""model_readout: the artefact that explains a service and its result.

A Grabatus service is not finished when it returns the right number. It
is finished when an LLM can explain that number to the client without
inventing anything around it.
"""

from __future__ import annotations

from grabatus_service_core.contract.readout.artifacts import (
    ArtifactDescription,
    FieldDescription,
    FieldType,
)
from grabatus_service_core.contract.readout.caveats import Caveat
from grabatus_service_core.contract.readout.data import (
    DataProvenance,
    EntitySummary,
    PeriodCovered,
)
from grabatus_service_core.contract.readout.diagnostics import Diagnostic, OverallQuality
from grabatus_service_core.contract.readout.enums import (
    READOUT_OUTPUT_ROLE,
    READOUT_VERSION,
    Confidence,
    DiagnosticStatus,
    Direction,
    ModelFamily,
    Paradigm,
    QualityStatus,
    Severity,
    UncertaintyKind,
)
from grabatus_service_core.contract.readout.findings import (
    ComparisonBaseline,
    Finding,
    Quantity,
    Uncertainty,
)
from grabatus_service_core.contract.readout.guide import (
    BASE_GUARDRAILS,
    ExplanationGuide,
    build_explanation_guide,
)
from grabatus_service_core.contract.readout.knowledge import (
    InputRequirement,
    InterpretationRule,
    Misreading,
    Persona,
    ServiceKnowledge,
    Term,
    WorkflowStep,
)
from grabatus_service_core.contract.readout.model import (
    Assumption,
    HyperparameterValue,
    ModelDescription,
    Prior,
)
from grabatus_service_core.contract.readout.provenance import (
    InputDigest,
    Reproducibility,
)
from grabatus_service_core.contract.readout.root import (
    ModelReadout,
    Origin,
    ReadoutRequest,
    ReadoutService,
)

__all__ = [
    "BASE_GUARDRAILS",
    "READOUT_OUTPUT_ROLE",
    "READOUT_VERSION",
    "ArtifactDescription",
    "Assumption",
    "Caveat",
    "ComparisonBaseline",
    "Confidence",
    "DataProvenance",
    "Diagnostic",
    "DiagnosticStatus",
    "Direction",
    "EntitySummary",
    "ExplanationGuide",
    "FieldDescription",
    "FieldType",
    "Finding",
    "HyperparameterValue",
    "InputDigest",
    "InputRequirement",
    "InterpretationRule",
    "Misreading",
    "ModelDescription",
    "ModelFamily",
    "ModelReadout",
    "Origin",
    "OverallQuality",
    "Paradigm",
    "PeriodCovered",
    "Persona",
    "Prior",
    "QualityStatus",
    "Quantity",
    "ReadoutRequest",
    "ReadoutService",
    "Reproducibility",
    "ServiceKnowledge",
    "Severity",
    "Term",
    "Uncertainty",
    "UncertaintyKind",
    "WorkflowStep",
    "build_explanation_guide",
]
