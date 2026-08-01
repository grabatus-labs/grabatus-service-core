# Integration contract

This document is the **canonical specification** of the protocol every
Grabatus computational service speaks: the Pub/Sub envelope the
platform sends in, the JWT-signed webhook the service sends back, and
the error taxonomy mapped onto both. It is the source of truth — any
disagreement between this file and an implementation is a bug in the
implementation.

The protocol is version 1.0. Breaking changes ship as a new
`protocol_version`; additive fields ship under the same version.

---

## Roles

```
┌──────────────────────┐     1. Pub/Sub envelope       ┌────────────────────┐
│  grabatus (Django)   │ ─────────────────────────────▶│  shared receiver   │
│  the platform        │                               │  (service-core)    │
└──────────────────────┘                               └─────────┬──────────┘
        ▲                                                        │ 2. dispatch
        │                                                        ▼
        │                                              ┌────────────────────┐
        │   3. JWT-signed webhook (HTTPS POST)         │  worker job        │
        └──────────────────────────────────────────────│  (e.g. forecasting)│
                                                       └────────────────────┘
```

The platform never talks to a worker directly. It publishes a Pub/Sub
message; the shared receiver routes it to the right worker; the
worker computes, persists outputs to GCS, and notifies the platform
via a JWT-signed webhook.

---

## 1. Pub/Sub envelope (platform → receiver)

### Transport shape

The receiver expects a standard GCP Pub/Sub push payload:

```json
{
  "message": {
    "data": "<base64-encoded UTF-8 JSON of the contract>",
    "messageId": "...",
    "publishTime": "..."
  },
  "subscription": "..."
}
```

`data` decodes to the **service contract** described below. Anything
else in `message` is metadata supplied by Pub/Sub and ignored by the
receiver.

### Service contract

```text
{
  "envelope": {
    "protocol_version": "1.0",
    "request_id": "<uuid v4>",
    "created_at": "<RFC 3339 with timezone>",
    "origin": "web | api | mcp | internal"
  },
  "identity": {
    "user_id": "<1..64 chars>",
    "tenant_id": "<lowercase + digits + hyphens, 1..64>"
  },
  "references": {
    "parameter_id": "<opaque platform id, 1..128>",
    "result_id":    "<opaque platform id, 1..128>"
  },
  "service": {
    "name":    "<lowercase slug, e.g. forecast>",
    "version": "<MAJOR.MINOR.PATCH>"
  },
  "inputs": [
    {
      "role":           "<lowercase, service-defined>",
      "source_uri":     "https://...  | gs://... | inline://...",
      "format":         "xlsx | csv | json | parquet | bigquery | inline",
      "format_hints":   { "...": "depends on format" },
      "compression":    "none | gzip | zstd",
      "credential_ref": null | { "secret_id": "...", "version": "latest" }
    }
  ],
  "outputs": [
    {
      "role":            "<lowercase, service-defined>",
      "destination_uri": "gs://...",
      "format":          "json | parquet | csv | xlsx",
      "format_hints":    { "...": "depends" },
      "compression":     "none | gzip | zstd",
      "write_mode":      "overwrite | append | fail_if_exists"
    }
  ],
  "callback": {
    "url":         "https://<platform>/api/v1/webhooks/<service>/callback/",
    "auth_scheme": "jwt_hs256"
  },
  "parameters": {
    "...": "service-specific Pydantic schema"
  }
}
```

### Field semantics that are easy to get wrong

- `envelope.request_id` is the **idempotency key** end-to-end. The
  platform must reuse the same UUID when re-publishing after a
  retryable failure; the receiver de-dupes on it.
- `identity.tenant_id` drives URI authorization. A request scoped to
  `tenant_id = grabatus` may only read/write URIs whose path is
  prefixed with `grabatus`. Cross-tenant access is rejected before any
  I/O.
- `service.version` is **strict semver**. `"1.0"` or `"1.0.0-rc1"` are
  rejected. Use `"1.0.0"`.
- `callback.url` must be HTTPS and `auth_scheme` is constrained to
  `jwt_hs256` in v1.0.
- `inputs[].role` and `outputs[].role` are service-defined slugs (e.g.
  `timeseries`, `forecast`). The service declares which roles are
  required and which are optional; missing required roles are rejected
  with `InvalidContractError` before any I/O.
- `parameters` is **opaque to the protocol** — only the target service
  validates it. Errors there map to `InvalidContractError` with the
  Pydantic message attached.

### Tenancy rule for URIs

URIs in `inputs[].source_uri` and `outputs[].destination_uri` must satisfy:

- Scheme is on the per-deployment allowlist (typically `gs`, `https`,
  `inline`).
- Host (for `gs://`/`https://`) is not on the blocklist.
- The default authorization policy (`TenantPrefixPolicy`) checks the
  **bucket name**, not the path, against the tenant: the bucket must
  start with `<bucket_prefix>-<tenant_id>` (`bucket_prefix` is a
  per-deployment constant, e.g. `gbt-storage`). With
  `require_user_path_segment=True` — the default — the URI's first path
  segment must additionally equal `user_<user_id>`. Concretely, for
  `tenant_id=grabatus`, `user_id=999`, `bucket_prefix=gbt-storage`:
  - `gs://gbt-storage-grabatus/user_999/data.xlsx` ✓
  - `gs://gbt-storage-another-tenant/user_999/data.xlsx` ✗ — bucket does
    not start with the expected `<bucket_prefix>-<tenant_id>` prefix,
    rejected with `UnauthorizedUriError`.
  - `gs://gbt-storage-grabatus/data.xlsx` ✗ — missing the required
    `user_<user_id>` first path segment, rejected with
    `UnauthorizedUriError`.

---

## 2. Webhook callback (worker → platform)

### Transport

```
POST <callback.url>
Authorization: Bearer <JWT-HS256>
Content-Type: application/json
```

The HMAC key is **the shared `SERVICE_SECRET_KEY`** secret. The
platform and the service load the same value (Secret Manager on GCP,
environment variable locally). Rotate the secret in Secret Manager;
both sides pick it up at next process start.

JWT header: `{ "alg": "HS256", "typ": "JWT" }`. There is no `kid` and
no JWK rotation — the secret is the only signal.

### Success payload

```json
{
  "request_id": "<same uuid as the envelope>",
  "status":     "ok",
  "outputs": [
    {
      "role":       "<matches a contract output role>",
      "uri":        "gs://.../result.json.gz",
      "version_id": "<GCS object generation, optional>",
      "size_bytes": 12345,
      "etag":       "<optional>"
    }
  ],
  "metadata": {
    "...": "service-defined; opaque to the platform"
  }
}
```

The platform should:
1. Decode the JWT with `SERVICE_SECRET_KEY` and `algorithms=["HS256"]`.
   Reject any other algorithm.
2. Match `request_id` to the in-flight job; ignore unknown ones (a
   stray retry).
3. Read `outputs[].uri` to know where the results landed; do not
   re-derive the URI from any other source.

### Error payload

```json
{
  "request_id": "<same uuid>",
  "status":     "error",
  "error": {
    "code":    "<one of the codes in §3>",
    "message": "<human-readable; safe to display to operators>"
  }
}
```

Errors **also notify the webhook** — the platform must not assume
silence on failure. If the webhook itself fails, the receiver records
it, but the worker still considers the job done (no retry storm).

---

## 3. Error taxonomy

Every public error inherits `GrabatusServiceError` and carries a stable
`error_code` string. The full set, grouped by stage:

| Stage    | Code                              | Meaning                                           |
| -------- | --------------------------------- | ------------------------------------------------- |
| Decode   | `MalformedMessageError`           | Pub/Sub `message.data` is not valid JSON / b64.   |
| Contract | `InvalidContractError`            | Schema valid but a field rule fails.              |
| Contract | `UnknownServiceError`             | `service.name` is not in the deployment registry. |
| Contract | `UnsupportedProtocolVersionError` | `envelope.protocol_version` is not 1.0.           |
| Auth     | `UnauthorizedUriError`            | URI fails the tenant-prefix check.                |
| Auth     | `UnsupportedSchemeError`          | URI scheme is not on the allowlist.               |
| Auth     | `BlockedHostError`                | URI host is on the blocklist.                     |
| I/O      | `InputNotFoundError`              | Storage adapter could not find an input.          |
| I/O      | `InputReadError`                  | Read failed (network, decompress, parse).         |
| I/O      | `OutputWriteError`                | Write failed.                                     |
| I/O      | `FormatParsingError`              | Bytes did not parse as the declared format.       |
| Compute  | `ComputeError`                    | Service-specific compute failure.                 |
| Compute  | `ComputeTimeoutError`             | Compute exceeded its budget.                      |
| Webhook  | `WebhookAuthError`                | JWT signing/verification failed.                  |
| Webhook  | `WebhookError`                    | Network failure delivering the callback.          |

Codes are stable; copy them into the platform's switch/dispatch verbatim.
Human messages may evolve; do not match on them.

---

## 4. Versioning

- `protocol_version: "1.0"` is the only accepted value today.
- New optional fields are additive within the same version (Pydantic
  models are `extra="forbid"`, so adding a field is a breaking change
  to existing producers — the platform should always emit the latest
  fields and the service deployment must be upgraded first).
- A new version (`"2.0"`, etc.) ships when the schema breaks. The
  receiver will then accept both versions during a transition window
  documented at the top of `docs/CHANGELOG.md`.

---

## 5. Model Readout

Alongside the numeric artefacts a service writes, it may also emit a
`model_readout`: a fixed-schema JSON document that carries everything an
LLM needs to explain a result to the client without inferring,
recalculating, or guessing at context the numbers alone don't carry. It
travels like any other output, under the fixed output role
`model_readout` and format `json`. The Pydantic models live under
`grabatus_service_core.contract.readout` (`ModelReadout` and its
sub-models).

### Top-level blocks (`ModelReadout`)

| Field               | Type                              | Required | Meaning                                                        |
| ------------------- | ---------------------------------- | -------- | --------------------------------------------------------------- |
| `readout_version`   | literal `"1.0"`                    | yes      | Schema version of the readout itself (independent of `protocol_version`). |
| `generated_at`      | datetime, timezone-aware           | yes      | When the readout was produced. A naive timestamp is rejected.   |
| `request`           | `ReadoutRequest`                   | yes      | Which request/result/parameter/tenant produced this readout.    |
| `service`           | `ReadoutService`                   | yes      | Which service, at which semver version, produced it.            |
| `service_knowledge` | `ServiceKnowledge`                 | yes      | What the service is, independent of any single run — see below. |
| `model`             | `ModelDescription`                 | yes      | What was fitted, its assumptions, priors, and what it cannot answer. |
| `data`              | `DataProvenance`                   | yes      | Shape and quality of the data behind the result.                 |
| `artifacts`         | tuple of `ArtifactDescription`, 1–11 | yes    | A data dictionary — role, URI, format, field meanings — for each numeric artefact the service wrote. |
| `findings`          | tuple of `Finding`, 0–50            | no       | The conclusions the service is willing to stand behind, each with its own quantity and uncertainty. |
| `diagnostics`       | tuple of `Diagnostic`, 0–30         | no       | Quality checks already judged against their thresholds.         |
| `overall_quality`   | `OverallQuality`                   | yes      | The single verdict on whether this result can be trusted.       |
| `caveats`           | tuple of `Caveat`, 0–20             | no       | Limitations, each paired with what must not be concluded from it. |
| `explanation_guide` | `ExplanationGuide`                 | yes      | Narration instructions for whichever LLM presents the result — audience, summary, guardrails. |
| `reproducibility`   | `Reproducibility`                  | yes      | Seed, compute duration, input hashes, and library versions needed to reproduce the run. |

### `service_knowledge` fields

This is the block the platform will lean on most for service discovery —
it is static per service version and describes the service itself, not
any particular run.

| Field                     | Type                                     | Required | Meaning                                                    |
| ------------------------- | ----------------------------------------- | -------- | ------------------------------------------------------------ |
| `one_liner`               | string, 1–280 chars                       | yes      | One sentence: what the service does.                        |
| `what_it_does`            | string, 1–2000 chars                      | yes      | Full description of the service's behaviour.                 |
| `problem_solved`          | string, 1–1000 chars                      | yes      | The business problem the service exists to fix.              |
| `when_to_use`             | tuple of string, 1–30 items                | yes      | Situations where this service is the right tool.              |
| `when_not_to_use`         | tuple of string, 1–30 items                | yes      | Situations where it is not — including "use X instead" cases. |
| `personas`                | tuple of `Persona`, 1–30 items             | yes      | Who uses the service (role) and their pains.                   |
| `workflow`                | tuple of `WorkflowStep`, 1–12 items         | yes      | Ordered steps of using the service; `order` values must be contiguous starting at 1. |
| `input_requirements`      | tuple of `InputRequirement`, 1–64 items     | yes      | Each column the service reads, in business terms, with an example. |
| `interpretation_playbook` | tuple of `InterpretationRule`, 1–30 items   | yes      | Situation → meaning → recommendation triples.                  |
| `common_misreadings`      | tuple of `Misreading`, 0–30 items           | no       | Wrong readings seen in the field, paired with the correction.   |
| `glossary`                | tuple of `Term`, 1–30 items                 | yes      | Technical terms mapped to client-facing language.               |
| `limitations`             | tuple of string, 1–30 items                 | yes      | What the service cannot do, stated plainly.                     |

### The base guardrails (immutable)

`ExplanationGuide.guardrails` must start with these four strings, in this
exact order and wording. They are an SDK-level constant
(`BASE_GUARDRAILS` in `contract/readout/guide.py`), **not** a default a
service can override:

1. "Responda apenas com o que este documento afirma. Não extrapole, não
   estime e não complete lacunas com conhecimento geral sobre o setor."
2. "Se a pergunta não puder ser respondida com este documento, diga que
   não sabe e ofereça o contato da Grabatus. Nunca produza um número que
   não esteja escrito aqui."
3. "Não recalcule nada a partir de dados brutos. Os números deste
   documento já são o resultado final da análise."
4. "Sempre que encontrar uma lacuna — algo que o cliente pediu e este
   documento não responde — registre uma sugestão de melhoria no canal
   da Grabatus, descrevendo o que faltou."

A service may append additional, domain-specific guardrails after these
four, but the first four elements of `explanation_guide.guardrails` are
validated by prefix (exact match, in order) at the schema level. A
readout that alters, reorders, or drops any of them is **rejected by the
Pydantic model** before it ever reaches a platform or an LLM.

### The hard rule

> `model_readout` carries conclusions, never raw arrays. Posterior
> samples, per-row records and any collection whose length scales with
> the input belong in the numeric artefact, which the readout describes
> in `artifacts[]`.

### Example (valid, complete)

Generated from the SDK's own canonical builder — never written by hand —
with:

```
uv run python -c "import json; from tests.unit.contract.readout.builders import build_valid_readout; print(json.dumps(build_valid_readout().model_dump(mode='json'), indent=2, ensure_ascii=False))"
```

```json
{
  "readout_version": "1.0",
  "generated_at": "2026-07-31T14:03:11Z",
  "request": {
    "request_id": "3f2b1c8e-0000-4000-8000-000000000000",
    "result_id": "res_0001",
    "parameter_id": "par_0001",
    "tenant_id": "grabatus",
    "origin": "web"
  },
  "service": {
    "name": "grabatus-basketanalysis",
    "version": "1.0.0"
  },
  "service_knowledge": {
    "one_liner": "Descobre quais produtos são comprados juntos.",
    "what_it_does": "Minera regras de associação e ranqueia por impacto financeiro.",
    "problem_solved": "O gerente monta combo por intuição.",
    "when_to_use": [
      "Definir planograma"
    ],
    "when_not_to_use": [
      "Medir efeito causal — use teste A/B"
    ],
    "personas": [
      {
        "role": "Gerente comercial",
        "pains": [
          "Não distingo afinidade real"
        ]
      }
    ],
    "workflow": [
      {
        "order": 1,
        "what_the_user_does": "Sobe a planilha",
        "what_the_llm_should_say": "Confirmo as colunas obrigatórias."
      }
    ],
    "input_requirements": [
      {
        "column": "transaction_id",
        "required": true,
        "business_meaning": "Identifica uma compra.",
        "example": "TX-000481"
      }
    ],
    "interpretation_playbook": [
      {
        "observed_situation": "Lift alto e addressable baixo",
        "what_it_means": "Afinidade real em volume pequeno.",
        "what_to_recommend": "Testar em uma loja."
      }
    ],
    "common_misreadings": [],
    "glossary": [
      {
        "technical_term": "lift",
        "client_language": "mais que o acaso"
      }
    ],
    "limitations": [
      "Não mede canibalização."
    ]
  },
  "model": {
    "display_name": "Regras de associação por FP-Growth",
    "family": "association_rules",
    "paradigm": "heuristic",
    "objective": "Encontrar produtos comprados juntos mais que o acaso.",
    "formulation": "lift(A→B) = P(B|A) / P(B)",
    "assumptions": [
      {
        "statement": "Cada transaction_id é uma cesta única.",
        "violation_impact": "Cestas fragmentadas inflam o suporte.",
        "checked": true
      }
    ],
    "hyperparameters": {
      "min_support": 0.005
    },
    "priors": [],
    "not_designed_for": [
      "inferir causalidade"
    ]
  },
  "data": {
    "observation_count": 142500,
    "granularity": "transaction",
    "period_covered": {
      "start": "2026-01-01",
      "end": "2026-06-30"
    },
    "entities": [
      {
        "label": "SKU",
        "count": 8200
      }
    ],
    "filters_applied": [],
    "known_gaps": [],
    "quality_flags": []
  },
  "artifacts": [
    {
      "role": "rules_json",
      "uri": "gs://gbt-storage-grabatus/user_999/rules.json",
      "format": "json",
      "description": "Regras ranqueadas por impacto financeiro.",
      "fields": [
        {
          "name": "lift",
          "type": "number",
          "unit": null,
          "interval_level": null,
          "meaning": "Razão entre frequência observada e esperada.",
          "read_as": "Quantas vezes mais provável que o acaso."
        }
      ]
    }
  ],
  "findings": [
    {
      "id": "rule_001",
      "importance": 1,
      "statement": "Vinho premium e queijo importado aparecem juntos em 73% das cestas.",
      "quantity": {
        "value": 18500.0,
        "unit": "BRL"
      },
      "uncertainty": {
        "kind": "none",
        "level": null,
        "lower": null,
        "upper": null
      },
      "direction": "increase",
      "comparison_baseline": null,
      "confidence": "high",
      "confidence_rationale": "Baseado em 1.730 cestas."
    }
  ],
  "diagnostics": [
    {
      "name": "data_quality_score",
      "value": 0.87,
      "threshold": "> 0.70",
      "status": "pass",
      "meaning": "Transações retidas e SKUs com preço e categoria."
    }
  ],
  "overall_quality": {
    "status": "pass",
    "summary": "Dados suficientes."
  },
  "caveats": [
    {
      "severity": "high",
      "statement": "Não separa período promocional de orgânico.",
      "do_not_conclude": "Não atribua a afinidade a preferência do cliente."
    }
  ],
  "explanation_guide": {
    "audience": "gerente comercial sem formação estatística",
    "summary_for_llm": "Três combos concentram a maior parte da oportunidade.",
    "what_was_solved": "Quais combos valem virar ação de gôndola.",
    "recommended_narrative_order": [
      "rule_001"
    ],
    "must_not_claim": [
      "que a associação prova causa"
    ],
    "guardrails": [
      "Responda apenas com o que este documento afirma. Não extrapole, não estime e não complete lacunas com conhecimento geral sobre o setor.",
      "Se a pergunta não puder ser respondida com este documento, diga que não sabe e ofereça o contato da Grabatus. Nunca produza um número que não esteja escrito aqui.",
      "Não recalcule nada a partir de dados brutos. Os números deste documento já são o resultado final da análise.",
      "Sempre que encontrar uma lacuna — algo que o cliente pediu e este documento não responde — registre uma sugestão de melhoria no canal da Grabatus, descrevendo o que faltou."
    ]
  },
  "reproducibility": {
    "random_seed": null,
    "compute_duration_seconds": 47.0,
    "input_digests": [
      {
        "role": "transactions",
        "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      }
    ],
    "library_versions": {
      "mlxtend": "0.23.1"
    }
  }
}
```

### State: schema only, not yet enforced

The schema above exists and is locked by a byte-for-byte JSON Schema
snapshot test (`tests/contract_compatibility/snapshots/v1.1/model_readout.schema.json`),
with valid and invalid fixtures exercising every model validator. **Runtime
enforcement is not wired up yet.** No service is required to emit a
`model_readout` today, and none is rejected for omitting or malforming
one. The remaining wiring — a `VALIDATE_READOUT` step in the
`ServiceRunner` between `run_compute` and `save_outputs`, the
`MissingReadoutError` / `InvalidReadoutError` error pair (both under
`ComputeError`, both `retriable=False`), and the `protocol_version:
"1.1"` bump that makes the readout mandatory — belong to later phases of
this work. Do not generate platform integration code that assumes a
`model_readout` will always be present until that lands and this section
is updated to say so.

---

The Pydantic models in `grabatus_service_core.contract` are the
machine-readable form of this document. When in doubt, defer to the
models — they validate everything stated above and a few invariants
that prose can't capture.
