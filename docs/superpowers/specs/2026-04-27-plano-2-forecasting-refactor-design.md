# Design Spec — Plano 2: Forecasting Refactor with Shared Receiver

- **Date**: 2026-04-27
- **Status**: Approved (pending implementation plan)
- **Authors**: Rodolpho Ivo, Claude (Opus 4.7)
- **Supersedes**: Section 7 of `2026-04-25-grabatus-service-core-design.md` (refines and extends)
- **Target version of the protocol**: `1.0`
- **Target version of the lib**: `0.2.0`

---

## 1. Contexto e Motivação

A `grabatus-service-core` foi entregue (Plano 1A: domain foundation; Plano 1C: integration layer) com a maioria das peças do spec original implementadas. O Plano 2 é o **primeiro consumidor real** da lib em produção: o `services/grabatus-forecasting/`, hoje monolítico e ad-hoc, é reescrito para consumir as abstrações da lib.

Este plano serve como **teste de fogo** das abstrações projetadas. Até um consumidor real exercitar `ComputeBackendPort`, `BaseServiceContract`, `ServiceRunner` e os adapters, não saberemos se o desenho da lib aguenta o caso de uso que motivou o trabalho todo.

Adicionalmente, o Plano 2 introduz uma **mudança arquitetural** em relação ao spec original: o receiver vira **compartilhado e parte da própria lib**, não um deploy por serviço.

## 2. Decisões consolidadas (do brainstorming)

Cada decisão abaixo foi confirmada pelo usuário durante o processo de design:

| # | Decisão | Justificativa |
|---|---------|---------------|
| Q1 | **Prophet roda in-process** dentro do worker (não via AWS Lambda externa) | A motivação histórica para a Lambda (Prophet não rodar no GCP anos atrás) pode não valer mais; trazer Prophet para dentro elimina hop de rede, dependência cross-cloud e duplicação de empacotamento |
| Q2 | **Cutover total** para o contrato v1.0 — plataforma também atualiza o emissor | Evita camada de tradução duradoura no consumidor; o forecasting refatorado só conhece o formato novo |
| Q3 | **Refactor in-place + uv + pyproject.toml** | Sem dívida técnica intencional duplicando código; `gbt/` é deletado; `uv.lock` substitui `requirements.txt` |
| Q4 | **Receiver+Worker split em produção, Monolith local** | Suporta jobs longos (até 24h via Cloud Run Jobs) sem extrapolar o ack deadline de 600s do Pub/Sub push |
| Q4-bis | **Receiver é compartilhado e parte da lib** (não 1 receiver por serviço) | Para N serviços: 1 + N deploys vs. 2N; receiver não tem lógica de negócio — é infra que valida envelope |
| Q5 | **Local mode usa Pub/Sub HTTP push real** (não bypass) | Máxima paridade dev/prod; erros de middleware/serialização são pegos localmente |
| Q6 | **Production-ready completo** (escopo B) | Inclui WIF, Terraform, Cloud Run + Cloud Run Jobs, IAM, alertas, deploy real |

Adicionalmente, durante a Seção 5 do design o usuário elevou a meta de mutation testing do forecasting para **100%** (vs. ≥85% sugerido inicialmente).

## 3. Não-objetivos

- Substituir `ServiceRunner.RECEIVER` mode da lib (continua existindo, mas marcado como legacy).
- Decomissionar a lib v0.1.0 — versões antigas continuam funcionando para serviços hipotéticos que ainda não migraram.
- Migrar abtest, optimization ou outros serviços computacionais (escopo restrito ao forecasting).
- Suportar múltiplos modelos de forecast simultaneamente — Prophet é o único compute backend.
- Mudar o formato de saída final (continua sendo JSON gzip; o que muda é como ele é produzido).

## 4. Arquitetura

### 4.1 Topologia em produção

```
[Plataforma Grabatus (atualizada para v1.0)]
        │
        ▼
[Pub/Sub topic forecast-trigger]
        │ HTTP push
        ▼
[grabatus-receiver  (Cloud Run Service)]
   imagem: grabatus-service-core:v0.2.0
   responsabilidade: decode, validate envelope, authorize URIs,
                     resolve service.name → worker_job via registry,
                     dispatch via CloudRunJobsDispatcher,
                     ack Pub/Sub
        │ Cloud Run Jobs API
        ▼
[grabatus-forecasting-worker  (Cloud Run Job)]
   imagem: grabatus-forecasting:v1.0.0
   responsabilidade: resolve credentials, load inputs (xlsx do GCS),
                     ProphetComputeBackend.run() in-process,
                     save outputs (json.gz no GCS),
                     notify webhook (JWT HS256)
        │ POST + JWT
        ▼
[Plataforma Grabatus webhook]
```

Receiver é **único e compartilhado** entre todos os serviços computacionais Grabatus (forecast hoje; abtest/optimization/etc. no futuro).

### 4.2 Topologia local

```
[scripts/run_local.py]
        │ HTTP push real (igual prod)
        ▼
[FastAPI monolith em http://127.0.0.1:8001/run_service]
   GBT_RUNTIME_MODE=monolith
   GBT_ENV=local
   adapters:
     - storage: LocalFsStorage + InlineStorage (lê data/*.xlsx)
     - message: PubSubMessagePort (real)
     - webhook: RecordingWebhookNotifier (grava em memória, não HTTP)
     - secrets: EnvVarSecretsAdapter
     - authorizer: AllowAllPolicy
     - job_dispatcher: InMemoryJobDispatcher (fude direto pro worker)
     - compute: ProphetComputeBackend (Prophet REAL)
```

Paridade dev/prod:
- ✅ HTTP push real
- ✅ Contrato v1.0 idêntico
- ✅ FastAPI middleware idêntico
- ✅ ServiceRunner idêntico
- ✅ Prophet idêntico
- ❌ Cloud Run Jobs Dispatch (mockado — único bypass funcional)
- ❌ Webhook HTTP real (gravado em memória)
- ❌ Storage GCS (substituído por `file://`; integration tests usam fake-gcs-server)

### 4.3 Repositórios e seus deploys

| Repo | Build outputs | Deploys |
|------|---------------|---------|
| `grabatus-service-core/` | wheel + imagem `grabatus-service-core:vX.Y.Z` (Artifact Registry) | Cloud Run Service `grabatus-receiver` |
| `services/grabatus-forecasting/` | imagem `grabatus-forecasting:vX.Y.Z` (Artifact Registry); consome wheel da lib via dependência git-pinned | Cloud Run Job `grabatus-forecasting-worker` |

A lib é instalada como **dependência git-pinned** no `pyproject.toml` do forecasting durante CI/produção. Para dev local com mudanças simultâneas na lib, o forecasting suporta `[tool.uv.sources]` com `path = "../../grabatus-service-core", editable = true`.

## 5. Mudanças na lib `grabatus-service-core`

### 5.1 Novo módulo `receiver/`

```
src/grabatus_service_core/
├── receiver/                    # NOVO
│   ├── __init__.py
│   ├── registry.py              # ServiceRegistry (domain utility, frozen dataclass)
│   ├── runner.py                # SharedReceiverRunner
│   ├── app.py                   # build_shared_receiver_app()
│   └── cli.py                   # entry point grabatus-receiver
└── ... (resto inalterado)
```

### 5.2 `ServiceRegistry`

Domain utility imutável (segue o padrão do `SchemeAllowlist`):

```python
@dataclass(frozen=True, slots=True)
class ServiceRegistry:
    by_name: Mapping[str, str]   # "forecast" → "grabatus-forecasting-worker"

    def resolve(self, service_name: str) -> str:
        try:
            return self.by_name[service_name]
        except KeyError as e:
            raise UnknownServiceError(
                f"service.name={service_name!r} not in registry; "
                f"known: {sorted(self.by_name)!r}"
            ) from e

    @classmethod
    def from_env_string(cls, raw: str) -> "ServiceRegistry":
        # "forecast:grabatus-forecasting-worker,abtest:grabatus-abtest-worker"
        ...
```

### 5.3 `SharedReceiverRunner` (classe nova, paralela ao `ServiceRunner`)

Justificativa para classe separada (vs. adicionar modo no `ServiceRunner`): o `ServiceRunner` é genérico sobre `ParamsT` e exige `ComputeBackendPort`. Encaixar shared receiver lá obrigaria opcionalizar 3+ campos e quebrar Single Responsibility.

```python
@dataclass(frozen=True, slots=True)
class SharedReceiverRunner:
    message: MessagePort
    authorizer: UriAuthorizationPort
    job_dispatcher: JobDispatcherPort
    observability: ObservabilityPort
    clock: ClockPort
    scheme_allowlist: SchemeAllowlist
    registry: ServiceRegistry

    def execute(self, raw: RawMessage) -> ReceiverExecutionResult:
        # decode → validate (OpaqueServiceContract) → authorize →
        # registry.resolve(service.name) → dispatch → ack
        ...
```

Reutiliza `decode`, `validate`, `authorize` de `runner/steps.py` — não duplica lógica. Pula `_check_role_compatibility` (não há compute backend no receiver).

### 5.4 `OpaqueServiceContract`

```python
class OpaqueParameters(BaseModel):
    """Parameters as opaque object — receiver doesn't validate them."""
    model_config = ConfigDict(extra="allow", frozen=True)

OpaqueServiceContract = BaseServiceContract[OpaqueParameters]
```

O receiver valida envelope, identity, references, service, inputs, outputs, callback. **Não** valida `parameters` — o worker faz isso quando recebe o payload (com `BaseServiceContract[ForecastParameters]`).

### 5.5 `build_shared_receiver_app()`

```python
def build_shared_receiver_app(
    *, settings: Settings, adapters: SharedReceiverAdapters,
) -> FastAPI:
    runner = SharedReceiverRunner(
        message=adapters.message,
        authorizer=adapters.authorizer,
        job_dispatcher=adapters.job_dispatcher,
        observability=adapters.observability,
        clock=adapters.clock or SystemClock(),
        scheme_allowlist=SchemeAllowlist(allowed=set(settings.allowed_schemes)),
        registry=settings.service_registry,
    )
    return build_app(runner=runner, observability=adapters.observability)
```

`build_app` (existente em `app/factory.py`) ganha generic sobre runner type — só anotação muda.

### 5.6 CLI entry point

```toml
[project.scripts]
grabatus-receiver = "grabatus_service_core.receiver.cli:main"
```

```python
def main() -> None:
    settings = Settings()
    adapters = SharedReceiverAdapters(
        message=PubSubMessagePort(),
        authorizer=TenantPrefixPolicy(),
        job_dispatcher=CloudRunJobsDispatcher(
            project=settings.gcp_project, region=settings.gcp_region,
        ),
        observability=OpenTelemetryObservability(...),
        clock=SystemClock(),
    )
    app = build_shared_receiver_app(settings=settings, adapters=adapters)
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
```

### 5.7 Settings adicionado

```python
class Settings(BaseSettings):
    # ... campos existentes
    service_registry: ServiceRegistry = Field(default_factory=lambda: ServiceRegistry(by_name={}))

    @field_validator("service_registry", mode="before")
    @classmethod
    def _parse_registry(cls, v: Any) -> ServiceRegistry:
        if isinstance(v, str):
            return ServiceRegistry.from_env_string(v)
        return v
```

Lê `GBT_SERVICE_REGISTRY` do env como string e faz parse. Default vazio (modo monolith/worker não precisa).

### 5.8 `Dockerfile.receiver`

Multi-stage, slim, non-root, segue o padrão da Seção 10.1 do spec original:

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
RUN pip install uv && uv build --wheel

FROM python:3.12-slim AS runtime
RUN useradd -r -u 1000 -m grabatus
USER grabatus
WORKDIR /app
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --user /tmp/*.whl && rm /tmp/*.whl
EXPOSE 8080
CMD ["grabatus-receiver"]
```

CI da lib ganha um job extra (`release.yml`) para construir e publicar `grabatus-service-core:vX.Y.Z` no Artifact Registry.

### 5.9 `CompressedStorage` decorator (gap detectado)

O contrato declara `compression: gzip|zstd|none` em `OutputSpec`, mas os adapters atuais (`GcsStorage`, `LocalFsStorage`) **escrevem bytes crus** sem honrar o campo. Para o forecasting funcionar conforme o spec original (`outputs[0].compression="gzip"`), Plano 2 adiciona um decorator:

```python
class CompressedStorage:
    """Decorator: applies compression on write, decompression on read,
    based on InputSpec/OutputSpec.compression."""
    def __init__(self, inner: StoragePort) -> None: ...
    def read(self, *, spec: InputSpec, credentials: Credentials) -> bytes: ...
    def write(self, *, spec: OutputSpec, payload: bytes, credentials: Credentials) -> WriteReceipt: ...
```

Mantém adapters individuais simples (write puro de bytes); compressão é responsabilidade da camada de cima.

### 5.10 Test fakes

`testing/` ganha:
- `InMemoryServiceRegistry(by_name=...)` — para unit tests do `SharedReceiverRunner` e `build_shared_receiver_app`.
- `make_opaque_contract(...)` — espelha `make_contract(...)` mas usa `OpaqueServiceContract`.

### 5.11 O que NÃO muda na lib

- `ServiceRunner.RECEIVER` mode continua existindo (marcado como legacy no Sphinx; remoção em v0.3.0).
- `JobDispatcherPort` já aceita `job_name` por chamada — perfeito para o shared receiver.
- Adapters existentes (GCS, S3, BigQuery, Pub/Sub, JWT webhook, Secret Manager, Cloud Run Jobs dispatcher) — sem mudança.

### 5.12 Estimativa de tamanho

| Arquivo | LOC novas |
|---|---|
| `receiver/registry.py` | ~40 |
| `receiver/runner.py` | ~80 |
| `receiver/app.py` | ~30 |
| `receiver/cli.py` | ~25 |
| `errors/contract.py` (UnknownServiceError) | +10 |
| `settings.py` (registry field) | +20 |
| `contract/base.py` (OpaqueServiceContract) | +15 |
| `adapters/storage_compressed.py` (CompressedStorage) | ~80 |
| `Dockerfile.receiver` | ~25 |
| `testing/__init__.py` (fakes) | +30 |
| Tests novos | ~530 |
| Sphinx docs | ~150 |
| **Total** | **~1035 linhas (≈530 lib + 530 testes/docs)** |

## 6. Refactor do `services/grabatus-forecasting/`

### 6.1 Layout novo (in-place)

```
services/grabatus-forecasting/
├── pyproject.toml                     # NOVO — substitui requirements.txt
├── uv.lock                            # NOVO
├── Dockerfile                         # REESCRITO — multi-stage com Prophet
├── README.md                          # REESCRITO
├── CLAUDE.md                          # REESCRITO
├── src/
│   └── grabatus_forecasting/
│       ├── __init__.py
│       ├── __main__.py                # entry point worker (Cloud Run Jobs)
│       ├── parameters.py              # ForecastParameters
│       ├── compute/
│       │   ├── backend.py             # ProphetComputeBackend
│       │   ├── data_preparation.py    # bytes → DataFrame
│       │   ├── prophet_runner.py      # fit + predict + enriquecimento
│       │   └── result_formatting.py   # forecast → JSON bytes
│       ├── bootstrap/
│       │   ├── shared.py              # adapters compartilhados
│       │   ├── worker.py              # build_worker_runner_for_forecast
│       │   └── monolith.py            # build_monolith_app_for_forecast
│       ├── api/
│       │   └── app.py                 # FastAPI local (monolith mode)
│       └── settings.py                # ForecastSettings
├── tests/                             # unit + property + integration + contract + fuzz
├── data/
│   └── grabatus_forecast_template_v1.xlsx   # MANTIDO (fixture)
├── docs/                              # NOVO — Sphinx
├── scripts/
│   ├── run_local.py                   # SUBSTITUI run_model_locally.py
│   └── plot_forecast.py               # NOVO — visualização separada
├── infra/                             # NOVO — Terraform
└── .github/workflows/                 # NOVO
```

### 6.2 `ForecastParameters` (Pydantic v2)

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
    yearly_seasonality: Literal["auto"] | bool | int = "auto"
    weekly_seasonality: Literal["auto"] | bool | int = "auto"
    daily_seasonality: Literal["auto"] | bool | int = "auto"
    seasonality_prior_scale: float = Field(default=10.0, gt=0.0)
    holidays_prior_scale: float = Field(default=10.0, gt=0.0)
    changepoint_prior_scale: float = Field(default=0.05, gt=0.0)
    interval_width: float = Field(default=0.80, gt=0.0, lt=1.0)
    uncertainty_samples: int = Field(default=1000, ge=0, le=10000)
    mcmc_samples: int = Field(default=0, ge=0, le=10000)
```

### 6.3 `ProphetComputeBackend`

```python
class ProphetComputeBackend:
    REQUIRED_INPUT_ROLES: ClassVar[frozenset[str]] = frozenset({"timeseries"})
    OPTIONAL_INPUT_ROLES: ClassVar[frozenset[str]] = frozenset({"holidays"})
    OUTPUT_ROLES: ClassVar[frozenset[str]] = frozenset({"forecast_json"})

    def __init__(self, *, observability: ObservabilityPort) -> None:
        self._obs = observability

    def run(
        self, *, inputs: LoadedInputs, parameters: ForecastParameters,
    ) -> ComputeResult:
        with self._obs.span("prophet.run"):
            df = prepare_timeseries(
                raw_bytes=inputs.by_role["timeseries"],
                ds_col=parameters.ds_col_name,
                y_col=parameters.y_col_name,
            )
            holidays_df = (
                prepare_holidays(inputs.by_role["holidays"])
                if "holidays" in inputs.by_role else None
            )
            forecast_df = run_prophet(df=df, holidays=holidays_df, parameters=parameters)
            json_bytes = serialize_forecast(forecast_df)
        return ComputeResult(
            by_role={"forecast_json": json_bytes},
            metadata={
                "rows_in": len(df),
                "rows_out": len(forecast_df),
                "horizon_periods": parameters.periods,
            },
        )
```

A separação em `data_preparation.py` / `prophet_runner.py` / `result_formatting.py` faz cada arquivo testável isoladamente.

### 6.4 Modos de execução

- **Worker (produção, Cloud Run Job)**: `__main__.py` lê payload do dispatcher, executa `ServiceRunner` em modo `WORKER`, sai com exit code 0/1.
- **Monolith (local/dev, FastAPI)**: `api/app.py` expõe `POST /run_service`; `ServiceRunner` em modo `MONOLITH` roda os 8 passos no mesmo processo.

### 6.5 `scripts/run_local.py`

Substitui `run_model_locally.py`. Diferenças:
- Constrói envelope **v1.0 real** (não payload legado).
- Usa `file://` para apontar para `data/grabatus_forecast_template_v1.xlsx`.
- POST para `http://127.0.0.1:8001/run_service` (HTTP push real).
- Sem `ipdb.set_trace()` em lugar nenhum.
- Visualização (matplotlib) movida para `scripts/plot_forecast.py`, separado.

### 6.6 `Dockerfile`

Multi-stage:
- Builder: `python:3.12-slim` + `gcc/g++` para compilar `cmdstanpy`.
- Runtime: `python:3.12-slim` + `libgomp1`, non-root user, `CMD ["python", "-m", "grabatus_forecasting"]`.

Imagem final estimada em ~500MB (cmdstan binary + numpy + pandas + prophet).

### 6.7 `pyproject.toml`

```toml
[project]
name = "grabatus-forecasting"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "grabatus-service-core @ git+https://github.com/.../grabatus-service-core@v0.2.0",
    "prophet>=1.1.7",
    "pandas>=2.2",
    "openpyxl>=3.1",
    "fastapi>=0.115",
    "uvicorn>=0.32",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [pytest, pytest-asyncio, pytest-cov, hypothesis, atheris, mutmut, testcontainers,
       freezegun, ruff, mypy, bandit, pip-audit, detect-secrets, sphinx, sphinx-autoapi,
       furo, myst-parser]

[tool.uv.sources]
# Para dev local com mudanças simultâneas na lib
grabatus-service-core = { path = "../../grabatus-service-core", editable = true }
```

### 6.8 O que é deletado do repo atual

| Arquivo | Motivo |
|---|---|
| `gbt/service_handle.py` | god class + magic strings + Lambda hardcoded |
| `gbt/utils.py` | god class + métodos S3 deprecated |
| `gbt/__init__.py` + pasta `gbt/` | obsoleto |
| `gbt/models/model_abtest_normal.{stan,binary}` | A/B test, não forecast — código morto |
| `compile_models.py` | Stan não usado pelo forecasting |
| `main.py` | substituído por `__main__.py` + `api/app.py` |
| `run_model_locally.py` | substituído por `scripts/run_local.py` + `scripts/plot_forecast.py` |
| `requirements.txt` | substituído por `pyproject.toml` + `uv.lock` |
| `__init__.py` raiz | obsoleto |
| `Dockerfile` original | reescrito multi-stage |

`data/grabatus_forecast_template_v1.xlsx` **fica** — fixture útil.

### 6.9 Estimativa de tamanho

| Componente | LOC novas |
|---|---|
| Código produção (`src/grabatus_forecasting/`) | ~810 |
| Tests (unit + property + integration + contract + fuzz) | ~1500 |
| Sphinx docs | ~400 |
| **Total** | **~2710 linhas** |

Deletado: ~600 linhas de `gbt/` + `main.py` + `run_model_locally.py`.

## 7. Estratégia de testes

### 7.1 Camadas

| Camada | % do total | Tempo alvo | Onde rodam I/O |
|---|---|---|---|
| Unit | ~65% | <100ms cada | Tudo em fakes da lib |
| Property (Hypothesis) | ~10% | <1s cada | Fakes |
| Integration (emulators) | ~12% | <5s cada | testcontainers (fake-gcs-server, pubsub-emulator, secret-manager-emulator) |
| Contract compatibility | ~3% | <100ms cada | Nenhum |
| Integration (real GCP) | ~5% | minutos | `grabatus-test` GCP project (pre-merge to main only) |
| Fuzz (Atheris) | ~3% | 5min nightly | Nenhum |
| Mutation (mutmut) | n/a | ~60min pre-merge | Nenhum |

### 7.2 Coverage gates

| Métrica | Lib (já existe) | Forecasting (Plano 2) |
|---|---|---|
| Line coverage | 100% | 100% |
| Branch coverage | 100% | 100% |
| **Mutation score** | ≥95% (manter) | **100%** |

Cada `# pragma: no cover` exige justificativa inline auditada por `scripts/check_pragma_comments.py`. Mutantes equivalentes (raros) exigem `# pragma: no mutate — equivalente: <prova>`.

### 7.3 Mocking — o que é fake, o que é real

Princípio: **fake apenas no boundary do sistema**. Tudo entre a borda e o `ServiceRunner` é real, igual em produção.

| Camada | Unit | Property | Integration emulators | Real-GCP | Production |
|---|---|---|---|---|---|
| `MessagePort` | fake | fake | real (PubSubMessagePort + emulator) | real | real |
| `StoragePort` | InMemoryStorage | InMemoryStorage | real (GcsStorage + fake-gcs-server) | real GCS | real GCS |
| `WebhookPort` | RecordingWebhookNotifier | recording | recording | recording | real (JwtWebhookNotifier) |
| `SecretsPort` | InMemorySecretsAdapter | in-memory | real (secret-manager-emulator) | real | real |
| `JobDispatcherPort` | InMemoryJobDispatcher | in-memory | in-memory | n/a | CloudRunJobsDispatcher |
| `ComputeBackendPort` (Prophet) | stub | stub | **REAL Prophet** | real | real |
| `ClockPort` | FrozenClock | FrozenClock | FrozenClock | SystemClock | SystemClock |
| `ObservabilityPort` | NullObservability | null | NullObservability | OTel exporting | OTel exporting |

Regra de ouro: **nenhum teste fake'a o ServiceRunner ou os steps do pipeline**.

### 7.4 Determinismo do Prophet

Prophet com `mcmc_samples=0` (default do contrato) usa otimização MAP — determinístico dado seed fixo. Fixture autouse em `conftest.py`:

```python
@pytest.fixture(autouse=True)
def _deterministic_prophet():
    np.random.seed(42)
    random.seed(42)
    yield
```

Para `mcmc_samples > 0`, unit tests **stubam** Prophet; só integration tests rodam Prophet de verdade, e nesses casos o assert é sobre estrutura+ranges, não valores exatos.

### 7.5 Implicações de 100% mutation score

1. Toda função numérica precisa de teste que distingue cada constante (ex.: limiar `0.95` falha se for `0.94` ou `0.96`).
2. Mutantes equivalentes anotados inline com prova.
3. Prophet entra na suíte de mutation (mutmut roda `pytest tests/unit tests/property tests/integration -x -q`).
4. Refator orientado a testabilidade onde necessário — extrair lógica matável em funções puras testáveis isoladamente; nunca baixar a meta.
5. Mutation testing também sobre integration — mudanças de `>` para `>=` em fronteira de feriado só morrem se houver assert sobre output do Prophet de verdade.

## 8. CI/CD e infraestrutura production-ready

### 8.1 GitHub Actions (mesmo padrão nos dois repos)

| Workflow | Trigger | Suítes | Tempo alvo |
|---|---|---|---|
| `ci.yml` (push/PR) | qualquer branch | unit + property + emulator integration + contract | <3min |
| `ci.yml` (pre-merge to main) | PR para main | acima + real-GCP integration + mutation | <90min (ajustado para mutation 100%; ver Risco #4) |
| `release.yml` | tag `v*.*.*` | build + Trivy + push para Artifact Registry | <15min |
| `deploy.yml` | workflow_dispatch manual | terraform apply em ambiente alvo | <10min |
| `nightly.yml` | cron noturno | fuzz (+ real-GCP no forecasting) | 5-10min |

### 8.2 Workload Identity Federation (sem service account JSON keys)

Configuração versionada em `grabatus-service-core/infra/wif/`:

- Pool: `github-actions-pool`
- Provider: GitHub Actions OIDC (`token.actions.githubusercontent.com`)
- Attribute condition: `assertion.repository_owner == 'grabatus'`
- Service accounts dedicados: `ci-{repo}`, `release-{repo}`, `deploy-{repo}-{env}`

Cada SA tem permissões mínimas para seu papel (CI lê test project, release pushes em Artifact Registry, deploy applya Terraform no ambiente respectivo).

### 8.3 Terraform layout

```
grabatus-service-core/infra/
├── wif/                         # GitHub Actions → GCP federation (uma vez para a org)
├── artifact_registry/           # repo us-east1-docker.pkg.dev/grabatus/services/
├── shared_receiver/             # Cloud Run Service + SA + IAM
└── alerts/                      # error rate, p99, security incidents

services/grabatus-forecasting/infra/
├── service_account.tf           # forecasting-worker SA + IAM tenant-scoped
├── cloud_run_job.tf             # Cloud Run Job + env vars
├── secrets.tf                   # SERVICE_SECRET_KEY no Secret Manager
├── pubsub.tf                    # tópico forecast-trigger + subscription push + DLQ
└── alerts.tf                    # alertas específicos do forecasting
```

### 8.4 Cloud Run Service (receiver compartilhado)

```hcl
resource "google_cloud_run_v2_service" "receiver" {
  name     = "grabatus-receiver"
  location = "us-east1"
  template {
    service_account = google_service_account.receiver.email
    timeout         = "60s"
    max_instance_request_concurrency = 80
    scaling {
      min_instance_count = 1   # warm sempre — ~$5-10/mês ocioso
      max_instance_count = 10
    }
    containers {
      image = "us-east1-docker.pkg.dev/grabatus/services/grabatus-service-core:${var.image_tag}"
      env {
        name  = "GBT_SERVICE_REGISTRY"
        value = var.service_registry  # "forecast:grabatus-forecasting-worker,abtest:..."
      }
      # ... outros envs
      resources { limits = { cpu = "1", memory = "512Mi" } }
    }
  }
}
```

### 8.5 Cloud Run Job (forecasting worker)

```hcl
resource "google_cloud_run_v2_job" "worker" {
  name     = "grabatus-forecasting-worker"
  location = "us-east1"
  template {
    template {
      service_account = google_service_account.worker.email
      timeout         = "1800s"   # 30 min — folga sobre Prophet típico (<5 min)
      max_retries     = 0          # service runner decide retriability por erro
      containers {
        image = "us-east1-docker.pkg.dev/grabatus/services/grabatus-forecasting:${var.image_tag}"
        env { name = "SERVICE_SECRET_KEY"; value_source { secret_key_ref { ... } } }
        resources { limits = { cpu = "2", memory = "4Gi" } }
      }
    }
  }
}
```

### 8.6 IAM least privilege

| Identidade | Permissões |
|---|---|
| `grabatus-receiver` | `run.invoker` em workers registrados; **nada** de Storage/Secrets/BigQuery |
| `grabatus-forecasting-worker` | `storage.objectViewer/objectCreator` em buckets escopados ao tenant; `secretmanager.secretAccessor` em `SERVICE_SECRET_KEY` |
| `pubsub-pusher` | `run.invoker` apenas no `grabatus-receiver` |
| `ci-*` | leitura em `grabatus-test`; nada em produção |
| `release-*` | push em Artifact Registry; deploy via `run.developer`; **nada** de delete |

### 8.7 Pub/Sub topic + subscription + DLQ

`forecast-trigger` (tópico) → push para `${receiver_url}/run_service` com OIDC token. `ack_deadline=60s`, retry exponencial 10s-600s. DLQ `forecast-trigger-dlq` recebe mensagens após 5 falhas; alertas configurados.

### 8.8 Alertas (Terraform)

- Error rate > 5% por 5 min (warning)
- Webhook failures > 10/min (critical)
- Circuit breaker open (critical)
- DLQ recebeu mensagem (critical)
- Unauthorized URI (critical, security incident)
- Worker p99 > 600s (warning, perto do timeout)

### 8.9 Coordenação com a plataforma Grabatus (cutover do contrato)

1. Plano 2 entrega imagens em staging (ambiente `grabatus-staging`).
2. Smoke test em staging com mensagens v1.0 sintéticas.
3. Time da plataforma faz PR no repo da Grabatus alterando emissor para v1.0; merge bloqueado até passar testes contra staging do forecasting.
4. Janela de cutover combinada: plataforma deploya emissor v1.0 + forecasting deploya em produção simultaneamente; legacy mantido warm por 7 dias.
5. Rollback combinado: plataforma volta para emissor legacy + forecasting redeploya Cloud Run service antigo.

### 8.10 Ambientes

| Ambiente | Projeto GCP | Quem deploya | Quem testa |
|---|---|---|---|
| `local` | n/a | dev | dev |
| `test` | `grabatus-test` | CI (real-GCP integration) | CI |
| `staging` | `grabatus-staging` | `deploy.yml` manual | dev + plataforma |
| `production` | `grabatus` | `deploy.yml` com aprovação CODEOWNERS | tráfego real |

### 8.11 Rollback

- Cloud Run Service: `gcloud run services update-traffic --to-revisions=<previous-rev>=100`
- Cloud Run Job: redeploy do tag anterior via `terraform apply -var image_tag=v1.0.0-prev` ou `gcloud run jobs replace-image`
- Imagens no Artifact Registry são imutáveis e ficam indefinidamente.

## 9. Plano de migração — fases

```
Fase 1: Lib enhancements              (grabatus-service-core)
Fase 2: Lib release infrastructure    (grabatus-service-core)
Fase 3: Forecasting refactor (local)  (services/grabatus-forecasting)
Fase 4: Forecasting CI                (services/grabatus-forecasting)
Fase 5: Infrastructure-as-Code        (ambos os repos)
Fase 6: Staging deploy
Fase 7: Coordenação com a plataforma  (dependência externa)
Fase 8: Production cutover
Fase 9: Decomissionamento
```

### 9.1 DAG de dependências

```
Fase 1 → Fase 2 → Fase 6 (lib publicada para staging puxar)
   │                ▲
   ▼                │
Fase 3 → Fase 4 → Fase 5 → Fase 6 → Fase 7 → Fase 8 → Fase 9
                              ▲
                              │
                       (aprovação humana)
```

Paralelizações possíveis:
- Fases 1 e 3 compartilham só `OpaqueServiceContract` + `CompressedStorage` — Fase 3 começa com lib em editable install, troca para wheel pinada quando Fase 2 publicar.
- Fase 4 (CI) começa com esqueleto de Fase 3.
- Fase 5 (Terraform) escrita em paralelo com Fase 3, mas só apply na Fase 6.

### 9.2 Marcos verificáveis

| Fase | Comando que prova "feito" |
|---|---|
| 1 | `cd grabatus-service-core && uv run pytest && uv run mutmut run && uv run python scripts/check_mutation_score.py --min=95` |
| 2 | `gcloud artifacts docker images list us-east1-docker.pkg.dev/grabatus/services/grabatus-service-core` retorna `:v0.2.0` |
| 3 | `cd services/grabatus-forecasting && uv run uvicorn grabatus_forecasting.api.app:app --port 8001 &` + `uv run python scripts/run_local.py` retorna webhook gravado com forecast válido |
| 4 | PR no forecasting com checks verdes em GitHub Actions |
| 5 | `terraform plan` limpo nos 3 ambientes após 2 aplicações idempotentes |
| 6 | Mensagem v1.0 sintética em staging dispara worker; webhook chega em endpoint de gravação |
| 7 | Time da plataforma confirma "pronto para emitir v1.0 em produção em data X" |
| 8 | Dashboards de produção mostram tráfego v1.0 sem erros por 24h |
| 9 | `aws lambda get-function --function-name grabatus-forecast-lambda` retorna 404; legacy Cloud Run service deletado |

### 9.3 Padrão para cada fase

1. Escrever testes primeiro (TDD) para a unidade nova.
2. Implementar código mínimo que faz testes passarem.
3. Refatorar para qualidade (clean code, anti-smells).
4. Atualizar Sphinx.
5. Validar pragmas, mutation, coverage.
6. Commit + revisão.

## 10. Riscos e mitigações

| # | Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|---|
| 1 | Prophet ainda não roda corretamente no Cloud Run Jobs | Média | Alto | Spike de teste isolado **antes** de Fase 3: `docker build` da imagem do worker + `docker run` do `__main__.py` com payload sintético. Se falhar, voltar para Q1 e reconsiderar Lambda |
| 2 | Imagem do worker > 2GB por Prophet + cmdstan | Alta | Médio | Multi-stage Dockerfile; medir na Fase 3; alpine ou distroless se necessário |
| 3 | Cold start do receiver excede ack deadline 60s | Baixa | Alto | `min_instance_count=1`; CPU "always allocated" |
| 4 | Mutation testing com 100% pre-merge ultrapassa target de 90 min | Média | Médio | Paralelizar mutmut por arquivo via `--use-coverage`; matrix no GitHub Actions com sharding por módulo se necessário; medir tempo real ao final de Fase 4 e revisar target |
| 5 | `OpaqueServiceContract` aceita envelopes malformados que deveriam ser rejeitados | Média | Alto | Property tests com hypothesis gerando envelopes adversariais; conferir que worker (com `extra="forbid"`) rejeita |
| 6 | Time da plataforma atrasa entrega do emissor v1.0 | Alta | Alto | Fase 6 (staging) não bloqueia Fase 7; staging consome envelopes sintéticos enquanto plataforma trabalha |
| 7 | `CompressedStorage` regride performance em outputs grandes | Baixa | Baixo | Benchmark: gzip de forecast JSON (~50KB-2MB) deve ser <100ms |
| 8 | Conflito `cmdstan` × Python 3.12 × Pydantic 2 | Média | Alto | Spike na Fase 1: `pip install prophet` em Python 3.12 limpo + smoke `Prophet().fit().predict()` |
| 9 | Custo do receiver warm 24/7 explode | Baixa | Baixo | Cloud Run com `min_instance=1` e CPU "request-based" custa ~$5-10/mês |
| 10 | Mensagens em flight perdidas no cutover | Média | Médio | Legacy drena subscription até `unacked_messages == 0`; nova subscription só ativa após plataforma flipar |

## 11. Critérios de sucesso

### Funcional
- ✅ Mensagem Pub/Sub v1.0 da plataforma resulta em forecast no GCS + webhook entregue, em produção, sem erros.
- ✅ AWS Lambda `grabatus-forecast-lambda` deletada.
- ✅ Cloud Run Service legacy `grabatus-forecasting` deletado.
- ✅ Receiver compartilhado serve forecast e suporta novos serviços sem novo deploy de receiver.

### Qualidade
- ✅ Lib v0.2.0: 100% line+branch coverage; mutation ≥95%.
- ✅ Forecasting v1.0.0: 100% line+branch coverage; **mutation 100%**.
- ✅ Sphinx docs publicados (lib + forecasting), zero warnings.
- ✅ Trivy scan limpo nas duas imagens em produção.
- ✅ Bandit + pip-audit + detect-secrets sem violações.

### Operacional
- ✅ Alertas armados (error rate, p99, circuit breaker, DLQ, unauthorized URI).
- ✅ Dashboards Cloud Monitoring acessíveis.
- ✅ Logs estruturados JSON com `request_id`, `tenant_id`, `service_name` correlacionados.
- ✅ p99 do worker em produção **não pior** que p99 da Lambda legacy.
- ✅ Runbook de rollback escrito e testado.

### Segurança
- ✅ WIF configurado — zero service account JSON keys em GitHub Secrets.
- ✅ IAM bindings tenant-scoped.
- ✅ Receiver tem `run.invoker` apenas nos workers registrados.
- ✅ Zero incidentes de unauthorized URI nos primeiros 7 dias.
- ✅ JWT do webhook resolvido via Secret Manager (nunca env var direta).

## 12. Questões em aberto

Resolvidas durante o brainstorming. Tactical decisions deferidas ao plano de implementação:

- Tag exata da lib v0.2.0 (decidido na Fase 1 quando implementação estiver pronta).
- Configuração específica de paralelismo do mutmut (Fase 4, baseado em medição empírica).
- Tempo exato do warm-up do receiver legacy pós-cutover (proposta: 7 dias; ajustável conforme volume de tráfego).
- Cardinalidade exata dos buckets de input/output em `var.input_buckets`/`var.output_buckets` do Terraform (lista vem da configuração atual do `grabatus-forecasting`).

---

**Fim do design.**
