"""A hand-written backend that satisfies the readout gate, as a service would.

Not a test double: nothing here comes from ``testing/``. It exists to prove
the claim the ComputeContext fix rests on — that a service author, given
only ``inputs``, ``parameters`` and ``context``, can now produce a readout
the runner accepts. Every identity field comes from ``context``; everything
else is knowledge the author writes once.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, ClassVar

from pydantic import AnyUrl, BaseModel

from grabatus_service_core.contract.readout.artifacts import (
    ArtifactDescription,
    FieldDescription,
)
from grabatus_service_core.contract.readout.caveats import Caveat
from grabatus_service_core.contract.readout.data import (
    DataProvenance,
    EntitySummary,
    PeriodCovered,
)
from grabatus_service_core.contract.readout.diagnostics import Diagnostic, OverallQuality
from grabatus_service_core.contract.readout.enums import READOUT_OUTPUT_ROLE
from grabatus_service_core.contract.readout.findings import Finding, Quantity, Uncertainty
from grabatus_service_core.contract.readout.guide import ExplanationGuide, build_explanation_guide
from grabatus_service_core.contract.readout.knowledge import (
    InputRequirement,
    InterpretationRule,
    Persona,
    ServiceKnowledge,
    Term,
    WorkflowStep,
)
from grabatus_service_core.contract.readout.model import Assumption, ModelDescription
from grabatus_service_core.contract.readout.provenance import InputDigest, Reproducibility
from grabatus_service_core.contract.readout.root import ModelReadout
from grabatus_service_core.ports.values import ComputeResult

if TYPE_CHECKING:
    from grabatus_service_core.ports.compute_context import ComputeContext
    from grabatus_service_core.ports.values import LoadedInputs

RESULT_URI = "gs://gbt-storage-grabatus/user_999/forecast.json"


class MovingAverageParameters(BaseModel):
    """How many periods ahead to project."""

    horizon: int


def _workflow() -> tuple[WorkflowStep, ...]:
    return (
        WorkflowStep(
            order=1,
            what_the_user_does="Sobe o histórico de vendas",
            what_the_llm_should_say="Confirmo o período coberto antes de projetar.",
        ),
    )


def _input_requirements() -> tuple[InputRequirement, ...]:
    return (
        InputRequirement(
            column="week",
            required=True,
            business_meaning="Semana da venda.",
            example="2026-03-02",
        ),
    )


def _playbook() -> tuple[InterpretationRule, ...]:
    return (
        InterpretationRule(
            observed_situation="Projeção estável e histórico curto",
            what_it_means="O modelo repete o nível recente, não detectou tendência.",
            what_to_recommend="Tratar como piso, não como previsão firme.",
        ),
    )


def _knowledge() -> ServiceKnowledge:
    return ServiceKnowledge(
        one_liner="Projeta a demanda das próximas semanas a partir do histórico.",
        what_it_does="Suaviza a série por média móvel e projeta o nível para frente.",
        problem_solved="O comprador decide reposição olhando só o último mês.",
        when_to_use=("Planejar compra de item com venda estável",),
        when_not_to_use=("Item novo, sem histórico — não há o que suavizar",),
        personas=(Persona(role="Comprador", pains=("Compro demais no pico e falto depois",)),),
        workflow=_workflow(),
        input_requirements=_input_requirements(),
        interpretation_playbook=_playbook(),
        common_misreadings=(),
        glossary=(Term(technical_term="média móvel", client_language="média das últimas semanas"),),
        limitations=("Não captura sazonalidade anual.",),
    )


def _model_description() -> ModelDescription:
    return ModelDescription(
        display_name="Média móvel simples de 4 semanas",
        family="time_series_forecast",
        paradigm="heuristic",
        objective="Projetar o nível de demanda das próximas semanas.",
        formulation="y(t+h) = média(y(t-3), y(t-2), y(t-1), y(t))",
        assumptions=(
            Assumption(
                statement="O nível recente se mantém no horizonte projetado.",
                violation_impact="Numa virada de tendência a projeção erra o sentido.",
                checked=False,
            ),
        ),
        hyperparameters={"window": 4},
        priors=(),
        not_designed_for=("prever ruptura causada por promoção",),
    )


def _data() -> DataProvenance:
    return DataProvenance(
        observation_count=104,
        granularity="week",
        period_covered=PeriodCovered(start=date(2024, 7, 1), end=date(2026, 6, 28)),
        entities=(EntitySummary(label="SKU", count=1),),
        filters_applied=(),
        known_gaps=(),
        quality_flags=(),
    )


def _artifacts() -> tuple[ArtifactDescription, ...]:
    return (
        ArtifactDescription(
            role="result_json",
            uri=AnyUrl(RESULT_URI),
            format="json",
            description="Projeção semanal para o horizonte pedido.",
            fields=(
                FieldDescription(
                    name="forecast",
                    type="number",
                    unit="unidades",
                    interval_level=None,
                    meaning="Demanda projetada na semana.",
                    read_as="Quanto esperar vender.",
                ),
            ),
        ),
    )


def _findings(horizon: int) -> tuple[Finding, ...]:
    return (
        Finding(
            id="level_001",
            importance=1,
            statement=f"A demanda projetada para as próximas {horizon} semanas fica em 120/semana.",
            quantity=Quantity(value=120.0, unit="unidades"),
            uncertainty=Uncertainty(kind="none", level=None, lower=None, upper=None),
            direction="stable",
            comparison_baseline=None,
            confidence="moderate",
            confidence_rationale="Baseado em 104 semanas sem quebra de nível.",
        ),
    )


def _diagnostics() -> tuple[Diagnostic, ...]:
    return (
        Diagnostic(
            name="weeks_observed",
            value=104.0,
            threshold=">= 52",
            status="pass",
            meaning="Histórico suficiente para estimar o nível.",
        ),
    )


def _caveats() -> tuple[Caveat, ...]:
    return (
        Caveat(
            severity="medium",
            statement="A média móvel reage devagar a mudanças de patamar.",
            do_not_conclude="Não trate a projeção como garantida numa virada de mercado.",
        ),
    )


def _reproducibility() -> Reproducibility:
    return Reproducibility(
        random_seed=None,
        compute_duration_seconds=0.4,
        input_digests=(InputDigest(role="timeseries", sha256="b" * 64),),
        library_versions={"statistics": "3.12"},
    )


def _guide(horizon: int) -> ExplanationGuide:
    return build_explanation_guide(
        audience="comprador sem formação estatística",
        summary_for_llm=f"O nível projetado para {horizon} semanas é estável em 120/semana.",
        what_was_solved="Quanto comprar para as próximas semanas.",
        must_not_claim=("que a projeção considera promoções futuras",),
        recommended_narrative_order=("level_001",),
    )


class MovingAverageBackend:
    """Projects demand and explains the projection, both in one run."""

    REQUIRED_INPUT_ROLES: ClassVar[frozenset[str]] = frozenset({"timeseries"})
    OPTIONAL_INPUT_ROLES: ClassVar[frozenset[str]] = frozenset()
    OUTPUT_ROLES: ClassVar[frozenset[str]] = frozenset({"result_json"})

    def run(
        self,
        *,
        inputs: LoadedInputs,
        parameters: MovingAverageParameters,
        context: ComputeContext,
    ) -> ComputeResult:
        del inputs
        readout = self._readout(parameters.horizon, context)
        return ComputeResult(
            by_role={
                "result_json": b'{"forecast": [120, 120, 120]}',
                READOUT_OUTPUT_ROLE: readout.model_dump_json().encode("utf-8"),
            },
            metadata={"window": 4},
        )

    @staticmethod
    def _readout(horizon: int, context: ComputeContext) -> ModelReadout:
        """Everything identifying the run comes from ``context``; nothing is invented."""
        return ModelReadout(
            generated_at=context.generated_at,
            request=context.readout_request(),
            service=context.readout_service(),
            service_knowledge=_knowledge(),
            model=_model_description(),
            data=_data(),
            artifacts=_artifacts(),
            findings=_findings(horizon),
            diagnostics=_diagnostics(),
            overall_quality=OverallQuality(status="pass", summary="Histórico completo."),
            caveats=_caveats(),
            explanation_guide=_guide(horizon),
            reproducibility=_reproducibility(),
        )
