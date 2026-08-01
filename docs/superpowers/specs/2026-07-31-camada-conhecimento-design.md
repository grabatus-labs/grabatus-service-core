# Camada de Conhecimento do Serviço — design

**Data:** 2026-07-31
**Status:** **SUBSTITUÍDA** no mesmo dia por
`2026-07-31-model-readout-unificado-design.md`. Foi escrita sem conhecimento da
spec de 2026-07-27 (`model_readout`), que resolve a outra metade do mesmo
problema. Não implementar a partir deste documento — o envelope
`result`/`presentation`/`llm_document` da §5 foi descartado, e a Camada de
Conhecimento virou um bloco dentro do `model_readout`. Mantido como registro do
raciocínio original.
**Escopo:** `grabatus-service-core` (padrão) + `grabatus-basketAnalysis` (piloto)

---

## 1. Motivação

A Grabatus passa a integrar via chat/MCP como interface principal. A meta
declarada é que o usuário faça pelo MCP tudo que faz pela API ou pelo site.
Isso muda o que é um serviço "pronto": entregar o número correto deixa de ser
suficiente.

Hoje `forecasting` e `abtest` devolvem JSON de resultado. Nenhum dos dois
carrega o que permite a uma LLM sentar do lado do cliente e agir como cientista
de dados — explicar o que foi calculado, traduzir para a linguagem do cliente e
ajudar a decidir.

---

## 2. Princípio organizador

**Quem comunica com a LLM é o próprio documento.** Documentação e resultados do
modelo viajam juntos, num artefato autocontido, entregue ao usuário com tudo
que é preciso saber.

A LLM não costura conhecimento vindo de um registro com números vindos de outro
lugar. Ela recebe um documento que já se explica. Isso elimina a possibilidade
de explicar um resultado com a documentação da versão errada, e elimina a
dependência de o worker estar no ar — ele é um Cloud Run Job e não está.

Existe uma exceção legítima: **descoberta antes da execução**. Quando o cliente
pergunta "o que vocês têm?" ainda não há resultado. Para isso, e só para isso,
o conhecimento estático fica publicado no registro da plataforma.

---

## 3. Decisões tomadas

| Decisão | Escolha | Por quê |
|---|---|---|
| Comunicação com a LLM | Documento autocontido: documentação + resultados | Sem costura, sem risco de versão trocada |
| Descoberta pré-execução | Conhecimento estático no registro da plataforma | Não há resultado ainda; workers são Jobs, não ficam no ar |
| Forma do artefato | Modelo Pydantic no SDK + snapshot JSON | Mesmo mecanismo que impede o schema de parâmetros de apodrecer |
| Trava contra apodrecimento | Snapshot em `tests/contract_compatibility/` | CI vermelho quando código muda e documentação não |
| Organização no serviço | Pacote `knowledge/`, não arquivo único | Prosa longa estoura o limite de 500 linhas por arquivo |
| Públicos da saída | `result`, `presentation`, `llm_document` | Armazenamento, tela e LLM têm necessidades incompatíveis |
| Geração do `llm_document` | Determinística, em Python, no serviço | Sem custo de token, snapshot-testável, nunca inventa |
| Propriedade dos guardrails | SDK; serviço só acrescenta | Impede que um serviço enfraqueça a garantia anti-alucinação |
| Escopo v1 do piloto | Janela única, sem temporal, sem clusters de loja | `DOMAIN_BRIEF` §10 e §7.2 colocam ambos na v1.1 |

---

## 4. O modelo `ServiceKnowledge`

Vive em `grabatus_service_core.knowledge`. Pydantic v2, `extra="forbid"`,
`frozen=True`. Cada serviço instancia em `src/grabatus_<slug>/knowledge/`.

É a fonte da documentação — usada tanto na descoberta pré-execução quanto
embutida no documento de resultado.

**O que o serviço faz**

| Campo | Tipo | Conteúdo |
|---|---|---|
| `service_name` | `str` | Slug, casa com `service.name` do contrato |
| `service_version` | `str` | Semver, casa com a versão publicada |
| `one_liner` | `str` | Uma frase, para listagem de serviços no MCP |
| `what_it_does` | `str` | Descrição detalhada |
| `when_to_use` | `list[str]` | Situações em que este é o serviço certo |
| `when_not_to_use` | `list[str]` | Situações em que não é — evita indicação errada |

**O que resolve**

| Campo | Tipo | Conteúdo |
|---|---|---|
| `problem_solved` | `str` | A dor de negócio, em linguagem de negócio |
| `personas` | `list[Persona]` | `role` + `pains[]` |

**Como usar**

| Campo | Tipo | Conteúdo |
|---|---|---|
| `workflow` | `list[WorkflowStep]` | `order`, `what_the_user_does`, `what_the_llm_should_say` |
| `input_requirements` | `list[InputRequirement]` | `column`, `required`, `business_meaning`, `example` |

**Como explicar ao cliente**

| Campo | Tipo | Conteúdo |
|---|---|---|
| `output_guide` | `list[OutputField]` | `field_path`, `plain_language`, `how_to_read` |
| `interpretation_playbook` | `list[InterpretationRule]` | `observed_situation`, `what_it_means`, `what_to_recommend` |
| `common_misreadings` | `list[Misreading]` | `wrong_reading`, `correction` |
| `glossary` | `list[Term]` | `technical_term`, `client_language` |
| `limitations` | `list[str]` | O que o serviço **não** responde |
| `models` | `list[ModelExplanation]` | Por modelo: `name`, `what_it_assumes`, `what_it_estimates`, `how_to_read_output`, `when_not_appropriate` |
| `llm_guardrails` | `Guardrails` | Base do SDK + acréscimos do serviço |

`interpretation_playbook` é o campo de maior valor: transforma número em
decisão. Exemplo do piloto — *"lift alto mas addressable baixo → afinidade real
com volume pequeno → não vale mudar planograma, vale testar em uma loja"*.

`models` existe porque serviços bayesianos precisam explicar o modelo, não só o
número. É o que garante que a LLM entendeu o que foi estimado.

---

## 5. A saída: três públicos

```json
{
  "result": {
    "summary":  { "...contagens e qualidade de dados..." },
    "items":    [ "...o resultado em si, específico do serviço..." ],
    "metadata": { "...parâmetros efetivos, premissas, tempo, versão..." }
  },
  "presentation": { "charts": [], "tables": [] },
  "llm_document": {
    "service_documentation": "...ServiceKnowledge da versão que rodou...",
    "what_was_computed": "...",
    "what_was_solved": "...",
    "key_findings": [
      { "finding": "...", "magnitude": 0.0, "uncertainty": "...", "confidence": "alta|média|baixa" }
    ],
    "how_to_explain": "...",
    "caveats": ["..."],
    "not_supported": ["..."],
    "data_quality_notes": ["..."],
    "guardrails": "...texto-base do SDK + acréscimos do serviço..."
  }
}
```

`llm_document` é autocontido: embute a documentação da versão que efetivamente
rodou. A LLM não precisa buscar nada em lugar nenhum para explicar o resultado.

### 5.1 Regra dura: a LLM nunca recebe array bruto

A LLM recebe **conclusão com incerteza**, não dado para agregar. Um modelo em
Stan não envia samples — envia média posterior, intervalo de credibilidade,
`P(efeito > 0)` e diagnóstico de convergência já resumido em confiável / não
confiável, com o motivo.

Justificativa: array bruto gasta contexto, faz a LLM se perder e a induz a
calcular por conta própria, que é a origem da alucinação. **Se a LLM precisa
calcular para responder, o serviço preparou mal a saída.**

Os samples continuam existindo em `result`, para armazenamento e reanálise.
Apenas não vão para `llm_document`.

### 5.2 `not_supported`

Campo obrigatório e não-vazio. Declara o que aquele resultado **não** autoriza
afirmar. É a diferença entre "as vendas vão subir 8%" e "o modelo projeta 8%,
com intervalo de 2% a 14%, e não captura efeito de promoção".

---

## 6. Guardrails

`Guardrails` tem um texto-base **imutável, definido no SDK**, que instrui a LLM a:

1. Não inventar e não extrapolar além do que o `llm_document` afirma.
2. Quando não souber, **dizer que não sabe** e oferecer contato com a Grabatus.
3. Não recalcular a partir de dados brutos.
4. Registrar cada lacuna encontrada no canal de sugestões de melhoria.

O serviço pode **acrescentar** regras de domínio, nunca remover ou enfraquecer
as quatro. O modelo Pydantic garante isso: o campo base não é sobrescrevível,
apenas estendido por uma lista adicional.

O item 4 fecha um loop deliberado: cada "não sei responder isso" vira item de
roadmap, no momento e no contexto exatos do atrito.

---

## 7. Piloto: `grabatus-basketAnalysis` v1.0.0

### 7.1 Contrato

Roles: input `transactions` (xlsx ou csv), output `rules_json`.

`BasketAnalysisParameters` — Pydantic v2, `extra="forbid"`, `frozen=True`:

| Campo | Tipo | Default | Restrição |
|---|---|---|---|
| `transaction_id_col` | `str` | `"transaction_id"` | 1–64 |
| `sku_col` | `str` | `"sku"` | 1–64 |
| `category_col` | `str` | `"category"` | 1–64 |
| `unit_price_col` | `str` | `"unit_price"` | 1–64 |
| `margin_pct_col` | `str` | `"margin_pct"` | 1–64 |
| `timestamp_col` | `str` | `"timestamp"` | 1–64 |
| `store_id_col` | `str` | `"store_id"` | 1–64 |
| `min_support` | `float` | `0.005` | `>0`, `<=1` |
| `min_confidence` | `float` | `0.30` | `>0`, `<=1` |
| `min_lift` | `float` | `1.5` | `>0` |
| `top_n` | `int` | `20` | `>0`, `<=100` |
| `level` | `Literal["sku","category","both"]` | `"both"` | — |
| `min_basket_size` | `int` | `3` | `>=2` |
| `exclude_top_frequency_pct` | `float` | `0.0` | `>=0`, `<1` |
| `analysis_window_days` | `int \| None` | `None` | `>0` se informado |
| `capture_rate` | `float` | `0.10` | `>0`, `<=1` |
| `bundle_discount_pct` | `float` | `0.10` | `>=0`, `<1` |
| `default_margin_pct` | `float` | `0.20` | `>0`, `<1` |

### 7.2 A matemática do impacto financeiro

Para a regra A→B:

```
cestas_alvo        = cestas_com_A − cestas_com_A_e_B
addressable_brl    = cestas_alvo × preço_médio(B)
addressable_margin = addressable_brl × margem(B)
uplift_estimado    = addressable_brl × capture_rate
actionable_score   = lift × support × margem(B)
```

`cestas_alvo` é o público real da ação: quem já leva A e ainda não leva B.
`capture_rate` aparece em `metadata` e em `not_supported`, tornando a premissa
auditável e recalculável. `data_quality_score` = proporção de transações
retidas × proporção de SKUs com categoria e preço preenchidos.

### 7.3 Arquitetura do `compute/`

DataFrame até a mineração (o `mlxtend` fala DataFrame); daí em diante, objetos
tipados sob `mypy --strict`, onde mora a lógica de dinheiro e a narrativa.

```
compute/
  data_preparation.py   # parse xlsx/csv → DataFrame, filtros, flags de qualidade
  fpgrowth_runner.py    # mlxtend → list[AssociationRule]  (frozen dataclass)
  financial_scoring.py  # AssociationRule → RankedAction   (frozen dataclass)
  narrative.py          # RankedAction → narrativa PT-BR + preço de combo
  result_formatting.py  # RankedAction[] → result + presentation + llm_document
  backend.py            # orquestra, ≤20 linhas
```

### 7.4 Fora de escopo na v1

- `temporal_changes` e `store_clusters` — v1.1, conforme `DOMAIN_BRIEF` §7.2.
- Fallback para Spark FP-Growth — o teto de 5M transações do §10 torna a
  dependência injustificável. Acima do teto: `ComputeError` com o número real.
- Enriquecimento do documento por LLM — v3.0, conforme §7.5.
- `action_type` — substituído por narrativa e combo calculado.

### 7.5 Degradações definidas

- `level="both"` sem coluna `category` → degrada para `"sku"` e registra flag
  em `data_quality_flags`.
- `analysis_window_days` informado sem coluna `timestamp` → `ComputeError`.
- `margin_pct` ausente → usa `default_margin_pct` e registra flag.
- `store_id` na v1 alimenta apenas `unique_stores` no summary.

---

## 8. Erros

Toda falha de domínio levanta `grabatus_service_core.errors.compute.ComputeError`
com o valor ofensivo na mensagem. Código de domínio nunca captura `Exception`.
Casos previstos: colunas obrigatórias ausentes, volume acima do teto, janela
temporal sem timestamp, nenhuma regra sobrevivendo aos filtros.

O último merece nota: zero regras é resultado legítimo, não erro. Retorna
`result` vazio com `llm_document` explicando que nenhuma associação superou os
limiares e sugerindo afrouxar `min_support` ou `min_lift`.

---

## 9. Testes

Cobertura 100% linha + branch. Fakes apenas de `grabatus_service_core.testing`.

- `unit/` — parâmetros, cada estágio do compute, bootstrap, api.
- `integration/` — contrato → resposta com fakes; exit codes do `__main__`.
- `property/` — Hypothesis nas restrições dos parâmetros e na monotonicidade do
  `actionable_score`.
- `contract_compatibility/` — snapshot do schema de parâmetros **e** do
  `ServiceKnowledge`.

Um teste adicional verifica que todo campo de `parameters.py` tem entrada
correspondente em `input_requirements` ou `output_guide`: mudar parâmetro sem
documentar quebra o build.

A geração determinística do `llm_document` é o que torna o snapshot possível:
mesma entrada, mesmo documento, sempre.

---

## 10. Riscos

| Risco | Mitigação |
|---|---|
| Documentação vira README esquecido | Snapshot no CI + teste de correspondência com `parameters.py` |
| `capture_rate` lido como previsão, não premissa | Aparece em `metadata` e em `not_supported` |
| Narrativa determinística soar repetitiva | Aceito na v1; enriquecimento por LLM é v3.0 |
| Muitos campos desencorajarem adoção | O piloto serve de exemplo preenchido para copiar |
| `llm_document` inchar ao embutir a documentação | Documentação é prosa curta e limitada; samples e arrays ficam em `result` |
| Retrofit de `forecasting`/`abtest` ficar para trás | Tarefa própria, rastreada como Issue |

---

## 11. Fora desta spec

- Paridade completa MCP ↔ API ↔ site na plataforma Django.
- O MCP de sugestões de melhoria escritas pela LLM (spec própria).
- Migração do `grabatus-survival`.
