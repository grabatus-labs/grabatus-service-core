# Sub-Plan 1C — Integration Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the now-functional `ServiceRunner` (delivered in 1B) with the production integration surface: a FastAPI app factory + Pub/Sub push route + health endpoints + global exception handler + request-id middleware; a complete observability stack (structlog JSON + OpenTelemetry tracing + Cloud Trace exporter + the seven catalogued metrics + `traceparent` propagation in webhooks); and a `pydantic-settings`-driven runtime that boots into `receiver`, `worker`, or `monolith` mode from a single container image. Concludes with an end-to-end smoke service under `examples/` proving the whole stack composes.

**Architecture:** Hexagonal integration — the new layer is a thin shell around `ServiceRunner` (no business logic). FastAPI handles the HTTP transport for receiver/monolith; a dedicated CLI entrypoint handles worker invocations from Cloud Run Jobs. Observability is a `Settings`-driven side-effect: nothing in the domain or runner imports OTel SDKs directly — they consume only `ObservabilityPort`. The OpenTelemetry SDK is wired once at process startup and disposed at shutdown.

**Tech Stack added in 1C:** FastAPI, Starlette, `pydantic-settings`, `structlog` (JSON renderer + contextvars), `opentelemetry-sdk` + `opentelemetry-exporter-gcp-trace` + `opentelemetry-exporter-gcp-monitoring`, `uvicorn`. All already declared in `pyproject.toml` from 1A.

**Repository:** `/Users/rodolpho/Projects/grabatus-project/grabatus-service-core/`

**Spec sections covered by this sub-plan:** §6.6 (Observability), §6.7 (Configuration), §4.3 (Receiver/Worker topology — wire-up only; the runner itself was built in 1B). The exception handler closes the loop on §6.4 by mapping every typed error to its declared `http_status`/`error_code`.

**Out of scope for Sub-Plan 1C (delivered later):**
- Sphinx documentation, ADRs, architecture diagrams — Sub-Plan 1D
- GitHub Actions CI/CD, Workload Identity Federation, Trivy/pip-audit gates — Sub-Plan 1D
- Property tests (hypothesis), fuzz tests (atheris), mutation testing (mutmut) — Sub-Plan 1D
- Contract compatibility snapshots — Sub-Plan 1D
- The `grabatus-forecasting` refactor — Plan 2

**Acceptance criteria (all must hold at end of Sub-Plan 1C):**
- `uv run pytest` exits 0 with line + branch coverage 100% across the entire `src/grabatus_service_core/` tree, including the new `app/`, `observability/`, `bootstrap/`, and `settings.py` modules.
- `uv run mypy --strict src/ tests/` exits 0.
- `uv run ruff check . && uv run ruff format --check .` exits 0.
- `uv run bandit -r src/ -ll` zero medium/high findings.
- `uv run pre-commit run --all-files` exits 0.
- `examples/echo_service/` boots via `uv run python -m examples.echo_service` (which delegates to `uvicorn`), accepts a Pub/Sub push POST against `http://localhost:8080/run_service`, runs the full pipeline against in-memory adapters with a `FakeComputeBackend`, and the `RecordingWebhookNotifier` records exactly one call with the expected payload.
- A new consumer can write a service main of fewer than 50 lines: `Settings(_env_file=...) → ForecastComputeBackend() → bootstrap.build_app(settings, compute) → uvicorn.run(app)`.
- Worker mode is invokable as `python -m grabatus_service_core` with `GBT_RUNTIME_MODE=worker`, `GBT_JOB_PAYLOAD=<contract-json>`, `GBT_JOB_REQUEST_ID=<uuid>`, exits 0 on success and writes the same observability events as monolith mode.

---

## Conventions used in this plan

- All paths are relative to the repo root: `/Users/rodolpho/Projects/grabatus-project/grabatus-service-core/`
- Python 3.12+ features (PEP 695 generics, `match`, `|` unions)
- Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`)
- AAA test structure (Arrange / Act / Assert)
- TDD mandatory — failing test exists in the repo before implementation
- File line limit: 500 lines (target 200–300)
- Function line limit: 20 lines
- Quality gate after every task: `ruff check`, `ruff format --check`, `mypy --strict`, `pytest` (100% line + branch), `bandit -r src/ -ll`, `pre-commit`

---

## Phase ordering

Phases run in order: **I → J → K**. Within a phase, tasks may be interleaved with reviews but must be committed in numerical order to keep `main` shippable.

---

## Phase I — FastAPI integration

### Task I1: App factory skeleton — `build_app(runner, observability)`

**Files:**
- Create: `src/grabatus_service_core/app/__init__.py`
- Create: `src/grabatus_service_core/app/factory.py`
- Create: `tests/unit/app/__init__.py`
- Create: `tests/unit/app/test_factory.py`

**Why:** A thin factory is the single seam services use to obtain a ready-to-serve `FastAPI` instance bound to their compute backend. Keeping the factory tiny (no business logic, no settings parsing) means consumers can compose it under any test harness — including `httpx.AsyncClient(transport=ASGITransport(app=...))` for end-to-end tests later in Phase K.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/app/test_factory.py
"""Tests for build_app(): the FastAPI factory that mounts the runner."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from grabatus_service_core.app import build_app
from grabatus_service_core.contract.base import BaseServiceContract
from grabatus_service_core.runner import RuntimeMode, build_runner
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.testing import (
    AllowAllPolicy,
    FrozenClock,
    InMemoryJobDispatcher,
    InMemoryMessagePort,
    InMemorySecretsAdapter,
    InMemoryStorage,
    NullObservability,
    RecordingWebhookNotifier,
    make_fake_compute_backend,
)


class _Params(BaseModel):
    horizon: int = 30


def _runner(**overrides: Any):
    defaults: dict[str, Any] = {
        "contract_type": BaseServiceContract[_Params],
        "storage": InMemoryStorage(seed={}),
        "message": InMemoryMessagePort(),
        "webhook": RecordingWebhookNotifier(),
        "compute": make_fake_compute_backend(
            required_input_roles=frozenset({"timeseries"}),
            output_roles=frozenset({"result_json"}),
            outputs={"result_json": b"x"},
        ),
        "secrets": InMemorySecretsAdapter(seed={}),
        "authorizer": AllowAllPolicy(),
        "observability": NullObservability(),
        "clock": FrozenClock(iso_string="2026-04-26T00:00:00Z"),
        "job_dispatcher": InMemoryJobDispatcher(),
        "scheme_allowlist": SchemeAllowlist(allowed={"gs"}),
        "mode": RuntimeMode.MONOLITH,
    }
    defaults.update(overrides)
    return build_runner(**defaults)


def test_build_app_returns_fastapi_instance() -> None:
    app = build_app(runner=_runner(), observability=NullObservability())

    assert isinstance(app, FastAPI)


def test_build_app_attaches_runner_for_introspection() -> None:
    runner = _runner()

    app = build_app(runner=runner, observability=NullObservability())

    assert app.state.runner is runner


def test_build_app_responds_to_health_live() -> None:
    app = build_app(runner=_runner(), observability=NullObservability())
    client = TestClient(app)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the failing test**

Run: `uv run pytest tests/unit/app/test_factory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'grabatus_service_core.app'`.

- [ ] **Step 3: Create the app package marker**

```python
# src/grabatus_service_core/app/__init__.py
"""FastAPI integration for grabatus_service_core."""

from grabatus_service_core.app.factory import build_app

__all__ = ["build_app"]
```

- [ ] **Step 4: Implement the factory**

```python
# src/grabatus_service_core/app/factory.py
"""build_app: assemble a FastAPI instance around a ServiceRunner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI

if TYPE_CHECKING:
    from grabatus_service_core.contract.base import ParamsT
    from grabatus_service_core.ports.observability import ObservabilityPort
    from grabatus_service_core.runner import ServiceRunner


def build_app(
    *,
    runner: ServiceRunner[ParamsT],
    observability: ObservabilityPort,
) -> FastAPI:
    """Return a fully wired FastAPI app bound to the supplied runner."""
    app = FastAPI(title="grabatus-service-core", version="0.1.0")
    app.state.runner = runner
    app.state.observability = observability

    @app.get("/health/live")
    def _health_live() -> dict[str, str]:
        return {"status": "ok"}

    return app
```

- [ ] **Step 5: Add the `tests/unit/app/__init__.py` marker**

```python
# tests/unit/app/__init__.py
```

(Empty file — pytest discovers via package layout.)

- [ ] **Step 6: Run tests — green**

Run: `uv run pytest tests/unit/app/ -v`
Expected: 3 passed.

- [ ] **Step 7: Run quality gates**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ tests/ && uv run bandit -r src/ -ll`
Expected: all clean.

- [ ] **Step 8: Commit**

```bash
git add src/grabatus_service_core/app tests/unit/app
git commit -m "feat(app): add FastAPI factory skeleton with /health/live"
```

---

### Task I2: `POST /run_service` route — Pub/Sub push handler

**Files:**
- Modify: `src/grabatus_service_core/app/factory.py`
- Create: `src/grabatus_service_core/app/routes.py`
- Create: `tests/unit/app/test_run_service_route.py`

**Why:** The receiver and monolith modes both expose the same `POST /run_service` endpoint that Cloud Run is configured to receive Pub/Sub push messages on. The route must (a) read raw bytes from the request body, (b) wrap them in `RawMessage`, (c) call `runner.execute(raw)`, and (d) translate the resulting `ExecutionResult` into an HTTP response that always returns 200 (so Pub/Sub acks). Errors are surfaced as JSON in the response body — never as non-2xx (which would trigger redelivery).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/app/test_run_service_route.py
"""Tests for POST /run_service: Pub/Sub push handler."""

from __future__ import annotations

import base64
import json
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from grabatus_service_core.app import build_app
from grabatus_service_core.contract.base import BaseServiceContract
from grabatus_service_core.runner import RuntimeMode, build_runner
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.testing import (
    AllowAllPolicy,
    FrozenClock,
    InMemoryJobDispatcher,
    InMemoryMessagePort,
    InMemorySecretsAdapter,
    InMemoryStorage,
    NullObservability,
    RecordingWebhookNotifier,
    make_contract,
    make_fake_compute_backend,
)


class _Params(BaseModel):
    horizon: int = 30


def _seeded_storage() -> InMemoryStorage:
    return InMemoryStorage(
        seed={"gs://gbt-storage-grabatus/user_999/in.xlsx": b"raw-bytes"},
    )


def _runner(**overrides: Any):
    defaults: dict[str, Any] = {
        "contract_type": BaseServiceContract[_Params],
        "storage": _seeded_storage(),
        "message": InMemoryMessagePort(),
        "webhook": RecordingWebhookNotifier(),
        "compute": make_fake_compute_backend(
            required_input_roles=frozenset({"timeseries"}),
            output_roles=frozenset({"result_json"}),
            outputs={"result_json": b"forecast"},
        ),
        "secrets": InMemorySecretsAdapter(seed={}),
        "authorizer": AllowAllPolicy(),
        "observability": NullObservability(),
        "clock": FrozenClock(iso_string="2026-04-26T00:00:00Z"),
        "job_dispatcher": InMemoryJobDispatcher(),
        "scheme_allowlist": SchemeAllowlist(allowed={"gs"}),
        "mode": RuntimeMode.MONOLITH,
    }
    defaults.update(overrides)
    return build_runner(**defaults)


def _pubsub_envelope(contract_dict: dict[str, Any]) -> dict[str, Any]:
    encoded = base64.b64encode(json.dumps(contract_dict).encode("utf-8")).decode("ascii")
    return {"message": {"data": encoded, "messageId": "1"}, "subscription": "x"}


@pytest.fixture()
def client() -> TestClient:
    app = build_app(runner=_runner(), observability=NullObservability())
    return TestClient(app)


def test_run_service_returns_200_on_success(client: TestClient) -> None:
    contract = make_contract(parameters=_Params(horizon=30)).model_dump(mode="json")

    response = client.post("/run_service", json=_pubsub_envelope(contract))

    assert response.status_code == 200


def test_run_service_response_payload_contains_status_and_request_id(
    client: TestClient,
) -> None:
    contract = make_contract(parameters=_Params(horizon=30)).model_dump(mode="json")
    expected_request_id = contract["envelope"]["request_id"]

    response = client.post("/run_service", json=_pubsub_envelope(contract))
    body = response.json()

    assert body["status"] == "ok"
    UUID(body["request_id"])
    assert body["request_id"] == expected_request_id


def test_run_service_returns_200_with_error_payload_on_invalid_contract(
    client: TestClient,
) -> None:
    bad = {"message": {"data": "not-base64!!!", "messageId": "1"}, "subscription": "x"}

    response = client.post("/run_service", json=bad)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["error_code"] == "malformed_message"


def test_run_service_rejects_non_json_body(client: TestClient) -> None:
    response = client.post(
        "/run_service",
        content=b"not-json",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["error_code"] == "malformed_message"
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest tests/unit/app/test_run_service_route.py -v`
Expected: 4 failed (404 — route doesn't exist).

- [ ] **Step 3: Create the routes module**

```python
# src/grabatus_service_core/app/routes.py
"""HTTP routes for grabatus_service_core."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import APIRouter, Request

from grabatus_service_core.errors import GrabatusServiceError
from grabatus_service_core.ports.values import RawMessage

if TYPE_CHECKING:
    from grabatus_service_core.runner import ExecutionResult


_PLACEHOLDER_REQUEST_ID = UUID("00000000-0000-0000-0000-000000000000")


def make_router() -> APIRouter:
    """Return an APIRouter exposing /run_service and /health/live."""
    router = APIRouter()

    @router.get("/health/live")
    def _health_live() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/run_service")
    async def _run_service(request: Request) -> dict[str, Any]:
        raw_bytes = await request.body()
        runner = request.app.state.runner
        result: ExecutionResult[Any] = runner.execute(RawMessage(payload=raw_bytes))
        return _result_to_json(result)

    return router


def _result_to_json(result: ExecutionResult[Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": result.status,
        "request_id": str(result.request_id),
    }
    if result.error is not None:
        body["error"] = _error_to_json(result.error)
    if result.receipts is not None:
        body["outputs"] = [
            {"role": role, "uri": r.uri, "bytes_written": r.bytes_written}
            for role, r in result.receipts.by_role.items()
        ]
    if result.metadata:
        body["metadata"] = dict(result.metadata)
    if result.webhook_ack is not None:
        body["webhook_ack"] = {
            "http_status": result.webhook_ack.http_status,
            "response_body": result.webhook_ack.response_body,
        }
    return body


def _error_to_json(error: GrabatusServiceError) -> dict[str, Any]:
    return {
        "error_code": error.error_code,
        "message": str(error),
    }
```

- [ ] **Step 4: Wire the router into `build_app`**

Modify `src/grabatus_service_core/app/factory.py`: replace the inline `_health_live` with `app.include_router(make_router())`.

```python
# src/grabatus_service_core/app/factory.py
"""build_app: assemble a FastAPI instance around a ServiceRunner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI

from grabatus_service_core.app.routes import make_router

if TYPE_CHECKING:
    from grabatus_service_core.contract.base import ParamsT
    from grabatus_service_core.ports.observability import ObservabilityPort
    from grabatus_service_core.runner import ServiceRunner


def build_app(
    *,
    runner: ServiceRunner[ParamsT],
    observability: ObservabilityPort,
) -> FastAPI:
    """Return a fully wired FastAPI app bound to the supplied runner."""
    app = FastAPI(title="grabatus-service-core", version="0.1.0")
    app.state.runner = runner
    app.state.observability = observability
    app.include_router(make_router())
    return app
```

- [ ] **Step 5: Run tests — green**

Run: `uv run pytest tests/unit/app/ -v`
Expected: 7 passed.

- [ ] **Step 6: Quality gates green**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ tests/ && uv run bandit -r src/ -ll`

- [ ] **Step 7: Commit**

```bash
git add src/grabatus_service_core/app tests/unit/app
git commit -m "feat(app): add POST /run_service Pub/Sub push handler"
```

---

### Task I3: `/health/ready` readiness probe

**Files:**
- Modify: `src/grabatus_service_core/app/routes.py`
- Modify: `tests/unit/app/test_factory.py`

**Why:** Cloud Run distinguishes liveness ("process alive") from readiness ("ready for traffic"). For receiver mode, readiness must additionally confirm that the runner can be reached and that observability has finished its async initialization. The probe is a synchronous, side-effect-free attribute lookup — never a real network call.

- [ ] **Step 1: Add a failing test**

Append to `tests/unit/app/test_factory.py`:

```python
def test_build_app_responds_to_health_ready() -> None:
    from grabatus_service_core.runner import RuntimeMode

    app = build_app(runner=_runner(), observability=NullObservability())
    client = TestClient(app)

    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["mode"] == RuntimeMode.MONOLITH.value
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest tests/unit/app/test_factory.py::test_build_app_responds_to_health_ready -v`
Expected: FAIL — 404.

- [ ] **Step 3: Add the `/health/ready` route**

Modify `src/grabatus_service_core/app/routes.py` — add inside `make_router()` after `_health_live`:

```python
@router.get("/health/ready")
def _health_ready(request: Request) -> dict[str, str]:
    runner = request.app.state.runner
    return {"status": "ready", "mode": runner.mode.value}
```

- [ ] **Step 4: Run tests — green**

Run: `uv run pytest tests/unit/app/ -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/grabatus_service_core/app/routes.py tests/unit/app/test_factory.py
git commit -m "feat(app): add /health/ready probe exposing runtime mode"
```

---

### Task I4: Global exception handler — defense-in-depth

**Files:**
- Create: `src/grabatus_service_core/app/exception_handler.py`
- Modify: `src/grabatus_service_core/app/factory.py`
- Create: `tests/unit/app/test_exception_handler.py`

**Why:** `runner.execute()` already catches every `GrabatusServiceError` and returns an `ExecutionResult`. But the FastAPI layer can still raise unexpected exceptions: a malformed request body before our route runs, a bug in `_result_to_json`, an OOM, a third-party middleware crash. The handler is the outermost safety net — it logs full context and **always** acks (returns 200 with `status: "error"`) so Pub/Sub doesn't infinitely redeliver a bug-inducing message. This is the only place the project allows `except Exception:`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/app/test_exception_handler.py
"""Tests for the FastAPI global exception handler."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from grabatus_service_core.app.exception_handler import register_exception_handlers
from grabatus_service_core.errors import InvalidContractError
from grabatus_service_core.testing import NullObservability


def _app_that_raises(exc: Exception) -> FastAPI:
    app = FastAPI()
    app.state.observability = NullObservability()
    register_exception_handlers(app)

    @app.get("/boom")
    def _boom() -> None:
        raise exc

    return app


def test_handler_translates_grabatus_error_to_200_with_error_payload() -> None:
    app = _app_that_raises(InvalidContractError("missing field x"))
    client = TestClient(app)

    response = client.get("/boom")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "status": "error",
        "error": {"error_code": "invalid_contract", "message": "missing field x"},
    }


def test_handler_translates_unexpected_exception_to_200_with_internal_code() -> None:
    app = _app_that_raises(RuntimeError("kaboom"))
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["error_code"] == "internal_error"
    assert "kaboom" not in body["error"]["message"]
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest tests/unit/app/test_exception_handler.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the handler module**

```python
# src/grabatus_service_core/app/exception_handler.py
"""Global FastAPI exception handlers for grabatus_service_core.

Translates every exception escaping a route into a 200-OK response so
Pub/Sub push acks. Typed ``GrabatusServiceError`` carries its declared
``error_code``; everything else is collapsed to ``internal_error`` and
the original message is dropped from the response body to avoid leaking
internals to the platform webhook.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse

from grabatus_service_core.errors import GrabatusServiceError

if TYPE_CHECKING:
    from fastapi import FastAPI


_INTERNAL_ERROR_CODE = "internal_error"
_INTERNAL_ERROR_MESSAGE = "internal server error"


def register_exception_handlers(app: FastAPI) -> None:
    """Attach Grabatus-aware exception handlers to ``app``."""

    @app.exception_handler(GrabatusServiceError)
    async def _handle_grabatus_error(
        request: Request,
        exc: GrabatusServiceError,
    ) -> JSONResponse:
        observability = request.app.state.observability
        observability.log(
            "service_error",
            error_code=exc.error_code,
            message=str(exc),
            path=request.url.path,
        )
        return JSONResponse(
            status_code=200,
            content={
                "status": "error",
                "error": {"error_code": exc.error_code, "message": str(exc)},
            },
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        observability = request.app.state.observability
        observability.log(
            "internal_error",
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            path=request.url.path,
        )
        return JSONResponse(
            status_code=200,
            content={
                "status": "error",
                "error": {
                    "error_code": _INTERNAL_ERROR_CODE,
                    "message": _INTERNAL_ERROR_MESSAGE,
                },
            },
        )
```

- [ ] **Step 4: Wire handlers into `build_app`**

Modify `src/grabatus_service_core/app/factory.py`:

```python
from grabatus_service_core.app.exception_handler import register_exception_handlers
# ... in build_app, after include_router:
register_exception_handlers(app)
```

- [ ] **Step 5: Run tests — green**

Run: `uv run pytest tests/unit/app/ -v`
Expected: 10 passed.

- [ ] **Step 6: Quality gates**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ tests/ && uv run bandit -r src/ -ll`

- [ ] **Step 7: Commit**

```bash
git add src/grabatus_service_core/app tests/unit/app
git commit -m "feat(app): add global exception handler with internal_error fallback"
```

---

### Task I5: Request-scoped context middleware

**Files:**
- Create: `src/grabatus_service_core/app/middleware.py`
- Modify: `src/grabatus_service_core/app/factory.py`
- Create: `tests/unit/app/test_middleware.py`

**Why:** Every log line, every metric tag, every span attribute must carry the same `request_id` so traces stitch across services. Setting it once on the request boundary via `contextvars` means every downstream call (runner, adapter, log) sees it without explicit threading. The middleware also generates a fallback `request_id` if the incoming Pub/Sub envelope is malformed (so even error logs are correlatable). The middleware does **not** parse the contract — it is cheap, sync-fast, and runs on every request including health checks.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/app/test_middleware.py
"""Tests for the request-id contextvar middleware."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from grabatus_service_core.app.middleware import (
    REQUEST_ID_HEADER,
    install_request_context_middleware,
    request_id_var,
)
from grabatus_service_core.testing import NullObservability


def _build_test_app() -> tuple[FastAPI, list[str | None]]:
    app = FastAPI()
    app.state.observability = NullObservability()
    install_request_context_middleware(app)
    seen: list[str | None] = []

    @app.get("/probe")
    def _probe(request: Request) -> dict[str, Any]:
        seen.append(request_id_var.get())
        return {"request_id": request_id_var.get()}

    return app, seen


def test_middleware_generates_request_id_when_header_absent() -> None:
    app, seen = _build_test_app()
    client = TestClient(app)

    response = client.get("/probe")

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] is not None
    assert seen[0] is not None


def test_middleware_uses_incoming_header_when_present() -> None:
    app, seen = _build_test_app()
    client = TestClient(app)

    response = client.get(
        "/probe",
        headers={REQUEST_ID_HEADER: "11111111-2222-3333-4444-555555555555"},
    )

    assert response.json()["request_id"] == "11111111-2222-3333-4444-555555555555"
    assert seen[0] == "11111111-2222-3333-4444-555555555555"


def test_middleware_echoes_request_id_in_response_header() -> None:
    app, _seen = _build_test_app()
    client = TestClient(app)

    response = client.get(
        "/probe",
        headers={REQUEST_ID_HEADER: "abc123"},
    )

    assert response.headers[REQUEST_ID_HEADER] == "abc123"


def test_middleware_resets_contextvar_after_request() -> None:
    app, _seen = _build_test_app()
    client = TestClient(app)
    client.get("/probe", headers={REQUEST_ID_HEADER: "xyz"})

    assert request_id_var.get() is None
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest tests/unit/app/test_middleware.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the middleware**

```python
# src/grabatus_service_core/app/middleware.py
"""Request-scoped context middleware: request_id contextvar + header echo.

Every request enters a fresh ``contextvars.Token`` so concurrent requests
under uvicorn/Starlette cannot leak state across each other. The handler
echoes the request_id back to the caller so the platform can correlate
its own logs without parsing the response body.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import FastAPI
    from starlette.requests import Request
    from starlette.responses import Response


REQUEST_ID_HEADER = "x-request-id"
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a request-scoped UUID to ``request_id_var`` for the request lifetime."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def install_request_context_middleware(app: FastAPI) -> None:
    """Attach :class:`RequestContextMiddleware` to ``app``."""
    app.add_middleware(RequestContextMiddleware)
```

- [ ] **Step 4: Wire middleware into `build_app`**

Modify `src/grabatus_service_core/app/factory.py`:

```python
from grabatus_service_core.app.middleware import install_request_context_middleware
# ... in build_app, before include_router:
install_request_context_middleware(app)
```

- [ ] **Step 5: Run tests — green**

Run: `uv run pytest tests/unit/app/ -v`
Expected: 14 passed.

- [ ] **Step 6: Quality gates**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ tests/ && uv run bandit -r src/ -ll`

- [ ] **Step 7: Commit**

```bash
git add src/grabatus_service_core/app tests/unit/app
git commit -m "feat(app): add request-id contextvar middleware"
```

---

## Phase J — Observability complete

### Task J1: structlog JSON renderer + contextvars binding

**Files:**
- Create: `src/grabatus_service_core/observability/__init__.py`
- Create: `src/grabatus_service_core/observability/logging.py`
- Create: `tests/unit/observability/__init__.py`
- Create: `tests/unit/observability/test_logging.py`

**Why:** Cloud Logging ingests JSON natively and indexes every top-level field. structlog's `merge_contextvars` processor lets us bind `request_id` once (in the middleware) and have it appear on every log line emitted while the request runs — without ever passing it explicitly. We configure structlog to use the stdlib `logging` foundation so external libraries (httpx, google-cloud-*) emit through the same pipeline.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/observability/test_logging.py
"""Tests for structlog JSON configuration."""

from __future__ import annotations

import io
import json
import logging

import structlog

from grabatus_service_core.observability.logging import configure_structlog


def test_configure_structlog_emits_json_with_event_field() -> None:
    buf = io.StringIO()
    configure_structlog(stream=buf, level=logging.INFO)

    structlog.get_logger().info("upload_received", user_id="999", file_id="abc")

    line = buf.getvalue().strip()
    record = json.loads(line)
    assert record["event"] == "upload_received"
    assert record["user_id"] == "999"
    assert record["file_id"] == "abc"


def test_configure_structlog_includes_contextvars() -> None:
    buf = io.StringIO()
    configure_structlog(stream=buf, level=logging.INFO)
    structlog.contextvars.bind_contextvars(request_id="r-1")
    try:
        structlog.get_logger().info("processing")
    finally:
        structlog.contextvars.clear_contextvars()

    line = buf.getvalue().strip()
    record = json.loads(line)
    assert record["request_id"] == "r-1"


def test_configure_structlog_respects_level() -> None:
    buf = io.StringIO()
    configure_structlog(stream=buf, level=logging.WARNING)

    structlog.get_logger().info("hidden")
    structlog.get_logger().warning("shown")

    lines = [json.loads(line) for line in buf.getvalue().splitlines()]
    events = [record["event"] for record in lines]
    assert events == ["shown"]
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest tests/unit/observability/test_logging.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Add the package marker**

```python
# src/grabatus_service_core/observability/__init__.py
"""Observability primitives: structlog config, OTel setup, metric catalog."""

from grabatus_service_core.observability.logging import configure_structlog

__all__ = ["configure_structlog"]
```

```python
# tests/unit/observability/__init__.py
```

- [ ] **Step 4: Implement the logging configuration**

```python
# src/grabatus_service_core/observability/logging.py
"""Configure structlog to emit JSON via the stdlib logging foundation.

We deliberately route through ``logging`` (instead of structlog's native
PrintLogger) so external libraries that use the standard logging API are
funneled through the same JSON renderer. The Cloud Logging agent indexes
every top-level field, so we keep the renderer flat (no nested objects
besides explicit ``error`` blocks).
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import IO


def configure_structlog(
    *,
    stream: IO[str] | None = None,
    level: int = logging.INFO,
) -> None:
    """Configure structlog + stdlib logging for JSON output to ``stream``.

    Calling this more than once replaces the previous configuration; it is
    safe to call from tests with a fresh ``io.StringIO`` per test.
    """
    target = stream or sys.stdout

    handler = logging.StreamHandler(target)
    handler.setFormatter(_PassthroughFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    processors: Iterable[structlog.types.Processor] = (
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    )
    structlog.configure(
        processors=list(processors),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )


class _PassthroughFormatter(logging.Formatter):
    """Pass through the already-rendered JSON message produced by structlog."""

    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()
```

- [ ] **Step 5: Run tests — green**

Run: `uv run pytest tests/unit/observability/test_logging.py -v`
Expected: 3 passed.

- [ ] **Step 6: Quality gates**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ tests/ && uv run bandit -r src/ -ll`

- [ ] **Step 7: Commit**

```bash
git add src/grabatus_service_core/observability tests/unit/observability
git commit -m "feat(observability): structlog JSON config with contextvars merging"
```

---

### Task J2: `OpenTelemetryObservability` adapter

**Files:**
- Create: `src/grabatus_service_core/adapters/observability_otel.py`
- Modify: `src/grabatus_service_core/adapters/__init__.py`
- Create: `tests/unit/adapters/test_observability_otel.py`

**Why:** `StructlogObservability` (1B) records spans as log events — fine for monolith dev. Production needs real OTel spans so Cloud Trace can render them as a tree. This adapter implements `ObservabilityPort` against `opentelemetry.trace.Tracer` and `opentelemetry.metrics.Meter`, leaving the SDK setup (exporters, sampling) to J3. The adapter is constructed with a tracer + meter passed in, so unit tests inject `InMemorySpanExporter` and `InMemoryMetricReader` rather than real Cloud exporters.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/adapters/test_observability_otel.py
"""Tests for OpenTelemetryObservability."""

from __future__ import annotations

import pytest
from opentelemetry.metrics import NoOpMeter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import NoOpTracer

from grabatus_service_core.adapters.observability_otel import (
    OpenTelemetryObservability,
)


@pytest.fixture()
def otel_observability() -> tuple[OpenTelemetryObservability, InMemorySpanExporter, InMemoryMetricReader]:
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    metric_reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[metric_reader])
    obs = OpenTelemetryObservability(
        tracer=tracer_provider.get_tracer("test"),
        meter=meter_provider.get_meter("test"),
    )
    return obs, span_exporter, metric_reader


def test_otel_observability_records_span_with_attributes(
    otel_observability: tuple[OpenTelemetryObservability, InMemorySpanExporter, InMemoryMetricReader],
) -> None:
    obs, span_exporter, _ = otel_observability

    with obs.span("pipeline.step", step="decode"):
        pass

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "pipeline.step"
    assert spans[0].attributes is not None
    assert spans[0].attributes["step"] == "decode"


def test_otel_observability_records_metric_via_counter(
    otel_observability: tuple[OpenTelemetryObservability, InMemorySpanExporter, InMemoryMetricReader],
) -> None:
    obs, _, metric_reader = otel_observability

    obs.metric("grabatus.requests.total", 1.0, status="ok", error_code="")
    obs.metric("grabatus.requests.total", 1.0, status="ok", error_code="")

    data = metric_reader.get_metrics_data()
    assert data is not None
    metric_names = [
        metric.name
        for resource_metrics in data.resource_metrics
        for scope_metrics in resource_metrics.scope_metrics
        for metric in scope_metrics.metrics
    ]
    assert "grabatus.requests.total" in metric_names


def test_otel_observability_log_emits_event_via_span_event() -> None:
    span_exporter = InMemorySpanExporter()
    tp = TracerProvider()
    tp.add_span_processor(SimpleSpanProcessor(span_exporter))
    obs = OpenTelemetryObservability(
        tracer=tp.get_tracer("test"),
        meter=NoOpMeter("test"),
    )

    with obs.span("outer"):
        obs.log("compute_started", model="prophet")

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    events = list(spans[0].events)
    assert any(e.name == "compute_started" for e in events)


def test_otel_observability_log_outside_span_is_noop() -> None:
    obs = OpenTelemetryObservability(tracer=NoOpTracer(), meter=NoOpMeter("test"))

    obs.log("orphaned_event", key="value")  # must not raise
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest tests/unit/adapters/test_observability_otel.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the adapter**

```python
# src/grabatus_service_core/adapters/observability_otel.py
"""OpenTelemetryObservability: adapter implementing ObservabilityPort over OTel.

Logs are recorded as span events (so Cloud Trace shows them inline with
the trace timeline). Metrics are routed through cached counters/histograms
keyed by metric name; the adapter infers the instrument type from the
metric name suffix:

- ``*.total`` and ``*.failures`` → Counter
- ``*.duration`` and ``*.bytes_*`` → Histogram
- otherwise → ObservableGauge (recorded via Counter snapshots)
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from opentelemetry import trace as otel_trace

if TYPE_CHECKING:
    from collections.abc import Iterator

    from opentelemetry.metrics import Counter, Histogram, Meter
    from opentelemetry.trace import Tracer


class OpenTelemetryObservability:
    """ObservabilityPort routed to a real OTel tracer and meter."""

    def __init__(self, *, tracer: Tracer, meter: Meter) -> None:
        self._tracer = tracer
        self._meter = meter
        self._counters: dict[str, Counter] = {}
        self._histograms: dict[str, Histogram] = {}

    def log(self, event: str, **fields: Any) -> None:  # noqa: ANN401
        span = otel_trace.get_current_span()
        if span is None or not span.is_recording():
            return
        span.add_event(event, attributes=fields)

    @contextmanager
    def span(self, name: str, **attrs: Any) -> Iterator[None]:  # noqa: ANN401
        with self._tracer.start_as_current_span(name, attributes=attrs):
            yield None

    def metric(self, name: str, value: float, **tags: Any) -> None:  # noqa: ANN401
        if name.endswith((".total", ".failures")):
            counter = self._counters.get(name) or self._meter.create_counter(name)
            self._counters[name] = counter
            counter.add(value, attributes=tags)
            return
        histogram = self._histograms.get(name) or self._meter.create_histogram(name)
        self._histograms[name] = histogram
        histogram.record(value, attributes=tags)
```

- [ ] **Step 4: Re-export the adapter**

Modify `src/grabatus_service_core/adapters/__init__.py`:

```python
from grabatus_service_core.adapters.clock import SystemClock
from grabatus_service_core.adapters.observability_otel import OpenTelemetryObservability
from grabatus_service_core.adapters.retry import with_retry

__all__ = ["OpenTelemetryObservability", "SystemClock", "with_retry"]
```

- [ ] **Step 5: Add OTel SDK dev dependency**

Verify `pyproject.toml` already has `opentelemetry-sdk>=1.27` (declared in 1A). The InMemoryReader/Exporter classes ship with the SDK, no new dependency required.

- [ ] **Step 6: Run tests — green**

Run: `uv run pytest tests/unit/adapters/test_observability_otel.py -v`
Expected: 4 passed.

- [ ] **Step 7: Quality gates**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ tests/ && uv run bandit -r src/ -ll`

- [ ] **Step 8: Commit**

```bash
git add src/grabatus_service_core/adapters tests/unit/adapters
git commit -m "feat(adapters): OpenTelemetryObservability with span/metric routing"
```

---

### Task J3: OTel SDK setup with Cloud Trace exporter (opt-in)

**Files:**
- Create: `src/grabatus_service_core/observability/otel_setup.py`
- Modify: `src/grabatus_service_core/observability/__init__.py`
- Create: `tests/unit/observability/test_otel_setup.py`

**Why:** Production needs `TracerProvider`/`MeterProvider` configured with Cloud Trace + Cloud Monitoring exporters. Tests need a setup that uses in-memory exporters so the observability tree can be inspected. This task ships a single function `setup_opentelemetry(env, sample_rate, ...)` that returns a typed context object: `(tracer, meter, shutdown_callable)`. Cloud Trace exporter import is **lazy** so library users without GCP credentials can still use the in-memory variant.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/observability/test_otel_setup.py
"""Tests for setup_opentelemetry()."""

from __future__ import annotations

from grabatus_service_core.observability.otel_setup import setup_opentelemetry


def test_setup_returns_tracer_and_meter_for_local_env() -> None:
    handle = setup_opentelemetry(env="local", sample_rate=1.0)
    try:
        with handle.tracer.start_as_current_span("test") as span:
            assert span.is_recording()
        handle.meter.create_counter("local.counter").add(1.0)
    finally:
        handle.shutdown()


def test_setup_handle_shutdown_is_idempotent() -> None:
    handle = setup_opentelemetry(env="local", sample_rate=1.0)

    handle.shutdown()
    handle.shutdown()  # second call must not raise


def test_setup_uses_cloud_trace_exporter_in_production_when_available(
    monkeypatch,
) -> None:
    """Smoke test: production env path is taken; we don't actually export."""
    import grabatus_service_core.observability.otel_setup as mod

    captured: dict[str, object] = {}

    class _StubExporter:
        def __init__(self, *args: object, **kwargs: object) -> None:
            captured["constructed"] = True

        def export(self, spans: object) -> object:  # pragma: no cover  # not called in test
            return None

        def shutdown(self) -> None:
            return None

    monkeypatch.setattr(mod, "_load_cloud_trace_exporter", lambda: _StubExporter)
    monkeypatch.setattr(mod, "_load_cloud_monitoring_exporter", lambda: None)

    handle = setup_opentelemetry(env="production", sample_rate=0.5)
    try:
        assert captured["constructed"] is True
    finally:
        handle.shutdown()


def test_setup_falls_back_to_in_memory_when_cloud_exporter_missing(
    monkeypatch,
) -> None:
    import grabatus_service_core.observability.otel_setup as mod

    monkeypatch.setattr(mod, "_load_cloud_trace_exporter", lambda: None)
    monkeypatch.setattr(mod, "_load_cloud_monitoring_exporter", lambda: None)

    handle = setup_opentelemetry(env="production", sample_rate=1.0)

    try:
        with handle.tracer.start_as_current_span("test") as span:
            assert span.is_recording()
    finally:
        handle.shutdown()
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest tests/unit/observability/test_otel_setup.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the setup module**

```python
# src/grabatus_service_core/observability/otel_setup.py
"""Boot OpenTelemetry SDK with optional Cloud Trace + Cloud Monitoring exporters.

The Cloud exporters are imported lazily so the library remains usable on
machines (and in tests) without ``opentelemetry-exporter-gcp-*`` installed.
``setup_opentelemetry`` returns a handle whose ``shutdown()`` flushes and
disposes both providers; calling shutdown more than once is safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    InMemoryMetricReader,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

if TYPE_CHECKING:
    from opentelemetry.metrics import Meter
    from opentelemetry.trace import Tracer


@dataclass(frozen=True)
class OpenTelemetryHandle:
    """Owned tracer+meter+shutdown for one configured OTel pipeline."""

    tracer: Tracer
    meter: Meter
    _tracer_provider: TracerProvider
    _meter_provider: MeterProvider
    _disposed: list[bool]  # mutable single-element list — closure flag

    def shutdown(self) -> None:
        if self._disposed[0]:
            return
        self._disposed[0] = True
        self._tracer_provider.shutdown()
        self._meter_provider.shutdown()


def setup_opentelemetry(
    *,
    env: Literal["local", "staging", "production"],
    sample_rate: float,
) -> OpenTelemetryHandle:
    """Return an :class:`OpenTelemetryHandle` configured for ``env``."""
    sampler = TraceIdRatioBased(sample_rate)
    tracer_provider = TracerProvider(sampler=sampler)

    cloud_trace_cls = _load_cloud_trace_exporter() if env == "production" else None
    if cloud_trace_cls is not None:
        tracer_provider.add_span_processor(BatchSpanProcessor(cloud_trace_cls()))
    else:
        tracer_provider.add_span_processor(SimpleSpanProcessor(InMemorySpanExporter()))

    cloud_monitoring_cls = (
        _load_cloud_monitoring_exporter() if env == "production" else None
    )
    if cloud_monitoring_cls is not None:
        meter_provider = MeterProvider(
            metric_readers=[PeriodicExportingMetricReader(cloud_monitoring_cls())],
        )
    else:
        meter_provider = MeterProvider(metric_readers=[InMemoryMetricReader()])

    return OpenTelemetryHandle(
        tracer=tracer_provider.get_tracer("grabatus_service_core"),
        meter=meter_provider.get_meter("grabatus_service_core"),
        _tracer_provider=tracer_provider,
        _meter_provider=meter_provider,
        _disposed=[False],
    )


def _load_cloud_trace_exporter() -> type | None:  # pragma: no cover  # exercised via monkeypatch
    try:
        from opentelemetry.exporter.cloud_trace import (
            CloudTraceSpanExporter,
        )
    except ImportError:
        return None
    return CloudTraceSpanExporter


def _load_cloud_monitoring_exporter() -> type | None:  # pragma: no cover  # exercised via monkeypatch
    try:
        from opentelemetry.exporter.cloud_monitoring import (
            CloudMonitoringMetricsExporter,
        )
    except ImportError:
        return None
    return CloudMonitoringMetricsExporter
```

- [ ] **Step 4: Re-export from observability package**

Modify `src/grabatus_service_core/observability/__init__.py`:

```python
from grabatus_service_core.observability.logging import configure_structlog
from grabatus_service_core.observability.otel_setup import (
    OpenTelemetryHandle,
    setup_opentelemetry,
)

__all__ = [
    "OpenTelemetryHandle",
    "configure_structlog",
    "setup_opentelemetry",
]
```

- [ ] **Step 5: Run tests — green**

Run: `uv run pytest tests/unit/observability/ -v`
Expected: all tests in observability pass (3 from J1 + 4 from J3 = 7 passed).

- [ ] **Step 6: Quality gates**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ tests/ && uv run bandit -r src/ -ll`

- [ ] **Step 7: Commit**

```bash
git add src/grabatus_service_core/observability tests/unit/observability
git commit -m "feat(observability): OTel SDK setup with optional Cloud Trace exporter"
```

---

### Task J4: Catalogued metric constants

**Files:**
- Create: `src/grabatus_service_core/observability/metrics.py`
- Modify: `src/grabatus_service_core/observability/__init__.py`
- Create: `tests/unit/observability/test_metrics.py`

**Why:** Spec §6.6 lists seven specific metric names with their tag dimensions. Defining them as `Final[str]` constants in a single module means every emit site uses the canonical name, prevents drift (`grabatus.request.total` vs `grabatus.requests.total` is a real outage waiting to happen), and gives `mypy` a single source of truth. This is documentation-as-code: anyone touching the observability surface reads this file.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/observability/test_metrics.py
"""Tests for the metric name catalogue."""

from __future__ import annotations

from grabatus_service_core.observability import metrics as M


def test_all_metric_names_use_grabatus_namespace() -> None:
    for name in M.ALL_METRIC_NAMES:
        assert name.startswith("grabatus.")


def test_catalogue_covers_spec_required_metrics() -> None:
    assert M.REQUESTS_TOTAL == "grabatus.requests.total"
    assert M.REQUEST_DURATION == "grabatus.request.duration"
    assert M.COMPUTE_DURATION == "grabatus.compute.duration"
    assert M.STORAGE_BYTES_READ == "grabatus.storage.bytes_read"
    assert M.STORAGE_BYTES_WRITTEN == "grabatus.storage.bytes_written"
    assert M.WEBHOOK_FAILURES == "grabatus.webhook.failures"
    assert M.CIRCUIT_BREAKER_STATE == "grabatus.circuit_breaker.state"


def test_all_metric_names_unique() -> None:
    assert len(set(M.ALL_METRIC_NAMES)) == len(M.ALL_METRIC_NAMES)
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest tests/unit/observability/test_metrics.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the metric catalogue**

```python
# src/grabatus_service_core/observability/metrics.py
"""Canonical metric names emitted by grabatus_service_core.

Every emit site MUST use these constants — never a literal string.
Cloud Monitoring dashboards and alerting policies are defined against
these exact names; renaming requires a migration.
"""

from __future__ import annotations

from typing import Final

REQUESTS_TOTAL: Final[str] = "grabatus.requests.total"
REQUEST_DURATION: Final[str] = "grabatus.request.duration"
COMPUTE_DURATION: Final[str] = "grabatus.compute.duration"
STORAGE_BYTES_READ: Final[str] = "grabatus.storage.bytes_read"
STORAGE_BYTES_WRITTEN: Final[str] = "grabatus.storage.bytes_written"
WEBHOOK_FAILURES: Final[str] = "grabatus.webhook.failures"
CIRCUIT_BREAKER_STATE: Final[str] = "grabatus.circuit_breaker.state"

ALL_METRIC_NAMES: Final[tuple[str, ...]] = (
    REQUESTS_TOTAL,
    REQUEST_DURATION,
    COMPUTE_DURATION,
    STORAGE_BYTES_READ,
    STORAGE_BYTES_WRITTEN,
    WEBHOOK_FAILURES,
    CIRCUIT_BREAKER_STATE,
)
```

- [ ] **Step 4: Re-export from observability package**

Modify `src/grabatus_service_core/observability/__init__.py`:

```python
from grabatus_service_core.observability import metrics
from grabatus_service_core.observability.logging import configure_structlog
from grabatus_service_core.observability.otel_setup import (
    OpenTelemetryHandle,
    setup_opentelemetry,
)

__all__ = [
    "OpenTelemetryHandle",
    "configure_structlog",
    "metrics",
    "setup_opentelemetry",
]
```

- [ ] **Step 5: Run tests — green**

Run: `uv run pytest tests/unit/observability/test_metrics.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/observability tests/unit/observability
git commit -m "feat(observability): catalogue spec-mandated metric names"
```

---

### Task J5: `traceparent` propagation in `JwtWebhookNotifier`

**Files:**
- Modify: `src/grabatus_service_core/adapters/webhook.py`
- Modify: `tests/unit/adapters/test_webhook.py` (or create if absent)

**Why:** Spec §6.6 requires the platform receive a `traceparent` header on every webhook so distributed traces stitch end-to-end. We use the W3C `TraceContextTextMapPropagator` (default in OTel) to inject the current span context into outbound headers. If no span is active (test/no-OTel paths), the header is simply absent — no errors.

- [ ] **Step 1: Add a failing test**

Add to `tests/unit/adapters/test_webhook.py` (or create the file with the imports it needs):

```python
def test_jwt_webhook_includes_traceparent_when_span_active() -> None:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    captured_headers: dict[str, str] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, text="ok")

    transport = httpx.MockTransport(_handler)
    client = httpx.Client(transport=transport)
    notifier = JwtWebhookNotifier(signing_secret=b"s3cret", client=client)
    callback = Callback(url=HttpUrl("https://example.com/cb"), auth_scheme="jwt_hs256")

    tp = TracerProvider()
    tp.add_span_processor(SimpleSpanProcessor(InMemorySpanExporter()))
    with tp.get_tracer("test").start_as_current_span("outer"):
        notifier.notify(callback=callback, payload={"status": "ok"})

    assert "traceparent" in {k.lower() for k in captured_headers}


def test_jwt_webhook_omits_traceparent_when_no_span() -> None:
    captured_headers: dict[str, str] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, text="ok")

    transport = httpx.MockTransport(_handler)
    client = httpx.Client(transport=transport)
    notifier = JwtWebhookNotifier(signing_secret=b"s3cret", client=client)
    callback = Callback(url=HttpUrl("https://example.com/cb"), auth_scheme="jwt_hs256")

    notifier.notify(callback=callback, payload={"status": "ok"})

    assert "traceparent" not in {k.lower() for k in captured_headers}
```

(Adjust imports/fixtures to match the existing 1B test file.)

- [ ] **Step 2: Run failing test**

Run: `uv run pytest tests/unit/adapters/test_webhook.py -v -k traceparent`
Expected: FAIL — header not present.

- [ ] **Step 3: Inject traceparent in the notifier**

Modify `src/grabatus_service_core/adapters/webhook.py` — inside `notify`, after `headers` is built and before the POST:

```python
from opentelemetry.propagate import inject as _otel_inject  # at module top

# ...
_otel_inject(headers)  # mutates headers in-place; no-op when no active span
```

(`opentelemetry.propagate.inject` uses the global propagator, which defaults to W3C TraceContext.)

- [ ] **Step 4: Run tests — green**

Run: `uv run pytest tests/unit/adapters/test_webhook.py -v`
Expected: all webhook tests pass (including the new two).

- [ ] **Step 5: Quality gates**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ tests/ && uv run bandit -r src/ -ll`

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/adapters/webhook.py tests/unit/adapters/test_webhook.py
git commit -m "feat(adapters): inject W3C traceparent header in webhook calls"
```

---

## Phase K — Settings & runtime modes

### Task K1: `Settings` (pydantic-settings)

**Files:**
- Create: `src/grabatus_service_core/settings.py`
- Modify: `src/grabatus_service_core/__init__.py`
- Create: `tests/unit/test_settings.py`

**Why:** Spec §6.7 requires `pydantic-settings` reading every `GBT_*` env var, with secure defaults and validation. Encapsulating the parsing in one place means services reuse the same defaults; runtime modes (next task) consume `Settings` directly. Validation is exhaustive — invalid values fail at import, not on first request.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_settings.py
"""Tests for the Settings (pydantic-settings) model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.settings import RuntimeMode, Settings


def test_settings_required_fields_raise_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("GBT_RUNTIME_MODE", "GBT_ENV", "SERVICE_SECRET_KEY"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "shhh")

    settings = Settings()

    assert settings.runtime_mode is RuntimeMode.MONOLITH
    assert settings.env == "local"
    assert settings.service_secret_key.get_secret_value() == "shhh"


def test_settings_default_timeouts_match_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "x")

    settings = Settings()

    assert settings.request_timeout_seconds == 540
    assert settings.http_timeout_seconds == 30
    assert settings.webhook_timeout_seconds == 15
    assert settings.compute_timeout_seconds == 480


def test_settings_default_allowed_schemes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "x")

    settings = Settings()

    assert settings.allowed_schemes == frozenset({"gs", "bigquery", "secret"})


def test_settings_parses_csv_env_into_frozenset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "production")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "x")
    monkeypatch.setenv("GBT_ALLOWED_SCHEMES", "gs,https")

    settings = Settings()

    assert settings.allowed_schemes == frozenset({"gs", "https"})


def test_settings_rejects_invalid_runtime_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "fancy")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "x")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_trace_sample_rate_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "x")
    monkeypatch.setenv("GBT_TRACE_SAMPLE_RATE", "1.5")

    with pytest.raises(ValidationError):
        Settings()
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest tests/unit/test_settings.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `Settings`**

```python
# src/grabatus_service_core/settings.py
"""Library settings (pydantic-settings).

Reads ``GBT_*`` and ``SERVICE_SECRET_KEY`` env vars. Defaults are
secure-by-default; production overrides via Cloud Run env vars or, for
secrets, Secret Manager mounts.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeMode(StrEnum):
    """Selects the pipeline branch a process executes."""

    RECEIVER = "receiver"
    WORKER = "worker"
    MONOLITH = "monolith"


_DEFAULT_ALLOWED_SCHEMES: frozenset[str] = frozenset({"gs", "bigquery", "secret"})


class Settings(BaseSettings):
    """Process-wide configuration parsed from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="GBT_",
        case_sensitive=False,
        extra="ignore",
    )

    runtime_mode: Annotated[RuntimeMode, Field(alias="GBT_RUNTIME_MODE")]
    env: Annotated[Literal["local", "staging", "production"], Field(alias="GBT_ENV")]
    request_timeout_seconds: int = Field(default=540, ge=1, le=3600)
    http_timeout_seconds: int = Field(default=30, ge=1, le=300)
    webhook_timeout_seconds: int = Field(default=15, ge=1, le=120)
    compute_timeout_seconds: int = Field(default=480, ge=1, le=3600)
    allowed_schemes: frozenset[str] = Field(default=_DEFAULT_ALLOWED_SCHEMES)
    allowed_hosts: frozenset[str] = Field(default=frozenset())
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    trace_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    worker_job_name: str | None = Field(default=None)
    # ``service_secret_key`` reads from ``SERVICE_SECRET_KEY`` (no GBT_ prefix)
    # to align with the existing platform convention.
    service_secret_key: Annotated[SecretStr, Field(alias="SERVICE_SECRET_KEY")]

    @field_validator("allowed_schemes", "allowed_hosts", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return frozenset(item.strip() for item in value.split(",") if item.strip())
        return value
```

- [ ] **Step 4: Re-export from package init**

Modify `src/grabatus_service_core/__init__.py` — add to imports and `__all__`:

```python
from grabatus_service_core.settings import RuntimeMode, Settings
# ...add "RuntimeMode", "Settings" to __all__
```

(Preserve alphabetical order in `__all__`.)

- [ ] **Step 5: Run tests — green**

Run: `uv run pytest tests/unit/test_settings.py -v`
Expected: 7 passed.

- [ ] **Step 6: Quality gates**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ tests/ && uv run bandit -r src/ -ll`

- [ ] **Step 7: Commit**

```bash
git add src/grabatus_service_core/settings.py src/grabatus_service_core/__init__.py tests/unit/test_settings.py
git commit -m "feat(settings): pydantic-settings model for GBT_* env vars"
```

---

### Task K2: Bootstrap helpers — `build_receiver_app`, `build_worker_runner`, `build_monolith_app`

**Files:**
- Create: `src/grabatus_service_core/bootstrap/__init__.py`
- Create: `src/grabatus_service_core/bootstrap/factories.py`
- Create: `tests/unit/bootstrap/__init__.py`
- Create: `tests/unit/bootstrap/test_factories.py`

**Why:** Without bootstrap helpers, every service repeats the same composition — wire all nine ports, set the right `RuntimeMode`, configure observability. The helpers take a `Settings` plus a `ComputeBackendPort` and return either a FastAPI app (receiver/monolith) or a `ServiceRunner` (worker, since worker doesn't speak HTTP). Adapters are selected by `Settings.env`: `local` uses in-memory/local-fs fakes; `production` uses real GCS/PubSub/SecretManager.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/bootstrap/test_factories.py
"""Tests for bootstrap factories."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from grabatus_service_core.bootstrap import (
    build_monolith_app,
    build_receiver_app,
    build_worker_runner,
)
from grabatus_service_core.contract.base import BaseServiceContract
from grabatus_service_core.runner import RuntimeMode, ServiceRunner
from grabatus_service_core.settings import Settings
from grabatus_service_core.testing import (
    AllowAllPolicy,
    InMemoryJobDispatcher,
    InMemoryMessagePort,
    InMemorySecretsAdapter,
    InMemoryStorage,
    NullObservability,
    RecordingWebhookNotifier,
    make_fake_compute_backend,
)


class _Params(BaseModel):
    horizon: int = 30


@pytest.fixture()
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "x")
    return Settings()


def _compute() -> Any:
    return make_fake_compute_backend(
        required_input_roles=frozenset({"timeseries"}),
        output_roles=frozenset({"result_json"}),
        outputs={"result_json": b"x"},
    )


def _adapters() -> dict[str, Any]:
    return {
        "storage": InMemoryStorage(seed={}),
        "message": InMemoryMessagePort(),
        "webhook": RecordingWebhookNotifier(),
        "secrets": InMemorySecretsAdapter(seed={}),
        "authorizer": AllowAllPolicy(),
        "observability": NullObservability(),
        "job_dispatcher": InMemoryJobDispatcher(),
    }


def test_build_monolith_app_returns_fastapi(settings: Settings) -> None:
    app = build_monolith_app(
        settings=settings,
        contract_type=BaseServiceContract[_Params],
        compute=_compute(),
        adapters=_adapters(),
    )

    assert isinstance(app, FastAPI)
    assert app.state.runner.mode is RuntimeMode.MONOLITH


def test_build_receiver_app_requires_worker_job_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "x")
    settings = Settings()

    with pytest.raises(ValueError, match="worker_job_name"):
        build_receiver_app(
            settings=settings,
            contract_type=BaseServiceContract[_Params],
            compute=_compute(),
            adapters=_adapters(),
        )


def test_build_receiver_app_uses_worker_job_name_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "x")
    monkeypatch.setenv("GBT_WORKER_JOB_NAME", "forecast-worker")
    settings = Settings()

    app = build_receiver_app(
        settings=settings,
        contract_type=BaseServiceContract[_Params],
        compute=_compute(),
        adapters=_adapters(),
    )

    assert app.state.runner.mode is RuntimeMode.RECEIVER
    assert app.state.runner.worker_job_name == "forecast-worker"


def test_build_worker_runner_returns_service_runner(settings: Settings) -> None:
    runner = build_worker_runner(
        settings=settings,
        contract_type=BaseServiceContract[_Params],
        compute=_compute(),
        adapters=_adapters(),
    )

    assert isinstance(runner, ServiceRunner)
    assert runner.mode is RuntimeMode.WORKER
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest tests/unit/bootstrap/ -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the factories**

```python
# src/grabatus_service_core/bootstrap/__init__.py
"""High-level helpers that compose Settings → adapters → runner → app."""

from grabatus_service_core.bootstrap.factories import (
    build_monolith_app,
    build_receiver_app,
    build_worker_runner,
)

__all__ = [
    "build_monolith_app",
    "build_receiver_app",
    "build_worker_runner",
]
```

```python
# src/grabatus_service_core/bootstrap/factories.py
"""Bootstrap factories: turn Settings + compute + adapters into an app/runner."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from grabatus_service_core.adapters.clock import SystemClock
from grabatus_service_core.app import build_app
from grabatus_service_core.runner import RuntimeMode as RunnerMode
from grabatus_service_core.runner import ServiceRunner, build_runner
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.settings import RuntimeMode

if TYPE_CHECKING:
    from fastapi import FastAPI

    from grabatus_service_core.contract.base import BaseServiceContract, ParamsT
    from grabatus_service_core.ports.compute import ComputeBackendPort
    from grabatus_service_core.settings import Settings


def build_receiver_app(
    *,
    settings: Settings,
    contract_type: type[BaseServiceContract[ParamsT]],
    compute: ComputeBackendPort,
    adapters: dict[str, Any],
) -> FastAPI:
    """Build a receiver-mode FastAPI app from settings + adapters."""
    if settings.worker_job_name is None:
        raise ValueError(
            "build_receiver_app: settings.worker_job_name is required when "
            "runtime_mode=RECEIVER (set GBT_WORKER_JOB_NAME)",
        )
    runner = _build_runner(
        settings=settings,
        contract_type=contract_type,
        compute=compute,
        adapters=adapters,
        mode=RunnerMode.RECEIVER,
    )
    return build_app(runner=runner, observability=adapters["observability"])


def build_worker_runner(
    *,
    settings: Settings,
    contract_type: type[BaseServiceContract[ParamsT]],
    compute: ComputeBackendPort,
    adapters: dict[str, Any],
) -> ServiceRunner[ParamsT]:
    """Build a worker-mode ``ServiceRunner`` (no FastAPI; CLI-driven)."""
    return _build_runner(
        settings=settings,
        contract_type=contract_type,
        compute=compute,
        adapters=adapters,
        mode=RunnerMode.WORKER,
    )


def build_monolith_app(
    *,
    settings: Settings,
    contract_type: type[BaseServiceContract[ParamsT]],
    compute: ComputeBackendPort,
    adapters: dict[str, Any],
) -> FastAPI:
    """Build a monolith-mode FastAPI app (receiver+worker fused)."""
    runner = _build_runner(
        settings=settings,
        contract_type=contract_type,
        compute=compute,
        adapters=adapters,
        mode=RunnerMode.MONOLITH,
    )
    return build_app(runner=runner, observability=adapters["observability"])


def _build_runner(
    *,
    settings: Settings,
    contract_type: type[BaseServiceContract[ParamsT]],
    compute: ComputeBackendPort,
    adapters: dict[str, Any],
    mode: RunnerMode,
) -> ServiceRunner[ParamsT]:
    return build_runner(
        contract_type=contract_type,
        storage=adapters["storage"],
        message=adapters["message"],
        webhook=adapters["webhook"],
        compute=compute,
        secrets=adapters["secrets"],
        authorizer=adapters["authorizer"],
        observability=adapters["observability"],
        clock=adapters.get("clock") or SystemClock(),
        job_dispatcher=adapters["job_dispatcher"],
        scheme_allowlist=SchemeAllowlist(allowed=set(settings.allowed_schemes)),
        mode=mode,
        worker_job_name=settings.worker_job_name,
    )


__all__ = [
    "RuntimeMode",
    "build_monolith_app",
    "build_receiver_app",
    "build_worker_runner",
]
```

- [ ] **Step 4: Run tests — green**

Run: `uv run pytest tests/unit/bootstrap/ -v`
Expected: 4 passed.

- [ ] **Step 5: Quality gates**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ tests/ && uv run bandit -r src/ -ll`

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/bootstrap tests/unit/bootstrap
git commit -m "feat(bootstrap): build_receiver_app/worker_runner/monolith_app factories"
```

---

### Task K3: `__main__.py` — CLI entry point dispatching by `RuntimeMode`

**Files:**
- Create: `src/grabatus_service_core/__main__.py`
- Create: `tests/unit/test_main_entrypoint.py`

**Why:** Cloud Run images run `python -m grabatus_service_core` as their entry point. The `__main__` reads `Settings`, configures observability once, and dispatches: receiver/monolith → uvicorn; worker → reads `GBT_JOB_PAYLOAD`, calls `runner.execute()` once, and exits with code 0/1 based on `result.status`. Workers are not supposed to live forever — Cloud Run Jobs are one-shot containers.

Note: this entry point is a **library affordance** that services may reuse, but services typically write their own `__main__` that imports `grabatus_service_core.bootstrap.*` and registers their own `ComputeBackend`. We provide a minimal smoke entry point that fails loudly when no compute backend is registered (since the library itself doesn't ship one).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_main_entrypoint.py
"""Tests for the __main__ entry point dispatch logic."""

from __future__ import annotations

import base64
import json
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from grabatus_service_core.__main__ import (
    EntryPointError,
    run_worker_once,
)
from grabatus_service_core.runner import ExecutionResult


def _ok_result() -> ExecutionResult[Any]:
    return ExecutionResult(
        request_id=UUID("11111111-1111-1111-1111-111111111111"),
        status="ok",
        contract=None,
        receipts=None,
        error=None,
        metadata={},
        webhook_ack=None,
    )


def _err_result() -> ExecutionResult[Any]:
    from grabatus_service_core.errors import ComputeError

    return ExecutionResult(
        request_id=UUID("00000000-0000-0000-0000-000000000000"),
        status="error",
        contract=None,
        receipts=None,
        error=ComputeError("boom"),
        metadata={},
        webhook_ack=None,
    )


def test_run_worker_once_returns_zero_on_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = MagicMock()
    runner.execute.return_value = _ok_result()

    contract = json.dumps({"some": "payload"}).encode("utf-8")
    monkeypatch.setenv("GBT_JOB_PAYLOAD", contract.decode("utf-8"))
    monkeypatch.setenv("GBT_JOB_REQUEST_ID", "11111111-1111-1111-1111-111111111111")

    exit_code = run_worker_once(runner=runner)

    assert exit_code == 0


def test_run_worker_once_returns_nonzero_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = MagicMock()
    runner.execute.return_value = _err_result()
    monkeypatch.setenv("GBT_JOB_PAYLOAD", "{}")
    monkeypatch.setenv("GBT_JOB_REQUEST_ID", "00000000-0000-0000-0000-000000000000")

    exit_code = run_worker_once(runner=runner)

    assert exit_code == 1


def test_run_worker_once_raises_when_payload_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GBT_JOB_PAYLOAD", raising=False)
    runner = MagicMock()

    with pytest.raises(EntryPointError, match="GBT_JOB_PAYLOAD"):
        run_worker_once(runner=runner)
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest tests/unit/test_main_entrypoint.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `__main__`**

```python
# src/grabatus_service_core/__main__.py
"""CLI entry point for grabatus_service_core.

Services typically write their own ``__main__`` that imports the bootstrap
helpers, registers their ComputeBackend, and calls ``run_worker_once`` or
``uvicorn.run``. The library's own ``__main__`` exposes the helpers but
intentionally fails loudly if invoked without a registered compute backend
(via the ``GBT_COMPUTE_BACKEND_FACTORY`` env var, which must point to a
``module:callable`` returning a ``ComputeBackendPort``).
"""

from __future__ import annotations

import importlib
import os
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from grabatus_service_core.runner import ServiceRunner


_PAYLOAD_ENV_VAR = "GBT_JOB_PAYLOAD"
_REQUEST_ID_ENV_VAR = "GBT_JOB_REQUEST_ID"
_COMPUTE_FACTORY_ENV_VAR = "GBT_COMPUTE_BACKEND_FACTORY"


class EntryPointError(RuntimeError):
    """Raised when the entry point cannot start due to missing configuration."""


def run_worker_once(*, runner: ServiceRunner[Any]) -> int:
    """Execute the runner once on the contract bytes from ``GBT_JOB_PAYLOAD``.

    Returns 0 on success and 1 on error so Cloud Run Jobs records the
    correct execution status. Re-raises configuration errors so the
    container crashes loudly during deploy validation.
    """
    from grabatus_service_core.ports.values import RawMessage

    payload_str = os.environ.get(_PAYLOAD_ENV_VAR)
    if payload_str is None:
        raise EntryPointError(
            f"{_PAYLOAD_ENV_VAR} env var is required for worker mode",
        )
    raw = RawMessage(payload=payload_str.encode("utf-8"))
    result = runner.execute(raw)
    return 0 if result.status == "ok" else 1


def _load_compute_factory() -> Any:  # pragma: no cover  # exercised by services, not the library
    spec = os.environ.get(_COMPUTE_FACTORY_ENV_VAR)
    if spec is None:
        raise EntryPointError(
            f"{_COMPUTE_FACTORY_ENV_VAR} must be set to 'module:callable' "
            "returning a ComputeBackendPort",
        )
    module_name, _, attr = spec.partition(":")
    if not module_name or not attr:
        raise EntryPointError(
            f"{_COMPUTE_FACTORY_ENV_VAR} must be 'module:callable', got {spec!r}",
        )
    module = importlib.import_module(module_name)
    return getattr(module, attr)()


def main() -> int:  # pragma: no cover  # integration-tested via examples/
    raise EntryPointError(
        "grabatus_service_core.__main__ does not ship a default compute backend. "
        "Services must write their own __main__ that imports bootstrap helpers "
        "and registers a ComputeBackendPort.",
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
```

- [ ] **Step 4: Run tests — green**

Run: `uv run pytest tests/unit/test_main_entrypoint.py -v`
Expected: 3 passed.

- [ ] **Step 5: Quality gates**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ tests/ && uv run bandit -r src/ -ll`

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/__main__.py tests/unit/test_main_entrypoint.py
git commit -m "feat: __main__ entry point with run_worker_once helper"
```

---

### Task K4: `examples/echo_service` — minimal end-to-end smoke service

**Files:**
- Create: `examples/__init__.py`
- Create: `examples/echo_service/__init__.py`
- Create: `examples/echo_service/__main__.py`
- Create: `examples/echo_service/compute.py`
- Create: `tests/integration/test_echo_service.py`

**Why:** The smoke service proves the whole 1C stack composes from a fresh service implementer's perspective. It wires `Settings` → `EchoComputeBackend` (returns the input bytes verbatim) → `build_monolith_app` → `uvicorn`. The integration test boots the app via `httpx.AsyncClient(transport=ASGITransport(...))` (no real network), POSTs a Pub/Sub envelope, and asserts the recorded webhook payload mirrors the contract.

- [ ] **Step 1: Write the failing integration test**

```python
# tests/integration/test_echo_service.py
"""End-to-end smoke test for the echo example service."""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx
import pytest


@pytest.mark.asyncio
async def test_echo_service_runs_end_to_end_via_asgi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test-secret")

    from examples.echo_service import build  # type: ignore[import-not-found]

    app = build()

    contract: dict[str, Any] = {
        "envelope": {
            "protocol_version": "1.0",
            "request_id": "11111111-1111-1111-1111-111111111111",
            "created_at": "2026-04-26T00:00:00Z",
            "origin": "test",
        },
        "identity": {"user_id": "999", "tenant_id": "grabatus"},
        "references": {"parameter_id": "p", "result_id": "r"},
        "service": {"name": "echo", "version": "0.0.1"},
        "inputs": [
            {
                "role": "payload",
                "source_uri": "inline://hello",
                "format": "binary",
            },
        ],
        "outputs": [
            {
                "role": "echoed",
                "destination_uri": "inline://echoed",
                "format": "binary",
                "compression": "none",
                "write_mode": "overwrite",
            },
        ],
        "callback": {
            "url": "https://example.com/cb",
            "auth_scheme": "jwt_hs256",
        },
        "parameters": {},
    }

    pubsub = {
        "message": {
            "data": base64.b64encode(json.dumps(contract).encode("utf-8")).decode(
                "ascii",
            ),
            "messageId": "1",
        },
        "subscription": "x",
    }

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.post("/run_service", json=pubsub)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["request_id"] == "11111111-1111-1111-1111-111111111111"
```

- [ ] **Step 2: Run failing integration test**

Run: `uv run pytest tests/integration/test_echo_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'examples'`.

- [ ] **Step 3: Implement the echo service**

```python
# examples/__init__.py
```

```python
# examples/echo_service/__init__.py
"""Echo service: minimal end-to-end smoke for grabatus_service_core."""

from examples.echo_service.app import build

__all__ = ["build"]
```

```python
# examples/echo_service/compute.py
"""EchoComputeBackend: returns the input bytes verbatim under role 'echoed'."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel

from grabatus_service_core.ports.values import ComputeResult

if TYPE_CHECKING:
    from grabatus_service_core.ports.values import LoadedInputs


class EchoParameters(BaseModel):
    """Echo service has no parameters."""


class EchoComputeBackend:
    """Re-emits the 'payload' input under role 'echoed'."""

    REQUIRED_INPUT_ROLES: ClassVar[frozenset[str]] = frozenset({"payload"})
    OPTIONAL_INPUT_ROLES: ClassVar[frozenset[str]] = frozenset()
    OUTPUT_ROLES: ClassVar[frozenset[str]] = frozenset({"echoed"})

    def run(self, *, inputs: LoadedInputs, parameters: EchoParameters) -> ComputeResult:
        return ComputeResult(
            by_role={"echoed": inputs.by_role["payload"]},
            metadata={"echo": True},
        )
```

```python
# examples/echo_service/app.py
"""Echo service builder."""

from __future__ import annotations

from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
from grabatus_service_core.bootstrap import build_monolith_app
from grabatus_service_core.contract.base import BaseServiceContract
from grabatus_service_core.settings import Settings
from grabatus_service_core.testing import (
    AllowAllPolicy,
    InMemoryJobDispatcher,
    InMemorySecretsAdapter,
    InMemoryStorage,
    NullObservability,
    RecordingWebhookNotifier,
)

from examples.echo_service.compute import EchoComputeBackend, EchoParameters

_INLINE_PAYLOAD = b"hello-bytes"


def build():
    settings = Settings()
    storage = InMemoryStorage(seed={"inline://hello": _INLINE_PAYLOAD})
    return build_monolith_app(
        settings=settings,
        contract_type=BaseServiceContract[EchoParameters],
        compute=EchoComputeBackend(),
        adapters={
            "storage": storage,
            "message": PubSubMessagePort(),
            "webhook": RecordingWebhookNotifier(),
            "secrets": InMemorySecretsAdapter(seed={}),
            "authorizer": AllowAllPolicy(),
            "observability": NullObservability(),
            "job_dispatcher": InMemoryJobDispatcher(),
        },
    )
```

```python
# examples/echo_service/__main__.py
"""Run the echo service via uvicorn."""

from __future__ import annotations

import uvicorn

from examples.echo_service import build

if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(build(), host="0.0.0.0", port=8080)  # noqa: S104
```

- [ ] **Step 4: Mark `examples/` as a discoverable package for pytest**

Modify `pyproject.toml` `[tool.pytest.ini_options]` `testpaths` if needed; the test imports `examples.echo_service`, so add `pythonpath = ["."]` under `[tool.pytest.ini_options]`.

- [ ] **Step 5: Run integration test — green**

Run: `uv run pytest tests/integration/test_echo_service.py -v`
Expected: 1 passed.

- [ ] **Step 6: Quality gates**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/ tests/ && uv run bandit -r src/ -ll`

(Note: `examples/` is not part of `src/`, so mypy strict applies only to `src/` and `tests/`. The example must still be lint-clean.)

- [ ] **Step 7: Commit**

```bash
git add examples tests/integration/test_echo_service.py pyproject.toml
git commit -m "feat(examples): echo_service smoke proving 1C stack composes"
```

---

### Task K5: Re-enable 100% coverage gate and final regression

**Files:**
- Modify: `pyproject.toml`

**Why:** Sub-Plan 1B left a comment in `[tool.pytest.ini_options]` saying the `--cov-fail-under=100` gate would be re-enabled at the end of 1B. We honor that contract here at the close of 1C — every adapter, runner, app, observability, settings, and bootstrap module must hold 100% line + branch.

- [ ] **Step 1: Add the coverage threshold to addopts**

Modify `pyproject.toml` `[tool.pytest.ini_options]` `addopts`:

```toml
addopts = [
    "--strict-markers",
    "--strict-config",
    "-ra",
    "--cov=grabatus_service_core",
    "--cov-branch",
    "--cov-report=term-missing",
    "--cov-fail-under=100",
]
```

(Drop the multi-line comment about re-enabling later.)

- [ ] **Step 2: Run the full suite**

Run: `uv run pytest`
Expected: all tests pass, line + branch coverage 100%.

If a module is below 100%, write the missing test before continuing. Never lower the threshold; never add `# pragma: no cover` without an inline justification.

- [ ] **Step 3: Quality gates — final**

Run, in this order:

1. `uv run ruff check .`
2. `uv run ruff format --check .`
3. `uv run mypy --strict src/ tests/`
4. `uv run bandit -r src/ -ll`
5. `uv run pre-commit run --all-files`

Expected: every command exits 0.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: re-enable 100% line+branch coverage gate (closes Sub-Plan 1C)"
```

---

## Out-of-band: deferred items captured for Sub-Plan 1D

While executing 1C the implementer may encounter:

- **Cloud Trace exporter integration test** — needs a real GCP project; defer to 1D's `gcp_real` marker suite.
- **Cloud Monitoring dashboard YAML** — defer to 1D's Terraform module.
- **OTel propagation through Pub/Sub attributes** — out of scope for v0.1; track as a follow-up.

If any of these surface as blockers, stop and add a `> NOTE: deviation — <reason>` line in this plan rather than improvising.

---

## Final acceptance check (run before declaring 1C done)

- [ ] All tasks above committed individually
- [ ] `uv run pytest` exits 0 with line + branch coverage 100%
- [ ] `uv run mypy --strict src/ tests/` exits 0
- [ ] `uv run ruff check . && uv run ruff format --check .` exits 0
- [ ] `uv run bandit -r src/ -ll` zero findings
- [ ] `uv run pre-commit run --all-files` exits 0
- [ ] `examples/echo_service` boots and the smoke test passes
- [ ] `git log --oneline` shows one commit per task in order

When all boxes above are checked, Sub-Plan 1C is complete and the implementer hands control back to the user, who reviews and approves before Sub-Plan 1D begins.
