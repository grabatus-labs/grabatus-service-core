# Design Spec — `grabatus-service-core` and Forecasting Service Refactor

- **Date**: 2026-04-25
- **Status**: Approved (pending implementation plan)
- **Authors**: Rodolpho Ivo, Claude (Sonnet 4.6)
- **Supersedes**: None
- **Target version of the protocol**: `1.0`

---

## 1. Context and Motivation

The Grabatus platform invokes computational services (forecasting, A/B testing, optimization, Bayesian inference, probabilistic simulation) through a fixed orchestration pattern:

```
[Pub/Sub trigger] → [Service compute] → [Storage write] → [Webhook callback]
```

The current `grabatus-forecasting` service implements this pattern in an ad-hoc, monolithic style. Each new service is expected to repeat the same plumbing (Pub/Sub decoding, Storage I/O, JWT webhook, contract parsing, error handling, logging) by hand. This:

- **Inflates per-service code** — ~600 LOC of plumbing per service vs. ~150 LOC of actual compute logic.
- **Multiplies bugs** — every service rewrites the same logic, every service has to be debugged separately.
- **Blocks evolution** — protocol changes require touching every service.
- **Hurts security** — every service must remember to validate URIs, scope tenants, and reject hostile inputs.
- **Hurts testability** — each service builds its own test scaffolding from scratch.

Additionally, the existing forecasting service has structural issues that motivated this redesign: a god class `ServiceDataHandler`, magic-string return signaling (`return 'ok'`), `running_in` mixed into the data payload, hardcoded AWS Lambda URL, and a synchronous compute path that hits the Pub/Sub 600-second ack deadline for non-trivial workloads.

This spec proposes a shared library, `grabatus-service-core`, that encapsulates all common plumbing as a hexagonal (Ports & Adapters) architecture, plus a refactor of the forecasting service to consume that library. The library is designed so that adding a new service (optimization, Bayesian, etc.) requires only writing a `Parameters` schema and a `ComputeBackend` implementation — every other concern is inherited.

## 2. Goals

1. **Single source of truth** for the platform–service communication protocol.
2. **Hexagonal architecture** — domain code never imports cloud SDKs directly; all I/O goes through Ports.
3. **Multi-cloud agnostic** — switching from GCP to AWS is a matter of swapping adapters.
4. **Multi-input / multi-output** native support for declarative I/O (BigQuery + xlsx + Sharepoint, etc.).
5. **Long-running compute support** — workloads up to several hours via decoupled receiver/worker.
6. **Multi-tenant from day one** — `tenant_id` mandatory, URI authorization tenant-scoped.
7. **100% line + branch coverage** on the library, with mutation score ≥ 95%.
8. **Strict typing** — `mypy --strict` enforced, no `Any` in domain code.
9. **Sphinx-generated documentation** in English.
10. **CI-enforced quality gates** — coverage, mutation, security scans, type check, formatting, dependency audits.
11. **Operational observability** — structured JSON logs, OpenTelemetry traces, Cloud Monitoring metrics with correlated `request_id`.

## 3. Non-Goals

- Replacing the Grabatus platform-side code that publishes Pub/Sub messages (this spec only covers the consumer side).
- Building a UI for service management.
- Migrating storage of historical results.
- Supporting languages other than Python.
- Synchronous response to the platform — the platform always receives results via webhook.

## 4. High-Level Architecture

### 4.1 Repository layout

```
grabatus-project/
├── grabatus-service-core/         # the shared library (new)
├── services/
│   └── grabatus-forecasting/      # refactored to consume the lib
└── docs/
    ├── adr/                        # Architecture Decision Records
    └── superpowers/specs/          # design documents (this file lives here)
```

The library lives at the project root, parallel to `services/`. The library is consumed by services via:

- **Development**: `uv pip install -e ../../grabatus-service-core`
- **Production**: `uv add "grabatus-service-core @ git+https://...@v0.1.0"` (pinned to semver tags)

### 4.2 Conceptual layers (hexagonal)

```
                ┌───────────────────────────────────────┐
                │        Application Layer              │
                │  ┌─────────────────────────────────┐  │
                │  │  ServiceRunner (orchestrator)   │  │
                │  │  8-step pipeline                │  │
                │  └─────────────────────────────────┘  │
                └────────────────┬──────────────────────┘
                                 │
                                 ▼
                ┌───────────────────────────────────────┐
                │           Domain Layer                │
                │  ┌──────────────┐  ┌───────────────┐  │
                │  │  Contract    │  │  Errors       │  │
                │  │  (Pydantic)  │  │  (typed)      │  │
                │  └──────────────┘  └───────────────┘  │
                │  ┌──────────────┐  ┌───────────────┐  │
                │  │  Ports       │  │  Security     │  │
                │  │  (Protocols) │  │  Policies     │  │
                │  └──────────────┘  └───────────────┘  │
                └────────────────┬──────────────────────┘
                                 │
                                 ▼
                ┌───────────────────────────────────────┐
                │          Adapters Layer               │
                │  GCS, S3, BigQuery, PubSub, JWT,      │
                │  Cloud Run Jobs, Cloud Tasks,         │
                │  Secret Manager, OpenTelemetry        │
                └───────────────────────────────────────┘
```

The domain layer (Contract, Ports, Errors, Security) has zero external dependencies beyond `pydantic`, `typing`, and the standard library. Adapters import cloud SDKs. The application layer composes ports into a runnable pipeline.

### 4.3 Runtime topology — Receiver/Worker split

To support compute jobs longer than the 600-second Pub/Sub push ack deadline, the system runs in two roles deployed from the same container image:

```
[Pub/Sub Push]
      │
      ▼
[Cloud Run Service "receiver"]    timeout 60s, concurrency 80
      │  - decodes message
      │  - validates contract
      │  - authorizes URIs
      │  - dispatches worker via JobDispatcherPort
      │  - returns 200 to ack Pub/Sub
      ▼
[Cloud Run Jobs "worker"]          timeout up to 24h, concurrency 1
      │  - resolves credentials
      │  - loads inputs
      │  - runs compute (the only service-specific code)
      │  - saves outputs
      │  - notifies webhook
      ▼
[Grabatus Platform Webhook]
```

The runtime mode is selected via the `GBT_RUNTIME_MODE` environment variable: `receiver`, `worker`, or `monolith` (used for local development to run the full pipeline inline in a single process).

Communication between receiver and worker uses `JobDispatcherPort`, with adapters for `CloudRunJobsDispatcher` (production) and `InMemoryJobDispatcher` (testing).

## 5. The Service Contract (Protocol v1.0)

### 5.1 Top-level structure

```json
{
  "envelope": {
    "protocol_version": "1.0",
    "request_id": "a3f9c21e-bf38-4e75-9a2f-c89b6c3f2d12",
    "created_at": "2026-04-25T14:32:10Z",
    "origin": "web"
  },
  "identity": {
    "user_id": "999",
    "tenant_id": "grabatus"
  },
  "references": {
    "parameter_id": "000",
    "result_id": "000"
  },
  "service": {
    "name": "forecast",
    "version": "1.2.0"
  },
  "inputs": [
    {
      "role": "timeseries",
      "source_uri": "gs://gbt-storage-grabatus/services/forecast/user_999/upload/abc.xlsx",
      "format": "xlsx",
      "format_hints": { "format": "xlsx", "sheet": "Dados", "header": 0 }
    }
  ],
  "outputs": [
    {
      "role": "forecast_json",
      "destination_uri": "gs://gbt-storage-grabatus/services/forecast/user_999/results/abc.json.gz",
      "format": "json",
      "compression": "gzip",
      "write_mode": "overwrite"
    }
  ],
  "callback": {
    "url": "https://grabatus.com/webhooks/service-response",
    "auth_scheme": "jwt_hs256"
  },
  "parameters": {
    "ds_col_name": "ds",
    "y_col_name": "y",
    "periods": 180,
    "frequency": "D",
    "seasonality_mode": "multiplicative"
  }
}
```

### 5.2 Section responsibilities

| Section | Owner | Purpose |
|---------|-------|---------|
| `envelope` | library | Protocol version, idempotency key, audit timestamps, request origin |
| `identity` | library + service | Caller identity (user + tenant for multi-tenant authorization) |
| `references` | webhook callback | IDs from the Grabatus platform that round-trip in the response |
| `service` | library | Routing + version compatibility check |
| `inputs` | library (storage) | Where to read data from, in what format, with which credentials |
| `outputs` | library (storage) | Where to write results to, with which write mode and compression |
| `callback` | library (webhook) | How to notify the platform when the work completes |
| `parameters` | service only | Service-specific payload, validated by the service's own Pydantic schema |

### 5.3 Multi-input/multi-output

`inputs` and `outputs` are arrays. Each element has a `role` (snake_case identifier) declared by the service's `ComputeBackendPort` implementation as either required or optional. Library validation rejects contracts that omit required roles or include unknown roles.

Example: a forecasting service requires `role: "timeseries"` and optionally accepts `role: "holidays"` (BigQuery table). It produces `role: "forecast_json"` and `role: "forecast_table"` (BigQuery target).

### 5.4 URI scheme support

Inputs and outputs are addressed via URIs with explicit schemes:

- `gs://bucket/path` — Google Cloud Storage
- `s3://bucket/key` — AWS S3
- `bigquery://project.dataset.table` — BigQuery (read or write)
- `postgres://host:port/db?query=...` — PostgreSQL via service account
- `sharepoint://site/path` — Microsoft Graph API
- `https://...` — read-only HTTP fetch (with host allowlist enforced)
- `file://...` — local filesystem (development only, blocked in production)
- `inline://base64,...` — small payloads embedded in the URI itself
- `secret://provider/name/version` — only for `credential_ref` fields

Each scheme is implemented by a dedicated `StoragePort` adapter. The library ships GCS, BigQuery, S3, local-fs, inline, and HTTP adapters; services can register additional adapters at bootstrap.

### 5.5 Format hints (discriminated union)

`format_hints` is a Pydantic discriminated union keyed on `format`. Each format has its own model with `extra='forbid'` to make typos fail validation:

```python
class XlsxHints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["xlsx"]
    sheet: str = "Sheet1"
    header: int = 0

class CsvHints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["csv"]
    delimiter: str = ","
    encoding: str = "utf-8"

class BigQueryHints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["bigquery"]
    query: str | None = None
    location: str = "US"

# ... etc
FormatHints = Annotated[
    Union[XlsxHints, CsvHints, BigQueryHints, ParquetHints, JsonHints, ...],
    Field(discriminator="format"),
]
```

Services can extend the union via a registry to support service-specific formats.

### 5.6 Versioning rules

- `envelope.protocol_version` follows semver (major.minor).
- The library supports the current major and the previous minor. v1.1 readers accept v1.0 messages.
- Breaking changes (field removal, type narrowing) bump major version. Library supports the previous major for one full release cycle.
- New optional fields are minor bumps.
- Service implementers never read `protocol_version` directly — the library validates compatibility at boot.

## 6. Library Components

### 6.1 Ports (interfaces)

All ports are `typing.Protocol` with `@runtime_checkable` for explicit contract enforcement.

| Port | Methods | Implementations (v1) |
|------|---------|----------------------|
| `StoragePort` | `read(spec, credentials)`, `write(spec, payload, credentials)` | `GcsStorage`, `S3Storage`, `BigQueryStorage`, `LocalFsStorage`, `InlineStorage`, `HttpFetchStorage`, `InMemoryStorage` (test) |
| `MessagePort` | `decode(raw_bytes)`, `encode(envelope)` | `PubSubMessagePort`, `InMemoryMessagePort` (test) |
| `WebhookPort` | `notify(callback, payload)` | `JwtWebhookNotifier`, `RecordingWebhookNotifier` (test) |
| `ComputeBackendPort` | `run(inputs, parameters)`, class-level `REQUIRED_INPUT_ROLES`, `OPTIONAL_INPUT_ROLES`, `OUTPUT_ROLES` | Implemented directly per service. The library ships only `HttpBackend` (legacy: forward request to an external HTTP endpoint such as the existing AWS Lambda) and `FakeComputeBackend` (test). New services implement the Port directly without inheritance. |
| `SecretsPort` | `resolve(secret_ref)` | `GoogleSecretManagerAdapter`, `EnvVarSecretsAdapter` (dev), `InMemorySecretsAdapter` (test) |
| `UriAuthorizationPort` | `authorize(uri, identity)` | `TenantPrefixPolicy`, `AllowAllPolicy` (test only) |
| `ObservabilityPort` | `log(...)`, `span(...)`, `metric(...)` | `StructlogObservability`, `OpenTelemetryObservability`, `NullObservability` (test) |
| `ClockPort` | `now()`, `monotonic()` | `SystemClock`, `FrozenClock` (test) |
| `JobDispatcherPort` | `dispatch(envelope, mode)` | `CloudRunJobsDispatcher`, `CloudTasksDispatcher`, `InMemoryJobDispatcher` (test) |

### 6.2 ServiceRunner (8-step pipeline)

```python
@dataclass(frozen=True, slots=True)
class ServiceRunner(Generic[ParamsT]):
    storage: StoragePort
    message: MessagePort
    webhook: WebhookPort
    compute: ComputeBackendPort
    secrets: SecretsPort
    authorizer: UriAuthorizationPort
    observability: ObservabilityPort
    clock: ClockPort
    job_dispatcher: JobDispatcherPort
    contract_type: type[BaseServiceContract[ParamsT]]
    mode: RuntimeMode  # receiver | worker | monolith

    def execute(self, raw: RawMessage) -> ExecutionResult: ...
```

The pipeline (`receiver` mode runs steps 1-3 plus dispatch; `worker` mode runs steps 4-8; `monolith` mode runs 1-8 in sequence):

1. **Decode** — base64 + JSON parsing of the Pub/Sub envelope.
2. **Validate** — Pydantic validation against `BaseServiceContract[ParamsT]`.
3. **Authorize** — `UriAuthorizationPort` checks every URI; `SchemeAllowlist` and `HostBlocklist` enforce defense-in-depth.
4. **Resolve credentials** — `SecretsPort` resolves every `credential_ref` to a `Credentials` object.
5. **Load inputs** — `StoragePort.read` for each input, in parallel via `asyncio.gather`.
6. **Run compute** — `ComputeBackendPort.run(inputs, parameters)` returns `ComputeResult`.
7. **Save outputs** — `StoragePort.write` for each output, in parallel.
8. **Notify webhook** — `WebhookPort.notify` with a structured payload (status, error if any, output receipts, metadata).

Each step is a function under 20 lines, fully typed, with a single typed exception type for failure. State is propagated as immutable frozen dataclasses (`ParsedEnvelope`, `ValidatedContract`, `AuthorizedContract`, `CredentialBundle`, `LoadedInputs`, `ComputeResult`, `WriteReceipts`, `ExecutionResult`).

### 6.3 Security primitives

Three pre-I/O checks, all enforced before any external call. `UriAuthorizationPort` is a Port (services may inject a stricter policy). `SchemeAllowlist` and `HostBlocklist` are domain utility classes owned by the library — not Ports — because their policy is dictated by the library's security defaults and may only be narrowed via configuration, never widened by a service.

| Component | Kind | Behavior |
|-----------|------|----------|
| `SchemeAllowlist` | Domain utility | Rejects URIs whose scheme is not in `GBT_ALLOWED_SCHEMES`. Default in production: `gs`, `bigquery`, `secret`. Services may narrow via config but not widen. |
| `UriAuthorizationPort` | Port | Default `TenantPrefixPolicy` enforces that every URI's bucket+prefix matches `tenant_id` and `user_id`. Failed auth raises `UnauthorizedUriError` and emits a security alert. Services may inject stricter policies. |
| `HostBlocklist` | Domain utility | For HTTP schemes, blocks `169.254.*` (cloud metadata), `127.*`, `10.*`, `*.internal`, `localhost`. Allowlisted hosts only in production. |

Credentials are never inlined in the contract — only `credential_ref: secret://provider/name/version` is permitted. The `SecretsPort` resolves these at runtime via the service account's IAM-restricted access.

The Cloud Run service account is granted minimum-necessary IAM:
- Receiver: `pubsub.subscriber` (own subscription), `run.invoker` on worker, `secretmanager.secretAccessor` on contract-validation secrets only.
- Worker: `storage.objectViewer/objectCreator` on tenant-scoped buckets, `secretmanager.secretAccessor` on per-tenant secrets, `bigquery.dataViewer/dataEditor` on tenant datasets.

### 6.4 Error taxonomy

```
GrabatusServiceError (abstract base)
├── ContractError
│   ├── MalformedMessageError
│   ├── InvalidContractError
│   └── UnsupportedProtocolVersionError
├── SecurityError
│   ├── UnsupportedSchemeError
│   ├── UnauthorizedUriError
│   ├── BlockedHostError
│   └── CredentialResolutionError
├── StorageError
│   ├── InputNotFoundError
│   ├── InputReadError
│   ├── OutputWriteError
│   └── FormatParsingError
├── ComputeError
│   └── ComputeTimeoutError
└── WebhookError
    └── WebhookAuthError
```

Every exception class declares:
- `error_code: ClassVar[str]` — snake_case identifier surfaced in logs and webhook payloads.
- `http_status: ClassVar[int]` — always 200 for Pub/Sub ack; differentiated for direct API callers.
- `retriable: ClassVar[bool]` — drives `tenacity` retry decisions inside adapters.

Every exception message includes the offending value (e.g. `f"unauthorized URI for tenant={tenant!r}, expected prefix={prefix!r}, got bucket={bucket!r}"`).

The only `except Exception:` permitted is in the FastAPI exception handler at the outermost boundary, which logs full context and acks the Pub/Sub message (re-delivering on a bug compounds damage).

### 6.5 Retry and circuit breaker

- **Tenacity** wraps storage and webhook adapters: 4 attempts (1 try + 3 retries), exponential backoff with jitter (1s, 2s, 4s, 8s+jitter), retried only on `GrabatusServiceError` subclasses whose `retriable: ClassVar[bool]` is `True`.
- **PyBreaker** circuit-breaks the webhook: 5 consecutive failures opens the circuit for 60 seconds. Open-circuit invocations fail fast with `WebhookCircuitOpenError`. Outputs are still saved to storage, so the platform can poll if needed.
- Compute is never retried automatically — the service declares idempotency.

### 6.6 Observability

**Logs** — `structlog` configured for JSON output with `request_id`, `tenant_id`, `service_name`, `service_version`, `protocol_version` bound via `contextvars` at request boundary.

**Traces** — OpenTelemetry SDK with Cloud Trace exporter. Root span per request; child spans per pipeline step; leaf spans per external I/O call. `traceparent` header propagated into the webhook so the platform can stitch end-to-end traces.

**Metrics** — OpenTelemetry metrics with Cloud Monitoring exporter:

| Metric | Type | Tags |
|--------|------|------|
| `grabatus.requests.total` | Counter | service, status, error_code |
| `grabatus.request.duration` | Histogram | service, step, status |
| `grabatus.compute.duration` | Histogram | service |
| `grabatus.storage.bytes_read` | Counter | service, format |
| `grabatus.storage.bytes_written` | Counter | service, format |
| `grabatus.webhook.failures` | Counter | service, error_code |
| `grabatus.circuit_breaker.state` | Gauge | service, target |

**Alerts** (managed via Terraform/yaml in the lib, opt-in per service):

- Error rate > 5% for 5 minutes (warning)
- Compute timeouts > 1/min for 10 minutes (warning)
- Circuit breaker open (critical)
- Webhook failures > 10/min (critical)
- Request duration p99 > 60s (warning)
- Any unauthorized URI attempt (critical, security incident)

### 6.7 Configuration

`pydantic-settings` `BaseSettings` reads from environment variables. Defaults are secure-by-default; production overrides via Cloud Run env vars.

Key variables (all documented in `.env.template`):

| Variable | Purpose | Default |
|----------|---------|---------|
| `GBT_RUNTIME_MODE` | `receiver`/`worker`/`monolith` | (required) |
| `GBT_ENV` | `local`/`staging`/`production` | (required) |
| `GBT_REQUEST_TIMEOUT_SECONDS` | overall request budget | 540 |
| `GBT_HTTP_TIMEOUT_SECONDS` | per outbound HTTP call | 30 |
| `GBT_WEBHOOK_TIMEOUT_SECONDS` | webhook call budget | 15 |
| `GBT_COMPUTE_TIMEOUT_SECONDS` | compute step budget | 480 |
| `GBT_ALLOWED_SCHEMES` | comma-separated URI schemes | `gs,bigquery,secret` |
| `GBT_ALLOWED_HOSTS` | comma-separated HTTP hosts | (empty in prod) |
| `GBT_LOG_LEVEL` | structlog level | `INFO` |
| `GBT_TRACE_SAMPLE_RATE` | OTel sampling | 1.0 |
| `SERVICE_SECRET_KEY` | webhook JWT signing key | (required, from Secret Manager) |

### 6.8 Test fakes (public testing API)

The library ships an importable `grabatus_service_core.testing` package that every service uses in its own tests:

```python
from grabatus_service_core.testing import (
    InMemoryStorage, InMemoryMessagePort, RecordingWebhookNotifier,
    FakeComputeBackend, InMemorySecretsAdapter, AllowAllPolicy,
    NullObservability, FrozenClock, InMemoryJobDispatcher,
    make_envelope, make_identity, make_input_spec, make_output_spec,
    make_contract, build_test_runner,
)
```

This eliminates the need for services to write boilerplate fakes; a service test becomes pure Arrange/Act/Assert with real components composed against fakes.

## 7. Forecasting Service Refactor

### 7.1 What stays in the service

```
src/grabatus_forecasting/
├── parameters.py            # ForecastParameters: Pydantic schema for Prophet hyperparams
├── compute/
│   ├── backend.py           # ForecastComputeBackend(ComputeBackendPort)
│   ├── prophet_runner.py    # wraps Prophet().fit().predict()
│   ├── data_preparation.py  # bytes → DataFrame (xlsx/csv/parquet)
│   └── result_formatting.py # Prophet output → JSON bytes
├── bootstrap/
│   ├── receiver.py          # composes adapters for receiver mode
│   ├── worker.py            # composes adapters for worker mode
│   ├── monolith.py          # local dev: full pipeline inline
│   └── shared.py            # adapters common across modes
├── api/
│   └── app.py               # build_app() — uses lib's app_factory
└── config/
    └── settings.py          # ForecastSettings extends lib's Settings
```

Total estimated LOC: ~400 lines of code + ~600 lines of tests.

### 7.2 What disappears (absorbed by the lib)

- `gbt/utils.py:ServiceDataHandler` (god class)
- `gbt/utils.py:ReadExcel` (becomes lib's xlsx adapter)
- 80% of `main.py` (becomes 20-line bootstrap)
- Pub/Sub decoding logic
- JWT webhook logic
- Storage I/O
- The 4-step pipeline (becomes lib's 8-step `ServiceRunner`)
- Magic-string `'ok'` return signaling
- All ad-hoc `try/except Exception:` blocks
- `running_in` field handling (replaced by `GBT_RUNTIME_MODE` env var)
- Hardcoded AWS Lambda URL (deleted; compute runs in-process via `ProphetComputeBackend`)
- `ipdb` debug breakpoints in `run_model_locally.py`

### 7.3 ForecastParameters schema

```python
class ForecastParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ds_col_name: str = Field("ds", min_length=1, max_length=64)
    y_col_name: str = Field("y", min_length=1, max_length=64)
    periods: int = Field(gt=0, le=3650)
    frequency: Literal["D", "W", "M", "Y"]
    seasonality_mode: Literal["additive", "multiplicative"] = "multiplicative"
    growth: Literal["linear", "logistic", "flat"] = "linear"
    n_changepoints: int = Field(default=25, ge=0, le=200)
    changepoint_range: float = Field(default=0.8, gt=0.0, le=1.0)
    yearly_seasonality: Literal["auto", True, False] | int = "auto"
    weekly_seasonality: Literal["auto", True, False] | int = "auto"
    daily_seasonality: Literal["auto", True, False] | int = "auto"
    seasonality_prior_scale: float = Field(default=10.0, gt=0.0)
    holidays_prior_scale: float = Field(default=10.0, gt=0.0)
    changepoint_prior_scale: float = Field(default=0.05, gt=0.0)
    interval_width: float = Field(default=0.80, gt=0.0, lt=1.0)
    uncertainty_samples: int = Field(default=1000, ge=0, le=10000)
    mcmc_samples: int = Field(default=0, ge=0, le=10000)
```

### 7.4 ForecastComputeBackend declaration

```python
class ForecastComputeBackend(ComputeBackendPort):
    REQUIRED_INPUT_ROLES = frozenset({"timeseries"})
    OPTIONAL_INPUT_ROLES = frozenset({"holidays"})
    OUTPUT_ROLES = frozenset({"forecast_json"})

    def run(
        self, inputs: LoadedInputs, parameters: ForecastParameters
    ) -> ComputeResult: ...
```

The library validates at step 2 that the contract declares all required roles and no unknown roles, failing fast with an actionable error.

## 8. Testing Strategy

### 8.1 Coverage requirements

- **Library**: 100% line + branch coverage measured by `coverage.py` with `branch=True`.
- **Library mutation score**: ≥ 95% via `mutmut`.
- **Service**: 100% line + branch coverage.
- **Service mutation score**: ≥ 85% (compute math contains some untestable mutants in numeric edge cases).

`# pragma: no cover` is permitted only with an inline comment explaining why; a CI check enforces this.

### 8.2 Test layers

```
tests/
├── unit/                    # ~70%, <100ms each, all I/O via fakes
├── integration/             # ~20%, seconds, against emulators (fake-gcs-server, pubsub-emulator) via testcontainers
├── integration_gcp/         # ~8%, minutes, against grabatus-test GCP project, runs pre-merge
├── property/                # hypothesis-based, edge case discovery
├── fuzz/                    # atheris, runs nightly, ensures malformed inputs fail safely
├── contract_compatibility/  # snapshot tests of generated JSON Schema + versioned fixtures
└── conftest.py              # shared fixtures, no I/O
```

### 8.3 Test execution timing

| Suite | Local | CI | Trigger |
|-------|-------|----|---------|
| Unit | <5s | <10s | every push |
| Property | <30s | <60s | every push |
| Integration (emulators) | <60s | <90s | every push |
| Contract compatibility | <5s | <10s | every push |
| Integration (real GCP) | <5min | <5min | pre-merge to main |
| Mutation | 10-30min | 30-45min | pre-merge to main |
| Fuzz | 5min | 5min | nightly |

### 8.4 Tooling

- `pytest` with `pytest-asyncio`, `pytest-cov`
- `hypothesis` for property-based tests
- `atheris` for fuzz testing
- `mutmut` for mutation testing
- `testcontainers` for emulator orchestration
- `freezegun` for time-frozen tests
- `factory_boy` is **not** used — Pydantic factories are sufficient and simpler.

## 9. Quality Gates (CI)

A pull request cannot merge unless all of the following pass:

- ✅ `ruff check .` — zero violations
- ✅ `ruff format --check .` — formatted
- ✅ `mypy --strict src/` — zero errors
- ✅ `bandit -r src/ -ll` — zero medium/high
- ✅ `pip-audit` — zero exploitable CVEs
- ✅ `detect-secrets` — no leaked secrets in commit
- ✅ Unit + property + emulator integration + contract compatibility — all pass
- ✅ Coverage line + branch == 100%
- ✅ `scripts/check_pragma_comments.py` — every `# pragma: no cover` has a justification comment
- ✅ `trivy image --severity HIGH,CRITICAL --exit-code 1` — clean image scan
- ✅ Sphinx build with `-W` flag — zero warnings
- ✅ Pre-merge to main only: real-GCP integration + mutation score ≥ thresholds

## 10. Deployment

### 10.1 Build pipeline

```
GitHub push to main → GitHub Actions:
  1. Lint, type, security checks
  2. Run all test layers
  3. Build multi-stage Docker image (slim, non-root user)
  4. Trivy scan on the image
  5. Tag with commit SHA + semver tag
  6. Push to Artifact Registry: us-east1-docker.pkg.dev/grabatus/services/<name>:<tag>
  7. Deploy receiver as Cloud Run Service
  8. Deploy worker as Cloud Run Job
```

### 10.2 Authentication

- **GitHub → GCP**: Workload Identity Federation (no service account JSON key in GitHub Secrets).
- **Receiver → Worker**: Cloud Run service account with `run.jobs.invoke` permission, scoped to the worker job only.
- **Worker → Storage/BigQuery/Secrets**: tenant-scoped service account with minimum-necessary IAM bindings.

### 10.3 Rollback

Reverting is `gcloud run deploy --image=<previous-tag>`. Previous images remain in Artifact Registry. No state migration needed since the service is stateless.

## 11. Documentation

All documentation is in English and built with Sphinx using the Furo theme.

```
docs/
├── conf.py
├── index.rst                     # entry point
├── quickstart.rst                # build a new service in 50 lines
├── tutorials/
│   ├── building_a_new_service.rst
│   ├── extending_a_port.rst
│   └── running_tests.rst
├── reference/                    # auto-generated by sphinx-autoapi from docstrings + types
│   ├── contract.rst
│   ├── ports.rst
│   ├── adapters.rst
│   ├── runner.rst
│   ├── errors.rst
│   └── testing.rst
├── architecture.rst              # diagrams + ports/adapters explanation
├── security.rst                  # threat model, URI policy, credentials
├── observability.rst             # logs, traces, metrics setup
└── adr/                          # Architecture Decision Records (mirrored)
```

CI builds with `sphinx-build -W` (warnings as errors) and deploys to GitHub Pages on tag pushes.

## 12. Architecture Decision Records

The following ADRs are created alongside this design (in `docs/adr/`):

- **ADR-0001** — Record architecture decisions
- **ADR-0002** — Hexagonal Ports & Adapters as the structural pattern
- **ADR-0003** — Pub/Sub push with decoupled receiver/worker for long-running compute
- **ADR-0004** — Pydantic v2 versioned contract over alternatives (Protobuf, Avro)
- **ADR-0005** — 100% line + branch coverage with explicitly justified pragmas
- **ADR-0006** — Workload Identity Federation for GitHub→GCP authentication
- **ADR-0007** — Multi-tenant from day one with tenant-prefix URI authorization

## 13. Migration Plan (high-level)

The detailed plan is produced by the `writing-plans` skill in a follow-up step. High-level phases:

1. **Bootstrap library** — create `grabatus-service-core/` with project scaffolding, CI, and skeleton modules.
2. **Implement core domain** — Contract (Pydantic), Ports (Protocols), Errors, Security primitives. Tests first.
3. **Implement essential adapters** — GCS, PubSub, JWT webhook, Secret Manager, Cloud Run Jobs dispatcher, structlog observability. Tests first.
4. **Implement ServiceRunner** — 8-step pipeline with full type-state propagation. Tests first.
5. **Implement testing package** — fakes and factories for downstream consumers.
6. **Sphinx documentation skeleton** — auto-generated reference + manual tutorials.
7. **Refactor forecasting service** — adopt the library, delete absorbed code, add comprehensive tests.
8. **CI/CD pipelines** — GitHub Actions, WIF, Artifact Registry, Cloud Run + Cloud Run Jobs deploy.
9. **Production cutover** — staged rollout with the existing service kept warm as fallback for one release cycle.
10. **Decommission AWS Lambda** — once the new in-process Prophet path is validated in production.

## 14. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| 100% coverage becomes performative (low-quality asserts) | Medium | High | Mutation score floor (95%/85%) catches weak tests; reviewer enforces behavior-over-implementation |
| Library evolution breaks existing services | Medium | High | Snapshot tests of JSON Schema; semver discipline; deprecation cycle of one minor version minimum |
| Workload Identity Federation setup is unfamiliar | Medium | Medium | Step-by-step runbook in docs; one-time Terraform module |
| GCP integration tests are flaky | Medium | Low | Run only pre-merge, not on every push; isolate to dedicated `grabatus-test` project |
| Receiver/Worker split adds operational complexity | High | Medium | `monolith` mode for local dev; clear runbook; deployment automated end-to-end |
| Mutmut runs are slow | High | Low | Run pre-merge only, not on every push; cache mutations |
| URI authorization defaults are too restrictive for legitimate cross-tenant use cases | Low | Medium | Policy is composable — services may inject narrower policies but the library default never widens |

## 15. Success Criteria

- The forecasting service is deployed in production using the library, with the existing functionality preserved.
- All tests, coverage, mutation, and security gates pass in CI.
- Sphinx documentation is published.
- A new hypothetical service can be implemented (skeleton + parameters + compute backend) in under 200 lines of code, demonstrated by a smoke prototype.
- p99 request latency does not regress vs. the current implementation.
- Zero security incidents related to URI authorization or credential leakage in the first 90 days post-launch.

## 16. Open Questions (to resolve during implementation)

None blocking. The following are tactical decisions deferred to the implementation plan:

- Exact set of URI schemes shipping in v0.1 vs. deferred to v0.2 (to avoid scope creep).
- Whether to ship a Terraform module for the alerting policies in v0.1 or only as documentation.
- Specific testcontainers images and versions (pinned during plan).
- Sphinx theme final choice (Furo proposed but not strictly final).
- Maximum payload size for `inline://` URIs (proposed default: 64 KiB, configurable via `GBT_INLINE_URI_MAX_BYTES`).
- Whether `factory_boy`-style helpers in `grabatus_service_core.testing.factories` should accept `**overrides` only or full parametric construction (proposed: overrides-only, simpler API).

---

**End of design.**
