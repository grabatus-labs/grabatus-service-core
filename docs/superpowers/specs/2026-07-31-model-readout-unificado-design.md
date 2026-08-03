# Design — `model_readout` unificado: o documento que explica o serviço e o resultado

**Data:** 2026-07-31
**Status:** aguardando revisão do usuário
**Issue:** #2
**Substitui:** `2026-07-27-model-readout-design.md` e `2026-07-31-camada-conhecimento-design.md`
**Escopo:** `grabatus-service-core` (contrato + runtime) e `grabatus-basketAnalysis` (piloto)

---

## 1. Por que esta spec existe

Duas specs foram escritas para o mesmo problema, com quatro dias de diferença e sem se conhecerem.

`2026-07-27-model-readout-design.md` partiu do resultado: o serviço devolve bytes e um dict sem schema, então quem precisa explicar o número **infere**, e inferência sobre estatística produz erro com aparência de autoridade. A resposta foi um artefato de schema fixo, imposto em runtime.

`2026-07-31-camada-conhecimento-design.md` partiu do serviço: com a integração via chat/MCP virando a interface principal, entregar o número correto deixou de bastar. A resposta foi documentar o que o serviço faz, que dor resolve, como se usa e como se explica o resultado ao cliente.

As duas estão certas sobre metades diferentes. **`model_readout` descreve uma execução; a Camada de Conhecimento descreve o serviço.** Uma responde "o que aconteceu neste run", a outra "o que é isto e como se fala disso com o cliente". Um documento que só tem a primeira metade obriga a LLM a inventar o contexto; um que só tem a segunda a obriga a inventar os números.

Esta spec funde as duas num artefato só.

---

## 2. O que se mantém de cada uma

Da spec de 27/07, integralmente:

- **Obrigatoriedade mecânica.** Output role fixo `model_readout`, validado pelo `ServiceRunner` entre `run_compute` e `save_outputs`. Serviço sem readout válido falha em runtime, não em revisão de código.
- **`artifacts[].fields[]`** — dicionário de dados. É o que permite abrir o JSON numérico cru e saber que `yhat_lower` é limite inferior de um intervalo de 90%, não um mínimo histórico.
- **`findings[]` estruturado** — valor, unidade, incerteza e linha de base separados. A IA narra; não calcula, não arredonda, não compara por conta própria.
- **`diagnostics[]`, `overall_quality`, `reproducibility`.**
- **Geração determinística.** O readout não é escrito por LLM. Texto de LLM dentro dele reintroduziria a imprecisão que ele existe para eliminar.

Da spec de 31/07:

- **O bloco `service_knowledge`** — o que o serviço faz, que dor resolve, workflow de uso, e como interpretar a saída na linguagem do cliente. Era o que faltava ao readout.
- **Guardrails como propriedade do SDK** — texto-base imutável que o serviço estende mas não enfraquece, agora com imposição em runtime (§5.3).
- **A regra dura contra array bruto** (§4.3).

---

## 3. Decisões da unificação

| Questão | Decisão | Por quê |
|---|---|---|
| Um artefato ou dois | Um: `model_readout`, com `service_knowledge` embutido | O usuário estabeleceu que quem comunica com a LLM é o próprio documento; dois artefatos exigem costura e permitem versão trocada |
| Repetir a documentação estática em toda execução | Sim, embutida | Autocontenção vale mais que os ~10 KB repetidos; o artefato numérico ao lado costuma ter ordens de grandeza a mais |
| Envelope `result`/`presentation`/`llm_document` | **Descartado** | O readout já é um role separado do artefato numérico. Juntar tudo num JSON obrigaria a LLM a baixar o `result` inteiro para ler as conclusões — exatamente o que a regra do array bruto proíbe |
| `presentation` para a tela | Não vira role novo | O artefato numérico já serve a tela hoje (`forecast_json` alimenta `results.html`). Dois roles bastam: o numérico e o readout |
| `output_guide` da spec de 31/07 | Absorvido por `artifacts[].fields[]` | `meaning` e `read_as` já existiam e cobrem `plain_language`/`how_to_read` |
| `glossary` | Move de `explanation_guide` para `service_knowledge` | É estático — propriedade do serviço, não da execução |
| `models[]` da spec de 31/07 | Descartado em favor do `model{}` do readout | O `model{}` é mais rico: `assumptions[].violation_impact`, `priors[]`, `formulation` |
| `not_supported` da spec de 31/07 | É o `must_not_claim` do readout | Mesmo conceito, nome do readout prevalece |
| Um modelo ou vários por readout | `model{}` singular na v1 | Nenhum serviço atual roda dois modelos no mesmo run; plural quando houver o caso real |

---

## 4. O artefato

Role fixo `model_readout`, formato `json`, emitido em toda execução bem-sucedida. O esqueleto completo dos blocos `request`, `service`, `model`, `data`, `artifacts`, `findings`, `diagnostics`, `overall_quality`, `caveats` e `reproducibility` é o da spec de 27/07 §4 e não se repete aqui. As mudanças são estas três.

### 4.1 Bloco novo: `service_knowledge`

Estático por versão do serviço. Instanciado uma vez no código do serviço, embutido em todo readout.

```json
"service_knowledge": {
  "one_liner": "Descobre quais produtos são comprados juntos e transforma isso em ação de gôndola, combo e sortimento.",
  "what_it_does": "Minera regras de associação sobre o histórico de transações e ranqueia as oportunidades por impacto financeiro estimado, não por força estatística.",
  "problem_solved": "O gerente comercial monta combo por intuição e não distingue afinidade real de coincidência de encarte.",
  "when_to_use": ["Definir planograma", "Montar tabloide promocional", "Decidir sortimento"],
  "when_not_to_use": [
    "Medir efeito causal de uma promoção já rodada — use teste A/B",
    "Prever demanda de um SKU — use previsão de demanda"
  ],
  "personas": [
    {
      "role": "Gerente comercial de rede de supermercado",
      "pains": [
        "Não distingo combo por afinidade real de combo por coincidência de encarte",
        "São milhões de transações; não consigo olhar regra a regra"
      ]
    }
  ],
  "workflow": [
    {
      "order": 1,
      "what_the_user_does": "Sobe a planilha de transações",
      "what_the_llm_should_say": "Confirmo que transaction_id e sku são obrigatórios, e que category, unit_price e margin_pct melhoram muito o resultado."
    }
  ],
  "input_requirements": [
    {
      "column": "transaction_id",
      "required": true,
      "business_meaning": "Identifica uma compra. Tudo que compartilha o mesmo valor é uma cesta.",
      "example": "TX-000481"
    }
  ],
  "interpretation_playbook": [
    {
      "observed_situation": "Lift alto e addressable_brl baixo",
      "what_it_means": "A afinidade é real, mas o público que ela atinge é pequeno.",
      "what_to_recommend": "Não mexer no planograma da rede. Testar em uma loja e medir."
    }
  ],
  "common_misreadings": [
    {
      "wrong_reading": "Confiança de 73% significa que o combo causa a segunda compra.",
      "correction": "É frequência observada entre quem já leva o primeiro item. Não há causa medida aqui."
    }
  ],
  "glossary": [
    { "technical_term": "lift", "plain_language": "quantas vezes mais provável que o acaso" }
  ],
  "limitations": [
    "Não mede canibalização entre produtos similares.",
    "Não separa período promocional de período orgânico."
  ]
}
```

Campos obrigatórios e não-vazios: todos, exceto `common_misreadings` — um serviço recém-nascido ainda não viu leitura errada nenhuma.

`workflow[].order` precisa ser contíguo a partir de 1. Um workflow que a LLM lê fora de ordem é um workflow que ela conta errado.

`limitations` (do serviço) e `model.not_designed_for` (do modelo estatístico) são campos distintos de propósito: o primeiro é produto, o segundo é método.

**Campo novo em `data`:** `quality_flags: tuple[str, ...]`, para degradações que não são lacuna de origem nem filtro aplicado — "coluna `category` ausente, análise degradada para nível SKU", "margem não informada, usado o default de 20%". Os três blocos ficam assim: `filters_applied` é o que o serviço tirou de propósito, `known_gaps` é o que faltava na origem, `quality_flags` é o que o serviço teve de assumir para conseguir rodar.

### 4.2 `explanation_guide`: dois campos novos, um que sai

Três mudanças em relação à spec de 27/07:

- **Sai** `glossary[]` — é estático, foi para `service_knowledge`.
- **Entra** `what_was_solved: str` — a dor de negócio que *esta execução* endereçou, em linguagem de negócio. Distinto de `service_knowledge.problem_solved`, que é a dor genérica do serviço.
- **Entra** `guardrails: tuple[str, ...]` — abaixo.

```json
"explanation_guide": {
  "audience": "gerente comercial sem formação estatística",
  "summary_for_llm": "...",
  "what_was_solved": "Quais combos valem virar ação de gôndola neste trimestre.",
  "recommended_narrative_order": ["findings.rule_001", "caveats[0]"],
  "must_not_claim": [
    "que a associação prova que um produto causa a compra do outro",
    "que o uplift estimado se realizará — ele depende da taxa de captura assumida"
  ],
  "guardrails": [
    "Responda apenas com o que este documento afirma. Não extrapole, não estime e não complete lacunas com conhecimento geral sobre o setor.",
    "Se a pergunta não puder ser respondida com este documento, diga que não sabe e ofereça o contato da Grabatus. Nunca produza um número que não esteja escrito aqui.",
    "Não recalcule nada a partir de dados brutos. Os números deste documento já são o resultado final da análise.",
    "Sempre que encontrar uma lacuna — algo que o cliente pediu e este documento não responde — registre uma sugestão de melhoria no canal da Grabatus, descrevendo o que faltou.",
    "Nunca cite um SKU que não apareça em findings[]."
  ]
}
```

O `glossary` sai daqui (foi para `service_knowledge`).

`guardrails[]` é validado: os quatro primeiros elementos devem ser **exatamente** `BASE_GUARDRAILS`, na ordem. Um serviço acrescenta regras de domínio a partir do quinto e não tem mecanismo para remover ou reescrever as quatro primeiras — a violação vira `ValidationError` no modelo e `InvalidReadoutError` no runner.

O SDK expõe `build_explanation_guide(...)`, que preenche o prefixo sozinho. O caminho fácil é o caminho correto; escrever o campo à mão é possível, passar na validação escrevendo errado não é.

O item 4 dos guardrails fecha um loop deliberado: cada "não sei responder isso" vira item de roadmap, no momento e no contexto exatos do atrito. O canal que o recebe tem spec própria (§9).

### 4.3 A regra dura: o readout nunca carrega array bruto

O readout recebe **conclusão com incerteza**, não dado para agregar. Um modelo em Stan não põe samples aqui — põe média posterior, intervalo de credibilidade, `P(efeito > 0)` e a convergência já resumida em confiável / não confiável, com o motivo. As samples continuam existindo no artefato numérico, que o readout descreve em `artifacts[]`.

Justificativa: array bruto gasta contexto, faz a LLM se perder e a induz a calcular por conta própria, que é a origem da alucinação. **Se a LLM precisa calcular para responder, o serviço preparou mal o readout.**

Consequência de projeto: nenhuma coleção do readout pode ter comprimento proporcional ao tamanho da entrada. `findings[]`, `caveats[]` e `diagnostics[]` têm `max_length` explícito no schema.

---

## 5. Arquitetura no SDK

### 5.1 Contrato

Subpacote `src/grabatus_service_core/contract/readout/`, na divisão da spec de 27/07 §5.1, com um arquivo a mais:

```
contract/readout/knowledge.py    # ServiceKnowledge, Persona, WorkflowStep,
                                 # InputRequirement, InterpretationRule,
                                 # Misreading, Term
```

`contract/readout/guide.py` passa a hospedar `BASE_GUARDRAILS: Final[tuple[str, ...]]` e o validador de prefixo.

Convenções herdadas: `ConfigDict(extra="forbid", frozen=True)` em todo modelo, constraints explícitas em todo campo, coleções como `tuple[...]` (`frozen=True` só é real com contêiner imutável), enums fechados como `Literal` ou `StrEnum`.

### 5.2 Imposição em runtime

Inalterada em relação à spec de 27/07 §5.2: passo `VALIDATE_READOUT` entre `run_compute` e `save_outputs`; `MissingReadoutError` e `InvalidReadoutError` sob `ComputeError`, ambos `retriable=False`, ambos na taxonomia da §3 do `integration_contract.md`.

### 5.3 Imposição dos guardrails

`ExplanationGuide.guardrails` carrega um `field_validator` que rejeita qualquer valor cujo prefixo não seja `BASE_GUARDRAILS`. A mensagem de erro inclui o valor ofensivo, conforme o padrão do repo.

Isso transforma a garantia anti-alucinação de convenção em contrato: passa a ser tão obrigatória quanto o resto do schema, e falha no mesmo lugar.

### 5.4 Protocolo, CI e ferramentas de teste

Sem mudança em relação à spec de 27/07 §§5.3–5.5: protocolo `"1.1"`, `_MAX_OUTPUTS` de 10 para 11, snapshot `snapshots/v1.1/model_readout.schema.json`, fixtures válidas e inválidas, fuzz do parser, `make_model_readout(**overrides)` e `FakeComputeBackend` emitindo readout válido por padrão.

O snapshot é o que impede a documentação de apodrecer: mudou o modelo e não mudou o documento, o CI fica vermelho.

---

## 6. Piloto: `grabatus-basketAnalysis` v1.0.0

Serviço novo, sem código legado, com persona e vocabulário já levantados no `DOMAIN_BRIEF.md`. Nasce com readout — é a prova de que o contrato é praticável antes de exigi-lo dos serviços existentes.

Roles: input `transactions` (xlsx ou csv), outputs `rules_json` e `model_readout`.

### 6.1 Parâmetros

`BasketAnalysisParameters`, Pydantic v2, `extra="forbid"`, `frozen=True`. Dezoito campos: sete de nome de coluna (`transaction_id_col`, `sku_col`, `category_col`, `unit_price_col`, `margin_pct_col`, `timestamp_col`, `store_id_col`, todos `str` 1–64 com default igual ao nome), e onze de análise:

| Campo | Tipo | Default | Restrição |
|---|---|---|---|
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

Os sete parâmetros de nome de coluna seguem o precedente do `grabatus-forecasting` (`ds_col_name`, `y_col_name`). São reversíveis: remover parâmetro com default é retrocompatível; passar a exigir formato fixo de planilha não é.

### 6.2 A matemática do impacto financeiro

Para a regra A→B:

```
cestas_alvo        = cestas_com_A − cestas_com_A_e_B
addressable_brl    = cestas_alvo × preço_médio(B)
addressable_margin = addressable_brl × margem(B)
uplift_estimado    = addressable_brl × capture_rate
actionable_score   = lift × support × margem(B)
```

`cestas_alvo` é o público real da ação: quem já leva A e ainda não leva B.

`capture_rate` é **premissa, não previsão**. Aparece em `model.hyperparameters` e em `explanation_guide.must_not_claim`, de modo que fique auditável e recalculável — é o parâmetro que mais facilmente vira promessa indevida na boca de quem apresenta o número.

`data_quality_score` = proporção de transações retidas × proporção de SKUs com categoria e preço preenchidos.

### 6.3 Arquitetura do `compute/`

DataFrame até a mineração — o `mlxtend` fala DataFrame. Daí em diante, objetos tipados sob `mypy --strict`, onde mora a lógica de dinheiro e a narrativa.

```
compute/
  data_preparation.py   # parse xlsx/csv → DataFrame, filtros, flags de qualidade
  fpgrowth_runner.py    # mlxtend → tuple[AssociationRule, ...]  (frozen dataclass)
  financial_scoring.py  # AssociationRule → RankedAction         (frozen dataclass)
  narrative.py          # RankedAction → narrativa PT-BR + preço de combo
  result_formatting.py  # RankedAction[] → rules_json
  readout_building.py   # RankedAction[] → ModelReadout
  knowledge.py          # a ServiceKnowledge do serviço, preenchida
  backend.py            # orquestra, ≤20 linhas
```

### 6.4 Degradações e erros

- `level="both"` sem coluna `category` → degrada para `"sku"` e registra flag em `data.quality_flags`.
- `analysis_window_days` informado sem coluna `timestamp` → `ComputeError`.
- `margin_pct` ausente → usa `default_margin_pct` e registra flag.
- `store_id` na v1 alimenta apenas a contagem de lojas em `data.entities`.
- Volume acima de 5M transações → `ComputeError` com o número real. O teto do `DOMAIN_BRIEF` §10 torna a dependência de Spark injustificável na v1.
- **Zero regras é resultado legítimo, não erro.** Retorna `rules_json` vazio e readout com `findings: []`, `overall_quality.status: "warn"` e um `caveat` explicando que nenhuma associação superou os limiares, sugerindo afrouxar `min_support` ou `min_lift`.

### 6.5 Fora de escopo na v1

`temporal_changes` e `store_clusters` (v1.1, conforme `DOMAIN_BRIEF` §7.2); detecção de canibalização (v1.2); recomendação personalizada (v2.0); enriquecimento do texto por LLM (v3.0); o campo `action_type`, substituído por narrativa e combo calculado.

---

## 7. Testes

Cobertura 100% linha + branch, nos dois repos. Fakes apenas de `grabatus_service_core.testing`.

No SDK, além do que a spec de 27/07 §5.3 já previa: teste de que `guardrails` com prefixo adulterado é rejeitado, e teste de que `build_explanation_guide` produz prefixo válido.

No `basketAnalysis`: `unit/` por estágio do compute; `integration/` contrato → resposta com fakes e exit codes do `__main__`; `property/` com Hypothesis nas restrições dos parâmetros e na monotonicidade do `actionable_score`; `contract_compatibility/` com snapshot do schema de parâmetros.

Um teste adicional verifica que **todo campo de `parameters.py` tem entrada correspondente em `service_knowledge.input_requirements` ou em `artifacts[].fields[]`**. Mudar parâmetro sem documentar quebra o build. É o mecanismo que impede a Camada de Conhecimento de virar README esquecido.

---

## 8. Ordem de execução

1. **SDK — schema:** `contract/readout/` completo, incluindo `knowledge.py` e os guardrails imponíveis; snapshots, fixtures, fuzz.
2. **SDK — runtime:** passo do runner, erros novos, factories de teste.
3. **SDK — protocolo:** `"1.1"`, validação do output role, `_MAX_OUTPUTS`.
4. **SDK — documentação:** `docs/model_readout_spec.md`, `integration_contract.md`, toctree, tradução pt_BR.
5. **`basketAnalysis` v1.0.0:** serviço completo, nascendo com readout.
6. **Distribuição:** plugin Claude Code, `CLAUDE.md` global, `CLAUDE.md` do template.
7. **Template:** correção da defasagem (importa `run_worker`, que não existe; assinatura `run` fora do Protocol) + readout de exemplo.
8. **Plataforma:** Django com contrato 1.1, persistência do readout, MCP devolvendo readout em `get_analysis_results`.
9. **Serviços existentes:** `grabatus-forecasting` e `grabatus-abtest`, com Issue própria cada.

As fases 1–4 e 6–7 ocorrem no `grabatus-service-core`; a 5 no repo do serviço; a 8 no `grabatus`; a 9 nos repos de serviço.

---

## 9. Fora desta spec

- O MCP de sugestões de melhoria escritas pela LLM — spec própria. Esta spec só produz o gatilho (guardrail 4).
- Paridade completa MCP ↔ API ↔ site na plataforma Django.
- Migração do `grabatus-survival` e o serviço de PCA.

---

## 10. Riscos

| Risco | Mitigação |
|---|---|
| `service_knowledge` vira README esquecido | Snapshot no CI + teste de correspondência com `parameters.py` (§7) |
| Readout inflado pela documentação repetida | Prosa curta e limitada; arrays proibidos (§4.3); o artefato numérico ao lado é ordens de grandeza maior |
| `capture_rate` lido como previsão | Aparece em `hyperparameters` e em `must_not_claim` |
| Serviço escrever guardrails enfraquecidos | Validador de prefixo → `InvalidReadoutError` em runtime (§5.3) |
| Protocolo 1.1 quebrar a plataforma | `"1.0"` continua aceita por um ciclo, deprecada, para dar janela de migração |
| Narrativa determinística soar repetitiva | Aceito na v1; enriquecimento por LLM é v3.0 |
| Retrofit de `forecasting`/`abtest` ficar para trás | Fase 9, Issue própria por serviço |
