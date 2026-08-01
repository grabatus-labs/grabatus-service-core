"""A complete, valid :class:`ModelReadout` for tests — services build on it.

Services consume this to exercise their pipeline without hand-writing the
26-field artifact. Every keyword passed to :func:`make_model_readout`
replaces one top-level field, so a test can make exactly the field it cares
about invalid and leave the rest coherent.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import AnyUrl

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
from grabatus_service_core.contract.readout.findings import Finding, Quantity, Uncertainty
from grabatus_service_core.contract.readout.guide import build_explanation_guide
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
from grabatus_service_core.contract.readout.root import (
    ModelReadout,
    ReadoutRequest,
    ReadoutService,
)

__all__ = ["make_model_readout"]


def _knowledge() -> ServiceKnowledge:
    return ServiceKnowledge(
        one_liner="Descobre quais produtos são comprados juntos.",
        what_it_does="Minera regras de associação e ranqueia por impacto financeiro.",
        problem_solved="O gerente monta combo por intuição.",
        when_to_use=("Definir planograma",),
        when_not_to_use=("Medir efeito causal — use teste A/B",),
        personas=(Persona(role="Gerente comercial", pains=("Não distingo afinidade real",)),),
        workflow=(
            WorkflowStep(
                order=1,
                what_the_user_does="Sobe a planilha",
                what_the_llm_should_say="Confirmo as colunas obrigatórias.",
            ),
        ),
        input_requirements=(
            InputRequirement(
                column="transaction_id",
                required=True,
                business_meaning="Identifica uma compra.",
                example="TX-000481",
            ),
        ),
        interpretation_playbook=(
            InterpretationRule(
                observed_situation="Lift alto e addressable baixo",
                what_it_means="Afinidade real em volume pequeno.",
                what_to_recommend="Testar em uma loja.",
            ),
        ),
        common_misreadings=(),
        glossary=(Term(technical_term="lift", client_language="mais que o acaso"),),
        limitations=("Não mede canibalização.",),
    )


def _model() -> ModelDescription:
    return ModelDescription(
        display_name="Regras de associação por FP-Growth",
        family="association_rules",
        paradigm="heuristic",
        objective="Encontrar produtos comprados juntos mais que o acaso.",
        formulation="lift(A→B) = P(B|A) / P(B)",
        assumptions=(
            Assumption(
                statement="Cada transaction_id é uma cesta única.",
                violation_impact="Cestas fragmentadas inflam o suporte.",
                checked=True,
            ),
        ),
        hyperparameters={"min_support": 0.005},
        priors=(),
        not_designed_for=("inferir causalidade",),
    )


def _artifacts() -> tuple[ArtifactDescription, ...]:
    return (
        ArtifactDescription(
            role="rules_json",
            uri=AnyUrl("gs://gbt-storage-grabatus/user_999/rules.json"),
            format="json",
            description="Regras ranqueadas por impacto financeiro.",
            fields=(
                FieldDescription(
                    name="lift",
                    type="number",
                    unit=None,
                    interval_level=None,
                    meaning="Razão entre frequência observada e esperada.",
                    read_as="Quantas vezes mais provável que o acaso.",
                ),
            ),
        ),
    )


def _request() -> ReadoutRequest:
    return ReadoutRequest(
        request_id="3f2b1c8e-0000-4000-8000-000000000000",
        result_id="res_0001",
        parameter_id="par_0001",
        tenant_id="grabatus",
        origin="web",
    )


def _data() -> DataProvenance:
    return DataProvenance(
        observation_count=142500,
        granularity="transaction",
        period_covered=PeriodCovered(start=date(2026, 1, 1), end=date(2026, 6, 30)),
        entities=(EntitySummary(label="SKU", count=8200),),
        filters_applied=(),
        known_gaps=(),
        quality_flags=(),
    )


def _findings() -> tuple[Finding, ...]:
    return (
        Finding(
            id="rule_001",
            importance=1,
            statement="Vinho premium e queijo importado aparecem juntos em 73% das cestas.",
            quantity=Quantity(value=18500.0, unit="BRL"),
            uncertainty=Uncertainty(kind="none", level=None, lower=None, upper=None),
            direction="increase",
            comparison_baseline=None,
            confidence="high",
            confidence_rationale="Baseado em 1.730 cestas.",
        ),
    )


def _diagnostics() -> tuple[Diagnostic, ...]:
    return (
        Diagnostic(
            name="data_quality_score",
            value=0.87,
            threshold="> 0.70",
            status="pass",
            meaning="Transações retidas e SKUs com preço e categoria.",
        ),
    )


def _caveats() -> tuple[Caveat, ...]:
    return (
        Caveat(
            severity="high",
            statement="Não separa período promocional de orgânico.",
            do_not_conclude="Não atribua a afinidade a preferência do cliente.",
        ),
    )


def _reproducibility() -> Reproducibility:
    return Reproducibility(
        random_seed=None,
        compute_duration_seconds=47.0,
        input_digests=(InputDigest(role="transactions", sha256="a" * 64),),
        library_versions={"mlxtend": "0.23.1"},
    )


def _defaults() -> dict[str, object]:
    return {
        "readout_version": "1.0",
        "generated_at": datetime(2026, 7, 31, 14, 3, 11, tzinfo=UTC),
        "request": _request(),
        "service": ReadoutService(name="grabatus-basketanalysis", version="1.0.0"),
        "service_knowledge": _knowledge(),
        "model": _model(),
        "data": _data(),
        "artifacts": _artifacts(),
        "findings": _findings(),
        "diagnostics": _diagnostics(),
        "overall_quality": OverallQuality(status="pass", summary="Dados suficientes."),
        "caveats": _caveats(),
        "explanation_guide": build_explanation_guide(
            audience="gerente comercial sem formação estatística",
            summary_for_llm="Três combos concentram a maior parte da oportunidade.",
            what_was_solved="Quais combos valem virar ação de gôndola.",
            must_not_claim=("que a associação prova causa",),
            recommended_narrative_order=("rule_001",),
        ),
        "reproducibility": _reproducibility(),
    }


def make_model_readout(**overrides: object) -> ModelReadout:
    """Build the canonical valid readout, replacing top-level fields with ``overrides``.

    Raises ``ValidationError`` when an override makes the readout invalid —
    that is the point: tests assert on the rejection.
    """
    return ModelReadout.model_validate(_defaults() | overrides)
