# Integration contract

This document is the **canonical specification** of the protocol every
Grabatus computational service speaks: the Pub/Sub envelope the
platform sends in, the JWT-signed webhook the service sends back, and
the error taxonomy mapped onto both. It is the source of truth — any
disagreement between this file and an implementation is a bug in the
implementation.

The protocol has two live versions. `1.0` is the original contract.
`1.1` adds one thing: `model_readout` is a declared output, so the
readout a service produces is written to storage and the platform can
fetch it. Breaking changes ship as a new `protocol_version`; additive
fields ship under the same version.

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
  per-deployment constant, e.g. `gbt-storage`). This check always runs,
  regardless of configuration.
- Whether the **path** is checked at all depends on the deployment's
  `require_user_path_segment` flag (`TenantPrefixPolicy`
  constructor argument, `security/tenant_prefix_policy.py`):
  - **`True` — the default.** In addition to the bucket check above, the
    URI's first path segment must equal `user_<user_id>`. Concretely,
    for `tenant_id=grabatus`, `user_id=999`, `bucket_prefix=gbt-storage`:
    - `gs://gbt-storage-grabatus/user_999/data.xlsx` ✓
    - `gs://gbt-storage-another-tenant/user_999/data.xlsx` ✗ — bucket
      does not start with the expected `<bucket_prefix>-<tenant_id>`
      prefix, rejected with `UnauthorizedUriError`.
    - `gs://gbt-storage-grabatus/data.xlsx` ✗ — missing the required
      `user_<user_id>` first path segment, rejected with
      `UnauthorizedUriError`.
  - **`False`.** The path is not inspected at all — `_check_user_segment`
    is skipped entirely. Only the bucket-prefix rule above applies, so
    any path under a correctly-prefixed bucket is authorized:
    - `gs://gbt-storage-grabatus/data.xlsx` ✓ — no user segment
      required.
    - `gs://gbt-storage-grabatus/anything/at/all.xlsx` ✓ — same reason.
    - `gs://gbt-storage-another-tenant/data.xlsx` ✗ — the bucket-prefix
      check still applies and still rejects with `UnauthorizedUriError`.
  A deployment that sets `require_user_path_segment=False` is trading
  away per-user isolation within a tenant's bucket — it still enforces
  tenant isolation, but not user isolation inside it. Same rule applies,
  mutatis mutandis, to `bigquery://` URIs via `_check_bigquery_uri`: only
  the project segment's prefix is checked, and there is no path-level
  concept to toggle for that scheme.

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
| Contract | `UnsupportedProtocolVersionError` | `envelope.protocol_version` is neither 1.0 nor 1.1. |
| Auth     | `UnauthorizedUriError`            | URI fails the tenant-prefix check.                |
| Auth     | `UnsupportedSchemeError`          | URI scheme is not on the allowlist.               |
| Auth     | `BlockedHostError`                | URI host is on the blocklist.                     |
| I/O      | `InputNotFoundError`              | Storage adapter could not find an input.          |
| I/O      | `InputReadError`                  | Read failed (network, decompress, parse).         |
| I/O      | `OutputWriteError`                | Write failed.                                     |
| I/O      | `FormatParsingError`              | Bytes did not parse as the declared format.       |
| Compute  | `ComputeError`                    | Service-specific compute failure.                 |
| Compute  | `ComputeTimeoutError`             | Compute exceeded its budget.                      |
| Compute  | `MissingReadoutError`             | Compute produced no `model_readout` role.         |
| Compute  | `InvalidReadoutError`             | The `model_readout` fails the readout schema.     |
| Compute  | `ReadoutMismatchError`            | The `model_readout` describes a different run.    |
| Compute  | `UnknownOutputRoleError`          | Backend asked for a role the contract lacks.      |
| Webhook  | `WebhookAuthError`                | JWT signing/verification failed.                  |
| Webhook  | `WebhookError`                    | Network failure delivering the callback.          |

Codes are stable; copy them into the platform's switch/dispatch verbatim.
Human messages may evolve; do not match on them.

---

## 4. Versioning

- `protocol_version` accepts `"1.0"` and `"1.1"`.
- Under `"1.1"` the contract **must** declare an output with role
  `model_readout`; under `"1.0"` it must **not**. The role is owned by
  the SDK — a service never lists it in its own `OUTPUT_ROLES`, and the
  runner adds it to the expected set on its behalf. A contract that gets
  this wrong fails with `InvalidContractError` before any I/O.
- `outputs` accepts up to 11 entries: 10 service artefacts plus the
  readout.
- New optional fields are additive within the same version (Pydantic
  models are `extra="forbid"`, so adding a field is a breaking change
  to existing producers — the platform should always emit the latest
  fields and the service deployment must be upgraded first).
- A new version (`"2.0"`, etc.) ships when the schema breaks. The
  receiver will then accept both versions during a transition window
  documented at the top of `docs/CHANGELOG.md`.

---

## 5. Model Readout

Alongside the numeric artefacts a service writes, it must also emit a
`model_readout`: a fixed-schema JSON document that carries everything an
LLM needs to explain a result to the client without inferring,
recalculating, or guessing at context the numbers alone don't carry. It
travels like any other output, under the fixed output role
`model_readout` and format `json`.

**Canonical import path:** `grabatus_service_core.contract.readout`. It
exports `ModelReadout`, every sub-model, `build_explanation_guide`, and
the closed vocabularies a service needs to annotate its own code under
`mypy --strict` — `ModelFamily`, `Paradigm`, `UncertaintyKind`,
`Direction`, `Confidence`, `DiagnosticStatus`, `QualityStatus`,
`Severity`, `FieldType`, `HyperparameterValue` and `Origin`. The modules
beneath it (`readout.enums`, `readout.root`, …) are implementation
detail: importing from them, or redeclaring a vocabulary locally, is how
services drift from the schema.

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
| `artifacts`         | tuple of `ArtifactDescription`, 1–10 | yes    | A data dictionary — role, URI, format, field meanings — for each numeric artefact the service wrote. The bound is the contract's output budget minus the readout's own slot; the readout never describes itself. |
| `findings`          | tuple of `Finding`, 0–50            | no       | The conclusions the service is willing to stand behind, each with its own quantity and uncertainty. |
| `diagnostics`       | tuple of `Diagnostic`, 0–30         | no       | Quality checks already judged against their thresholds.         |
| `overall_quality`   | `OverallQuality`                   | yes      | The single verdict on whether this result can be trusted.       |
| `caveats`           | tuple of `Caveat`, 0–20             | no       | Limitations, each paired with what must not be concluded from it. |
| `explanation_guide` | `ExplanationGuide`                 | yes      | Narration instructions for whichever LLM presents the result — audience, summary, guardrails. |
| `reproducibility`   | `Reproducibility`                  | yes      | Seed, compute duration, input hashes, and library versions needed to reproduce the run. |

### Cross-field invariants

Four rules hold across the collections above, enforced by model
validators rather than by any single field:

- `findings` ids are unique. Two findings under one id make every
  reference to it ambiguous.
- `artifacts` roles are unique — the same rule the contract's `outputs`
  already follow.
- `reproducibility.input_digests` roles are unique. Two hashes for one
  role make the run unreproducible, not better documented.
- every entry of `explanation_guide.recommended_narrative_order` names an
  id present in `findings`. A dangling reference hands the LLM an
  instruction it can only obey by inventing the finding, which the
  guardrails in the same document forbid.

The following sections give the field-level detail for every submodel
named above, in the same order. Nothing here is inferred from the
example JSON below — each table is transcribed from the Pydantic model
that owns it.

### `request` fields (`ReadoutRequest`)

| Field          | Type    | Required | Constraints                                    | Meaning                                              |
| -------------- | ------- | -------- | ----------------------------------------------- | ------------------------------------------------------ |
| `request_id`   | string  | yes      | `min_length=1`, `max_length=64`                  | Correlates the readout to the platform request that produced it. |
| `result_id`    | string  | yes      | `min_length=1`, `max_length=128`                 | Opaque platform id of the result record. Matches `contract.references.References`. |
| `parameter_id` | string  | yes      | `min_length=1`, `max_length=128`                 | Opaque platform id of the parameter set used. Matches `contract.references.References`. |
| `tenant_id`    | string  | yes      | `min_length=1`, `max_length=64`, pattern `^[a-z0-9-]+$` | Tenant that owns this readout. Same pattern as `contract.identity.Identity.tenant_id`. |
| `origin`       | literal | yes      | one of `"web"`, `"api"`, `"mcp"`, `"internal"`    | Where the originating request came from. Imported from `contract.envelope.Origin` — not a second, independent vocabulary. |

### `service` fields (`ReadoutService`)

| Field     | Type   | Required | Constraints                                          | Meaning                                        |
| --------- | ------ | -------- | ------------------------------------------------------ | ------------------------------------------------- |
| `name`    | string | yes      | `min_length=1`, `max_length=64`, pattern `^[a-z][a-z0-9_-]*$` | Service slug, e.g. `grabatus-basketanalysis`. Same pattern as `contract.service_descriptor.ServiceDescriptor.name`. |
| `version` | string | yes      | pattern `^\d+\.\d+\.\d+$` (strict semver)                | Service version that produced this readout.     |

### `service_knowledge` fields

This is the block the platform will lean on most for service discovery —
it is static per service version and describes the service itself, not
any particular run.

| Field                     | Type                                     | Required | Meaning                                                    |
| ------------------------- | ----------------------------------------- | -------- | ------------------------------------------------------------ |
| `one_liner`               | string, 1–280 chars                       | yes      | One sentence: what the service does.                        |
| `what_it_does`            | string, 1–2000 chars                      | yes      | Full description of the service's behaviour.                 |
| `problem_solved`          | string, 1–1000 chars                      | yes      | The business problem the service exists to fix.              |
| `when_to_use`             | tuple of string, 1–30 items, each ≤300 chars | yes    | Situations where this service is the right tool.              |
| `when_not_to_use`         | tuple of string, 1–30 items, each ≤300 chars | yes    | Situations where it is not — including "use X instead" cases. |
| `personas`                | tuple of `Persona`, 1–30 items             | yes      | Who uses the service (role) and their pains.                   |
| `workflow`                | tuple of `WorkflowStep`, 1–12 items         | yes      | Ordered steps of using the service; `order` values must be contiguous starting at 1. |
| `input_requirements`      | tuple of `InputRequirement`, 1–64 items     | yes      | Each column the service reads, in business terms, with an example. |
| `interpretation_playbook` | tuple of `InterpretationRule`, 1–30 items   | yes      | Situation → meaning → recommendation triples.                  |
| `common_misreadings`      | tuple of `Misreading`, 0–30 items           | no       | Wrong readings seen in the field, paired with the correction.   |
| `glossary`                | tuple of `Term`, 1–30 items                 | yes      | Technical terms mapped to client-facing language.               |
| `limitations`             | tuple of string, 1–30 items, each ≤300 chars | yes     | What the service cannot do, stated plainly.                     |

#### `service_knowledge` nested types

**`Persona`**

| Field   | Type              | Required | Constraints                       | Meaning                          |
| ------- | ----------------- | -------- | ------------------------------------ | ------------------------------------ |
| `role`  | string             | yes      | `min_length=1`, `max_length=200`     | Who uses the service.               |
| `pains` | tuple of string    | yes      | `min_length=1`, `max_length=30`      | What hurts today for this persona.  |

**`WorkflowStep`**

| Field                      | Type    | Required | Constraints                    | Meaning                                        |
| --------------------------- | ------- | -------- | --------------------------------- | -------------------------------------------------- |
| `order`                      | integer | yes      | `ge=1`, `le=12`                   | Position in the workflow; contiguous from 1 across all steps (enforced across the whole `workflow` tuple, not per-item). |
| `what_the_user_does`         | string  | yes      | `min_length=1`, `max_length=500`  | The user's action at this step.                    |
| `what_the_llm_should_say`    | string  | yes      | `min_length=1`, `max_length=1000` | What the LLM should say at this point.             |

**`InputRequirement`**

| Field               | Type    | Required | Constraints                       | Meaning                             |
| -------------------- | ------- | -------- | ------------------------------------ | ---------------------------------------- |
| `column`             | string  | yes      | `min_length=1`, `max_length=64`      | Name of the column the service reads.    |
| `required`           | boolean | yes      | —                                     | Whether the column is mandatory.          |
| `business_meaning`   | string  | yes      | `min_length=1`, `max_length=500`     | What the column means in business terms. |
| `example`            | string  | yes      | `min_length=1`, `max_length=200`     | Example value.                            |

**`InterpretationRule`**

| Field                 | Type   | Required | Constraints                      | Meaning                                    |
| ---------------------- | ------ | -------- | ------------------------------------ | ----------------------------------------------- |
| `observed_situation`   | string | yes      | `min_length=1`, `max_length=300`     | The situation observed in the result.           |
| `what_it_means`        | string | yes      | `min_length=1`, `max_length=500`     | What that situation means.                      |
| `what_to_recommend`    | string | yes      | `min_length=1`, `max_length=500`     | What to recommend given that meaning.           |

**`Misreading`**

| Field            | Type   | Required | Constraints                   | Meaning                              |
| ----------------- | ------ | -------- | --------------------------------- | ------------------------------------------ |
| `wrong_reading`   | string | yes      | `min_length=1`, `max_length=500`  | A wrong reading seen in the field.         |
| `correction`      | string | yes      | `min_length=1`, `max_length=500`  | The correction.                             |

**`Term`**

| Field              | Type   | Required | Constraints                   | Meaning                          |
| ------------------- | ------ | -------- | --------------------------------- | ------------------------------------- |
| `technical_term`    | string | yes      | `min_length=1`, `max_length=120`  | The technical term.                  |
| `client_language`   | string | yes      | `min_length=1`, `max_length=300`  | How to say it to the client.         |

### `model` fields (`ModelDescription`)

| Field              | Type                                | Required | Constraints                                      | Meaning                                            |
| ------------------- | ------------------------------------ | -------- | ---------------------------------------------------- | ------------------------------------------------------- |
| `display_name`       | string                                | yes      | `min_length=1`, `max_length=200`                     | Human-readable model name.                              |
| `family`             | literal, 10 values                    | yes      | one of `time_series_forecast`, `bayesian_inference`, `ab_test`, `optimization`, `classification`, `regression`, `clustering`, `survival_analysis`, `simulation`, `association_rules` | Broad model family. |
| `paradigm`           | literal, 6 values                     | yes      | one of `bayesian`, `frequentist`, `optimization`, `heuristic`, `ml_supervised`, `ml_unsupervised` | Statistical/computational paradigm used. |
| `objective`          | string                                | yes      | `min_length=1`, `max_length=1000`                    | What the model was fit to do.                           |
| `formulation`        | string \| null                        | no       | default `null`, `max_length=500`                     | Optional formula or equation summary.                   |
| `assumptions`        | tuple of `Assumption`                 | yes      | `min_length=1`, `max_length=30`                      | Stated assumptions, each with its violation impact.     |
| `hyperparameters`    | dict[string, scalar\|null]            | yes      | `max_length=50` (dict length); key ≤120 chars; string values ≤300 chars | Hyperparameter name → strict scalar (`bool`/`int`/`float`/`str`/`None` only — no other collection, no cross-type coercion, and no unbounded string). |
| `priors`             | tuple of `Prior`                      | no       | default `()`, `max_length=30`                        | Prior distributions used, when the paradigm is Bayesian. |
| `not_designed_for`   | tuple of string                       | yes      | `min_length=1`, `max_length=30`, each ≤300 chars     | What the model cannot answer.                           |

**`Assumption`**

| Field               | Type    | Required | Constraints                       | Meaning                                |
| -------------------- | ------- | -------- | ------------------------------------ | -------------------------------------------- |
| `statement`           | string  | yes      | `min_length=1`, `max_length=500`     | The assumption, stated.                       |
| `violation_impact`    | string  | yes      | `min_length=1`, `max_length=500`     | Cost of the assumption being wrong.           |
| `checked`             | boolean | yes      | —                                     | Whether the assumption was actually verified. |

**`Prior`**

| Field           | Type   | Required | Constraints                       | Meaning                                  |
| ---------------- | ------ | -------- | ------------------------------------ | ---------------------------------------------- |
| `parameter`       | string | yes      | `min_length=1`, `max_length=120`     | Which parameter the prior applies to.          |
| `distribution`    | string | yes      | `min_length=1`, `max_length=200`     | The distribution, e.g. `"Normal(0, 1)"`.       |
| `rationale`       | string | yes      | `min_length=1`, `max_length=500`     | Why this prior was chosen.                     |

### `data` fields (`DataProvenance`)

| Field                | Type                     | Required | Constraints                       | Meaning                                          |
| --------------------- | ------------------------- | -------- | ------------------------------------ | ------------------------------------------------------ |
| `observation_count`    | integer                   | yes      | `gt=0`                               | Number of observations behind the result.               |
| `granularity`          | string                     | yes      | `min_length=1`, `max_length=64`      | Grain of one observation, e.g. `"transaction"`.          |
| `period_covered`       | `PeriodCovered` \| null    | no       | default `null`                        | Inclusive date range covered, if applicable.             |
| `entities`             | tuple of `EntitySummary`   | yes      | `min_length=1`, `max_length=30`      | Counts of distinct entities analysed.                    |
| `filters_applied`      | tuple of string            | no       | default `()`, `max_length=30`, each ≤300 chars | What the service removed on purpose.                     |
| `known_gaps`           | tuple of string            | no       | default `()`, `max_length=30`, each ≤300 chars | What was missing at the source.                          |
| `quality_flags`        | tuple of string            | no       | default `()`, `max_length=30`, each ≤300 chars | What the service had to assume in order to run at all.   |

**`PeriodCovered`**

| Field   | Type | Required | Constraints                              | Meaning              |
| ------- | ---- | -------- | -------------------------------------------- | ------------------------ |
| `start`  | date | yes      | —                                              | Inclusive start date.    |
| `end`    | date | yes      | must not precede `start` (model validator)    | Inclusive end date.      |

**`EntitySummary`**

| Field    | Type    | Required | Constraints                   | Meaning                                     |
| -------- | ------- | -------- | --------------------------------- | -------------------------------------------------- |
| `label`   | string  | yes      | `min_length=1`, `max_length=64`  | Kind of entity counted, e.g. `"SKU"`.               |
| `count`   | integer | yes      | `ge=0`                            | How many distinct entities of that kind.            |

### `artifacts` fields (`ArtifactDescription`)

| Field          | Type                          | Required | Constraints                                       | Meaning                                                  |
| --------------- | ------------------------------ | -------- | ------------------------------------------------------ | --------------------------------------------------------------- |
| `role`           | string                          | yes      | `min_length=1`, `max_length=32`, pattern `^[a-z][a-z0-9_]*$` | Matches an output role declared in the envelope's `outputs[]`. |
| `uri`            | URL                             | yes      | valid `AnyUrl`, `max_length=2048`, scheme one of `gs`, `bigquery`, `secret`, published as `"pattern": "^(gs\|bigquery\|secret)://"` | Where the artefact was written. `data:` and `inline://` are rejected — both embed their payload directly in the URI, which would let raw data back into a document that carries none. |
| `format`         | literal                         | yes      | one of `xlsx`, `csv`, `json`, `parquet`, `bigquery`, `inline` | Artefact file format.                                     |
| `description`    | string                          | yes      | `min_length=1`, `max_length=500`                        | What this artefact is.                                          |
| `fields`         | tuple of `FieldDescription`     | yes      | `min_length=1`, `max_length=100`                        | Data dictionary for the artefact's columns.                      |

**`FieldDescription`**

| Field              | Type              | Required | Constraints                              | Meaning                                                        |
| ------------------- | ----------------- | -------- | -------------------------------------------- | -------------------------------------------------------------------- |
| `name`               | string             | yes      | `min_length=1`, `max_length=120`             | Column name.                                                          |
| `type`               | literal            | yes      | one of `number`, `integer`, `string`, `boolean`, `date`, `datetime` | Column's data type.                             |
| `unit`               | string \| null     | no       | default `null`, `max_length=64`              | Unit of measure, if any.                                              |
| `interval_level`     | float \| null      | no       | default `null`, `gt=0.0`, `lt=1.0`           | Confidence/credible level, if this column is an interval bound.       |
| `meaning`            | string             | yes      | `min_length=1`, `max_length=500`             | What the column represents.                                           |
| `read_as`            | string             | yes      | `min_length=1`, `max_length=500`             | How to read the value in plain language.                              |

### `findings` fields (`Finding`)

| Field                    | Type                       | Required | Constraints                                       | Meaning                                                  |
| ------------------------- | --------------------------- | -------- | ------------------------------------------------------ | --------------------------------------------------------------- |
| `id`                       | string                       | yes      | `min_length=1`, `max_length=64`, pattern `^[a-z][a-z0-9_]*$` | Stable identifier for the finding.                        |
| `importance`               | integer                     | yes      | `ge=1`, `le=100`                                        | Relative importance, for ranking/ordering.                       |
| `statement`                | string                       | yes      | `min_length=1`, `max_length=1000`                       | The conclusion, in prose.                                        |
| `quantity`                 | `Quantity`                  | yes      | —                                                        | The number itself, with its unit.                                |
| `uncertainty`               | `Uncertainty`                | yes      | —                                                        | How sure the number is — three conditional regimes, see below.   |
| `direction`                | literal                     | yes      | one of `increase`, `decrease`, `stable`, `not_applicable` | Direction of the finding relative to its baseline.            |
| `comparison_baseline`      | `ComparisonBaseline` \| null | no       | default `null`                                          | What the finding is compared against, if anything.               |
| `confidence`               | literal                     | yes      | one of `high`, `moderate`, `low`                        | Overall confidence in the finding.                               |
| `confidence_rationale`     | string                       | yes      | `min_length=1`, `max_length=500`                        | Why that confidence level.                                       |

**`Quantity`**

| Field   | Type   | Required | Constraints                       | Meaning                          |
| ------- | ------ | -------- | ------------------------------------ | -------------------------------------- |
| `value`  | float  | yes      | —                                     | The numeric value.                    |
| `unit`   | string | yes      | `min_length=1`, `max_length=64`      | Unit of the value, e.g. `"BRL"`.       |

**`Uncertainty`**

| Field   | Type          | Required            | Constraints                       | Meaning                                            |
| ------- | ------------- | -------------------- | ------------------------------------ | --------------------------------------------------------- |
| `kind`   | literal        | yes                  | one of `credible_interval`, `confidence_interval`, `prediction_interval`, `standard_error`, `none` | Vocabulary of the uncertainty method used. |
| `level`  | float \| null  | conditional (see below) | default `null`, `gt=0.0`, `lt=1.0`   | Interval level, e.g. `0.95`.                                |
| `lower`  | float \| null  | conditional (see below) | default `null`                       | Lower bound.                                                |
| `upper`  | float \| null  | conditional (see below) | default `null`                       | Upper bound.                                                |

`Uncertainty` has **three conditional regimes**, enforced by a model
validator (`_bounds_match_the_kind` in `findings.py`) — the per-field
constraints above are necessary but not sufficient, and a code generator
that only reads the field table will produce payloads that fail at
validation time:

- `kind` in `{credible_interval, confidence_interval, prediction_interval}`:
  `level`, `lower`, and `upper` are all **required** (must be non-null),
  and `upper` must not be less than `lower`. Omitting any of the three,
  or supplying `upper < lower`, raises a `ValueError`.
- `kind == "none"`: `lower` and `upper` **must both be null**. Supplying
  either one raises a `ValueError` — there is no interval to report.
- `kind == "standard_error"`: no cross-field rule applies. `level`,
  `lower`, and `upper` may each be null or set; the validator neither
  requires nor forbids them for this kind.

**`ComparisonBaseline`**

| Field   | Type   | Required | Constraints                       | Meaning                               |
| ------- | ------ | -------- | ------------------------------------ | -------------------------------------------- |
| `label`  | string | yes      | `min_length=1`, `max_length=200`     | What the finding is being compared against.  |
| `value`  | float  | yes      | —                                     | The baseline's numeric value.                |

### `diagnostics` and `overall_quality` fields

**`Diagnostic`**

| Field        | Type    | Required | Constraints                       | Meaning                                        |
| ------------- | ------- | -------- | ------------------------------------ | ----------------------------------------------------- |
| `name`         | string  | yes      | `min_length=1`, `max_length=120`     | Name of the quality check.                            |
| `value`        | float   | yes      | —                                     | The measured value.                                    |
| `threshold`    | string  | yes      | `min_length=1`, `max_length=64`      | The threshold it was judged against, e.g. `"> 0.70"`.  |
| `status`       | literal | yes      | one of `pass`, `warn`, `fail`        | Verdict for this specific check.                       |
| `meaning`      | string  | yes      | `min_length=1`, `max_length=500`     | What this check means in plain language.               |

**`OverallQuality`**

| Field     | Type    | Required | Constraints                       | Meaning                                    |
| --------- | ------- | -------- | ------------------------------------ | ------------------------------------------------ |
| `status`   | literal | yes      | one of `pass`, `warn`, `fail`        | Single trust verdict for the whole readout.       |
| `summary`  | string  | yes      | `min_length=1`, `max_length=1000`    | Why that verdict.                                  |

### `caveats` fields (`Caveat`)

| Field               | Type    | Required | Constraints                       | Meaning                                                                 |
| -------------------- | ------- | -------- | ------------------------------------ | ------------------------------------------------------------------------------ |
| `severity`            | literal | yes      | one of `high`, `medium`, `low`       | How serious the limitation is.                                                  |
| `statement`           | string  | yes      | `min_length=1`, `max_length=500`     | The limitation, stated.                                                          |
| `do_not_conclude`     | string  | yes      | `min_length=1`, `max_length=500`     | What must not be concluded from the result because of this limitation. Mandatory — a caveat without it is a disclaimer that changes nobody's reading. |

### `explanation_guide` fields (`ExplanationGuide`)

| Field                          | Type            | Required | Constraints                                                                 | Meaning                                                          |
| -------------------------------- | ---------------- | -------- | -------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `audience`                        | string            | yes      | `min_length=1`, `max_length=200`                                                 | Who the narration is written for.                                       |
| `summary_for_llm`                 | string            | yes      | `min_length=1`, `max_length=2000`                                                | The summary the presenting LLM should base its narration on.            |
| `what_was_solved`                 | string            | yes      | `min_length=1`, `max_length=1000`                                                | The problem this run solved.                                            |
| `recommended_narrative_order`     | tuple of string   | no       | default `()`, `max_length=20`, each ≤64 chars; every entry **must** be an id present in `findings` | Order to narrate the findings in. Ids only — never prose. |
| `must_not_claim`                  | tuple of string   | yes      | `min_length=1`, `max_length=20`, each ≤500 chars                                 | Claims the presenting LLM must never make about this result.            |
| `guardrails`                      | tuple of string   | yes      | `min_length=4` (`len(BASE_GUARDRAILS)`), `max_length=20`, each ≤500 chars; first 4 elements must equal `BASE_GUARDRAILS` verbatim, in order | Narration rules — see "The base guardrails" below for the mandatory prefix. |

### `reproducibility` fields (`Reproducibility`)

| Field                     | Type                     | Required | Constraints                       | Meaning                                                  |
| -------------------------- | ------------------------- | -------- | ------------------------------------ | --------------------------------------------------------------- |
| `random_seed`                | integer \| null           | no       | default `null`                        | Seed used, if the method is stochastic.                          |
| `compute_duration_seconds`   | float                     | yes      | `ge=0.0`                              | Wall-clock time of the compute step.                             |
| `input_digests`              | tuple of `InputDigest`    | yes      | `min_length=1`, `max_length=20`      | Hash of each input, so the same run can be identified later.     |
| `library_versions`           | dict[string, string]      | yes      | `min_length=1`, `max_length=20` (dict length); key ≤120 chars; value ≤64 chars | Library name → pinned version used during compute.       |

**`InputDigest`**

| Field     | Type   | Required | Constraints                                             | Meaning                                             |
| --------- | ------ | -------- | ---------------------------------------------------------- | ---------------------------------------------------------- |
| `role`     | string | yes      | `min_length=1`, `max_length=32`, pattern `^[a-z][a-z0-9_]*$` | Matches an input role declared in the envelope's `inputs[]`. |
| `sha256`   | string | yes      | pattern `^[0-9a-f]{64}$`                                     | SHA-256 hex digest of the input.                              |

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
readout built or parsed through the normal Pydantic constructor —
`ModelReadout(...)`, `.model_validate(...)`, `.model_validate_json(...)`,
or any path that goes through validation — that alters, reorders, or
drops any of the four is **rejected**, whether the tampering happens at
the top level or on an already-built `ExplanationGuide` instance nested
into a `ModelReadout` later (`ExplanationGuide.model_config` sets
`revalidate_instances="always"` specifically so that nesting a
previously-built instance re-runs its validators instead of accepting it
verbatim).

**Limitation, not a gap:** Pydantic's `model_construct()` skips all
validation, by design, at whatever level it is called. A readout (or any
of its sub-models) assembled via `ModelReadout.model_construct(...)`
carries no validation guarantee at all — this is true of every field in
this schema, not just `guardrails`, and no model configuration can close
it: `model_construct()` exists precisely to bypass validation. Nothing in
this SDK calls `model_construct()` to build a readout; the guarantee holds
for every normal construction and parsing path.

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

### State: enforced and persisted under protocol 1.1

The schema above is locked by a byte-for-byte JSON Schema snapshot test
(`tests/contract_compatibility/snapshots/v1.1/model_readout.schema.json`),
with valid and invalid fixtures exercising every model validator.

**Runtime enforcement is live.** `ServiceRunner` runs a `validate_readout`
step between `run_compute` and `save_outputs`. A compute backend that
returns no `model_readout` key in its `ComputeResult` fails with
`MissingReadoutError`; one whose readout does not satisfy the schema above
fails with `InvalidReadoutError`. Both sit under `ComputeError` and are
`retriable=False` — a backend that omits the readout will omit it again on
the next attempt. Both fire before anything is written to storage, so a run
that cannot be explained produces no output at all.

**Persistence follows the protocol version.** Under `1.1` the contract
declares a `model_readout` output and the runner writes the artefact there
like any other, so the platform fetches it by URI. Under `1.0` the readout
is still validated but has nowhere declared to go, and is dropped after the
check. Emit `1.1` contracts to retrieve readouts.

**The service is given what the readout demands.**
`ComputeBackendPort.run` receives a third keyword argument, `context: ComputeContext`,
carrying the run identity the `request` and `service` blocks require:

```python
def run(self, *, inputs, parameters, context) -> ComputeResult:
    readout = ModelReadout(
        generated_at=context.generated_at,   # from the SDK clock, not datetime.now()
        request=context.readout_request(),   # request/result/parameter/tenant/origin
        service=context.readout_service(),   # name and version from the contract
        ...                                  # everything else is the service's own
    )
```

`ComputeContext` exposes `request_id`, `result_id`, `parameter_id`,
`tenant_id`, `origin`, `service_name`, `service_version` and
`generated_at`, plus the two builders above. It is a projection of the
contract, not the contract: a backend never sees callbacks, credentials or
input URIs. `HttpComputeBackend` forwards the same fields to off-platform
backends under a `context` key in its request envelope.

It also exposes `output_uris` — the contract's `destination_uri` for each
declared output role — read through `context.artifact_uri(role)`:

```python
ArtifactDescription(
    role="forecast_json",
    uri=AnyUrl(context.artifact_uri("forecast_json")),
    ...
)
```

`artifacts[].uri` must name where the artefact is actually written, and
only the contract knows that. A backend asking for an undeclared role gets
`UnknownOutputRoleError` rather than a fallback: a plausible-looking wrong
URI in the one document the client is told to trust is worse than a failed
run.

After the schema check, the runner compares the readout's `request` and
`service` blocks against the contract. A readout that is schema-valid but
belongs to another run — a cached or copied artefact — fails with
`ReadoutMismatchError` before anything is written.

---

The Pydantic models in `grabatus_service_core.contract` are the
machine-readable form of this document. When in doubt, defer to the
models — they validate everything stated above and a few invariants
that prose can't capture.
