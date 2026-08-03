# Design — `model_readout`: saída de modelo legível e explicável por IA

Data: 2026-07-27
Status: **SUBSTITUÍDA** em 2026-07-31 por
`2026-07-31-model-readout-unificado-design.md`, que funde este design com a
Camada de Conhecimento. Não implementar a partir deste documento — as §§4 e 5
mudaram (bloco `service_knowledge` novo, `glossary` migrado para fora do
`explanation_guide`, `guardrails[]` com validação de prefixo, `data.quality_flags`
novo). Mantido como registro do raciocínio original.

## 1. Problema

Hoje o resultado de um serviço Grabatus é opaco. O contrato
(`src/grabatus_service_core/contract/`) modela apenas o *request*; o
resultado existe em três formas não-tipadas e divergentes entre si:

| Camada | Representação | Tipo |
|---|---|---|
| Compute backend → runner | `ComputeResult(by_role: Mapping[str, bytes], metadata)` | `@dataclass`, não Pydantic |
| Runner → chamador Python | `ExecutionResult[ParamsT]` | `@dataclass`, não Pydantic |
| Runner → plataforma (webhook) | `dict[str, Any]` montado à mão (`runner/runner.py:239`) | dict cru, sem schema |

Cada serviço serializa como quer: `grabatus-forecasting` tem
`serialize_forecast()`, `grabatus-abtest` tem `serialize_posterior()`.
Nenhum dos dois emite qualquer metadado sobre o modelo que produziu os
números.

A consequência: quando uma IA — o servidor MCP que atende o cliente, um
agente da plataforma, ou uma LLM lendo o artefato bruto — precisa
**explicar** um resultado, ela não tem material. Ela infere. Inferência
sobre número estatístico produz erro de interpretação com aparência de
autoridade: confundir intervalo de credibilidade com desvio-padrão,
afirmar causalidade onde há correlação, extrapolar além do horizonte
validado.

## 2. Objetivo

Todo serviço computacional Grabatus — existente ou futuro — deve emitir,
junto aos artefatos numéricos, um documento JSON de schema fixo chamado
**`model_readout`**, contendo tudo que uma IA precisa para explicar o
resultado com máxima exatidão: identificação do modelo, dicionário dos
dados produzidos, achados quantificados com incerteza, diagnósticos de
qualidade, limitações, e instruções explícitas sobre o que **não** pode
ser afirmado.

A obrigatoriedade é mecânica, não documental: um serviço que não emite
readout válido falha em tempo de execução e no CI.

## 3. Não-objetivos

- O readout **não substitui** os artefatos numéricos. Ele os descreve.
- O readout **não é gerado por LLM**. É produzido deterministicamente
  pelo serviço, a partir do próprio ajuste do modelo. Texto gerado por
  LLM dentro do readout reintroduziria exatamente a imprecisão que o
  readout existe para eliminar.
- O readout **não carrega dados brutos**. Séries, posteriores e matrizes
  continuam nos seus próprios artefatos.

## 4. O artefato

Output role fixo: `model_readout`. Formato: `json`. Emitido por todo
serviço, em toda execução bem-sucedida.

```json
{
  "readout_version": "1.0",
  "generated_at": "2026-07-27T14:03:11Z",

  "request": {
    "request_id": "3f2b1c8e-0000-4000-8000-000000000000",
    "result_id": "res_0001",
    "parameter_id": "par_0001",
    "tenant_id": "acme-varejo",
    "origin": "web"
  },

  "service": {
    "name": "grabatus-forecasting",
    "version": "0.4.1",
    "protocol_version": "1.1"
  },

  "model": {
    "display_name": "Previsão de demanda com Prophet",
    "family": "time_series_forecast",
    "paradigm": "bayesian",
    "objective": "Prever a demanda semanal de cada SKU nas próximas 12 semanas.",
    "formulation": "y(t) = g(t) + s(t) + h(t) + eps_t",
    "assumptions": [
      {
        "statement": "A sazonalidade anual é estável ao longo do período observado.",
        "violation_impact": "Previsões enviesadas em períodos de mudança estrutural.",
        "checked": true
      }
    ],
    "hyperparameters": { "changepoint_prior_scale": 0.05, "horizon_weeks": 12 },
    "priors": [
      {
        "parameter": "changepoint_prior_scale",
        "distribution": "Laplace(0, 0.05)",
        "rationale": "Penaliza mudanças bruscas de tendência sem proibi-las."
      }
    ],
    "not_designed_for": [
      "inferir causalidade entre promoção e venda",
      "prever SKUs sem histórico mínimo de 52 semanas"
    ]
  },

  "data": {
    "observation_count": 5312,
    "granularity": "weekly",
    "period_covered": { "start": "2023-01-01", "end": "2026-06-30" },
    "entities": { "label": "SKU", "count": 214 },
    "filters_applied": ["SKUs com menos de 52 semanas de histórico foram excluídos"],
    "known_gaps": ["Semanas 12–14 de 2024 ausentes na origem"]
  },

  "artifacts": [
    {
      "role": "forecast_json",
      "uri": "gs://grabatus-acme-varejo/results/res_0001/forecast.json",
      "format": "json",
      "description": "Série prevista por SKU e semana, com intervalo de credibilidade.",
      "fields": [
        {
          "name": "yhat",
          "type": "number",
          "unit": "unidades",
          "meaning": "Valor central previsto (mediana a posteriori).",
          "read_as": "Demanda esperada naquela semana."
        },
        {
          "name": "yhat_lower",
          "type": "number",
          "unit": "unidades",
          "interval_level": 0.9,
          "meaning": "Limite inferior do intervalo de credibilidade de 90%.",
          "read_as": "Em 90% dos cenários, a demanda fica acima deste valor."
        }
      ]
    }
  ],

  "findings": [
    {
      "id": "total_demand_h12",
      "importance": 1,
      "statement": "A demanda total prevista para as próximas 12 semanas é de 48.300 unidades.",
      "quantity": { "value": 48300, "unit": "unidades" },
      "uncertainty": {
        "kind": "credible_interval",
        "level": 0.9,
        "lower": 41100,
        "upper": 56800
      },
      "direction": "increase",
      "comparison_baseline": { "label": "12 semanas anteriores", "value": 43900 },
      "confidence": "high",
      "confidence_rationale": "Erro de validação fora da amostra abaixo de 12% em rolling-origin CV."
    }
  ],

  "diagnostics": [
    {
      "name": "r_hat_max",
      "value": 1.01,
      "threshold": "< 1.01",
      "status": "pass",
      "meaning": "As cadeias MCMC convergiram."
    },
    {
      "name": "mape_holdout",
      "value": 0.112,
      "threshold": "< 0.20",
      "status": "pass",
      "meaning": "Erro percentual médio fora da amostra."
    }
  ],

  "overall_quality": {
    "status": "pass",
    "summary": "Convergência e erro fora da amostra dentro dos limites de aceite."
  },

  "caveats": [
    {
      "severity": "high",
      "statement": "O modelo não incorpora calendário promocional.",
      "do_not_conclude": "Não atribua variações previstas a ações de marketing."
    }
  ],

  "explanation_guide": {
    "audience": "gestor de operações sem formação estatística",
    "summary_for_llm": "A demanda das próximas 12 semanas deve somar cerca de 48,3 mil unidades, 10% acima das 12 semanas anteriores. O intervalo plausível vai de 41,1 mil a 56,8 mil. O modelo passou nos testes de qualidade, mas ignora promoções.",
    "glossary": [
      {
        "term": "intervalo de credibilidade",
        "plain_language": "faixa dentro da qual o valor real deve cair, com a probabilidade indicada"
      }
    ],
    "recommended_narrative_order": [
      "findings.total_demand_h12",
      "diagnostics.mape_holdout",
      "caveats[0]"
    ],
    "must_not_claim": [
      "que o modelo prova causalidade",
      "que os limites do intervalo são cenários de melhor/pior caso garantidos"
    ]
  },

  "reproducibility": {
    "random_seed": 42,
    "compute_duration_seconds": 84.2,
    "input_digests": [{ "role": "sales", "sha256": "<64 caracteres hexadecimais>" }],
    "library_versions": { "prophet": "1.1.5", "cmdstan": "2.35.0" }
  }
}
```

### 4.1 Por que estas seções

Três decisões carregam o peso do design:

**`explanation_guide.must_not_claim` é o mecanismo de exatidão.** Sem uma
lista explícita de conclusões proibidas, a IA preenche lacunas com o que
é plausível. Com ela, o serviço — que é quem sabe — declara as fronteiras
da interpretação.

**`artifacts[].fields[]` é um dicionário de dados, não prosa.** É o que
permite a uma IA abrir o `forecast_json` cru e saber que `yhat_lower` é o
limite inferior de um intervalo de 90%, e não um mínimo histórico.

**`findings[]` é estruturado, não texto.** Valor, unidade, incerteza e
linha de base separados. A IA narra; ela não calcula, não arredonda e não
compara por conta própria.

## 5. Arquitetura no SDK

### 5.1 Contrato

Novo subpacote `src/grabatus_service_core/contract/readout/`, dividido por
responsabilidade para respeitar o limite de 500 linhas por arquivo:

```
contract/readout/__init__.py     # reexporta ModelReadout e submodelos
contract/readout/root.py         # ModelReadout
contract/readout/model.py        # ModelDescription, Assumption, Prior
contract/readout/data.py         # DataProvenance, PeriodCovered, EntitySummary
contract/readout/artifacts.py    # ArtifactDescription, FieldDescription
contract/readout/findings.py     # Finding, Quantity, Uncertainty, ComparisonBaseline
contract/readout/diagnostics.py  # Diagnostic, OverallQuality
contract/readout/caveats.py      # Caveat
contract/readout/guide.py        # ExplanationGuide, GlossaryEntry
contract/readout/provenance.py   # Reproducibility, InputDigest
```

Convenções herdadas do contrato existente: `ConfigDict(extra="forbid",
frozen=True)` em todo modelo, constraints explícitas em todo campo
(`min_length`/`max_length`/`ge`/`le`), enums como `Literal`.

Constante pública `READOUT_OUTPUT_ROLE: Final[str] = "model_readout"`.

Enums fechados relevantes:

- `ModelFamily`: `time_series_forecast`, `bayesian_inference`,
  `ab_test`, `optimization`, `classification`, `regression`,
  `clustering`, `survival_analysis`, `simulation`
- `Paradigm`: `bayesian`, `frequentist`, `optimization`, `heuristic`,
  `ml_supervised`, `ml_unsupervised`
- `UncertaintyKind`: `credible_interval`, `confidence_interval`,
  `prediction_interval`, `standard_error`, `none`
- `Direction`: `increase`, `decrease`, `stable`, `not_applicable`
- `Confidence`: `high`, `moderate`, `low`
- `DiagnosticStatus` e `QualityStatus`: `pass`, `warn`, `fail`
- `Severity`: `high`, `medium`, `low`

### 5.2 Imposição em runtime

Novo passo no `ServiceRunner`, entre `run_compute` e `save_outputs`:

```
decode → validate → check_roles → authorize → resolve_credentials
       → load_inputs → run_compute → VALIDATE_READOUT → save_outputs → notify_webhook
```

`_validate_readout` exige a chave `model_readout` em
`ComputeResult.by_role` e a valida com `ModelReadout.model_validate_json`.
Falha levanta erro de domínio, não `Exception` genérica.

Novos erros em `errors/compute.py`, sob `ComputeError`:

| Classe | `error_code` | `retriable` | Significado |
|---|---|---|---|
| `MissingReadoutError` | `missing_model_readout` | `False` | O backend não produziu o role `model_readout` |
| `InvalidReadoutError` | `invalid_model_readout` | `False` | O readout produzido não satisfaz o schema |

Ambos entram na tabela de taxonomia da §3 do `integration_contract.md`,
com stage `Compute`.

### 5.3 Imposição no CI

O gate de drift já existente (`tests/contract_compatibility/`) é estendido:

- `_harness.py` ganha a âncora do readout
- novo snapshot `snapshots/v1.1/model_readout.schema.json`, comparado
  byte a byte
- `scripts/update_schema_snapshots.py` passa a regenerar os dois schemas
- fixtures `fixtures/v1.1/readout/valid/*.json` e `.../invalid/*.json`,
  varridas por teste parametrizado, no mesmo padrão de
  `test_fixtures.py`
- harness de fuzz para o parser de readout, junto ao
  `fuzz_contract_parser.py` existente

Cobertura 100% linha + branch continua obrigatória.

### 5.4 Protocolo

`protocol_version` `"1.1"`. `SUPPORTED_PROTOCOL_VERSIONS` passa a
`frozenset({"1.0", "1.1"})`.

Em `"1.1"`, o `BaseServiceContract` valida que `outputs` contém um
`OutputSpec` com `role == "model_readout"` e `format == "json"`. Em
`"1.0"` a validação não ocorre — a versão continua aceita por um ciclo,
marcada como deprecada, para dar à plataforma Django janela de migração.

O limite `_MAX_OUTPUTS` sobe de 10 para 11, de modo que o readout não
consuma um slot de artefato de nenhum serviço existente. Isso altera
`maxItems` no schema de `BaseServiceContract` e, portanto, invalida o
snapshot `snapshots/v1.0/base_service_contract.schema.json` — que precisa
ser regenerado no mesmo commit. É a única mudança que o readout impõe ao
schema do *request*.

### 5.5 Ferramentas de teste

`testing/` ganha:

- `make_model_readout(**overrides)` — factory que produz um readout
  válido mínimo, no padrão das factories existentes em
  `testing/factories.py`
- `FakeComputeBackend` e `make_fake_compute_backend` passam a emitir um
  readout válido por padrão, e a aceitar `readout=` para casos de teste
  que exercitam readout inválido

Sem isso, todo teste de todo serviço quebraria ao subir a versão do SDK —
inaceitável.

## 6. Propagação

### 6.1 Especificação canônica

`docs/model_readout_spec.md` no `grabatus-service-core`, referenciado
pela §2 do `integration_contract.md`. Fonte de verdade única, versionada
junto ao código, sujeita à mesma regra já vigente no `CLAUDE.md`: mudou o
modelo Pydantic, atualiza o documento no mesmo commit.

Entra no toctree do `docs/index.rst` e no fluxo de tradução pt_BR
(`docs/locale/`), já que o CI faz build duplo com `-W`.

### 6.2 Plugin Claude Code

Novo plugin `~/.claude/plugins/grabatus-model-readout/`, seguindo o
precedente estrutural do `grabatus-quality`:

```
.claude-plugin/plugin.json
skills/model-readout-contract/SKILL.md        # dispara em qualquer trabalho de serviço
skills/model-readout-contract/references/schema.md
skills/model-readout-contract/references/writing-good-readouts.md
commands/readout-audit.md                     # /readout-audit
```

A skill usa progressive disclosure: `SKILL.md` curto com a regra e o
esqueleto; `references/` com o schema completo e os anti-padrões.

### 6.3 Instruções de agente

- Cláusula nova no bloco imutável de `~/.claude/CLAUDE.md`: nenhum
  serviço computacional é considerado completo sem `model_readout`
  válido.
- `CLAUDE.md` do `service-template` com a mesma regra e o ponteiro para o
  spec canônico.

### 6.4 Template e serviços existentes

O `service-template` está hoje **defasado** em relação ao SDK: usa
`from grabatus_service_core.ports.compute import ComputeResult` (o
símbolo vive em `ports/values.py`), assinatura `run(self, data, parameters)`
em vez de `run(self, *, inputs, parameters)`, e não declara os `ClassVar`
`REQUIRED_INPUT_ROLES` / `OPTIONAL_INPUT_ROLES` / `OUTPUT_ROLES`. Quem
clona o template hoje começa com código que não satisfaz o Protocol.

O template será corrigido **e** passará a emitir um readout de exemplo,
com teste unitário que o valida.

Para `grabatus-forecasting` e `grabatus-abtest`, Issues no GitHub
conforme a regra do `CLAUDE.md`, com a implementação do readout em cada
um — inclusive o mapeamento dos diagnósticos que cada um já calcula
(R-hat, ESS, divergências no abtest; métricas de validação no
forecasting) para o bloco `diagnostics[]`.

### 6.5 Plataforma Django e MCP

Trabalho no repo `grabatus`, na mesma entrega:

1. O `TaskDispatcher` passa a incluir o `OutputSpec` de `model_readout`
   ao montar o contrato, e a emitir `protocol_version: "1.1"`.
2. O `WebhookService` persiste o readout junto ao resultado da análise.
3. O servidor MCP retorna o readout em `get_analysis_results`, de forma
   que a IA que atende o cliente narre a partir dele.
4. A skill local `integrating-with-service-core` (em
   `grabatus/.claude/skills/`) é atualizada com a nova versão do
   protocolo.

Regra de consumo, documentada no spec: **qualquer superfície que exponha
um resultado a um cliente — MCP, API, UI — deve entregar o readout junto,
e qualquer IA que narre o resultado deve respeitar `must_not_claim`.**

## 7. Ordem de execução

O faseamento existe porque a §5.4 (protocolo 1.1) só faz sentido depois
que o readout existe e é testável, e a §6.5 só faz sentido depois que o
SDK impõe o readout.

1. **Schema** — `contract/readout/`, snapshots, fixtures, fuzz
2. **Runtime** — passo do runner, erros novos, factories de teste
3. **Protocolo** — `"1.1"`, validação de output role, `_MAX_OUTPUTS`
4. **Documentação** — `model_readout_spec.md`, `integration_contract.md`,
   toctree, tradução
5. **Distribuição** — plugin, `CLAUDE.md` global, `CLAUDE.md` do template
6. **Template** — correção da defasagem + readout de exemplo
7. **Plataforma** — Django: contrato 1.1, persistência, MCP, skill local
8. **Serviços** — `grabatus-forecasting` e `grabatus-abtest`

As fases 1–6 ocorrem em `grabatus-service-core` e nos artefatos de
configuração; a 7 em `grabatus`; a 8 nos repos de serviço.

## 8. Verificação

- `uv run pytest` verde com cobertura 100% linha + branch
- `uv run mypy --strict src/ tests/` limpo
- snapshot de schema estável (`scripts/update_schema_snapshots.py` não
  produz diff após rodar os testes)
- fixture inválida de readout rejeitada com `InvalidReadoutError`
- backend de teste sem readout rejeitado com `MissingReadoutError`
- build Sphinx EN e pt_BR com `-W`, sem warnings
- ponta a ponta: contrato `"1.1"` → runner → readout escrito no
  destino → payload de webhook → leitura pelo MCP
