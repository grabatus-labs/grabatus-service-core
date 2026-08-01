# Fase 1 — Schema do `model_readout` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** criar o subpacote `contract/readout/` com todos os modelos Pydantic do artefato `model_readout`, incluindo o bloco `service_knowledge` e os guardrails com validação de prefixo, travados por snapshot, fixtures e fuzz.

**Architecture:** modelos Pydantic v2 imutáveis, sem I/O e sem dependência de nenhum outro subsistema além de `contract/`. Um arquivo por responsabilidade, para respeitar o limite de 500 linhas. Os guardrails anti-alucinação são constante de módulo validada por prefixo — um serviço acrescenta regras, e não tem mecanismo para remover as quatro básicas. O snapshot de JSON Schema segue o mecanismo já existente em `tests/contract_compatibility/`, estendido para uma pasta `v1.1/`.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Atheris (fuzz, Linux-only), mypy --strict, ruff.

**Spec de origem:** `docs/superpowers/specs/2026-07-31-model-readout-unificado-design.md`, §8 item 1.

## Global Constraints

Valores copiados da spec e do `CLAUDE.md` do repo. Valem para toda tarefa.

- Todo modelo: `model_config = ConfigDict(extra="forbid", frozen=True)`.
- Coleções em modelos são `tuple[...]`, nunca `list[...]` — `frozen=True` só é real com contêiner imutável.
- Toda coleção tem `max_length` explícito. Nenhuma pode crescer com o tamanho da entrada (spec §4.3).
- Enums fechados como `Literal`, seguindo `contract/io_spec.py`. **Nomes de campo e valores de enum em inglês**; apenas o conteúdo preenchido pelo serviço é PT-BR.
- Funções: máximo 20 linhas. Arquivos: máximo 500 linhas.
- `mypy --strict` é gate. Sem `Any`, sem função sem tipo.
- Mensagem de erro inclui o valor ofensivo: `f"... got {value!r}"`.
- Cobertura 100% linha + branch. `# pragma: no cover` exige justificativa inline.
- Rodar `uv run ruff format && uv run ruff check --fix` antes de cada commit.
- Conventional commits com `refs #2`. Branch `feat-model-readout-contract`, já ativa.
- **Fora do escopo desta fase:** o passo `VALIDATE_READOUT` no runner (Fase 2); o protocolo `"1.1"` e `_MAX_OUTPUTS` (Fase 3); `docs/model_readout_spec.md` e `integration_contract.md` (Fase 4). Não tocar em `runner/`, `contract/version.py` nem `contract/base.py`.

---

### Task 1: Enums fechados do readout

Todos os vocabulários fechados num arquivo só, porque são importados por quase todos os demais módulos e defini-los localmente criaria ciclo de import.

**Files:**
- Create: `src/grabatus_service_core/contract/readout/__init__.py`
- Create: `src/grabatus_service_core/contract/readout/enums.py`
- Test: `tests/unit/contract/readout/__init__.py`
- Test: `tests/unit/contract/readout/test_enums.py`

**Interfaces:**
- Consumes: nada.
- Produces: `ModelFamily`, `Paradigm`, `UncertaintyKind`, `Direction`, `Confidence`, `DiagnosticStatus`, `QualityStatus`, `Severity` — todos aliases `Literal[...]`. Também `READOUT_OUTPUT_ROLE: Final[str] = "model_readout"` e `READOUT_VERSION: Final[str] = "1.0"`.

- [ ] **Step 1: Write the failing test**

`tests/unit/contract/readout/__init__.py` fica vazio (pacote de teste, como os demais).

```python
# tests/unit/contract/readout/test_enums.py
"""The readout vocabularies are closed sets, pinned here against drift."""

from __future__ import annotations

from typing import get_args

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


def test_output_role_is_the_fixed_contract_role() -> None:
    assert READOUT_OUTPUT_ROLE == "model_readout"


def test_readout_version_is_pinned() -> None:
    assert READOUT_VERSION == "1.0"


def test_model_family_covers_every_grabatus_service_kind() -> None:
    assert set(get_args(ModelFamily)) == {
        "time_series_forecast",
        "bayesian_inference",
        "ab_test",
        "optimization",
        "classification",
        "regression",
        "clustering",
        "survival_analysis",
        "simulation",
        "association_rules",
    }


def test_paradigm_values() -> None:
    assert set(get_args(Paradigm)) == {
        "bayesian",
        "frequentist",
        "optimization",
        "heuristic",
        "ml_supervised",
        "ml_unsupervised",
    }


def test_uncertainty_kind_includes_none_for_deterministic_results() -> None:
    """Association rules have no interval — the readout must still be expressible."""
    assert "none" in get_args(UncertaintyKind)


def test_direction_values() -> None:
    assert set(get_args(Direction)) == {"increase", "decrease", "stable", "not_applicable"}


def test_confidence_values() -> None:
    assert set(get_args(Confidence)) == {"high", "moderate", "low"}


def test_status_vocabularies_share_the_same_three_levels() -> None:
    assert set(get_args(DiagnosticStatus)) == {"pass", "warn", "fail"}
    assert set(get_args(QualityStatus)) == {"pass", "warn", "fail"}


def test_severity_values() -> None:
    assert set(get_args(Severity)) == {"high", "medium", "low"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/contract/readout/test_enums.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'grabatus_service_core.contract.readout'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/grabatus_service_core/contract/readout/__init__.py
"""model_readout: the artefact that explains a service and its result."""

from __future__ import annotations
```

```python
# src/grabatus_service_core/contract/readout/enums.py
"""Closed vocabularies used across the readout models."""

from __future__ import annotations

from typing import Final, Literal

READOUT_OUTPUT_ROLE: Final[str] = "model_readout"
READOUT_VERSION: Final[str] = "1.0"

ModelFamily = Literal[
    "time_series_forecast",
    "bayesian_inference",
    "ab_test",
    "optimization",
    "classification",
    "regression",
    "clustering",
    "survival_analysis",
    "simulation",
    "association_rules",
]

Paradigm = Literal[
    "bayesian",
    "frequentist",
    "optimization",
    "heuristic",
    "ml_supervised",
    "ml_unsupervised",
]

UncertaintyKind = Literal[
    "credible_interval",
    "confidence_interval",
    "prediction_interval",
    "standard_error",
    "none",
]

Direction = Literal["increase", "decrease", "stable", "not_applicable"]
Confidence = Literal["high", "moderate", "low"]
DiagnosticStatus = Literal["pass", "warn", "fail"]
QualityStatus = Literal["pass", "warn", "fail"]
Severity = Literal["high", "medium", "low"]
```

`association_rules` foi acrescentado à `ModelFamily` da spec de 27/07 porque o serviço piloto da Fase 5 é o `basketAnalysis`, e sem esse valor ele não teria família válida.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/contract/readout/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/grabatus_service_core/contract/readout/ tests/unit/contract/readout/
git commit -m "feat: add closed vocabularies for the model readout

Vocabulário aberto em campo que a IA lê vira string livre, e string
livre vira interpretação divergente entre serviços.

refs #2"
```

---

### Task 2: `service_knowledge` — a documentação estática do serviço

O bloco que responde o que o serviço é, para quem serve e como se explica a saída. É o que a spec de 27/07 não tinha.

**Files:**
- Create: `src/grabatus_service_core/contract/readout/knowledge.py`
- Test: `tests/unit/contract/readout/test_knowledge.py`

**Interfaces:**
- Consumes: nada.
- Produces: `Persona`, `WorkflowStep`, `InputRequirement`, `InterpretationRule`, `Misreading`, `Term`, `ServiceKnowledge`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/contract/readout/test_knowledge.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/contract/readout/test_knowledge.py -v`
Expected: FAIL com `ModuleNotFoundError: ... readout.knowledge`

- [ ] **Step 3: Write minimal implementation**

```python
# src/grabatus_service_core/contract/readout/knowledge.py
"""ServiceKnowledge: what the service is, independent of any single run.

Static per service version, embedded verbatim into every readout. It is
what lets an LLM answer "what is this and who is it for" without
inventing the context around the numbers.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

_FROZEN = ConfigDict(extra="forbid", frozen=True)

_MAX_ITEMS = 30
_MAX_WORKFLOW_STEPS = 12
_MAX_COLUMNS = 64


class Persona(BaseModel):
    """Who uses the service, and what hurts today."""

    model_config = _FROZEN

    role: str = Field(min_length=1, max_length=200)
    pains: tuple[str, ...] = Field(min_length=1, max_length=_MAX_ITEMS)


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

    when_to_use: tuple[str, ...] = Field(min_length=1, max_length=_MAX_ITEMS)
    when_not_to_use: tuple[str, ...] = Field(min_length=1, max_length=_MAX_ITEMS)

    personas: tuple[Persona, ...] = Field(min_length=1, max_length=_MAX_ITEMS)
    workflow: tuple[WorkflowStep, ...] = Field(min_length=1, max_length=_MAX_WORKFLOW_STEPS)
    input_requirements: tuple[InputRequirement, ...] = Field(
        min_length=1, max_length=_MAX_COLUMNS
    )

    interpretation_playbook: tuple[InterpretationRule, ...] = Field(
        min_length=1, max_length=_MAX_ITEMS
    )
    common_misreadings: tuple[Misreading, ...] = Field(default=(), max_length=_MAX_ITEMS)
    glossary: tuple[Term, ...] = Field(min_length=1, max_length=_MAX_ITEMS)
    limitations: tuple[str, ...] = Field(min_length=1, max_length=_MAX_ITEMS)

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/contract/readout/ -v --cov=grabatus_service_core.contract.readout --cov-branch`
Expected: PASS, cobertura 100%

- [ ] **Step 5: Commit**

```bash
git add src/grabatus_service_core/contract/readout/knowledge.py tests/unit/contract/readout/test_knowledge.py
git commit -m "feat: add the service_knowledge block to the readout

O readout descrevia bem a execução e não dizia em lugar nenhum o que o
serviço é nem para quem serve. A LLM preenchia esse contexto sozinha.

refs #2"
```

---

### Task 3: `explanation_guide` e os guardrails imponíveis

A peça de maior valor do contrato. O texto-base é constante de módulo, e um validador de prefixo transforma a garantia anti-alucinação de convenção em contrato.

**Files:**
- Create: `src/grabatus_service_core/contract/readout/guide.py`
- Test: `tests/unit/contract/readout/test_guide.py`

**Interfaces:**
- Consumes: nada.
- Produces: `BASE_GUARDRAILS: Final[tuple[str, ...]]` (4 itens), `ExplanationGuide`, `build_explanation_guide(*, audience, summary_for_llm, what_was_solved, must_not_claim, recommended_narrative_order=(), additional_guardrails=()) -> ExplanationGuide`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/contract/readout/test_guide.py
"""The base guardrails survive any service's customisation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.guide import (
    BASE_GUARDRAILS,
    ExplanationGuide,
    build_explanation_guide,
)


def _guide(**overrides: object) -> ExplanationGuide:
    payload: dict[str, object] = {
        "audience": "gerente comercial sem formação estatística",
        "summary_for_llm": "Três combos concentram 60% da oportunidade estimada.",
        "what_was_solved": "Quais combos valem virar ação de gôndola.",
        "must_not_claim": ("que a associação prova causa",),
        "recommended_narrative_order": ("rule_001",),
        "guardrails": BASE_GUARDRAILS,
    }
    payload.update(overrides)
    return ExplanationGuide(**payload)  # type: ignore[arg-type]


def test_base_has_exactly_four_rules() -> None:
    assert len(BASE_GUARDRAILS) == 4


def test_base_covers_the_four_mandates() -> None:
    joined = " ".join(BASE_GUARDRAILS).lower()
    assert "não extrapole" in joined
    assert "não sabe" in joined
    assert "grabatus" in joined
    assert "não recalcule" in joined
    assert "sugestão de melhoria" in joined


def test_guide_accepts_the_exact_base() -> None:
    assert _guide().guardrails == BASE_GUARDRAILS


def test_guide_accepts_base_plus_service_rules() -> None:
    extended = (*BASE_GUARDRAILS, "Nunca cite um SKU ausente de findings[].")
    assert _guide(guardrails=extended).guardrails[-1].startswith("Nunca cite")


def test_guide_rejects_a_dropped_base_rule() -> None:
    with pytest.raises(ValidationError, match="must start with the SDK base guardrails"):
        _guide(guardrails=BASE_GUARDRAILS[:3])


def test_guide_rejects_a_rewritten_base_rule() -> None:
    tampered = ("Pode estimar quando fizer sentido.", *BASE_GUARDRAILS[1:])
    with pytest.raises(ValidationError, match="must start with the SDK base guardrails"):
        _guide(guardrails=tampered)


def test_guide_rejects_reordered_base_rules() -> None:
    reordered = (BASE_GUARDRAILS[1], BASE_GUARDRAILS[0], *BASE_GUARDRAILS[2:])
    with pytest.raises(ValidationError, match="must start with the SDK base guardrails"):
        _guide(guardrails=reordered)


def test_guide_rejects_service_rules_before_the_base() -> None:
    """Prefix, not membership — order carries meaning for a reader."""
    prefixed = ("Regra do serviço primeiro.", *BASE_GUARDRAILS)
    with pytest.raises(ValidationError, match="must start with the SDK base guardrails"):
        _guide(guardrails=prefixed)


def test_builder_fills_the_base_automatically() -> None:
    guide = build_explanation_guide(
        audience="gerente comercial",
        summary_for_llm="Resumo.",
        what_was_solved="A dor endereçada.",
        must_not_claim=("que prova causa",),
    )
    assert guide.guardrails == BASE_GUARDRAILS


def test_builder_appends_service_rules_after_the_base() -> None:
    guide = build_explanation_guide(
        audience="gerente comercial",
        summary_for_llm="Resumo.",
        what_was_solved="A dor endereçada.",
        must_not_claim=("que prova causa",),
        additional_guardrails=("Nunca cite um SKU ausente de findings[].",),
    )
    assert guide.guardrails[:4] == BASE_GUARDRAILS
    assert guide.guardrails[4].startswith("Nunca cite")


def test_must_not_claim_is_mandatory_and_non_empty() -> None:
    """The difference between a result and an overclaim."""
    with pytest.raises(ValidationError):
        _guide(must_not_claim=())


def test_recommended_narrative_order_may_be_empty() -> None:
    assert _guide(recommended_narrative_order=()).recommended_narrative_order == ()


def test_guide_is_frozen() -> None:
    guide = _guide()
    with pytest.raises(ValidationError):
        guide.audience = "outro"  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/contract/readout/test_guide.py -v`
Expected: FAIL com `ModuleNotFoundError: ... readout.guide`

- [ ] **Step 3: Write minimal implementation**

```python
# src/grabatus_service_core/contract/readout/guide.py
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
    guardrails: tuple[str, ...] = Field(
        min_length=len(BASE_GUARDRAILS), max_length=_MAX_GUARDRAILS
    )

    @field_validator("guardrails")
    @classmethod
    def _starts_with_the_base(cls, rules: tuple[str, ...]) -> tuple[str, ...]:
        """Prefix, not membership: order and wording both carry meaning."""
        prefix = rules[: len(BASE_GUARDRAILS)]
        if prefix != BASE_GUARDRAILS:
            raise ValueError(
                f"guardrails must start with the SDK base guardrails, got {prefix!r}"
            )
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/contract/readout/ -v --cov=grabatus_service_core.contract.readout --cov-branch`
Expected: PASS, cobertura 100%

- [ ] **Step 5: Commit**

```bash
git add src/grabatus_service_core/contract/readout/guide.py tests/unit/contract/readout/test_guide.py
git commit -m "feat: make the anti-hallucination guardrails enforceable

Garantia que depende de o serviço lembrar de copiá-la não é garantia.
O validador de prefixo faz um readout adulterado falhar no schema.

refs #2"
```

---

### Task 4: `model` — o que o modelo assume, estima e não serve para responder

**Files:**
- Create: `src/grabatus_service_core/contract/readout/model.py`
- Test: `tests/unit/contract/readout/test_model.py`

**Interfaces:**
- Consumes: `ModelFamily`, `Paradigm` (Tarefa 1).
- Produces: `Assumption`, `Prior`, `HyperparameterValue`, `ModelDescription`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/contract/readout/test_model.py
"""ModelDescription carries method, not just name."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.model import Assumption, ModelDescription, Prior


def _model(**overrides: object) -> ModelDescription:
    payload: dict[str, object] = {
        "display_name": "Regras de associação por FP-Growth",
        "family": "association_rules",
        "paradigm": "heuristic",
        "objective": "Encontrar produtos comprados juntos mais que o acaso.",
        "formulation": "lift(A→B) = P(B|A) / P(B)",
        "assumptions": (
            Assumption(
                statement="Cada transaction_id representa uma cesta única.",
                violation_impact="Cestas fragmentadas inflam o suporte artificialmente.",
                checked=True,
            ),
        ),
        "hyperparameters": {"min_support": 0.005, "capture_rate": 0.10},
        "priors": (),
        "not_designed_for": ("inferir causalidade entre os itens da regra",),
    }
    payload.update(overrides)
    return ModelDescription(**payload)  # type: ignore[arg-type]


def test_complete_model_validates() -> None:
    assert _model().family == "association_rules"


def test_assumptions_are_mandatory() -> None:
    """A model with no stated assumption is a model nobody can challenge."""
    with pytest.raises(ValidationError):
        _model(assumptions=())


def test_not_designed_for_is_mandatory() -> None:
    with pytest.raises(ValidationError):
        _model(not_designed_for=())


def test_priors_may_be_empty_for_non_bayesian_models() -> None:
    assert _model().priors == ()


def test_formulation_is_optional() -> None:
    assert _model(formulation=None).formulation is None


def test_unknown_family_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _model(family="deep_learning")


def test_hyperparameters_reject_collections() -> None:
    """A nested array here would be raw data smuggled into the readout."""
    with pytest.raises(ValidationError):
        _model(hyperparameters={"samples": [1, 2, 3]})


def test_hyperparameters_accept_bool_int_float_str_and_none() -> None:
    model = _model(
        hyperparameters={"level": "both", "top_n": 20, "rate": 0.1, "flag": True, "window": None}
    )
    assert model.hyperparameters["top_n"] == 20


def test_model_is_frozen() -> None:
    model = _model()
    with pytest.raises(ValidationError):
        model.display_name = "outro"  # type: ignore[misc]


def test_prior_requires_rationale() -> None:
    with pytest.raises(ValidationError):
        Prior(parameter="alpha", distribution="Beta(1,1)", rationale="")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/contract/readout/test_model.py -v`
Expected: FAIL com `ModuleNotFoundError: ... readout.model`

- [ ] **Step 3: Write minimal implementation**

```python
# src/grabatus_service_core/contract/readout/model.py
"""ModelDescription: the method behind the numbers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from grabatus_service_core.contract.readout.enums import ModelFamily, Paradigm

_FROZEN = ConfigDict(extra="forbid", frozen=True)

_MAX_ITEMS = 30
_MAX_HYPERPARAMETERS = 50

# Scalars only: accepting a collection here would let raw data into the
# readout through the side door (spec §4.3).
HyperparameterValue = bool | int | float | str | None


class Assumption(BaseModel):
    """A stated assumption, with the cost of it being wrong."""

    model_config = _FROZEN

    statement: str = Field(min_length=1, max_length=500)
    violation_impact: str = Field(min_length=1, max_length=500)
    checked: bool


class Prior(BaseModel):
    """A prior distribution and why it was chosen."""

    model_config = _FROZEN

    parameter: str = Field(min_length=1, max_length=120)
    distribution: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=500)


class ModelDescription(BaseModel):
    """What was fitted, under what assumptions, and what it cannot answer."""

    model_config = _FROZEN

    display_name: str = Field(min_length=1, max_length=200)
    family: ModelFamily
    paradigm: Paradigm
    objective: str = Field(min_length=1, max_length=1000)
    formulation: str | None = Field(default=None, max_length=500)
    assumptions: tuple[Assumption, ...] = Field(min_length=1, max_length=_MAX_ITEMS)
    hyperparameters: dict[str, HyperparameterValue] = Field(max_length=_MAX_HYPERPARAMETERS)
    priors: tuple[Prior, ...] = Field(default=(), max_length=_MAX_ITEMS)
    not_designed_for: tuple[str, ...] = Field(min_length=1, max_length=_MAX_ITEMS)
```

Atenção ao executar: Pydantic coage tipos em união por ordem. Se `test_hyperparameters_reject_collections` passar mas `test_hyperparameters_accept_bool_int_float_str_and_none` devolver tipos inesperados (por exemplo `True` virando `1`), acrescentar `model_config = ConfigDict(..., strict=True)` apenas nesse modelo, ou trocar a união por `StrictBool | StrictInt | StrictFloat | StrictStr | None`. A segunda opção é a preferida — mantém o resto do repo sem modo estrito.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/contract/readout/ -v --cov=grabatus_service_core.contract.readout --cov-branch`
Expected: PASS, cobertura 100%

- [ ] **Step 5: Commit**

```bash
git add src/grabatus_service_core/contract/readout/model.py tests/unit/contract/readout/test_model.py
git commit -m "feat: describe the fitted model in the readout

Premissa não declarada é premissa que ninguém consegue contestar — e
que a IA apresenta como se fosse fato verificado.

refs #2"
```

---

### Task 5: `data` — proveniência, filtros, lacunas e degradações

**Files:**
- Create: `src/grabatus_service_core/contract/readout/data.py`
- Test: `tests/unit/contract/readout/test_data.py`

**Interfaces:**
- Consumes: nada.
- Produces: `PeriodCovered`, `EntitySummary`, `DataProvenance`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/contract/readout/test_data.py
"""DataProvenance separates what was removed, what was missing, and what was assumed."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.data import (
    DataProvenance,
    EntitySummary,
    PeriodCovered,
)


def _provenance(**overrides: object) -> DataProvenance:
    payload: dict[str, object] = {
        "observation_count": 142500,
        "granularity": "transaction",
        "period_covered": PeriodCovered(start=date(2026, 1, 1), end=date(2026, 6, 30)),
        "entities": (EntitySummary(label="SKU", count=8200),),
        "filters_applied": ("Cestas com menos de 3 itens foram descartadas",),
        "known_gaps": ("Semanas 12–14 ausentes na origem",),
        "quality_flags": ("Margem não informada; usado o default de 20%",),
    }
    payload.update(overrides)
    return DataProvenance(**payload)  # type: ignore[arg-type]


def test_complete_provenance_validates() -> None:
    assert _provenance().observation_count == 142500


def test_period_end_must_not_precede_start() -> None:
    with pytest.raises(ValidationError, match="precedes"):
        PeriodCovered(start=date(2026, 6, 30), end=date(2026, 1, 1))


def test_period_may_be_a_single_day() -> None:
    same = date(2026, 6, 30)
    assert PeriodCovered(start=same, end=same).start == same


def test_period_covered_is_optional() -> None:
    """A service with no timestamp column still produces a valid readout."""
    assert _provenance(period_covered=None).period_covered is None


def test_observation_count_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        _provenance(observation_count=0)


def test_entities_are_mandatory() -> None:
    with pytest.raises(ValidationError):
        _provenance(entities=())


def test_the_three_note_lists_may_each_be_empty() -> None:
    clean = _provenance(filters_applied=(), known_gaps=(), quality_flags=())
    assert clean.quality_flags == ()


def test_provenance_is_frozen() -> None:
    provenance = _provenance()
    with pytest.raises(ValidationError):
        provenance.observation_count = 1  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/contract/readout/test_data.py -v`
Expected: FAIL com `ModuleNotFoundError: ... readout.data`

- [ ] **Step 3: Write minimal implementation**

```python
# src/grabatus_service_core/contract/readout/data.py
"""DataProvenance: what went into the fit, and what did not.

Three note lists, deliberately distinct: ``filters_applied`` is what the
service removed on purpose, ``known_gaps`` is what was missing at the
source, and ``quality_flags`` is what the service had to assume in order
to run at all. Collapsing them into one field would hide which of the
three a given caveat came from.
"""

from __future__ import annotations

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

_FROZEN = ConfigDict(extra="forbid", frozen=True)

_MAX_ITEMS = 30


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
    entities: tuple[EntitySummary, ...] = Field(min_length=1, max_length=_MAX_ITEMS)
    filters_applied: tuple[str, ...] = Field(default=(), max_length=_MAX_ITEMS)
    known_gaps: tuple[str, ...] = Field(default=(), max_length=_MAX_ITEMS)
    quality_flags: tuple[str, ...] = Field(default=(), max_length=_MAX_ITEMS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/contract/readout/ -v --cov=grabatus_service_core.contract.readout --cov-branch`
Expected: PASS, cobertura 100%

- [ ] **Step 5: Commit**

```bash
git add src/grabatus_service_core/contract/readout/data.py tests/unit/contract/readout/test_data.py
git commit -m "feat: describe data provenance in the readout

Filtro deliberado, lacuna de origem e premissa forçada têm consequências
diferentes para quem lê o número. Um campo só os confundiria.

refs #2"
```

---

### Task 6: `artifacts` — o dicionário de dados

O que permite a uma IA abrir o JSON numérico cru e saber que `yhat_lower` é limite inferior de um intervalo de 90%, não um mínimo histórico.

**Files:**
- Create: `src/grabatus_service_core/contract/readout/artifacts.py`
- Test: `tests/unit/contract/readout/test_artifacts.py`

**Interfaces:**
- Consumes: `DataFormat` de `contract/io_spec.py` (já existe).
- Produces: `FieldType`, `FieldDescription`, `ArtifactDescription`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/contract/readout/test_artifacts.py
"""ArtifactDescription is a data dictionary, not prose."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.artifacts import (
    ArtifactDescription,
    FieldDescription,
)


def _field(**overrides: object) -> FieldDescription:
    payload: dict[str, object] = {
        "name": "lift",
        "type": "number",
        "unit": None,
        "interval_level": None,
        "meaning": "Razão entre a frequência conjunta observada e a esperada sob independência.",
        "read_as": "Quantas vezes mais provável que o acaso.",
    }
    payload.update(overrides)
    return FieldDescription(**payload)  # type: ignore[arg-type]


def _artifact(**overrides: object) -> ArtifactDescription:
    payload: dict[str, object] = {
        "role": "rules_json",
        "uri": "gs://gbt-storage-grabatus/user_999/rules.json",
        "format": "json",
        "description": "Regras de associação ranqueadas por impacto financeiro.",
        "fields": (_field(),),
    }
    payload.update(overrides)
    return ArtifactDescription(**payload)  # type: ignore[arg-type]


def test_complete_artifact_validates() -> None:
    assert _artifact().role == "rules_json"


def test_role_follows_the_contract_role_pattern() -> None:
    """Same pattern as InputSpec/OutputSpec roles in contract/io_spec.py."""
    with pytest.raises(ValidationError):
        _artifact(role="Rules JSON")


def test_fields_are_mandatory() -> None:
    """An artefact with no field dictionary is opaque again."""
    with pytest.raises(ValidationError):
        _artifact(fields=())


def test_interval_level_must_be_a_probability() -> None:
    with pytest.raises(ValidationError):
        _field(interval_level=1.5)


def test_interval_level_accepts_a_valid_probability() -> None:
    assert _field(interval_level=0.9).interval_level == 0.9


def test_field_type_is_a_closed_vocabulary() -> None:
    with pytest.raises(ValidationError):
        _field(type="dataframe")


def test_read_as_is_mandatory() -> None:
    """`meaning` is technical; `read_as` is the sentence the client hears."""
    with pytest.raises(ValidationError):
        _field(read_as="")


def test_artifact_is_frozen() -> None:
    artifact = _artifact()
    with pytest.raises(ValidationError):
        artifact.role = "outro"  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/contract/readout/test_artifacts.py -v`
Expected: FAIL com `ModuleNotFoundError: ... readout.artifacts`

- [ ] **Step 3: Write minimal implementation**

```python
# src/grabatus_service_core/contract/readout/artifacts.py
"""ArtifactDescription: a data dictionary for each numeric artefact.

The readout does not carry the numbers. It carries what each column of
each artefact means, so that reading the raw file does not require
guessing.
"""

from __future__ import annotations

from typing import Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field

from grabatus_service_core.contract.io_spec import DataFormat

_FROZEN = ConfigDict(extra="forbid", frozen=True)

# Mirrors _ROLE_PATTERN in contract/io_spec.py. Duplicated rather than
# imported to keep the readout subpackage free of private cross-imports.
_ROLE_PATTERN = r"^[a-z][a-z0-9_]*$"
_MAX_FIELDS = 100

FieldType = Literal["number", "integer", "string", "boolean", "date", "datetime"]


class FieldDescription(BaseModel):
    """One column of one artefact, in technical and plain terms."""

    model_config = _FROZEN

    name: str = Field(min_length=1, max_length=120)
    type: FieldType
    unit: str | None = Field(default=None, max_length=64)
    interval_level: float | None = Field(default=None, gt=0.0, lt=1.0)
    meaning: str = Field(min_length=1, max_length=500)
    read_as: str = Field(min_length=1, max_length=500)


class ArtifactDescription(BaseModel):
    """One numeric artefact the service wrote, and its field dictionary."""

    model_config = _FROZEN

    role: str = Field(min_length=1, max_length=32, pattern=_ROLE_PATTERN)
    uri: AnyUrl
    format: DataFormat
    description: str = Field(min_length=1, max_length=500)
    fields: tuple[FieldDescription, ...] = Field(min_length=1, max_length=_MAX_FIELDS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/contract/readout/ -v --cov=grabatus_service_core.contract.readout --cov-branch`
Expected: PASS, cobertura 100%

- [ ] **Step 5: Commit**

```bash
git add src/grabatus_service_core/contract/readout/artifacts.py tests/unit/contract/readout/test_artifacts.py
git commit -m "feat: add the artefact field dictionary to the readout

Sem dicionário, abrir o JSON cru exige adivinhar se yhat_lower é limite
de intervalo ou mínimo histórico. As duas leituras levam a decisões
opostas.

refs #2"
```

---

### Task 7: `findings` — conclusão com magnitude e incerteza separadas

**Files:**
- Create: `src/grabatus_service_core/contract/readout/findings.py`
- Test: `tests/unit/contract/readout/test_findings.py`

**Interfaces:**
- Consumes: `UncertaintyKind`, `Direction`, `Confidence` (Tarefa 1).
- Produces: `Quantity`, `Uncertainty`, `ComparisonBaseline`, `Finding`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/contract/readout/test_findings.py
"""Findings are structured so the LLM narrates instead of computing."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.findings import (
    ComparisonBaseline,
    Finding,
    Quantity,
    Uncertainty,
)


def _finding(**overrides: object) -> Finding:
    payload: dict[str, object] = {
        "id": "rule_001",
        "importance": 1,
        "statement": "Quem leva vinho premium leva queijo importado em 73% das cestas.",
        "quantity": Quantity(value=18500.0, unit="BRL"),
        "uncertainty": Uncertainty(kind="none", level=None, lower=None, upper=None),
        "direction": "increase",
        "comparison_baseline": ComparisonBaseline(label="cestas sem a ação", value=0.0),
        "confidence": "high",
        "confidence_rationale": "Baseado em 1.730 cestas observadas.",
    }
    payload.update(overrides)
    return Finding(**payload)  # type: ignore[arg-type]


def test_complete_finding_validates() -> None:
    assert _finding().id == "rule_001"


def test_id_follows_a_referenceable_pattern() -> None:
    """`recommended_narrative_order` points at these ids."""
    with pytest.raises(ValidationError):
        _finding(id="rule 001")


def test_importance_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        _finding(importance=0)


def test_interval_requires_both_bounds() -> None:
    with pytest.raises(ValidationError, match="lower and upper"):
        Uncertainty(kind="credible_interval", level=0.9, lower=41100.0, upper=None)


def test_interval_requires_a_level() -> None:
    with pytest.raises(ValidationError, match="requires a level"):
        Uncertainty(kind="credible_interval", level=None, lower=41100.0, upper=56800.0)


def test_interval_upper_must_not_precede_lower() -> None:
    with pytest.raises(ValidationError, match="precedes"):
        Uncertainty(kind="credible_interval", level=0.9, lower=56800.0, upper=41100.0)


def test_kind_none_forbids_bounds() -> None:
    """A deterministic result claiming an interval would be a fabricated one."""
    with pytest.raises(ValidationError, match="forbids bounds"):
        Uncertainty(kind="none", level=None, lower=1.0, upper=2.0)


def test_kind_none_is_valid_without_bounds() -> None:
    assert Uncertainty(kind="none", level=None, lower=None, upper=None).kind == "none"


def test_standard_error_needs_no_bounds() -> None:
    error = Uncertainty(kind="standard_error", level=None, lower=None, upper=None)
    assert error.kind == "standard_error"


def test_comparison_baseline_is_optional() -> None:
    assert _finding(comparison_baseline=None).comparison_baseline is None


def test_confidence_rationale_is_mandatory() -> None:
    """A confidence level with no reason is an opinion wearing a number."""
    with pytest.raises(ValidationError):
        _finding(confidence_rationale="")


def test_finding_is_frozen() -> None:
    finding = _finding()
    with pytest.raises(ValidationError):
        finding.statement = "outro"  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/contract/readout/test_findings.py -v`
Expected: FAIL com `ModuleNotFoundError: ... readout.findings`

- [ ] **Step 3: Write minimal implementation**

```python
# src/grabatus_service_core/contract/readout/findings.py
"""Finding: one conclusion, with its size and its uncertainty kept apart.

Value, unit, uncertainty and baseline are separate fields so the LLM
narrates them. It does not compute, round, or compare on its own.
"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from grabatus_service_core.contract.readout.enums import (
    Confidence,
    Direction,
    UncertaintyKind,
)

_FROZEN = ConfigDict(extra="forbid", frozen=True)

_ID_PATTERN = r"^[a-z][a-z0-9_]*$"
_INTERVAL_KINDS = frozenset(
    {"credible_interval", "confidence_interval", "prediction_interval"}
)


class Quantity(BaseModel):
    """The number itself, with its unit."""

    model_config = _FROZEN

    value: float
    unit: str = Field(min_length=1, max_length=64)


class Uncertainty(BaseModel):
    """How sure the number is, in the vocabulary of the method used."""

    model_config = _FROZEN

    kind: UncertaintyKind
    level: float | None = Field(default=None, gt=0.0, lt=1.0)
    lower: float | None = None
    upper: float | None = None

    @model_validator(mode="after")
    def _bounds_match_the_kind(self) -> Self:
        if self.kind in _INTERVAL_KINDS:
            return self._validated_interval()
        if self.kind == "none" and (self.lower is not None or self.upper is not None):
            raise ValueError(
                f"kind='none' forbids bounds, got lower={self.lower!r}, upper={self.upper!r}"
            )
        return self

    def _validated_interval(self) -> Self:
        if self.level is None:
            raise ValueError(f"kind={self.kind!r} requires a level, got None")
        if self.lower is None or self.upper is None:
            raise ValueError(
                f"kind={self.kind!r} requires lower and upper, "
                f"got lower={self.lower!r}, upper={self.upper!r}"
            )
        if self.upper < self.lower:
            raise ValueError(f"upper={self.upper!r} precedes lower={self.lower!r}")
        return self


class ComparisonBaseline(BaseModel):
    """What the finding is being compared against."""

    model_config = _FROZEN

    label: str = Field(min_length=1, max_length=200)
    value: float


class Finding(BaseModel):
    """One conclusion the service is willing to stand behind."""

    model_config = _FROZEN

    id: str = Field(min_length=1, max_length=64, pattern=_ID_PATTERN)
    importance: int = Field(ge=1, le=100)
    statement: str = Field(min_length=1, max_length=1000)
    quantity: Quantity
    uncertainty: Uncertainty
    direction: Direction
    comparison_baseline: ComparisonBaseline | None = None
    confidence: Confidence
    confidence_rationale: str = Field(min_length=1, max_length=500)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/contract/readout/ -v --cov=grabatus_service_core.contract.readout --cov-branch`
Expected: PASS, cobertura 100%

- [ ] **Step 5: Commit**

```bash
git add src/grabatus_service_core/contract/readout/findings.py tests/unit/contract/readout/test_findings.py
git commit -m "feat: structure findings so the LLM narrates instead of computing

Achado em prosa obriga a IA a extrair o número do texto. Extração é
cálculo, e cálculo é onde ela inventa.

refs #2"
```

---

### Task 8: `diagnostics`, `caveats` e `provenance`

Três arquivos pequenos com uma responsabilidade comum: dizer o quanto confiar e de onde veio.

**Files:**
- Create: `src/grabatus_service_core/contract/readout/diagnostics.py`
- Create: `src/grabatus_service_core/contract/readout/caveats.py`
- Create: `src/grabatus_service_core/contract/readout/provenance.py`
- Test: `tests/unit/contract/readout/test_diagnostics.py`
- Test: `tests/unit/contract/readout/test_caveats.py`
- Test: `tests/unit/contract/readout/test_provenance.py`

**Interfaces:**
- Consumes: `DiagnosticStatus`, `QualityStatus`, `Severity` (Tarefa 1).
- Produces: `Diagnostic`, `OverallQuality`, `Caveat`, `InputDigest`, `Reproducibility`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/contract/readout/test_diagnostics.py
"""Diagnostics carry the threshold, not just the number."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.diagnostics import Diagnostic, OverallQuality


def test_diagnostic_states_its_threshold_and_meaning() -> None:
    diagnostic = Diagnostic(
        name="data_quality_score",
        value=0.87,
        threshold="> 0.70",
        status="pass",
        meaning="Proporção de transações retidas e de SKUs com preço e categoria.",
    )
    assert diagnostic.status == "pass"


def test_diagnostic_meaning_is_mandatory() -> None:
    """A metric with no stated meaning is a number the LLM will guess about."""
    with pytest.raises(ValidationError):
        Diagnostic(name="r_hat_max", value=1.01, threshold="< 1.01", status="pass", meaning="")


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Diagnostic(name="x", value=1.0, threshold="< 2", status="unknown", meaning="m")


def test_overall_quality_summarises() -> None:
    quality = OverallQuality(status="warn", summary="Nenhuma regra superou os limiares.")
    assert quality.status == "warn"
```

```python
# tests/unit/contract/readout/test_caveats.py
"""A caveat pairs a limitation with the conclusion it forbids."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.caveats import Caveat


def test_caveat_pairs_statement_with_forbidden_conclusion() -> None:
    caveat = Caveat(
        severity="high",
        statement="A análise não separa período promocional de período orgânico.",
        do_not_conclude="Não atribua a afinidade observada a preferência do cliente.",
    )
    assert caveat.severity == "high"


def test_do_not_conclude_is_mandatory() -> None:
    """A caveat without it is a disclaimer nobody acts on."""
    with pytest.raises(ValidationError):
        Caveat(severity="low", statement="Alguma limitação.", do_not_conclude="")


def test_unknown_severity_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Caveat(severity="critical", statement="s", do_not_conclude="d")
```

```python
# tests/unit/contract/readout/test_provenance.py
"""Reproducibility pins what would be needed to rerun the fit."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.provenance import InputDigest, Reproducibility

_DIGEST = "a" * 64


def _reproducibility(**overrides: object) -> Reproducibility:
    payload: dict[str, object] = {
        "random_seed": 42,
        "compute_duration_seconds": 84.2,
        "input_digests": (InputDigest(role="transactions", sha256=_DIGEST),),
        "library_versions": {"mlxtend": "0.23.1", "pandas": "2.2.0"},
    }
    payload.update(overrides)
    return Reproducibility(**payload)  # type: ignore[arg-type]


def test_complete_reproducibility_validates() -> None:
    assert _reproducibility().random_seed == 42


def test_random_seed_is_optional_for_deterministic_methods() -> None:
    assert _reproducibility(random_seed=None).random_seed is None


def test_sha256_must_be_64_hex_characters() -> None:
    with pytest.raises(ValidationError):
        InputDigest(role="transactions", sha256="abc")


def test_sha256_rejects_non_hex_characters() -> None:
    with pytest.raises(ValidationError):
        InputDigest(role="transactions", sha256="z" * 64)


def test_duration_must_not_be_negative() -> None:
    with pytest.raises(ValidationError):
        _reproducibility(compute_duration_seconds=-1.0)


def test_library_versions_are_mandatory() -> None:
    with pytest.raises(ValidationError):
        _reproducibility(library_versions={})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/contract/readout/test_diagnostics.py tests/unit/contract/readout/test_caveats.py tests/unit/contract/readout/test_provenance.py -v`
Expected: FAIL com `ModuleNotFoundError` nos três módulos

- [ ] **Step 3: Write minimal implementation**

```python
# src/grabatus_service_core/contract/readout/diagnostics.py
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
```

```python
# src/grabatus_service_core/contract/readout/caveats.py
"""Caveat: a limitation paired with the conclusion it forbids."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from grabatus_service_core.contract.readout.enums import Severity


class Caveat(BaseModel):
    """A limitation stated together with what not to conclude from it.

    ``do_not_conclude`` is mandatory: a caveat without it is a disclaimer
    that changes nobody's reading.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    severity: Severity
    statement: str = Field(min_length=1, max_length=500)
    do_not_conclude: str = Field(min_length=1, max_length=500)
```

```python
# src/grabatus_service_core/contract/readout/provenance.py
"""Reproducibility: what would be needed to run this fit again."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

_FROZEN = ConfigDict(extra="forbid", frozen=True)

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_ROLE_PATTERN = r"^[a-z][a-z0-9_]*$"
_MAX_ITEMS = 20


class InputDigest(BaseModel):
    """Hash of one input, so the same run can be identified later."""

    model_config = _FROZEN

    role: str = Field(min_length=1, max_length=32, pattern=_ROLE_PATTERN)
    sha256: str = Field(pattern=_SHA256_PATTERN)


class Reproducibility(BaseModel):
    """Seed, timing, input hashes and library versions."""

    model_config = _FROZEN

    random_seed: int | None = None
    compute_duration_seconds: float = Field(ge=0.0)
    input_digests: tuple[InputDigest, ...] = Field(min_length=1, max_length=_MAX_ITEMS)
    library_versions: dict[str, str] = Field(min_length=1, max_length=_MAX_ITEMS)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/contract/readout/ -v --cov=grabatus_service_core.contract.readout --cov-branch`
Expected: PASS, cobertura 100%

- [ ] **Step 5: Commit**

```bash
git add src/grabatus_service_core/contract/readout/diagnostics.py \
        src/grabatus_service_core/contract/readout/caveats.py \
        src/grabatus_service_core/contract/readout/provenance.py \
        tests/unit/contract/readout/test_diagnostics.py \
        tests/unit/contract/readout/test_caveats.py \
        tests/unit/contract/readout/test_provenance.py
git commit -m "feat: add diagnostics, caveats and reproducibility to the readout

Ressalva sem 'não conclua que' é disclaimer que ninguém aplica.
Diagnóstico sem limiar é número que a IA julga por conta própria.

refs #2"
```

---

### Task 9: `ModelReadout` — a raiz, e a superfície pública

**Files:**
- Create: `src/grabatus_service_core/contract/readout/root.py`
- Modify: `src/grabatus_service_core/contract/readout/__init__.py`
- Create: `tests/unit/contract/readout/builders.py`
- Create: `tests/unit/contract/readout/conftest.py`
- Test: `tests/unit/contract/readout/test_root.py`

**Interfaces:**
- Consumes: tudo das Tarefas 1–8.
- Produces: `Origin`, `ReadoutRequest`, `ReadoutService`, `ModelReadout`; a função `build_valid_readout()` em `builders.py` e a fixture `valid_readout` que apenas a chama. A Tarefa 10 importa `build_valid_readout` para gerar as fixtures JSON — por isso é função, e não só fixture.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/contract/readout/builders.py
"""A minimal but complete readout, shared by unit tests and fixture generation."""

from __future__ import annotations

from datetime import UTC, date, datetime

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
            uri="gs://gbt-storage-grabatus/user_999/rules.json",
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


def build_valid_readout() -> ModelReadout:
    """The canonical valid readout used across tests and JSON fixtures."""
    return ModelReadout(
        readout_version="1.0",
        generated_at=datetime(2026, 7, 31, 14, 3, 11, tzinfo=UTC),
        request=ReadoutRequest(
            request_id="3f2b1c8e-0000-4000-8000-000000000000",
            result_id="res_0001",
            parameter_id="par_0001",
            tenant_id="grabatus",
            origin="web",
        ),
        service=ReadoutService(name="grabatus-basketanalysis", version="1.0.0"),
        service_knowledge=_knowledge(),
        model=_model(),
        data=DataProvenance(
            observation_count=142500,
            granularity="transaction",
            period_covered=PeriodCovered(start=date(2026, 1, 1), end=date(2026, 6, 30)),
            entities=(EntitySummary(label="SKU", count=8200),),
            filters_applied=(),
            known_gaps=(),
            quality_flags=(),
        ),
        artifacts=_artifacts(),
        findings=(
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
        ),
        diagnostics=(
            Diagnostic(
                name="data_quality_score",
                value=0.87,
                threshold="> 0.70",
                status="pass",
                meaning="Transações retidas e SKUs com preço e categoria.",
            ),
        ),
        overall_quality=OverallQuality(status="pass", summary="Dados suficientes."),
        caveats=(
            Caveat(
                severity="high",
                statement="Não separa período promocional de orgânico.",
                do_not_conclude="Não atribua a afinidade a preferência do cliente.",
            ),
        ),
        explanation_guide=build_explanation_guide(
            audience="gerente comercial sem formação estatística",
            summary_for_llm="Três combos concentram a maior parte da oportunidade.",
            what_was_solved="Quais combos valem virar ação de gôndola.",
            must_not_claim=("que a associação prova causa",),
            recommended_narrative_order=("rule_001",),
        ),
        reproducibility=Reproducibility(
            random_seed=None,
            compute_duration_seconds=47.0,
            input_digests=(InputDigest(role="transactions", sha256="a" * 64),),
            library_versions={"mlxtend": "0.23.1"},
        ),
    )
```

```python
# tests/unit/contract/readout/conftest.py
"""Fixtures for the readout unit tests."""

from __future__ import annotations

import pytest

from grabatus_service_core.contract.readout.root import ModelReadout
from tests.unit.contract.readout.builders import build_valid_readout


@pytest.fixture
def valid_readout() -> ModelReadout:
    return build_valid_readout()
```

```python
# tests/unit/contract/readout/test_root.py
"""ModelReadout: the whole artefact, and what it refuses."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.root import ModelReadout


def test_valid_readout_round_trips(valid_readout: ModelReadout) -> None:
    raw = valid_readout.model_dump_json()
    rebuilt = ModelReadout.model_validate_json(raw)
    assert rebuilt.service.name == "grabatus-basketanalysis"


def test_readout_embeds_the_service_documentation(valid_readout: ModelReadout) -> None:
    """Self-contained: the LLM needs nothing else to explain this."""
    assert valid_readout.service_knowledge.one_liner.startswith("Descobre")


def test_readout_carries_the_base_guardrails(valid_readout: ModelReadout) -> None:
    assert len(valid_readout.explanation_guide.guardrails) >= 4


def test_unknown_top_level_field_is_rejected(valid_readout: ModelReadout) -> None:
    payload = valid_readout.model_dump(mode="json")
    payload["raw_samples"] = [1, 2, 3]
    with pytest.raises(ValidationError):
        ModelReadout.model_validate(payload)


def test_service_version_must_be_semver(valid_readout: ModelReadout) -> None:
    payload = valid_readout.model_dump(mode="json")
    payload["service"]["version"] = "1.0"
    with pytest.raises(ValidationError):
        ModelReadout.model_validate(payload)


def test_readout_version_is_pinned(valid_readout: ModelReadout) -> None:
    payload = valid_readout.model_dump(mode="json")
    payload["readout_version"] = "2.0"
    with pytest.raises(ValidationError):
        ModelReadout.model_validate(payload)


def test_generated_at_must_be_timezone_aware(valid_readout: ModelReadout) -> None:
    payload = valid_readout.model_dump(mode="json")
    payload["generated_at"] = "2026-07-31T14:03:11"
    with pytest.raises(ValidationError, match="timezone"):
        ModelReadout.model_validate(payload)


def test_findings_may_be_empty(valid_readout: ModelReadout) -> None:
    """Zero findings is a legitimate outcome — and must stay explainable."""
    payload = valid_readout.model_dump(mode="json")
    payload["findings"] = []
    assert ModelReadout.model_validate(payload).findings == ()


def test_artifacts_are_mandatory(valid_readout: ModelReadout) -> None:
    payload = valid_readout.model_dump(mode="json")
    payload["artifacts"] = []
    with pytest.raises(ValidationError):
        ModelReadout.model_validate(payload)


def test_serialisation_preserves_accents(valid_readout: ModelReadout) -> None:
    raw = json.loads(valid_readout.model_dump_json())
    assert "não" in raw["explanation_guide"]["guardrails"][0]


def test_readout_is_frozen(valid_readout: ModelReadout) -> None:
    with pytest.raises(ValidationError):
        valid_readout.readout_version = "9.9"  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/contract/readout/test_root.py -v`
Expected: FAIL com `ModuleNotFoundError: ... readout.root`

- [ ] **Step 3: Write minimal implementation**

```python
# src/grabatus_service_core/contract/readout/root.py
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
    artifacts: tuple[ArtifactDescription, ...] = Field(
        min_length=1, max_length=_MAX_ARTIFACTS
    )

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
            raise ValueError(
                f"generated_at must carry a timezone, got {self.generated_at!r}"
            )
        return self
```

`_MAX_ARTIFACTS = 11` casa com o novo teto de outputs que a Fase 3 introduzirá (10 artefatos do serviço + o readout).

```python
# src/grabatus_service_core/contract/readout/__init__.py
"""model_readout: the artefact that explains a service and its result.

A Grabatus service is not finished when it returns the right number. It
is finished when an LLM can explain that number to the client without
inventing anything around it.
"""

from __future__ import annotations

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
from grabatus_service_core.contract.readout.enums import (
    READOUT_OUTPUT_ROLE,
    READOUT_VERSION,
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
    ModelDescription,
    Prior,
)
from grabatus_service_core.contract.readout.provenance import (
    InputDigest,
    Reproducibility,
)
from grabatus_service_core.contract.readout.root import (
    ModelReadout,
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
    "DataProvenance",
    "Diagnostic",
    "EntitySummary",
    "ExplanationGuide",
    "FieldDescription",
    "Finding",
    "InputDigest",
    "InputRequirement",
    "InterpretationRule",
    "Misreading",
    "ModelDescription",
    "ModelReadout",
    "OverallQuality",
    "PeriodCovered",
    "Persona",
    "Prior",
    "Quantity",
    "ReadoutRequest",
    "ReadoutService",
    "Reproducibility",
    "ServiceKnowledge",
    "Term",
    "Uncertainty",
    "WorkflowStep",
    "build_explanation_guide",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/contract/readout/ -v --cov=grabatus_service_core.contract.readout --cov-branch`
Expected: PASS, cobertura 100%

- [ ] **Step 5: Commit**

```bash
git add src/grabatus_service_core/contract/readout/root.py \
        src/grabatus_service_core/contract/readout/__init__.py \
        tests/unit/contract/readout/builders.py \
        tests/unit/contract/readout/conftest.py \
        tests/unit/contract/readout/test_root.py
git commit -m "feat: assemble the ModelReadout root model

Documentação e resultado num artefato só: a LLM não costura conhecimento
de um registro com números de outro, nem explica um resultado com a
documentação da versão errada.

refs #2"
```

---

### Task 10: Snapshot, fixtures e fuzz

A trava contra apodrecimento, no mesmo mecanismo já usado por `BaseServiceContract`.

**Files:**
- Modify: `scripts/update_schema_snapshots.py`
- Create: `tests/contract_compatibility/snapshots/v1.1/model_readout.schema.json`
- Create: `tests/contract_compatibility/fixtures/v1.1/readout/valid/basket_minimal.json`
- Create: `tests/contract_compatibility/fixtures/v1.1/readout/invalid/tampered_guardrails.json`
- Create: `tests/contract_compatibility/fixtures/v1.1/readout/invalid/missing_service_knowledge.json`
- Create: `tests/contract_compatibility/fixtures/v1.1/readout/invalid/naive_generated_at.json`
- Create: `tests/contract_compatibility/fixtures/v1.1/readout/invalid/interval_without_level.json`
- Create: `tests/contract_compatibility/test_readout_schema.py`
- Create: `tests/contract_compatibility/test_readout_fixtures.py`
- Create: `tests/fuzz/fuzz_readout_parser.py`
- Modify: `tests/fuzz/test_fuzz_harness_smoke.py`

**Interfaces:**
- Consumes: `ModelReadout` (Tarefa 9), `build_valid_readout` (Tarefa 9).
- Produces: nada consumido adiante; é a trava de CI.

- [ ] **Step 1: Write the failing tests**

```python
# tests/contract_compatibility/test_readout_schema.py
"""Snapshot test: the ModelReadout JSON Schema is byte-stable.

Any intentional change requires regenerating the snapshot via
``scripts/update_schema_snapshots.py``, which forces the reviewer to
acknowledge the schema change in the same pull request.
"""

from __future__ import annotations

import json
from pathlib import Path

from grabatus_service_core.contract.readout import ModelReadout

_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent / "snapshots" / "v1.1" / "model_readout.schema.json"
)


def test_model_readout_json_schema_matches_snapshot() -> None:
    expected = _SNAPSHOT_PATH.read_text(encoding="utf-8")
    actual = json.dumps(ModelReadout.model_json_schema(), indent=2, sort_keys=True) + "\n"

    assert actual == expected, (
        "ModelReadout JSON Schema drifted from snapshot. If the change is "
        "intentional, run `uv run python scripts/update_schema_snapshots.py` "
        "and commit."
    )
```

```python
# tests/contract_compatibility/test_readout_fixtures.py
"""Every JSON sample under fixtures/v1.1/readout behaves as labelled.

``valid/*.json`` must validate cleanly; ``invalid/*.json`` must raise.
Adding a sample is the canonical way to lock in a regression.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout import ModelReadout

_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "v1.1" / "readout"


def _collect(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.json"))


@pytest.mark.parametrize(
    "fixture_path", _collect(_FIXTURE_ROOT / "valid"), ids=lambda p: p.name
)
def test_valid_fixture_validates_cleanly(fixture_path: Path) -> None:
    ModelReadout.model_validate(json.loads(fixture_path.read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    "fixture_path", _collect(_FIXTURE_ROOT / "invalid"), ids=lambda p: p.name
)
def test_invalid_fixture_raises_validation_error(fixture_path: Path) -> None:
    with pytest.raises(ValidationError):
        ModelReadout.model_validate(json.loads(fixture_path.read_text(encoding="utf-8")))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/contract_compatibility/test_readout_schema.py tests/contract_compatibility/test_readout_fixtures.py -v`
Expected: FAIL — `FileNotFoundError` no snapshot; a coleta de fixtures devolve lista vazia

- [ ] **Step 3: Extend the snapshot script**

Substituir `scripts/update_schema_snapshots.py` inteiro por esta versão, que escreve os dois snapshots e mantém o bootstrap de `sys.path` existente:

```python
"""Regenerate the pinned JSON Schema snapshots under ``tests/contract_compatibility/snapshots/``.

Run this when (and only when) a contract is intentionally changed.
The CI test suite reads the snapshot files and fails on any drift.

Usage::

    uv run python scripts/update_schema_snapshots.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from grabatus_service_core.contract.readout import ModelReadout  # noqa: E402
from tests.contract_compatibility._harness import SnapshotContract  # noqa: E402

_SNAPSHOT_ROOT = _REPO_ROOT / "tests" / "contract_compatibility" / "snapshots"

_TARGETS: tuple[tuple[type[BaseModel], Path], ...] = (
    (SnapshotContract, _SNAPSHOT_ROOT / "v1.0" / "base_service_contract.schema.json"),
    (ModelReadout, _SNAPSHOT_ROOT / "v1.1" / "model_readout.schema.json"),
)


def _render_schema(model: type[BaseModel]) -> str:
    return json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    for model, path in _TARGETS:
        path.parent.mkdir(parents=True, exist_ok=True)
        rendered = _render_schema(model)
        path.write_text(rendered, encoding="utf-8")
        print(f"wrote {path} ({len(rendered)} bytes)")
    return 0


if __name__ == "__main__":  # pragma: no cover  # CLI entry only
    raise SystemExit(main())
```

- [ ] **Step 4: Generate the snapshot and the valid fixture**

```bash
uv run python scripts/update_schema_snapshots.py

mkdir -p tests/contract_compatibility/fixtures/v1.1/readout/valid
mkdir -p tests/contract_compatibility/fixtures/v1.1/readout/invalid

uv run python - <<'PY'
import json
from pathlib import Path

from tests.unit.contract.readout.builders import build_valid_readout

target = Path("tests/contract_compatibility/fixtures/v1.1/readout/valid/basket_minimal.json")
payload = build_valid_readout().model_dump(mode="json")
target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {target}")
PY
```

Gerar a fixture a partir de `build_valid_readout()` — e não escrevê-la à mão — é o que impede a fixture e os testes unitários de divergirem com o tempo.

- [ ] **Step 5: Write the four invalid fixtures**

Cada uma é a fixture válida com **uma** alteração:

```bash
uv run python - <<'PY'
import json
from pathlib import Path

root = Path("tests/contract_compatibility/fixtures/v1.1/readout")
base = json.loads((root / "valid" / "basket_minimal.json").read_text(encoding="utf-8"))


def write(name, mutate):
    payload = json.loads(json.dumps(base))
    mutate(payload)
    path = root / "invalid" / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path}")


write(
    "tampered_guardrails.json",
    lambda p: p["explanation_guide"]["guardrails"].__setitem__(
        0, "Pode estimar quando fizer sentido."
    ),
)
write("missing_service_knowledge.json", lambda p: p.pop("service_knowledge"))
write("naive_generated_at.json", lambda p: p.__setitem__("generated_at", "2026-07-31T14:03:11"))
write(
    "interval_without_level.json",
    lambda p: p["findings"][0].__setitem__(
        "uncertainty",
        {"kind": "credible_interval", "level": None, "lower": 1.0, "upper": 2.0},
    ),
)
PY
```

`tampered_guardrails.json` é a mais importante do conjunto: é a prova de que a garantia anti-alucinação falha no schema, e não só na intenção de quem escreveu o serviço.

- [ ] **Step 6: Write the fuzz harness and register it in the smoke test**

O harness segue exatamente o padrão de `tests/fuzz/fuzz_contract_parser.py` — `fuzz_one_input(data: bytes)` no nível do módulo, `atheris` importado apenas dentro de `main()` porque é Linux-only.

```python
# tests/fuzz/fuzz_readout_parser.py
"""Fuzz the ModelReadout JSON parser.

Run locally on Linux::

    uv run python tests/fuzz/fuzz_readout_parser.py -atheris_runs=10000

CI runs this for a 60-second budget on every push to ``main``.

Invariant: validating arbitrary bytes either succeeds (well-formed
readout) or raises ``ValidationError``. Any other exception is a
fuzz finding.
"""

from __future__ import annotations

import sys

from pydantic import ValidationError

from grabatus_service_core.contract.readout import ModelReadout


def fuzz_one_input(data: bytes) -> None:
    try:
        ModelReadout.model_validate_json(data)
    except ValidationError:
        return
    except (UnicodeDecodeError, ValueError):
        return


def main() -> None:  # pragma: no cover  # entry point only on Linux runners
    import atheris  # noqa: PLC0415  # atheris is Linux-only

    atheris.Setup(sys.argv, fuzz_one_input)
    atheris.Fuzz()


if __name__ == "__main__":  # pragma: no cover  # CLI guard
    main()
```

Registrar no smoke test, sem o qual `fuzz_one_input` nunca é executado e a cobertura de 100% falha. Em `tests/fuzz/test_fuzz_harness_smoke.py`, estender o import e acrescentar o caso:

```python
from tests.fuzz import fuzz_contract_parser, fuzz_pubsub_decoder, fuzz_readout_parser
```

```python
@pytest.mark.parametrize("payload", _FUZZ_SAMPLES)
def test_readout_fuzz_input_never_raises_unexpected(payload: bytes) -> None:
    fuzz_readout_parser.fuzz_one_input(payload)
```

- [ ] **Step 7: Run the full gate**

Run: `make check`
Expected: lint, `mypy --strict`, testes e security verdes; cobertura de `contract/readout/` em 100% linha + branch.

Verificar explicitamente que `tests/contract_compatibility/snapshots/v1.0/base_service_contract.schema.json` **não** aparece em `git status`. Esta fase não toca em `BaseServiceContract`; se o snapshot v1.0 mudou, algo saiu do escopo e deve ser revertido antes do commit.

- [ ] **Step 8: Commit**

```bash
git add scripts/update_schema_snapshots.py \
        tests/contract_compatibility/snapshots/v1.1/ \
        tests/contract_compatibility/fixtures/v1.1/ \
        tests/contract_compatibility/test_readout_schema.py \
        tests/contract_compatibility/test_readout_fixtures.py \
        tests/fuzz/fuzz_readout_parser.py \
        tests/fuzz/test_fuzz_harness_smoke.py
git commit -m "test: lock the readout schema against silent drift

Contrato sem snapshot apodrece em silêncio: o código muda, o documento
fica, e a plataforma gera integração a partir de uma versão que não
existe mais.

refs #2"
```

---

## Self-Review

**Cobertura da spec (Fase 1 = §8 item 1):**

| Requisito | Tarefa |
|---|---|
| `contract/readout/` completo | 1–9 |
| Bloco `service_knowledge` (§4.1) | 2 |
| Guardrails imponíveis (§5.3) | 3 |
| `data.quality_flags`, campo novo (§4.1) | 5 |
| `explanation_guide.what_was_solved` novo; `glossary` removido de lá (§4.2) | 3 |
| `artifacts[].fields[]` (§2) | 6 |
| `findings[]` estruturado (§2) | 7 |
| Coleções com `max_length` (§4.3) | 1–9, em cada modelo |
| Snapshot, fixtures, fuzz (§5.4) | 10 |

**Fora do escopo, por fase:** runner (2), protocolo `"1.1"` e `_MAX_OUTPUTS` (3), documentação (4). Declarado nas Global Constraints, e o Passo 7 da Tarefa 10 verifica que o snapshot `v1.0` não se mexeu.

**Consistência de tipos verificada:** `BASE_GUARDRAILS` é definido em `guide.py` (Tarefa 3) e consumido por `build_explanation_guide` na mesma tarefa e por `builders.py` na Tarefa 9. `build_valid_readout()` é definido na Tarefa 9 e importado pela Tarefa 10 — por isso vive em `builders.py`, e não dentro do `conftest.py`, onde não seria importável de fora do diretório de testes unitários. `_ROLE_PATTERN` aparece em `artifacts.py` e `provenance.py` com o mesmo valor de `contract/io_spec.py`; a duplicação é anotada em comentário nos dois arquivos.

**Três pontos que exigem julgamento na hora de executar:**

1. **`hyperparameters` e coerção de união** (Tarefa 4). Pydantic pode coagir `True` para `1` na união `bool | int | float | str | None`. Se o teste de aceitação falhar, trocar para os tipos `Strict*`, não ligar modo estrito global.
2. **Campo `model` em `ModelReadout`** (Tarefa 9). Resolvido com `protected_namespaces=()`. Não renomear o campo — o nome é contrato publicado e a spec o documenta assim.
3. **Cobertura do harness de fuzz** (Tarefa 10, Passo 6). O registro no smoke test não é opcional: sem ele o gate de 100% falha, e a causa não é óbvia a partir da mensagem do coverage.
