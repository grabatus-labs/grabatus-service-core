# Sub-Plan 1A — Domain Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the pure-Python domain foundation of `grabatus-service-core`: project scaffolding, typed exception hierarchy, Pydantic v2 contract schemas, Port (Protocol) definitions, security primitives, and the testing-fakes package. No I/O, no cloud SDK imports, no FastAPI yet — those arrive in Sub-Plans 1B and 1C.

**Architecture:** Hexagonal (Ports & Adapters), domain layer only. Domain code imports nothing beyond `pydantic`, `typing`, `pyjwt`, and stdlib. Concrete adapters that touch the network are deferred to Sub-Plan 1B. The fakes added in Phase F implement the same Ports the real adapters will, proving the abstractions are sound before any cloud SDK is wired up.

**Tech Stack (1A only):** Python 3.12, uv, Pydantic v2, PyJWT, pytest with branch coverage, ruff, mypy --strict, bandit, pre-commit. Heavier dependencies (FastAPI, structlog, OpenTelemetry, google-cloud-*) are declared in `pyproject.toml` for downstream sub-plans but not exercised here.

**Repository:** `/Users/rodolpho/Projects/grabatus-project/grabatus-service-core/` (already initialized as git repo with the design spec committed at `66631b7`).

**Spec sections covered by this sub-plan:** §5 (contract structure), §6.1 (Port table), §6.3 (security primitives), §6.4 (error taxonomy), §6.8 (testing API). All other spec sections are addressed in Sub-Plans 1B/1C/1D.

**Out of scope for Sub-Plan 1A (delivered later):**
- All adapters that touch I/O — Sub-Plan 1B
- `ServiceRunner` and 8-step pipeline — Sub-Plan 1B
- FastAPI integration — Sub-Plan 1C
- Settings (`pydantic-settings`) — Sub-Plan 1C
- Observability runtime (structlog/OTel exporters) — Sub-Plan 1C
- Sphinx, ADRs, CI/CD — Sub-Plan 1D
- `grabatus-forecasting` refactor — Plan 2

**Acceptance criteria (all must hold at end of Sub-Plan 1A):**
- `uv run pytest` exits 0 with line + branch coverage 100% on every module under `src/grabatus_service_core/`.
- `uv run mypy --strict src/ tests/` exits 0.
- `uv run ruff check . && uv run ruff format --check .` exits 0.
- `uv run bandit -r src/ -ll` zero medium/high findings.
- `uv run pre-commit run --all-files` exits 0.
- A consumer can `from grabatus_service_core import …` and: (a) instantiate `BaseServiceContract` with parsed JSON, (b) receive typed exceptions on invalid input, (c) construct fake adapters from `grabatus_service_core.testing` and use them in their own tests, (d) run an `AllowAllPolicy` against arbitrary URIs.
- Importing the library does not import any cloud SDK (`google.cloud`, `boto3`, etc.). This is enforced by a smoke test in Phase A.

---

## Conventions used in this plan

- All paths are relative to the repo root: `/Users/rodolpho/Projects/grabatus-project/grabatus-service-core/`
- All Python code uses Python 3.12+ features (PEP 695 generics, `match`, `|` unions)
- Every commit message follows conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`)
- Every test follows AAA structure (Arrange / Act / Assert)
- TDD is mandatory — failing test first, then implementation
- File line limit: 500 lines (target 200-300)
- Function line limit: 20 lines

---

## Phase A — Project Bootstrap

### Task A1: Initialize uv project and pyproject.toml

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.gitignore`

- [ ] **Step 1: Create `.python-version`**

```
3.12
```

- [ ] **Step 2: Create `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
ENV/

# uv
.uv/

# Testing & coverage
.pytest_cache/
.coverage
.coverage.*
htmlcov/
.tox/
.mutmut-cache
coverage.xml
*.cover

# Type checking
.mypy_cache/
.dmypy.json
.ruff_cache/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Build artifacts
build/
dist/
*.egg-info/
*.egg

# Sphinx
docs/_build/
docs/_autoapi/

# Environment
.env
.env.local
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "grabatus-service-core"
version = "0.1.0"
description = "Hexagonal core library for Grabatus computational services"
readme = "README.md"
requires-python = ">=3.12"
license = { text = "Proprietary" }
authors = [{ name = "Grabatus", email = "contato@grabatus.com" }]
dependencies = [
    "fastapi>=0.115",
    "pydantic>=2.7",
    "pydantic-settings>=2.5",
    "structlog>=24.4",
    "opentelemetry-api>=1.27",
    "opentelemetry-sdk>=1.27",
    "google-cloud-storage>=2.18",
    "google-cloud-pubsub>=2.26",
    "google-cloud-secret-manager>=2.20",
    "google-cloud-run>=0.10",
    "httpx>=0.27",
    "tenacity>=9.0",
    "pybreaker>=1.2",
    "pyjwt>=2.9",
    "uvicorn>=0.32",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "hypothesis>=6.115",
    "atheris>=2.3",
    "mutmut>=2.5",
    "testcontainers>=4.8",
    "freezegun>=1.5",
    "ruff>=0.7",
    "mypy>=1.13",
    "bandit>=1.7",
    "pip-audit>=2.7",
    "detect-secrets>=1.5",
    "pre-commit>=4.0",
    "sphinx>=8.0",
    "sphinx-autoapi>=3.3",
    "furo>=2024.8",
    "myst-parser>=4.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/grabatus_service_core"]

[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E", "F", "I", "N", "UP", "B", "SIM", "S", "ANN", "RUF",
    "PL", "PT", "TCH", "TID", "RET", "C4", "DTZ"
]
ignore = ["S101", "ANN101", "ANN102", "PLR0913"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S", "ANN", "PLR2004"]

[tool.mypy]
python_version = "3.12"
strict = true
disallow_any_explicit = true
warn_unreachable = true
warn_unused_ignores = true
files = ["src", "tests"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "gcp_real: requires real GCP project credentials",
    "slow: takes more than 1 second",
]
addopts = [
    "--strict-markers",
    "--strict-config",
    "-ra",
    "--cov=grabatus_service_core",
    "--cov-branch",
    "--cov-report=term-missing",
    "--cov-fail-under=100",
]

[tool.coverage.run]
branch = true
source = ["src/grabatus_service_core"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "\\.\\.\\.",
    "@(abc\\.)?abstractmethod",
]

[tool.bandit]
exclude_dirs = ["tests"]

[tool.mutmut]
paths_to_mutate = "src/grabatus_service_core/"
runner = "uv run pytest tests/unit tests/property -x -q"
tests_dir = "tests/"
```

- [ ] **Step 4: Run `uv sync` to create virtualenv**

Run: `cd /Users/rodolpho/Projects/grabatus-project/grabatus-service-core && uv sync --all-extras`
Expected: Creates `.venv/`, installs all dependencies, generates `uv.lock`.

- [ ] **Step 5: Commit**

```bash
git add .python-version .gitignore pyproject.toml uv.lock
git commit -m "chore: initialize uv project with pyproject.toml and dev dependencies"
```

---

### Task A2: Create source layout and `py.typed` marker

**Files:**
- Create: `src/grabatus_service_core/__init__.py`
- Create: `src/grabatus_service_core/py.typed`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create empty source package marker**

`src/grabatus_service_core/__init__.py`:
```python
"""Grabatus Service Core: hexagonal library for Grabatus computational services."""

__version__ = "0.1.0"
```

- [ ] **Step 2: Create `py.typed` marker (PEP 561)**

`src/grabatus_service_core/py.typed`:
```
```

(empty file — its presence signals to type checkers that this package ships type information)

- [ ] **Step 3: Create tests root**

`tests/__init__.py`:
```
```

- [ ] **Step 4: Create empty conftest**

`tests/conftest.py`:
```python
"""Shared test fixtures for grabatus_service_core."""
```

- [ ] **Step 5: Verify mypy and pytest import the package**

Run: `uv run mypy src/`
Expected: `Success: no issues found in 1 source file`

Run: `uv run pytest --collect-only`
Expected: `collected 0 items` (no tests yet, but pytest finds the package)

- [ ] **Step 6: Commit**

```bash
git add src/ tests/
git commit -m "chore: scaffold src layout with py.typed marker"
```

---

### Task A3: Configure pre-commit hooks

**Files:**
- Create: `.pre-commit-config.yaml`
- Create: `.secrets.baseline`

- [ ] **Step 1: Create `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
        args: [--maxkb=500]
      - id: check-merge-conflict
      - id: check-case-conflict
      - id: detect-private-key

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.4
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies:
          - pydantic>=2.7
          - pydantic-settings>=2.5
          - structlog>=24.4
        args: [--strict, --config-file=pyproject.toml]
        files: ^src/

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.10
    hooks:
      - id: bandit
        args: [-c, pyproject.toml, -r]
        files: ^src/

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: [--baseline, .secrets.baseline]
```

- [ ] **Step 2: Generate detect-secrets baseline**

Run: `uv run detect-secrets scan > .secrets.baseline`
Expected: `.secrets.baseline` file created with empty findings.

- [ ] **Step 3: Install hooks**

Run: `uv run pre-commit install`
Expected: `pre-commit installed at .git/hooks/pre-commit`

- [ ] **Step 4: Run on all files to verify**

Run: `uv run pre-commit run --all-files`
Expected: All hooks pass (or fix issues automatically).

- [ ] **Step 5: Commit**

```bash
git add .pre-commit-config.yaml .secrets.baseline
git commit -m "chore: configure pre-commit hooks (ruff, mypy, bandit, detect-secrets)"
```

---

### Task A4: Create README and CLAUDE.md skeleton

**Files:**
- Create: `README.md`
- Create: `CLAUDE.md`
- Create: `CHANGELOG.md`
- Create: `.env.template`

- [ ] **Step 1: Create `README.md`**

```markdown
# grabatus-service-core

Hexagonal core library for Grabatus computational services. Encapsulates the platform-to-service communication protocol so that new services (forecasting, optimization, Bayesian inference) only implement their own compute logic — every other concern (Pub/Sub, Storage I/O, JWT webhook, contract validation, observability, security) is inherited from this library.

## Status

v0.1.0 — work in progress.

## Documentation

Full Sphinx documentation lives in `docs/`. Build with `uv run sphinx-build -W docs/ docs/_build/html`.

## Development

```bash
uv sync --all-extras
uv run pre-commit install
uv run pytest
```

## License

Proprietary. © Grabatus.
```

- [ ] **Step 2: Create `CLAUDE.md`**

```markdown
# CLAUDE.md

Guidance for Claude Code agents working in this repository.

## Code style

- Functions: max 20 lines. Split if longer.
- Files: under 500 lines. Split by responsibility.
- One thing per function, one responsibility per module (SRP).
- Names: specific enough that every grep hit is relevant. Avoid `data`, `handler`, `Manager`.
- Types: explicit everywhere. No `Any`, no untyped functions. `mypy --strict` is the gate.
- No code duplication. Extract shared logic before it needs to change.
- Early returns over nested ifs. Max 3 levels of indentation.
- Exception messages must include the offending value: `f"expected X, got {repr(v)!r}"`.
- No magic numbers or strings — use named constants.
- No positional boolean parameters — keyword-only or enums.
- Functions return one consistent type or raise — never `T | None` as control flow.

## Errors & failures

- No silent failures: every `except` must log+reraise or handle explicitly. Never `pass`.
- Catch the most specific exception type available.
- Domain code never catches `Exception` — only the FastAPI boundary handler does.

## Tests

- Run: `uv run pytest`
- Single file: `uv run pytest tests/unit/path/test_x.py -v`
- Coverage 100% line + branch is enforced. `# pragma: no cover` requires inline justification.
- Mock only at system boundaries (cloud SDKs). Never mock our own services.
- Tests must be FIRST: Fast, Independent, Repeatable, Self-validating, Timely.

## Dependencies

- Inject through constructor/parameter, not global/import.
- Wrap third-party libs behind a Protocol owned by this project (see `ports/`).

## Structure

- `src/grabatus_service_core/contract/` — Pydantic schemas (the protocol)
- `src/grabatus_service_core/ports/` — Protocols (interfaces)
- `src/grabatus_service_core/adapters/` — concrete implementations of ports
- `src/grabatus_service_core/runner/` — orchestrator (`ServiceRunner`)
- `src/grabatus_service_core/errors/` — exception hierarchy
- `src/grabatus_service_core/api/` — FastAPI integration
- `src/grabatus_service_core/security/` — security primitives
- `src/grabatus_service_core/observability/` — logging/tracing/metrics
- `src/grabatus_service_core/testing/` — public test fakes (consumed by services)

## Formatting

- `uv run ruff format` — automated, no debate.
- `uv run ruff check --fix` — lints and autofixes.

## Logging

- Structured JSON via `structlog`. Always use `extra={...}` with named fields.
- Bind `request_id`, `tenant_id`, `service_name` via `contextvars` at request boundary.

## Commits

- Conventional commits: `type: describe the WHY, not the WHAT`.
- Reference issue numbers when relevant.
- Never amend commits unless explicitly asked.

## Defensive requirements

- All external HTTP calls: timeout 30s, retry 3x with exponential backoff via `tenacity`.
- Webhook publish: circuit breaker after 5 consecutive failures via `pybreaker`.
- All URIs validated by `UriAuthorizationPort` before any I/O.
```

- [ ] **Step 3: Create `CHANGELOG.md`**

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial library scaffold: contract schemas, ports, adapters, ServiceRunner.

## [0.1.0] — TBD

Initial public release.
```

- [ ] **Step 4: Create `.env.template`**

```bash
# Runtime mode for the service: receiver | worker | monolith
GBT_RUNTIME_MODE=monolith

# Environment: local | staging | production
GBT_ENV=local

# Timeouts (seconds)
GBT_REQUEST_TIMEOUT_SECONDS=540
GBT_HTTP_TIMEOUT_SECONDS=30
GBT_WEBHOOK_TIMEOUT_SECONDS=15
GBT_COMPUTE_TIMEOUT_SECONDS=480

# Security
GBT_ALLOWED_SCHEMES=gs,bigquery,secret
GBT_ALLOWED_HOSTS=
GBT_INLINE_URI_MAX_BYTES=65536

# Observability
GBT_LOG_LEVEL=INFO
GBT_TRACE_SAMPLE_RATE=1.0

# Webhook signing key (in production: read from Secret Manager)
SERVICE_SECRET_KEY=replace-me-in-production

# GCP
GBT_GCP_PROJECT=grabatus
GBT_GCP_REGION=us-east1
```

- [ ] **Step 5: Commit**

```bash
git add README.md CLAUDE.md CHANGELOG.md .env.template
git commit -m "docs: add README, CLAUDE.md, CHANGELOG, and env template"
```

---

## Phase B — Error Hierarchy

### Task B1: Implement `GrabatusServiceError` base

**Files:**
- Create: `src/grabatus_service_core/errors/__init__.py`
- Create: `src/grabatus_service_core/errors/base.py`
- Create: `tests/unit/errors/__init__.py`
- Create: `tests/unit/errors/test_base.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/errors/test_base.py`:
```python
"""Tests for the base error class."""

from __future__ import annotations

import pytest

from grabatus_service_core.errors.base import GrabatusServiceError


class _SampleError(GrabatusServiceError):
    error_code = "sample_error"
    http_status = 200
    retriable = False


def test_grabatus_service_error_has_error_code_classvar() -> None:
    assert _SampleError.error_code == "sample_error"


def test_grabatus_service_error_has_http_status_classvar() -> None:
    assert _SampleError.http_status == 200


def test_grabatus_service_error_has_retriable_classvar() -> None:
    assert _SampleError.retriable is False


def test_grabatus_service_error_message_is_passed_through() -> None:
    err = _SampleError("something failed at boundary")
    assert str(err) == "something failed at boundary"


def test_grabatus_service_error_context_defaults_to_empty_dict() -> None:
    err = _SampleError("msg")
    assert err.context == {}


def test_grabatus_service_error_context_is_stored() -> None:
    ctx = {"input_uri": "gs://bucket/key", "tenant": "grabatus"}
    err = _SampleError("msg", context=ctx)
    assert err.context == ctx


def test_grabatus_service_error_is_an_exception() -> None:
    with pytest.raises(GrabatusServiceError):
        raise _SampleError("boom")


def test_grabatus_service_error_subclass_must_declare_error_code() -> None:
    """Concrete subclasses must declare error_code; base class is abstract."""
    with pytest.raises(NotImplementedError, match="error_code"):
        GrabatusServiceError("msg")
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/errors/test_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'grabatus_service_core.errors'`

- [ ] **Step 3: Create errors package init**

`src/grabatus_service_core/errors/__init__.py`:
```python
"""Exception hierarchy for grabatus_service_core."""

from grabatus_service_core.errors.base import GrabatusServiceError

__all__ = ["GrabatusServiceError"]
```

- [ ] **Step 4: Create test package init**

`tests/unit/errors/__init__.py`:
```
```

`tests/unit/__init__.py`:
```
```

- [ ] **Step 5: Implement base error class**

`src/grabatus_service_core/errors/base.py`:
```python
"""Base exception class for all grabatus_service_core errors."""

from __future__ import annotations

from typing import ClassVar


class GrabatusServiceError(Exception):
    """Abstract base for all errors raised by grabatus_service_core.

    Subclasses MUST declare the three ``ClassVar`` attributes ``error_code``,
    ``http_status``, and ``retriable``. Direct instantiation of this base
    class is not permitted.

    Example::

        class InputReadError(StorageError):
            error_code = "input_read_failed"
            http_status = 200
            retriable = True
    """

    error_code: ClassVar[str]
    http_status: ClassVar[int]
    retriable: ClassVar[bool]

    def __init__(
        self,
        message: str,
        *,
        context: dict[str, object] | None = None,
    ) -> None:
        if "error_code" not in type(self).__dict__ and not hasattr(
            type(self), "error_code"
        ):
            raise NotImplementedError(
                f"{type(self).__name__} must declare a class-level "
                f"'error_code' attribute"
            )
        if type(self) is GrabatusServiceError:
            raise NotImplementedError(
                "GrabatusServiceError is abstract; subclass must declare "
                "'error_code', 'http_status', and 'retriable'"
            )
        super().__init__(message)
        self.context: dict[str, object] = context or {}
```

- [ ] **Step 6: Run test to verify pass**

Run: `uv run pytest tests/unit/errors/test_base.py -v`
Expected: All 8 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/grabatus_service_core/errors/ tests/unit/
git commit -m "feat(errors): add GrabatusServiceError abstract base class"
```

---

### Task B2: Implement contract, security, storage, compute, webhook error subclasses

**Files:**
- Create: `src/grabatus_service_core/errors/contract.py`
- Create: `src/grabatus_service_core/errors/security.py`
- Create: `src/grabatus_service_core/errors/io.py`
- Create: `src/grabatus_service_core/errors/compute.py`
- Create: `src/grabatus_service_core/errors/webhook.py`
- Create: `tests/unit/errors/test_subclasses.py`
- Modify: `src/grabatus_service_core/errors/__init__.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/errors/test_subclasses.py`:
```python
"""Tests for the concrete exception subclasses."""

from __future__ import annotations

import pytest

from grabatus_service_core.errors import (
    BlockedHostError,
    ComputeError,
    ComputeTimeoutError,
    ContractError,
    CredentialResolutionError,
    FormatParsingError,
    GrabatusServiceError,
    InputNotFoundError,
    InputReadError,
    InvalidContractError,
    MalformedMessageError,
    OutputWriteError,
    SecurityError,
    StorageError,
    UnauthorizedUriError,
    UnsupportedProtocolVersionError,
    UnsupportedSchemeError,
    WebhookAuthError,
    WebhookError,
)


@pytest.mark.parametrize(
    ("cls", "expected_code", "expected_retriable"),
    [
        (MalformedMessageError, "malformed_message", False),
        (InvalidContractError, "invalid_contract", False),
        (UnsupportedProtocolVersionError, "unsupported_protocol_version", False),
        (UnsupportedSchemeError, "unsupported_scheme", False),
        (UnauthorizedUriError, "unauthorized_uri", False),
        (BlockedHostError, "blocked_host", False),
        (CredentialResolutionError, "credential_resolution_failed", True),
        (InputNotFoundError, "input_not_found", False),
        (InputReadError, "input_read_failed", True),
        (OutputWriteError, "output_write_failed", True),
        (FormatParsingError, "format_parsing_failed", False),
        (ComputeError, "compute_failed", False),
        (ComputeTimeoutError, "compute_timeout", False),
        (WebhookError, "webhook_failed", True),
        (WebhookAuthError, "webhook_auth_failed", False),
    ],
)
def test_error_class_has_expected_attributes(
    cls: type[GrabatusServiceError],
    expected_code: str,
    expected_retriable: bool,
) -> None:
    assert cls.error_code == expected_code
    assert cls.http_status == 200
    assert cls.retriable is expected_retriable


def test_contract_subclasses_inherit_from_contract_error() -> None:
    assert issubclass(MalformedMessageError, ContractError)
    assert issubclass(InvalidContractError, ContractError)
    assert issubclass(UnsupportedProtocolVersionError, ContractError)


def test_security_subclasses_inherit_from_security_error() -> None:
    assert issubclass(UnsupportedSchemeError, SecurityError)
    assert issubclass(UnauthorizedUriError, SecurityError)
    assert issubclass(BlockedHostError, SecurityError)
    assert issubclass(CredentialResolutionError, SecurityError)


def test_storage_subclasses_inherit_from_storage_error() -> None:
    assert issubclass(InputNotFoundError, StorageError)
    assert issubclass(InputReadError, StorageError)
    assert issubclass(OutputWriteError, StorageError)
    assert issubclass(FormatParsingError, StorageError)


def test_compute_timeout_inherits_from_compute_error() -> None:
    assert issubclass(ComputeTimeoutError, ComputeError)


def test_webhook_auth_inherits_from_webhook_error() -> None:
    assert issubclass(WebhookAuthError, WebhookError)


def test_all_errors_inherit_from_base() -> None:
    classes: list[type[GrabatusServiceError]] = [
        ContractError, SecurityError, StorageError, ComputeError, WebhookError,
    ]
    for cls in classes:
        assert issubclass(cls, GrabatusServiceError)


def test_error_message_includes_offending_value() -> None:
    err = UnauthorizedUriError(
        "unauthorized URI for tenant='grabatus', got bucket='other-tenant'",
        context={"tenant": "grabatus", "got_bucket": "other-tenant"},
    )
    assert "tenant='grabatus'" in str(err)
    assert err.context["got_bucket"] == "other-tenant"
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/errors/test_subclasses.py -v`
Expected: FAIL — imports do not exist.

- [ ] **Step 3: Implement contract errors**

`src/grabatus_service_core/errors/contract.py`:
```python
"""Errors related to message decoding and contract validation."""

from __future__ import annotations

from grabatus_service_core.errors.base import GrabatusServiceError


class ContractError(GrabatusServiceError):
    """Base for any contract-related failure."""

    error_code = "contract_error"
    http_status = 200
    retriable = False


class MalformedMessageError(ContractError):
    """Raised when the Pub/Sub message envelope cannot be decoded."""

    error_code = "malformed_message"


class InvalidContractError(ContractError):
    """Raised when the decoded payload fails Pydantic validation."""

    error_code = "invalid_contract"


class UnsupportedProtocolVersionError(ContractError):
    """Raised when the envelope's protocol_version is not supported."""

    error_code = "unsupported_protocol_version"
```

- [ ] **Step 4: Implement security errors**

`src/grabatus_service_core/errors/security.py`:
```python
"""Errors raised by the security layer (URI auth, schemes, hosts, secrets)."""

from __future__ import annotations

from grabatus_service_core.errors.base import GrabatusServiceError


class SecurityError(GrabatusServiceError):
    """Base for security-related failures."""

    error_code = "security_error"
    http_status = 200
    retriable = False


class UnsupportedSchemeError(SecurityError):
    """URI uses a scheme that is not in GBT_ALLOWED_SCHEMES."""

    error_code = "unsupported_scheme"


class UnauthorizedUriError(SecurityError):
    """URI does not match the tenant/user prefix policy."""

    error_code = "unauthorized_uri"


class BlockedHostError(SecurityError):
    """HTTP URI targets a blocked host (metadata, internal, etc.)."""

    error_code = "blocked_host"


class CredentialResolutionError(SecurityError):
    """Secret manager could not resolve a credential reference."""

    error_code = "credential_resolution_failed"
    retriable = True
```

- [ ] **Step 5: Implement storage errors**

`src/grabatus_service_core/errors/io.py`:
```python
"""Errors raised by storage adapters during input read or output write."""

from __future__ import annotations

from grabatus_service_core.errors.base import GrabatusServiceError


class StorageError(GrabatusServiceError):
    """Base for storage I/O failures."""

    error_code = "storage_error"
    http_status = 200
    retriable = True


class InputNotFoundError(StorageError):
    """The requested input URI does not exist."""

    error_code = "input_not_found"
    retriable = False


class InputReadError(StorageError):
    """Reading the input failed (network, permissions, transient I/O)."""

    error_code = "input_read_failed"


class OutputWriteError(StorageError):
    """Writing the output failed."""

    error_code = "output_write_failed"


class FormatParsingError(StorageError):
    """The bytes could not be parsed in the declared format."""

    error_code = "format_parsing_failed"
    retriable = False
```

- [ ] **Step 6: Implement compute errors**

`src/grabatus_service_core/errors/compute.py`:
```python
"""Errors raised by the compute backend."""

from __future__ import annotations

from grabatus_service_core.errors.base import GrabatusServiceError


class ComputeError(GrabatusServiceError):
    """Base for compute failures."""

    error_code = "compute_failed"
    http_status = 200
    retriable = False


class ComputeTimeoutError(ComputeError):
    """Compute exceeded GBT_COMPUTE_TIMEOUT_SECONDS."""

    error_code = "compute_timeout"
```

- [ ] **Step 7: Implement webhook errors**

`src/grabatus_service_core/errors/webhook.py`:
```python
"""Errors raised when notifying the Grabatus webhook."""

from __future__ import annotations

from grabatus_service_core.errors.base import GrabatusServiceError


class WebhookError(GrabatusServiceError):
    """Base for webhook failures."""

    error_code = "webhook_failed"
    http_status = 200
    retriable = True


class WebhookAuthError(WebhookError):
    """Webhook returned 401/403 — JWT was rejected."""

    error_code = "webhook_auth_failed"
    retriable = False
```

- [ ] **Step 8: Update `errors/__init__.py` to export everything**

`src/grabatus_service_core/errors/__init__.py`:
```python
"""Exception hierarchy for grabatus_service_core."""

from grabatus_service_core.errors.base import GrabatusServiceError
from grabatus_service_core.errors.compute import (
    ComputeError,
    ComputeTimeoutError,
)
from grabatus_service_core.errors.contract import (
    ContractError,
    InvalidContractError,
    MalformedMessageError,
    UnsupportedProtocolVersionError,
)
from grabatus_service_core.errors.io import (
    FormatParsingError,
    InputNotFoundError,
    InputReadError,
    OutputWriteError,
    StorageError,
)
from grabatus_service_core.errors.security import (
    BlockedHostError,
    CredentialResolutionError,
    SecurityError,
    UnauthorizedUriError,
    UnsupportedSchemeError,
)
from grabatus_service_core.errors.webhook import (
    WebhookAuthError,
    WebhookError,
)

__all__ = [
    "BlockedHostError",
    "ComputeError",
    "ComputeTimeoutError",
    "ContractError",
    "CredentialResolutionError",
    "FormatParsingError",
    "GrabatusServiceError",
    "InputNotFoundError",
    "InputReadError",
    "InvalidContractError",
    "MalformedMessageError",
    "OutputWriteError",
    "SecurityError",
    "StorageError",
    "UnauthorizedUriError",
    "UnsupportedProtocolVersionError",
    "UnsupportedSchemeError",
    "WebhookAuthError",
    "WebhookError",
]
```

- [ ] **Step 9: Run test to verify pass**

Run: `uv run pytest tests/unit/errors/ -v`
Expected: All tests PASS.

- [ ] **Step 10: Commit**

```bash
git add src/grabatus_service_core/errors/ tests/unit/errors/
git commit -m "feat(errors): add typed exception hierarchy (contract/security/storage/compute/webhook)"
```

---

## Phase C — Contract Schemas

Phase C implements every Pydantic v2 model that defines the platform↔service protocol. Every model is `frozen=True` and `extra='forbid'` to prevent silent mutation and silent typos. All models live under `src/grabatus_service_core/contract/`.

### Task C1: Implement `Envelope`

**Files:**
- Create: `src/grabatus_service_core/contract/__init__.py`
- Create: `src/grabatus_service_core/contract/envelope.py`
- Create: `tests/unit/contract/__init__.py`
- Create: `tests/unit/contract/test_envelope.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/contract/test_envelope.py`:
```python
"""Tests for the Envelope schema."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.envelope import Envelope


def _valid_envelope_dict() -> dict[str, object]:
    return {
        "protocol_version": "1.0",
        "request_id": "a3f9c21e-bf38-4e75-9a2f-c89b6c3f2d12",
        "created_at": "2026-04-25T14:32:10Z",
        "origin": "web",
    }


def test_envelope_accepts_valid_payload() -> None:
    env = Envelope.model_validate(_valid_envelope_dict())

    assert env.protocol_version == "1.0"
    assert isinstance(env.request_id, UUID)
    assert env.created_at == datetime(2026, 4, 25, 14, 32, 10, tzinfo=UTC)
    assert env.origin == "web"


def test_envelope_rejects_unknown_protocol_version() -> None:
    payload = _valid_envelope_dict() | {"protocol_version": "0.9"}

    with pytest.raises(ValidationError, match="protocol_version"):
        Envelope.model_validate(payload)


@pytest.mark.parametrize("origin", ["web", "api", "mcp", "internal"])
def test_envelope_accepts_all_known_origins(origin: str) -> None:
    payload = _valid_envelope_dict() | {"origin": origin}

    env = Envelope.model_validate(payload)

    assert env.origin == origin


def test_envelope_rejects_unknown_origin() -> None:
    payload = _valid_envelope_dict() | {"origin": "telegram"}

    with pytest.raises(ValidationError, match="origin"):
        Envelope.model_validate(payload)


def test_envelope_rejects_naive_created_at() -> None:
    payload = _valid_envelope_dict() | {"created_at": "2026-04-25T14:32:10"}

    with pytest.raises(ValidationError, match="created_at"):
        Envelope.model_validate(payload)


def test_envelope_rejects_extra_fields() -> None:
    payload = _valid_envelope_dict() | {"unknown_field": "boom"}

    with pytest.raises(ValidationError, match="extra"):
        Envelope.model_validate(payload)


def test_envelope_is_frozen() -> None:
    env = Envelope.model_validate(_valid_envelope_dict())

    with pytest.raises(ValidationError, match="frozen"):
        env.protocol_version = "2.0"  # type: ignore[misc]


def test_envelope_round_trips_through_json() -> None:
    raw = Envelope.model_validate(_valid_envelope_dict()).model_dump_json()
    restored = Envelope.model_validate_json(raw)

    assert restored == Envelope.model_validate(_valid_envelope_dict())
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/contract/test_envelope.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'grabatus_service_core.contract'`

- [ ] **Step 3: Create contract package init**

`src/grabatus_service_core/contract/__init__.py`:
```python
"""Pydantic v2 schemas defining the platform-service protocol."""

from grabatus_service_core.contract.envelope import Envelope

__all__ = ["Envelope"]
```

`tests/unit/contract/__init__.py`:
```
```

- [ ] **Step 4: Implement Envelope**

`src/grabatus_service_core/contract/envelope.py`:
```python
"""The Envelope: top-level metadata of every contract message."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict


Origin = Literal["web", "api", "mcp", "internal"]
ProtocolVersion = Literal["1.0"]


class Envelope(BaseModel):
    """Metadata that wraps every service request.

    Carries the protocol version (for forward/backward compatibility),
    a unique request_id (used as the idempotency key end-to-end), the
    creation timestamp, and the origin channel of the request.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: ProtocolVersion
    request_id: UUID
    created_at: AwareDatetime
    origin: Origin
```

- [ ] **Step 5: Run test to verify pass**

Run: `uv run pytest tests/unit/contract/test_envelope.py -v --no-cov`
Expected: All 8 tests PASS.

- [ ] **Step 6: Run with coverage to confirm 100%**

Run: `uv run pytest tests/unit/contract/test_envelope.py --cov=grabatus_service_core.contract.envelope --cov-report=term-missing`
Expected: `TOTAL 100%`.

- [ ] **Step 7: Commit**

```bash
git add src/grabatus_service_core/contract/ tests/unit/contract/
git commit -m "feat(contract): add Envelope schema with protocol_version and origin"
```

---

### Task C2: Implement `Identity`

**Files:**
- Create: `src/grabatus_service_core/contract/identity.py`
- Create: `tests/unit/contract/test_identity.py`
- Modify: `src/grabatus_service_core/contract/__init__.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/contract/test_identity.py`:
```python
"""Tests for the Identity schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.identity import Identity


def test_identity_accepts_valid_user_and_tenant() -> None:
    identity = Identity.model_validate({"user_id": "999", "tenant_id": "grabatus"})

    assert identity.user_id == "999"
    assert identity.tenant_id == "grabatus"


@pytest.mark.parametrize(
    "tenant_id",
    ["Grabatus", "grabatus_v2", "grabatus.client", "grabatus client", ""],
)
def test_identity_rejects_invalid_tenant_id(tenant_id: str) -> None:
    with pytest.raises(ValidationError, match="tenant_id"):
        Identity.model_validate({"user_id": "999", "tenant_id": tenant_id})


@pytest.mark.parametrize("tenant_id", ["grabatus", "client-a", "tenant-123"])
def test_identity_accepts_valid_tenant_slugs(tenant_id: str) -> None:
    identity = Identity.model_validate({"user_id": "999", "tenant_id": tenant_id})

    assert identity.tenant_id == tenant_id


def test_identity_rejects_empty_user_id() -> None:
    with pytest.raises(ValidationError, match="user_id"):
        Identity.model_validate({"user_id": "", "tenant_id": "grabatus"})


def test_identity_rejects_oversized_user_id() -> None:
    with pytest.raises(ValidationError, match="user_id"):
        Identity.model_validate({"user_id": "x" * 65, "tenant_id": "grabatus"})


def test_identity_is_frozen() -> None:
    identity = Identity.model_validate({"user_id": "1", "tenant_id": "grabatus"})

    with pytest.raises(ValidationError, match="frozen"):
        identity.user_id = "2"  # type: ignore[misc]


def test_identity_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="extra"):
        Identity.model_validate(
            {"user_id": "1", "tenant_id": "grabatus", "role": "admin"},
        )
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/contract/test_identity.py -v`
Expected: FAIL with `ModuleNotFoundError: ... identity`.

- [ ] **Step 3: Implement Identity**

`src/grabatus_service_core/contract/identity.py`:
```python
"""Identity: caller identification for multi-tenant authorization."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


_TENANT_SLUG_PATTERN = r"^[a-z0-9-]+$"


class Identity(BaseModel):
    """Who is making the request.

    The ``tenant_id`` slug drives URI authorization (a request scoped to
    tenant ``grabatus`` may only access buckets/datasets prefixed with
    ``grabatus``). Slug is restricted to lowercase letters, digits, and
    hyphens to prevent path-traversal and case-folding ambiguity.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1, max_length=64)
    tenant_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=_TENANT_SLUG_PATTERN,
    )
```

- [ ] **Step 4: Update package init**

Edit `src/grabatus_service_core/contract/__init__.py`:
```python
"""Pydantic v2 schemas defining the platform-service protocol."""

from grabatus_service_core.contract.envelope import Envelope
from grabatus_service_core.contract.identity import Identity

__all__ = ["Envelope", "Identity"]
```

- [ ] **Step 5: Run tests to verify pass + coverage**

Run: `uv run pytest tests/unit/contract/ -v`
Expected: All tests PASS, coverage 100%.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/contract/ tests/unit/contract/
git commit -m "feat(contract): add Identity schema with tenant slug validation"
```

---

### Task C3: Implement `References`

**Files:**
- Create: `src/grabatus_service_core/contract/references.py`
- Create: `tests/unit/contract/test_references.py`
- Modify: `src/grabatus_service_core/contract/__init__.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/contract/test_references.py`:
```python
"""Tests for the References schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.references import References


def test_references_accepts_valid_ids() -> None:
    refs = References.model_validate(
        {"parameter_id": "param-001", "result_id": "result-001"},
    )

    assert refs.parameter_id == "param-001"
    assert refs.result_id == "result-001"


def test_references_rejects_empty_parameter_id() -> None:
    with pytest.raises(ValidationError, match="parameter_id"):
        References.model_validate({"parameter_id": "", "result_id": "r-1"})


def test_references_rejects_empty_result_id() -> None:
    with pytest.raises(ValidationError, match="result_id"):
        References.model_validate({"parameter_id": "p-1", "result_id": ""})


def test_references_is_frozen() -> None:
    refs = References.model_validate({"parameter_id": "p", "result_id": "r"})

    with pytest.raises(ValidationError, match="frozen"):
        refs.parameter_id = "x"  # type: ignore[misc]


def test_references_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="extra"):
        References.model_validate(
            {"parameter_id": "p", "result_id": "r", "other": "x"},
        )
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/contract/test_references.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement References**

`src/grabatus_service_core/contract/references.py`:
```python
"""References: platform-side IDs that round-trip in the webhook response."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class References(BaseModel):
    """Opaque IDs from the Grabatus platform.

    The service does not interpret these — they are echoed back in the
    webhook callback so the platform can correlate the response with its
    own database records.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    parameter_id: str = Field(min_length=1, max_length=128)
    result_id: str = Field(min_length=1, max_length=128)
```

- [ ] **Step 4: Update package init**

```python
"""Pydantic v2 schemas defining the platform-service protocol."""

from grabatus_service_core.contract.envelope import Envelope
from grabatus_service_core.contract.identity import Identity
from grabatus_service_core.contract.references import References

__all__ = ["Envelope", "Identity", "References"]
```

- [ ] **Step 5: Run tests, coverage**

Run: `uv run pytest tests/unit/contract/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/contract/ tests/unit/contract/
git commit -m "feat(contract): add References schema for platform-side IDs"
```

---

### Task C4: Implement `ServiceDescriptor`

**Files:**
- Create: `src/grabatus_service_core/contract/service_descriptor.py`
- Create: `tests/unit/contract/test_service_descriptor.py`
- Modify: `src/grabatus_service_core/contract/__init__.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/contract/test_service_descriptor.py`:
```python
"""Tests for the ServiceDescriptor schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.service_descriptor import ServiceDescriptor


def test_service_descriptor_accepts_valid_name_and_semver() -> None:
    desc = ServiceDescriptor.model_validate({"name": "forecast", "version": "1.2.0"})

    assert desc.name == "forecast"
    assert desc.version == "1.2.0"


@pytest.mark.parametrize(
    "name",
    ["Forecast", "forecast service", "forecast.v1", "forecast/v1", ""],
)
def test_service_descriptor_rejects_invalid_names(name: str) -> None:
    with pytest.raises(ValidationError, match="name"):
        ServiceDescriptor.model_validate({"name": name, "version": "1.0.0"})


@pytest.mark.parametrize(
    "name",
    ["forecast", "ab-test", "linear_optimization", "bayesian-mcmc-v2"],
)
def test_service_descriptor_accepts_valid_slugs(name: str) -> None:
    desc = ServiceDescriptor.model_validate({"name": name, "version": "1.0.0"})

    assert desc.name == name


@pytest.mark.parametrize(
    "version",
    ["1", "1.0", "v1.0.0", "1.0.0-alpha", "1.0.0+sha", "1.0.0.0"],
)
def test_service_descriptor_rejects_non_semver(version: str) -> None:
    with pytest.raises(ValidationError, match="version"):
        ServiceDescriptor.model_validate({"name": "forecast", "version": version})


@pytest.mark.parametrize("version", ["0.0.1", "1.0.0", "10.20.30"])
def test_service_descriptor_accepts_valid_semver(version: str) -> None:
    desc = ServiceDescriptor.model_validate({"name": "forecast", "version": version})

    assert desc.version == version


def test_service_descriptor_is_frozen() -> None:
    desc = ServiceDescriptor.model_validate({"name": "forecast", "version": "1.0.0"})

    with pytest.raises(ValidationError, match="frozen"):
        desc.name = "other"  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/contract/test_service_descriptor.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement ServiceDescriptor**

`src/grabatus_service_core/contract/service_descriptor.py`:
```python
"""ServiceDescriptor: identifies the target service and its version."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


_SERVICE_SLUG_PATTERN = r"^[a-z][a-z0-9_-]*$"
_SEMVER_PATTERN = r"^\d+\.\d+\.\d+$"


class ServiceDescriptor(BaseModel):
    """Identifies which service handles the request and at what version.

    Service ``name`` is a lowercase slug; ``version`` is strict
    ``MAJOR.MINOR.PATCH`` semver — pre-release and build metadata are not
    accepted in the contract (services release stable versions only).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=64, pattern=_SERVICE_SLUG_PATTERN)
    version: str = Field(min_length=5, max_length=32, pattern=_SEMVER_PATTERN)
```

- [ ] **Step 4: Update package init**

```python
"""Pydantic v2 schemas defining the platform-service protocol."""

from grabatus_service_core.contract.envelope import Envelope
from grabatus_service_core.contract.identity import Identity
from grabatus_service_core.contract.references import References
from grabatus_service_core.contract.service_descriptor import ServiceDescriptor

__all__ = ["Envelope", "Identity", "References", "ServiceDescriptor"]
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/contract/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/contract/ tests/unit/contract/
git commit -m "feat(contract): add ServiceDescriptor with slug + semver validation"
```

---

### Task C5: Implement `SecretRef` value object

**Files:**
- Create: `src/grabatus_service_core/contract/secret_ref.py`
- Create: `tests/unit/contract/test_secret_ref.py`
- Modify: `src/grabatus_service_core/contract/__init__.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/contract/test_secret_ref.py`:
```python
"""Tests for the SecretRef value object."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.secret_ref import SecretRef


def test_secret_ref_parses_full_uri() -> None:
    ref = SecretRef.model_validate("secret://gcp-secret-manager/bq-reader/3")

    assert ref.provider == "gcp-secret-manager"
    assert ref.name == "bq-reader"
    assert ref.version == "3"


def test_secret_ref_parses_uri_without_version_defaults_to_latest() -> None:
    ref = SecretRef.model_validate("secret://gcp-secret-manager/bq-reader")

    assert ref.provider == "gcp-secret-manager"
    assert ref.name == "bq-reader"
    assert ref.version == "latest"


def test_secret_ref_rejects_non_secret_scheme() -> None:
    with pytest.raises(ValidationError, match="scheme"):
        SecretRef.model_validate("https://example.com/secret/v1")


def test_secret_ref_rejects_uri_missing_provider() -> None:
    with pytest.raises(ValidationError, match="provider"):
        SecretRef.model_validate("secret:///bq-reader/1")


def test_secret_ref_rejects_uri_missing_name() -> None:
    with pytest.raises(ValidationError, match="name"):
        SecretRef.model_validate("secret://gcp-secret-manager")


def test_secret_ref_to_uri_round_trip() -> None:
    original = "secret://gcp-secret-manager/bq-reader/3"

    ref = SecretRef.model_validate(original)

    assert ref.to_uri() == original


def test_secret_ref_to_uri_omits_default_latest() -> None:
    ref = SecretRef.model_validate("secret://gcp-secret-manager/bq-reader")

    assert ref.to_uri() == "secret://gcp-secret-manager/bq-reader"


def test_secret_ref_is_frozen() -> None:
    ref = SecretRef.model_validate("secret://gsm/bq/1")

    with pytest.raises(ValidationError, match="frozen"):
        ref.name = "other"  # type: ignore[misc]


def test_secret_ref_serializes_as_uri_string() -> None:
    ref = SecretRef.model_validate("secret://gsm/bq/1")

    dumped = ref.model_dump(mode="json")

    assert dumped == "secret://gsm/bq/1"
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/contract/test_secret_ref.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement SecretRef**

`src/grabatus_service_core/contract/secret_ref.py`:
```python
"""SecretRef: typed reference to a secret in a remote secret manager."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator


_SECRET_SCHEME = "secret"
_DEFAULT_VERSION = "latest"


class SecretRef(BaseModel):
    """Typed reference to a secret stored in a secret manager.

    Wire format: ``secret://<provider>/<name>[/<version>]``. Examples::

        secret://gcp-secret-manager/bq-reader/3
        secret://gcp-secret-manager/webhook-signing-key  # implies latest

    The ``SecretsPort`` resolves a ``SecretRef`` to actual credential bytes
    at runtime. The reference itself is safe to log — it does not contain
    the secret value.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(default=_DEFAULT_VERSION, min_length=1, max_length=32)

    @model_validator(mode="before")
    @classmethod
    def _parse_uri(cls, value: Any) -> Any:
        if isinstance(value, str):
            return cls._parse_secret_uri(value)
        return value

    @staticmethod
    def _parse_secret_uri(uri: str) -> dict[str, str]:
        parsed = urlparse(uri)
        if parsed.scheme != _SECRET_SCHEME:
            raise ValueError(
                f"SecretRef requires scheme='{_SECRET_SCHEME}://', "
                f"got scheme={parsed.scheme!r}",
            )
        provider = parsed.netloc
        if not provider:
            raise ValueError(
                f"SecretRef requires a provider after 'secret://', "
                f"got uri={uri!r}",
            )
        path = parsed.path.lstrip("/")
        if not path:
            raise ValueError(
                f"SecretRef requires a secret name in the path, got uri={uri!r}",
            )
        parts = path.split("/", 1)
        name = parts[0]
        version = parts[1] if len(parts) == 2 else _DEFAULT_VERSION
        return {"provider": provider, "name": name, "version": version}

    def to_uri(self) -> str:
        """Render this reference back to its canonical URI form."""
        if self.version == _DEFAULT_VERSION:
            return f"{_SECRET_SCHEME}://{self.provider}/{self.name}"
        return f"{_SECRET_SCHEME}://{self.provider}/{self.name}/{self.version}"

    @model_serializer
    def _serialize(self) -> str:
        return self.to_uri()
```

- [ ] **Step 4: Update package init**

```python
"""Pydantic v2 schemas defining the platform-service protocol."""

from grabatus_service_core.contract.envelope import Envelope
from grabatus_service_core.contract.identity import Identity
from grabatus_service_core.contract.references import References
from grabatus_service_core.contract.secret_ref import SecretRef
from grabatus_service_core.contract.service_descriptor import ServiceDescriptor

__all__ = [
    "Envelope",
    "Identity",
    "References",
    "SecretRef",
    "ServiceDescriptor",
]
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/contract/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/contract/ tests/unit/contract/
git commit -m "feat(contract): add SecretRef value object with URI parsing"
```

---

### Task C6: Implement `FormatHints` discriminated union

**Files:**
- Create: `src/grabatus_service_core/contract/format_hints.py`
- Create: `tests/unit/contract/test_format_hints.py`
- Modify: `src/grabatus_service_core/contract/__init__.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/contract/test_format_hints.py`:
```python
"""Tests for the FormatHints discriminated union."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from grabatus_service_core.contract.format_hints import (
    BigQueryHints,
    CsvHints,
    FormatHints,
    InlineHints,
    JsonHints,
    ParquetHints,
    XlsxHints,
)


class _Holder(BaseModel):
    """Lightweight model exercising the discriminated union."""

    hints: FormatHints


def test_xlsx_hints_accepts_full_payload() -> None:
    holder = _Holder.model_validate(
        {"hints": {"format": "xlsx", "sheet": "Dados", "header": 0}},
    )

    assert isinstance(holder.hints, XlsxHints)
    assert holder.hints.sheet == "Dados"
    assert holder.hints.header == 0


def test_xlsx_hints_uses_defaults_when_omitted() -> None:
    holder = _Holder.model_validate({"hints": {"format": "xlsx"}})

    assert isinstance(holder.hints, XlsxHints)
    assert holder.hints.sheet == "Sheet1"
    assert holder.hints.header == 0


def test_xlsx_hints_rejects_typos() -> None:
    with pytest.raises(ValidationError, match="extra"):
        _Holder.model_validate({"hints": {"format": "xlsx", "sheetname": "Dados"}})


def test_csv_hints_round_trips() -> None:
    holder = _Holder.model_validate(
        {"hints": {"format": "csv", "delimiter": ";", "encoding": "latin-1"}},
    )

    assert isinstance(holder.hints, CsvHints)
    assert holder.hints.delimiter == ";"
    assert holder.hints.encoding == "latin-1"


def test_bigquery_hints_optional_query() -> None:
    holder = _Holder.model_validate(
        {"hints": {"format": "bigquery", "location": "US"}},
    )

    assert isinstance(holder.hints, BigQueryHints)
    assert holder.hints.query is None
    assert holder.hints.location == "US"


def test_parquet_hints_partition() -> None:
    holder = _Holder.model_validate(
        {"hints": {"format": "parquet", "partition": "year=2026"}},
    )

    assert isinstance(holder.hints, ParquetHints)
    assert holder.hints.partition == "year=2026"


def test_json_hints_default() -> None:
    holder = _Holder.model_validate({"hints": {"format": "json"}})

    assert isinstance(holder.hints, JsonHints)


def test_inline_hints_default() -> None:
    holder = _Holder.model_validate({"hints": {"format": "inline"}})

    assert isinstance(holder.hints, InlineHints)


def test_unknown_format_is_rejected() -> None:
    with pytest.raises(ValidationError, match="format"):
        _Holder.model_validate({"hints": {"format": "yaml"}})


def test_discriminator_routes_to_correct_class() -> None:
    holder = _Holder.model_validate(
        {"hints": {"format": "csv", "delimiter": "\t"}},
    )

    assert type(holder.hints).__name__ == "CsvHints"


def test_xlsx_header_must_be_non_negative() -> None:
    with pytest.raises(ValidationError, match="header"):
        _Holder.model_validate({"hints": {"format": "xlsx", "header": -1}})


def test_each_hint_class_is_frozen() -> None:
    holder = _Holder.model_validate({"hints": {"format": "xlsx"}})

    with pytest.raises(ValidationError, match="frozen"):
        holder.hints.sheet = "Other"  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/contract/test_format_hints.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement FormatHints**

`src/grabatus_service_core/contract/format_hints.py`:
```python
"""FormatHints: per-format parsing/serialization options.

Implemented as a discriminated union keyed on ``format``. Each format
declares its own model with ``extra='forbid'`` so that typos (e.g.
``sheetname`` instead of ``sheet``) fail validation immediately rather
than silently falling through to a default value at runtime.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _BaseHints(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class XlsxHints(_BaseHints):
    """Hints for reading or writing Excel spreadsheets."""

    format: Literal["xlsx"]
    sheet: str = Field(default="Sheet1", min_length=1, max_length=64)
    header: int = Field(default=0, ge=0, le=128)


class CsvHints(_BaseHints):
    """Hints for reading or writing CSV files."""

    format: Literal["csv"]
    delimiter: str = Field(default=",", min_length=1, max_length=4)
    encoding: str = Field(default="utf-8", min_length=1, max_length=32)


class JsonHints(_BaseHints):
    """Hints for reading or writing JSON files."""

    format: Literal["json"]


class ParquetHints(_BaseHints):
    """Hints for reading or writing Parquet files."""

    format: Literal["parquet"]
    partition: str | None = Field(default=None, max_length=256)


class BigQueryHints(_BaseHints):
    """Hints for BigQuery sources or destinations."""

    format: Literal["bigquery"]
    query: str | None = Field(default=None, max_length=8192)
    location: str = Field(default="US", min_length=1, max_length=32)


class InlineHints(_BaseHints):
    """Hints for inline payloads (small data embedded in the URI)."""

    format: Literal["inline"]


FormatHints = Annotated[
    XlsxHints | CsvHints | JsonHints | ParquetHints | BigQueryHints | InlineHints,
    Field(discriminator="format"),
]
```

- [ ] **Step 4: Update package init**

```python
"""Pydantic v2 schemas defining the platform-service protocol."""

from grabatus_service_core.contract.envelope import Envelope
from grabatus_service_core.contract.format_hints import (
    BigQueryHints,
    CsvHints,
    FormatHints,
    InlineHints,
    JsonHints,
    ParquetHints,
    XlsxHints,
)
from grabatus_service_core.contract.identity import Identity
from grabatus_service_core.contract.references import References
from grabatus_service_core.contract.secret_ref import SecretRef
from grabatus_service_core.contract.service_descriptor import ServiceDescriptor

__all__ = [
    "BigQueryHints",
    "CsvHints",
    "Envelope",
    "FormatHints",
    "Identity",
    "InlineHints",
    "JsonHints",
    "ParquetHints",
    "References",
    "SecretRef",
    "ServiceDescriptor",
    "XlsxHints",
]
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/contract/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/contract/ tests/unit/contract/
git commit -m "feat(contract): add FormatHints discriminated union (xlsx/csv/json/parquet/bigquery/inline)"
```

---

### Task C7: Implement `InputSpec`

**Files:**
- Create: `src/grabatus_service_core/contract/io_spec.py` (this task adds `InputSpec`; `OutputSpec` is added in Task C8 to the same file)
- Create: `tests/unit/contract/test_input_spec.py`
- Modify: `src/grabatus_service_core/contract/__init__.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/contract/test_input_spec.py`:
```python
"""Tests for the InputSpec schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.io_spec import InputSpec
from grabatus_service_core.contract.secret_ref import SecretRef


def _valid_input() -> dict[str, object]:
    return {
        "role": "timeseries",
        "source_uri": "gs://bucket/path/file.xlsx",
        "format": "xlsx",
        "format_hints": {"format": "xlsx", "sheet": "Dados", "header": 0},
    }


def test_input_spec_accepts_minimal_valid_payload() -> None:
    spec = InputSpec.model_validate(_valid_input())

    assert spec.role == "timeseries"
    assert str(spec.source_uri) == "gs://bucket/path/file.xlsx"
    assert spec.format == "xlsx"
    assert spec.credential_ref is None


def test_input_spec_accepts_credential_ref_uri() -> None:
    payload = _valid_input() | {"credential_ref": "secret://gsm/bq-reader/1"}

    spec = InputSpec.model_validate(payload)

    assert isinstance(spec.credential_ref, SecretRef)
    assert spec.credential_ref.name == "bq-reader"


@pytest.mark.parametrize(
    "role",
    ["Timeseries", "time-series", "time series", "1timeseries", ""],
)
def test_input_spec_rejects_invalid_roles(role: str) -> None:
    payload = _valid_input() | {"role": role}

    with pytest.raises(ValidationError, match="role"):
        InputSpec.model_validate(payload)


@pytest.mark.parametrize(
    "role",
    ["timeseries", "holidays", "training_data", "auxiliary_features"],
)
def test_input_spec_accepts_valid_roles(role: str) -> None:
    payload = _valid_input() | {"role": role}

    spec = InputSpec.model_validate(payload)

    assert spec.role == role


def test_input_spec_rejects_format_hint_mismatch() -> None:
    payload = _valid_input() | {
        "format": "csv",
        "format_hints": {"format": "xlsx", "sheet": "X"},
    }

    with pytest.raises(ValidationError, match="format"):
        InputSpec.model_validate(payload)


def test_input_spec_is_frozen() -> None:
    spec = InputSpec.model_validate(_valid_input())

    with pytest.raises(ValidationError, match="frozen"):
        spec.role = "other"  # type: ignore[misc]


def test_input_spec_rejects_extra_fields() -> None:
    payload = _valid_input() | {"unknown": "x"}

    with pytest.raises(ValidationError, match="extra"):
        InputSpec.model_validate(payload)
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/contract/test_input_spec.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `InputSpec` (and shared format Literal)**

`src/grabatus_service_core/contract/io_spec.py`:
```python
"""InputSpec and OutputSpec: declarative I/O for service contracts."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from grabatus_service_core.contract.format_hints import FormatHints
from grabatus_service_core.contract.secret_ref import SecretRef


_ROLE_PATTERN = r"^[a-z][a-z0-9_]*$"

DataFormat = Literal["xlsx", "csv", "json", "parquet", "bigquery", "inline"]


class InputSpec(BaseModel):
    """Declarative description of an input to be loaded by the service.

    Each input carries a service-defined ``role`` (e.g. ``timeseries``,
    ``holidays``) which the service's ``ComputeBackendPort`` declares as
    required or optional. The library validates roles at contract time.

    The ``format_hints`` discriminator must match the ``format`` field; a
    mismatch is rejected by the validator at model creation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str = Field(min_length=1, max_length=32, pattern=_ROLE_PATTERN)
    source_uri: AnyUrl
    format: DataFormat
    format_hints: FormatHints
    credential_ref: SecretRef | None = None

    @model_validator(mode="after")
    def _format_matches_hints(self) -> Self:
        if self.format_hints.format != self.format:
            raise ValueError(
                f"format_hints.format={self.format_hints.format!r} does not "
                f"match format={self.format!r}",
            )
        return self
```

- [ ] **Step 4: Update package init (export InputSpec)**

```python
# add to grabatus_service_core/contract/__init__.py
from grabatus_service_core.contract.io_spec import InputSpec
```

Add `"InputSpec"` to `__all__` (keep alphabetical).

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/contract/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/contract/ tests/unit/contract/
git commit -m "feat(contract): add InputSpec with role+URI+format hints validation"
```

---

### Task C8: Implement `OutputSpec`

**Files:**
- Modify: `src/grabatus_service_core/contract/io_spec.py` (add `OutputSpec` class)
- Create: `tests/unit/contract/test_output_spec.py`
- Modify: `src/grabatus_service_core/contract/__init__.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/contract/test_output_spec.py`:
```python
"""Tests for the OutputSpec schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.io_spec import OutputSpec


def _valid_output() -> dict[str, object]:
    return {
        "role": "forecast_json",
        "destination_uri": "gs://bucket/path/result.json.gz",
        "format": "json",
        "format_hints": {"format": "json"},
    }


def test_output_spec_accepts_minimal_payload_uses_defaults() -> None:
    spec = OutputSpec.model_validate(_valid_output())

    assert spec.compression == "none"
    assert spec.write_mode == "overwrite"


@pytest.mark.parametrize("compression", ["none", "gzip", "zstd"])
def test_output_spec_accepts_known_compressions(compression: str) -> None:
    payload = _valid_output() | {"compression": compression}

    spec = OutputSpec.model_validate(payload)

    assert spec.compression == compression


def test_output_spec_rejects_unknown_compression() -> None:
    payload = _valid_output() | {"compression": "lz4"}

    with pytest.raises(ValidationError, match="compression"):
        OutputSpec.model_validate(payload)


@pytest.mark.parametrize("mode", ["overwrite", "append", "fail_if_exists"])
def test_output_spec_accepts_known_write_modes(mode: str) -> None:
    payload = _valid_output() | {"write_mode": mode}

    spec = OutputSpec.model_validate(payload)

    assert spec.write_mode == mode


def test_output_spec_rejects_unknown_write_mode() -> None:
    payload = _valid_output() | {"write_mode": "upsert"}

    with pytest.raises(ValidationError, match="write_mode"):
        OutputSpec.model_validate(payload)


def test_output_spec_format_must_match_hints() -> None:
    payload = _valid_output() | {
        "format": "csv",
        "format_hints": {"format": "json"},
    }

    with pytest.raises(ValidationError, match="format"):
        OutputSpec.model_validate(payload)


def test_output_spec_is_frozen() -> None:
    spec = OutputSpec.model_validate(_valid_output())

    with pytest.raises(ValidationError, match="frozen"):
        spec.compression = "gzip"  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/contract/test_output_spec.py -v`
Expected: FAIL — `OutputSpec` not defined.

- [ ] **Step 3: Append `OutputSpec` to `io_spec.py`**

Append at the end of `src/grabatus_service_core/contract/io_spec.py`:
```python
Compression = Literal["none", "gzip", "zstd"]
WriteMode = Literal["overwrite", "append", "fail_if_exists"]


class OutputSpec(BaseModel):
    """Declarative description of an output the service must persist.

    Carries the destination URI, format, optional compression, and a
    write mode that adapters honor (overwrite/append/fail_if_exists).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str = Field(min_length=1, max_length=32, pattern=_ROLE_PATTERN)
    destination_uri: AnyUrl
    format: DataFormat
    format_hints: FormatHints
    compression: Compression = "none"
    write_mode: WriteMode = "overwrite"
    credential_ref: SecretRef | None = None

    @model_validator(mode="after")
    def _format_matches_hints(self) -> Self:
        if self.format_hints.format != self.format:
            raise ValueError(
                f"format_hints.format={self.format_hints.format!r} does not "
                f"match format={self.format!r}",
            )
        return self
```

- [ ] **Step 4: Update package init**

Add `from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec` and add `"OutputSpec"` to `__all__`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/contract/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/contract/ tests/unit/contract/
git commit -m "feat(contract): add OutputSpec with compression and write_mode"
```

---

### Task C9: Implement `Callback`

**Files:**
- Create: `src/grabatus_service_core/contract/callback.py`
- Create: `tests/unit/contract/test_callback.py`
- Modify: `src/grabatus_service_core/contract/__init__.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/contract/test_callback.py`:
```python
"""Tests for the Callback schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.callback import Callback


def test_callback_accepts_https_url_with_jwt_scheme() -> None:
    cb = Callback.model_validate(
        {"url": "https://grabatus.com/webhooks/svc", "auth_scheme": "jwt_hs256"},
    )

    assert str(cb.url) == "https://grabatus.com/webhooks/svc"
    assert cb.auth_scheme == "jwt_hs256"


def test_callback_rejects_http_url_in_production_default() -> None:
    with pytest.raises(ValidationError, match="https"):
        Callback.model_validate(
            {"url": "http://example.com/webhook", "auth_scheme": "jwt_hs256"},
        )


def test_callback_rejects_unknown_auth_scheme() -> None:
    with pytest.raises(ValidationError, match="auth_scheme"):
        Callback.model_validate(
            {"url": "https://x.com/wh", "auth_scheme": "bearer"},
        )


def test_callback_is_frozen() -> None:
    cb = Callback.model_validate(
        {"url": "https://x.com/wh", "auth_scheme": "jwt_hs256"},
    )

    with pytest.raises(ValidationError, match="frozen"):
        cb.auth_scheme = "other"  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/contract/test_callback.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement Callback**

`src/grabatus_service_core/contract/callback.py`:
```python
"""Callback: how the service notifies the platform when work completes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator


AuthScheme = Literal["jwt_hs256"]


class Callback(BaseModel):
    """Webhook destination the service notifies after the pipeline finishes.

    Only HTTPS URLs are accepted. The signing scheme is constrained to a
    closed set; ``jwt_hs256`` is the only scheme supported in v1.0.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: HttpUrl
    auth_scheme: AuthScheme

    @field_validator("url")
    @classmethod
    def _require_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError(
                f"Callback url must use https scheme, got {value.scheme!r}",
            )
        return value
```

- [ ] **Step 4: Update package init**

Add `from grabatus_service_core.contract.callback import Callback` and `"Callback"` to `__all__`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/contract/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/contract/ tests/unit/contract/
git commit -m "feat(contract): add Callback schema (https + jwt_hs256 only)"
```

---

### Task C10: Implement `BaseServiceContract` (generic) and `version` compatibility helper

**Files:**
- Create: `src/grabatus_service_core/contract/base.py`
- Create: `src/grabatus_service_core/contract/version.py`
- Create: `tests/unit/contract/test_base_contract.py`
- Create: `tests/unit/contract/test_version_compatibility.py`
- Modify: `src/grabatus_service_core/contract/__init__.py`

- [ ] **Step 1: Write failing tests for `version.py`**

`tests/unit/contract/test_version_compatibility.py`:
```python
"""Tests for protocol version compatibility helpers."""

from __future__ import annotations

import pytest

from grabatus_service_core.contract.version import (
    SUPPORTED_PROTOCOL_VERSIONS,
    is_protocol_version_supported,
)


def test_supported_versions_contains_v1_0() -> None:
    assert "1.0" in SUPPORTED_PROTOCOL_VERSIONS


@pytest.mark.parametrize("version", ["1.0"])
def test_is_protocol_version_supported_accepts_known(version: str) -> None:
    assert is_protocol_version_supported(version) is True


@pytest.mark.parametrize("version", ["0.9", "2.0", "1.1", "abc", ""])
def test_is_protocol_version_supported_rejects_unknown(version: str) -> None:
    assert is_protocol_version_supported(version) is False
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest tests/unit/contract/test_version_compatibility.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `version.py`**

`src/grabatus_service_core/contract/version.py`:
```python
"""Protocol version constants and compatibility helpers."""

from __future__ import annotations

from typing import Final


SUPPORTED_PROTOCOL_VERSIONS: Final[frozenset[str]] = frozenset({"1.0"})


def is_protocol_version_supported(version: str) -> bool:
    """Return True iff this library supports the given protocol_version.

    Used by the runner to fail fast with
    ``UnsupportedProtocolVersionError`` before deeper validation runs.
    """
    return version in SUPPORTED_PROTOCOL_VERSIONS
```

- [ ] **Step 4: Run version test to verify pass**

Run: `uv run pytest tests/unit/contract/test_version_compatibility.py -v`
Expected: PASS.

- [ ] **Step 5: Write failing tests for `BaseServiceContract`**

`tests/unit/contract/test_base_contract.py`:
```python
"""Tests for BaseServiceContract (generic over the parameters type)."""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from grabatus_service_core.contract import BaseServiceContract


class _SampleParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    period: int = 30
    mode: Literal["fast", "slow"] = "fast"


def _valid_payload() -> dict[str, object]:
    return {
        "envelope": {
            "protocol_version": "1.0",
            "request_id": "a3f9c21e-bf38-4e75-9a2f-c89b6c3f2d12",
            "created_at": "2026-04-25T14:32:10Z",
            "origin": "web",
        },
        "identity": {"user_id": "999", "tenant_id": "grabatus"},
        "references": {"parameter_id": "p-1", "result_id": "r-1"},
        "service": {"name": "sample", "version": "1.0.0"},
        "inputs": [
            {
                "role": "timeseries",
                "source_uri": "gs://bucket/in.xlsx",
                "format": "xlsx",
                "format_hints": {"format": "xlsx", "sheet": "Dados"},
            },
        ],
        "outputs": [
            {
                "role": "result_json",
                "destination_uri": "gs://bucket/out.json",
                "format": "json",
                "format_hints": {"format": "json"},
            },
        ],
        "callback": {
            "url": "https://grabatus.com/webhook",
            "auth_scheme": "jwt_hs256",
        },
        "parameters": {"period": 60, "mode": "slow"},
    }


def test_base_contract_accepts_full_valid_payload() -> None:
    contract = BaseServiceContract[_SampleParameters].model_validate(_valid_payload())

    assert contract.envelope.protocol_version == "1.0"
    assert contract.identity.tenant_id == "grabatus"
    assert len(contract.inputs) == 1
    assert len(contract.outputs) == 1
    assert isinstance(contract.parameters, _SampleParameters)
    assert contract.parameters.period == 60


def test_base_contract_requires_at_least_one_input() -> None:
    payload = _valid_payload() | {"inputs": []}

    with pytest.raises(ValidationError, match="inputs"):
        BaseServiceContract[_SampleParameters].model_validate(payload)


def test_base_contract_requires_at_least_one_output() -> None:
    payload = _valid_payload() | {"outputs": []}

    with pytest.raises(ValidationError, match="outputs"):
        BaseServiceContract[_SampleParameters].model_validate(payload)


def test_base_contract_caps_input_count_at_ten() -> None:
    one_input = _valid_payload()["inputs"][0]  # type: ignore[index]
    payload = _valid_payload() | {"inputs": [one_input] * 11}

    with pytest.raises(ValidationError, match="inputs"):
        BaseServiceContract[_SampleParameters].model_validate(payload)


def test_base_contract_rejects_duplicate_input_roles() -> None:
    one_input = _valid_payload()["inputs"][0]  # type: ignore[index]
    payload = _valid_payload() | {"inputs": [one_input, one_input]}

    with pytest.raises(ValidationError, match="role"):
        BaseServiceContract[_SampleParameters].model_validate(payload)


def test_base_contract_rejects_duplicate_output_roles() -> None:
    one_output = _valid_payload()["outputs"][0]  # type: ignore[index]
    payload = _valid_payload() | {"outputs": [one_output, one_output]}

    with pytest.raises(ValidationError, match="role"):
        BaseServiceContract[_SampleParameters].model_validate(payload)


def test_base_contract_propagates_parameters_validation() -> None:
    payload = _valid_payload() | {"parameters": {"mode": "turbo"}}

    with pytest.raises(ValidationError, match="mode"):
        BaseServiceContract[_SampleParameters].model_validate(payload)


def test_base_contract_is_frozen() -> None:
    contract = BaseServiceContract[_SampleParameters].model_validate(_valid_payload())

    with pytest.raises(ValidationError, match="frozen"):
        contract.parameters = _SampleParameters()  # type: ignore[misc]


def test_base_contract_rejects_unsupported_protocol_version() -> None:
    payload = _valid_payload()
    payload_envelope = dict(payload["envelope"])  # type: ignore[arg-type]
    payload_envelope["protocol_version"] = "0.9"
    payload = payload | {"envelope": payload_envelope}

    with pytest.raises(ValidationError, match="protocol_version"):
        BaseServiceContract[_SampleParameters].model_validate(payload)
```

- [ ] **Step 6: Run failing test**

Run: `uv run pytest tests/unit/contract/test_base_contract.py -v`
Expected: FAIL — `BaseServiceContract` not exported.

- [ ] **Step 7: Implement `BaseServiceContract`**

`src/grabatus_service_core/contract/base.py`:
```python
"""BaseServiceContract: the generic top-level contract every service receives."""

from __future__ import annotations

from typing import Generic, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from grabatus_service_core.contract.callback import Callback
from grabatus_service_core.contract.envelope import Envelope
from grabatus_service_core.contract.identity import Identity
from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
from grabatus_service_core.contract.references import References
from grabatus_service_core.contract.service_descriptor import ServiceDescriptor


_MAX_INPUTS = 10
_MAX_OUTPUTS = 10

ParamsT = TypeVar("ParamsT", bound=BaseModel)


class BaseServiceContract(BaseModel, Generic[ParamsT]):
    """Generic top-level contract that wraps every service request.

    A concrete service parameterizes this with its own ``Parameters``
    Pydantic model::

        class ForecastContract(BaseServiceContract[ForecastParameters]):
            pass

    The library validates every section here; service code only validates
    its own ``parameters`` payload.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    envelope: Envelope
    identity: Identity
    references: References
    service: ServiceDescriptor
    inputs: list[InputSpec] = Field(min_length=1, max_length=_MAX_INPUTS)
    outputs: list[OutputSpec] = Field(min_length=1, max_length=_MAX_OUTPUTS)
    callback: Callback
    parameters: ParamsT

    @model_validator(mode="after")
    def _input_roles_are_unique(self) -> Self:
        roles = [item.role for item in self.inputs]
        if len(roles) != len(set(roles)):
            duplicates = sorted({r for r in roles if roles.count(r) > 1})
            raise ValueError(
                f"input roles must be unique, got duplicates={duplicates!r}",
            )
        return self

    @model_validator(mode="after")
    def _output_roles_are_unique(self) -> Self:
        roles = [item.role for item in self.outputs]
        if len(roles) != len(set(roles)):
            duplicates = sorted({r for r in roles if roles.count(r) > 1})
            raise ValueError(
                f"output roles must be unique, got duplicates={duplicates!r}",
            )
        return self
```

- [ ] **Step 8: Update package init**

`src/grabatus_service_core/contract/__init__.py`:
```python
"""Pydantic v2 schemas defining the platform-service protocol."""

from grabatus_service_core.contract.base import BaseServiceContract
from grabatus_service_core.contract.callback import Callback
from grabatus_service_core.contract.envelope import Envelope
from grabatus_service_core.contract.format_hints import (
    BigQueryHints,
    CsvHints,
    FormatHints,
    InlineHints,
    JsonHints,
    ParquetHints,
    XlsxHints,
)
from grabatus_service_core.contract.identity import Identity
from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
from grabatus_service_core.contract.references import References
from grabatus_service_core.contract.secret_ref import SecretRef
from grabatus_service_core.contract.service_descriptor import ServiceDescriptor
from grabatus_service_core.contract.version import (
    SUPPORTED_PROTOCOL_VERSIONS,
    is_protocol_version_supported,
)

__all__ = [
    "SUPPORTED_PROTOCOL_VERSIONS",
    "BaseServiceContract",
    "BigQueryHints",
    "Callback",
    "CsvHints",
    "Envelope",
    "FormatHints",
    "Identity",
    "InlineHints",
    "InputSpec",
    "JsonHints",
    "OutputSpec",
    "ParquetHints",
    "References",
    "SecretRef",
    "ServiceDescriptor",
    "XlsxHints",
    "is_protocol_version_supported",
]
```

- [ ] **Step 9: Run all contract tests**

Run: `uv run pytest tests/unit/contract/ -v`
Expected: All tests PASS.

- [ ] **Step 10: Run full coverage on contract module**

Run: `uv run pytest tests/unit/contract/ --cov=grabatus_service_core.contract --cov-branch --cov-report=term-missing`
Expected: 100% line + branch coverage.

- [ ] **Step 11: Commit**

```bash
git add src/grabatus_service_core/contract/ tests/unit/contract/
git commit -m "feat(contract): add BaseServiceContract generic and protocol version helpers"
```

---

## Phase D — Ports (Protocols)

Phase D defines every Port as a `typing.Protocol`. Ports declare *what* the runner needs from a collaborator; concrete adapters (Sub-Plan 1B) implement *how*. Each Port lives in its own module under `src/grabatus_service_core/ports/`. All Protocols are `@runtime_checkable` so the testing fakes (Phase F) can be verified against them via `isinstance`.

The Phase D tests do not exercise behavior — Protocols have no behavior. They verify shape: a class missing a required method is rejected; a fake that satisfies the Protocol is accepted by `isinstance(fake, Port)`.

### Task D1: Implement infrastructure Ports (Clock, Observability, JobDispatcher)

**Files:**
- Create: `src/grabatus_service_core/ports/__init__.py`
- Create: `src/grabatus_service_core/ports/clock.py`
- Create: `src/grabatus_service_core/ports/observability.py`
- Create: `src/grabatus_service_core/ports/job_dispatcher.py`
- Create: `tests/unit/ports/__init__.py`
- Create: `tests/unit/ports/test_infrastructure_ports.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/ports/test_infrastructure_ports.py`:
```python
"""Shape tests for infrastructure Ports (Clock, Observability, JobDispatcher)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from grabatus_service_core.ports.clock import ClockPort
from grabatus_service_core.ports.job_dispatcher import (
    DispatchedJob,
    JobDispatcherPort,
)
from grabatus_service_core.ports.observability import ObservabilityPort


class _OkClock:
    def now(self) -> datetime:
        return datetime(2026, 4, 25, tzinfo=UTC)

    def monotonic(self) -> float:
        return 0.0


class _BadClock:
    def now(self) -> datetime:
        return datetime(2026, 4, 25, tzinfo=UTC)


class _OkObservability:
    def log(self, event: str, **fields: Any) -> None: ...
    def span(self, name: str, **attrs: Any) -> object:
        return object()
    def metric(self, name: str, value: float, **tags: Any) -> None: ...


class _BadObservability:
    def log(self, event: str, **fields: Any) -> None: ...


class _OkDispatcher:
    def dispatch(
        self, *, job_name: str, payload: bytes, request_id: UUID,
    ) -> DispatchedJob:
        return DispatchedJob(job_id="abc", request_id=request_id)


def test_clock_port_accepts_full_implementation() -> None:
    assert isinstance(_OkClock(), ClockPort)


def test_clock_port_rejects_missing_monotonic() -> None:
    assert not isinstance(_BadClock(), ClockPort)


def test_observability_port_accepts_full_implementation() -> None:
    assert isinstance(_OkObservability(), ObservabilityPort)


def test_observability_port_rejects_missing_method() -> None:
    assert not isinstance(_BadObservability(), ObservabilityPort)


def test_job_dispatcher_port_accepts_full_implementation() -> None:
    assert isinstance(_OkDispatcher(), JobDispatcherPort)


def test_dispatched_job_carries_job_id_and_request_id() -> None:
    rid = UUID("a3f9c21e-bf38-4e75-9a2f-c89b6c3f2d12")
    job = DispatchedJob(job_id="job-1", request_id=rid)

    assert job.job_id == "job-1"
    assert job.request_id == rid
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/ports/test_infrastructure_ports.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement `ClockPort`**

`src/grabatus_service_core/ports/clock.py`:
```python
"""ClockPort: abstract over wall-clock time for testability."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class ClockPort(Protocol):
    """Abstract clock; tests inject FrozenClock for determinism."""

    def now(self) -> datetime:
        """Return the current timezone-aware UTC datetime."""
        ...

    def monotonic(self) -> float:
        """Return a monotonic counter in seconds for duration measurement."""
        ...
```

- [ ] **Step 4: Implement `ObservabilityPort`**

`src/grabatus_service_core/ports/observability.py`:
```python
"""ObservabilityPort: structured logs, traces, and metrics."""

from __future__ import annotations

from typing import Any, ContextManager, Protocol, runtime_checkable


@runtime_checkable
class ObservabilityPort(Protocol):
    """Single entry point for emitting logs, spans, and metrics.

    Implementations route to structlog (logs), OpenTelemetry (spans),
    and OTel/Cloud Monitoring (metrics). Tests inject ``NullObservability``
    which records nothing.
    """

    def log(self, event: str, **fields: Any) -> None:
        """Emit a structured log event with named fields."""
        ...

    def span(self, name: str, **attrs: Any) -> ContextManager[object]:
        """Return a context manager that records a tracing span."""
        ...

    def metric(self, name: str, value: float, **tags: Any) -> None:
        """Record a metric data point with tag dimensions."""
        ...
```

- [ ] **Step 5: Implement `JobDispatcherPort`**

`src/grabatus_service_core/ports/job_dispatcher.py`:
```python
"""JobDispatcherPort: enqueue worker jobs from the receiver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DispatchedJob:
    """Outcome of dispatching a worker job."""

    job_id: str
    request_id: UUID


@runtime_checkable
class JobDispatcherPort(Protocol):
    """Hand off the validated envelope from receiver to worker.

    Implementations wrap Cloud Run Jobs (production) or in-memory queues
    (tests). The ``payload`` is the already-validated, re-serialized
    contract the worker should execute.
    """

    def dispatch(
        self, *, job_name: str, payload: bytes, request_id: UUID,
    ) -> DispatchedJob:
        """Enqueue the worker run; return a handle for log correlation."""
        ...
```

- [ ] **Step 6: Create ports package init**

`src/grabatus_service_core/ports/__init__.py`:
```python
"""Protocol definitions (Ports) for hexagonal collaborators."""

from grabatus_service_core.ports.clock import ClockPort
from grabatus_service_core.ports.job_dispatcher import (
    DispatchedJob,
    JobDispatcherPort,
)
from grabatus_service_core.ports.observability import ObservabilityPort

__all__ = [
    "ClockPort",
    "DispatchedJob",
    "JobDispatcherPort",
    "ObservabilityPort",
]
```

`tests/unit/ports/__init__.py`:
```
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/unit/ports/ -v`
Expected: All 6 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add src/grabatus_service_core/ports/ tests/unit/ports/
git commit -m "feat(ports): add ClockPort, ObservabilityPort, JobDispatcherPort"
```

---

### Task D2: Implement domain Ports (Storage, Message, Webhook, Compute, Secrets, UriAuthorization)

**Files:**
- Create: `src/grabatus_service_core/ports/storage.py`
- Create: `src/grabatus_service_core/ports/message.py`
- Create: `src/grabatus_service_core/ports/webhook.py`
- Create: `src/grabatus_service_core/ports/compute.py`
- Create: `src/grabatus_service_core/ports/secrets.py`
- Create: `src/grabatus_service_core/ports/authorization.py`
- Create: `src/grabatus_service_core/ports/values.py` (shared value objects: `Credentials`, `RawMessage`, `WriteReceipt`, `LoadedInputs`, `ComputeResult`, `WebhookAck`)
- Create: `tests/unit/ports/test_domain_ports.py`
- Modify: `src/grabatus_service_core/ports/__init__.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/ports/test_domain_ports.py`:
```python
"""Shape tests for domain Ports (Storage/Message/Webhook/Compute/Secrets/Auth)."""

from __future__ import annotations

from typing import Any

from grabatus_service_core.ports.authorization import UriAuthorizationPort
from grabatus_service_core.ports.compute import ComputeBackendPort
from grabatus_service_core.ports.message import MessagePort
from grabatus_service_core.ports.secrets import SecretsPort
from grabatus_service_core.ports.storage import StoragePort
from grabatus_service_core.ports.values import (
    ComputeResult,
    Credentials,
    LoadedInputs,
    RawMessage,
    WebhookAck,
    WriteReceipt,
)
from grabatus_service_core.ports.webhook import WebhookPort


class _OkStorage:
    def read(self, *, spec: Any, credentials: Credentials) -> bytes:
        return b""
    def write(
        self, *, spec: Any, payload: bytes, credentials: Credentials,
    ) -> WriteReceipt:
        return WriteReceipt(uri="gs://x/y", bytes_written=0, request_id_tag="r")


class _OkMessage:
    def decode(self, raw: RawMessage) -> dict[str, Any]:
        return {}
    def encode(self, envelope: dict[str, Any]) -> bytes:
        return b""


class _OkWebhook:
    def notify(self, *, callback: Any, payload: dict[str, Any]) -> WebhookAck:
        return WebhookAck(http_status=200, response_body="")


class _OkCompute:
    REQUIRED_INPUT_ROLES: frozenset[str] = frozenset({"timeseries"})
    OPTIONAL_INPUT_ROLES: frozenset[str] = frozenset()
    OUTPUT_ROLES: frozenset[str] = frozenset({"result"})

    def run(self, *, inputs: LoadedInputs, parameters: Any) -> ComputeResult:
        return ComputeResult(by_role={}, metadata={})


class _OkSecrets:
    def resolve(self, *, secret_ref: Any) -> Credentials:
        return Credentials(token=b"", token_type="bearer")


class _OkAuth:
    def authorize(self, *, uri: str, identity: Any) -> None:
        return None


def test_storage_port_accepts_full_implementation() -> None:
    assert isinstance(_OkStorage(), StoragePort)


def test_message_port_accepts_full_implementation() -> None:
    assert isinstance(_OkMessage(), MessagePort)


def test_webhook_port_accepts_full_implementation() -> None:
    assert isinstance(_OkWebhook(), WebhookPort)


def test_compute_port_accepts_full_implementation() -> None:
    assert isinstance(_OkCompute(), ComputeBackendPort)


def test_secrets_port_accepts_full_implementation() -> None:
    assert isinstance(_OkSecrets(), SecretsPort)


def test_uri_authorization_port_accepts_full_implementation() -> None:
    assert isinstance(_OkAuth(), UriAuthorizationPort)


def test_value_objects_are_frozen_dataclasses() -> None:
    receipt = WriteReceipt(uri="gs://x/y", bytes_written=10, request_id_tag="r1")
    ack = WebhookAck(http_status=200, response_body="ok")
    creds = Credentials(token=b"abc", token_type="bearer")
    inputs = LoadedInputs(by_role={"timeseries": b"abc"})
    result = ComputeResult(by_role={"out": b"def"}, metadata={"n": 1})
    raw = RawMessage(payload=b"x")

    for obj in (receipt, ack, creds, inputs, result, raw):
        with pytest.raises((AttributeError, TypeError)):  # type: ignore[name-defined]
            obj.__dict__["new_attr"] = "x"  # type: ignore[attr-defined]
```

(Add `import pytest` at the top of the test file.)

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/ports/test_domain_ports.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement shared value objects**

`src/grabatus_service_core/ports/values.py`:
```python
"""Value objects passed between Ports and the runner."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class RawMessage:
    """Raw bytes received from the message broker."""

    payload: bytes


@dataclass(frozen=True, slots=True)
class Credentials:
    """Resolved credential bytes plus its token type (bearer, hmac, etc.)."""

    token: bytes
    token_type: str


@dataclass(frozen=True, slots=True)
class WriteReceipt:
    """Outcome of writing a single output."""

    uri: str
    bytes_written: int
    request_id_tag: str


@dataclass(frozen=True, slots=True)
class LoadedInputs:
    """Bytes loaded for each input role."""

    by_role: Mapping[str, bytes]

    def __post_init__(self) -> None:
        # Freeze the mapping so it cannot be mutated after construction.
        object.__setattr__(self, "by_role", MappingProxyType(dict(self.by_role)))


@dataclass(frozen=True, slots=True)
class ComputeResult:
    """Bytes produced for each output role plus optional metadata."""

    by_role: Mapping[str, bytes]
    metadata: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "by_role", MappingProxyType(dict(self.by_role)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WebhookAck:
    """Result of notifying the webhook."""

    http_status: int
    response_body: str
```

- [ ] **Step 4: Implement `StoragePort`**

`src/grabatus_service_core/ports/storage.py`:
```python
"""StoragePort: abstract reads and writes against any URI scheme."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
from grabatus_service_core.ports.values import Credentials, WriteReceipt


@runtime_checkable
class StoragePort(Protocol):
    """Read input artifacts, write output artifacts.

    A single Port covers all schemes; concrete adapters (GCS, S3, BigQuery,
    LocalFs, Inline, HttpFetch) dispatch internally based on the URI.
    Adapters that don't support a scheme raise ``UnsupportedSchemeError``.
    """

    def read(self, *, spec: InputSpec, credentials: Credentials) -> bytes:
        """Return raw bytes from ``spec.source_uri``."""
        ...

    def write(
        self, *, spec: OutputSpec, payload: bytes, credentials: Credentials,
    ) -> WriteReceipt:
        """Persist ``payload`` to ``spec.destination_uri``; return receipt."""
        ...
```

- [ ] **Step 5: Implement `MessagePort`**

`src/grabatus_service_core/ports/message.py`:
```python
"""MessagePort: decode broker envelopes to raw dicts and back."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from grabatus_service_core.ports.values import RawMessage


@runtime_checkable
class MessagePort(Protocol):
    """Translate between broker wire format and Python dicts.

    The runner calls ``decode`` on incoming bytes, then hands the dict to
    ``BaseServiceContract.model_validate``. Adapters wrap Pub/Sub envelopes
    (base64 + JSON) or in-memory dicts (tests).
    """

    def decode(self, raw: RawMessage) -> dict[str, Any]:
        """Parse the broker envelope to a Python dict."""
        ...

    def encode(self, envelope: dict[str, Any]) -> bytes:
        """Serialize a Python dict back to broker wire format."""
        ...
```

- [ ] **Step 6: Implement `WebhookPort`**

`src/grabatus_service_core/ports/webhook.py`:
```python
"""WebhookPort: notify the platform of pipeline completion."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from grabatus_service_core.contract.callback import Callback
from grabatus_service_core.ports.values import WebhookAck


@runtime_checkable
class WebhookPort(Protocol):
    """Send a JWT-signed POST to the platform's webhook URL."""

    def notify(self, *, callback: Callback, payload: dict[str, Any]) -> WebhookAck:
        """POST ``payload`` to ``callback.url`` with a signed Authorization."""
        ...
```

- [ ] **Step 7: Implement `ComputeBackendPort`**

`src/grabatus_service_core/ports/compute.py`:
```python
"""ComputeBackendPort: the only Port a service implements directly."""

from __future__ import annotations

from typing import Any, ClassVar, Protocol, runtime_checkable

from grabatus_service_core.ports.values import ComputeResult, LoadedInputs


@runtime_checkable
class ComputeBackendPort(Protocol):
    """Service-specific compute logic.

    The library validates at contract time that every required role is
    present in ``inputs`` and that no unknown role appears in ``outputs``.
    Implementers declare these sets as ``ClassVar`` so the runner can
    inspect them without instantiating.
    """

    REQUIRED_INPUT_ROLES: ClassVar[frozenset[str]]
    OPTIONAL_INPUT_ROLES: ClassVar[frozenset[str]]
    OUTPUT_ROLES: ClassVar[frozenset[str]]

    def run(self, *, inputs: LoadedInputs, parameters: Any) -> ComputeResult:
        """Execute the service-specific computation."""
        ...
```

- [ ] **Step 8: Implement `SecretsPort`**

`src/grabatus_service_core/ports/secrets.py`:
```python
"""SecretsPort: resolve ``secret://`` URIs to credential bytes."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from grabatus_service_core.contract.secret_ref import SecretRef
from grabatus_service_core.ports.values import Credentials


@runtime_checkable
class SecretsPort(Protocol):
    """Look up a secret in the configured secret manager."""

    def resolve(self, *, secret_ref: SecretRef) -> Credentials:
        """Return the credential bytes referenced by ``secret_ref``."""
        ...
```

- [ ] **Step 9: Implement `UriAuthorizationPort`**

`src/grabatus_service_core/ports/authorization.py`:
```python
"""UriAuthorizationPort: enforce tenant-scoped URI access."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from grabatus_service_core.contract.identity import Identity


@runtime_checkable
class UriAuthorizationPort(Protocol):
    """Authorize that ``uri`` is allowed for ``identity``.

    Default implementation (`TenantPrefixPolicy`) requires bucket+prefix
    to match ``identity.tenant_id``. Implementations raise
    ``UnauthorizedUriError`` on denial; success returns ``None``.
    """

    def authorize(self, *, uri: str, identity: Identity) -> None:
        """Raise ``UnauthorizedUriError`` if ``identity`` may not access ``uri``."""
        ...
```

- [ ] **Step 10: Update `ports/__init__.py`**

```python
"""Protocol definitions (Ports) for hexagonal collaborators."""

from grabatus_service_core.ports.authorization import UriAuthorizationPort
from grabatus_service_core.ports.clock import ClockPort
from grabatus_service_core.ports.compute import ComputeBackendPort
from grabatus_service_core.ports.job_dispatcher import (
    DispatchedJob,
    JobDispatcherPort,
)
from grabatus_service_core.ports.message import MessagePort
from grabatus_service_core.ports.observability import ObservabilityPort
from grabatus_service_core.ports.secrets import SecretsPort
from grabatus_service_core.ports.storage import StoragePort
from grabatus_service_core.ports.values import (
    ComputeResult,
    Credentials,
    LoadedInputs,
    RawMessage,
    WebhookAck,
    WriteReceipt,
)
from grabatus_service_core.ports.webhook import WebhookPort

__all__ = [
    "ClockPort",
    "ComputeBackendPort",
    "ComputeResult",
    "Credentials",
    "DispatchedJob",
    "JobDispatcherPort",
    "LoadedInputs",
    "MessagePort",
    "ObservabilityPort",
    "RawMessage",
    "SecretsPort",
    "StoragePort",
    "UriAuthorizationPort",
    "WebhookAck",
    "WebhookPort",
    "WriteReceipt",
]
```

- [ ] **Step 11: Run all tests**

Run: `uv run pytest tests/unit/ports/ -v`
Expected: All tests PASS.

- [ ] **Step 12: Run coverage on ports**

Run: `uv run pytest tests/unit/ports/ --cov=grabatus_service_core.ports --cov-branch --cov-report=term-missing`
Expected: 100% coverage. Protocol method bodies (`...`) are excluded by `pyproject.toml` config.

- [ ] **Step 13: Commit**

```bash
git add src/grabatus_service_core/ports/ tests/unit/ports/
git commit -m "feat(ports): add domain Ports (Storage/Message/Webhook/Compute/Secrets/UriAuth) + value objects"
```

---

## Phase E — Security Primitives

Phase E adds the security building blocks that the runner (Sub-Plan 1B) wires up before any I/O. All primitives live under `src/grabatus_service_core/security/`. They are pure functions or small frozen classes — no network, no SDK imports.

The order matters: the safe URI parser (E1) is reused by the scheme allowlist (E2), the host blocklist (E3), and the tenant policy (E4). JWT helpers (E5) are independent. The `Credentials` value object already exists from D2.

### Task E1: Implement safe URI parser

**Files:**
- Create: `src/grabatus_service_core/security/__init__.py`
- Create: `src/grabatus_service_core/security/uri_parser.py`
- Create: `tests/unit/security/__init__.py`
- Create: `tests/unit/security/test_uri_parser.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/security/test_uri_parser.py`:
```python
"""Tests for the safe URI parser."""

from __future__ import annotations

import pytest

from grabatus_service_core.errors import UnsupportedSchemeError
from grabatus_service_core.security.uri_parser import ParsedUri, parse_uri


def test_parse_uri_extracts_scheme_host_path() -> None:
    parsed = parse_uri("gs://my-bucket/path/to/file.xlsx")

    assert parsed.scheme == "gs"
    assert parsed.host == "my-bucket"
    assert parsed.path == "/path/to/file.xlsx"


def test_parse_uri_lowercases_scheme() -> None:
    parsed = parse_uri("GS://Bucket/Path")

    assert parsed.scheme == "gs"


def test_parse_uri_preserves_path_case() -> None:
    parsed = parse_uri("gs://bucket/Path/To/File")

    assert parsed.path == "/Path/To/File"


def test_parse_uri_rejects_empty_string() -> None:
    with pytest.raises(UnsupportedSchemeError, match="empty"):
        parse_uri("")


def test_parse_uri_rejects_missing_scheme() -> None:
    with pytest.raises(UnsupportedSchemeError, match="scheme"):
        parse_uri("//bucket/path")


def test_parse_uri_rejects_path_traversal_in_path() -> None:
    with pytest.raises(UnsupportedSchemeError, match="traversal"):
        parse_uri("gs://bucket/safe/../../escape")


def test_parse_uri_rejects_double_slash_after_path() -> None:
    with pytest.raises(UnsupportedSchemeError, match="path"):
        parse_uri("gs://bucket//path")


def test_parsed_uri_is_frozen() -> None:
    parsed = parse_uri("gs://bucket/path")

    with pytest.raises((AttributeError, TypeError)):
        parsed.scheme = "s3"  # type: ignore[misc]


def test_parse_uri_handles_inline_scheme() -> None:
    parsed = parse_uri("inline://base64,SGVsbG8=")

    assert parsed.scheme == "inline"
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/security/test_uri_parser.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `uri_parser.py`**

`src/grabatus_service_core/security/uri_parser.py`:
```python
"""Safe URI parser used by every security primitive.

Rejects empty input, missing scheme, double-slash path components, and
any path containing ``..`` segments. All checks happen here so that the
allowlist, blocklist, and tenant policy can trust the parsed result.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from grabatus_service_core.errors import UnsupportedSchemeError


_TRAVERSAL_SEGMENT = ".."


@dataclass(frozen=True, slots=True)
class ParsedUri:
    """Normalized parts of a URI used by security primitives."""

    scheme: str
    host: str
    path: str


def parse_uri(uri: str) -> ParsedUri:
    """Parse and validate ``uri``; raise ``UnsupportedSchemeError`` on bad input."""
    if not uri:
        raise UnsupportedSchemeError(
            f"URI is empty, expected scheme://host/path, got uri={uri!r}",
        )
    parsed = urlparse(uri)
    if not parsed.scheme:
        raise UnsupportedSchemeError(
            f"URI is missing a scheme, got uri={uri!r}",
        )
    path = parsed.path
    if "//" in path:
        raise UnsupportedSchemeError(
            f"URI path contains '//', got uri={uri!r}",
        )
    segments = [seg for seg in path.split("/") if seg]
    if _TRAVERSAL_SEGMENT in segments:
        raise UnsupportedSchemeError(
            f"URI path contains '..' traversal segment, got uri={uri!r}",
        )
    return ParsedUri(
        scheme=parsed.scheme.lower(),
        host=parsed.netloc,
        path=path,
    )
```

- [ ] **Step 4: Create security package init**

`src/grabatus_service_core/security/__init__.py`:
```python
"""Security primitives: URI parsing, scheme allowlist, host blocklist, tenant policy, JWT."""

from grabatus_service_core.security.uri_parser import ParsedUri, parse_uri

__all__ = ["ParsedUri", "parse_uri"]
```

`tests/unit/security/__init__.py`:
```
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/security/test_uri_parser.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/security/ tests/unit/security/
git commit -m "feat(security): add safe URI parser with traversal and shape checks"
```

---

### Task E2: Implement `SchemeAllowlist`

**Files:**
- Create: `src/grabatus_service_core/security/scheme_allowlist.py`
- Create: `tests/unit/security/test_scheme_allowlist.py`
- Modify: `src/grabatus_service_core/security/__init__.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/security/test_scheme_allowlist.py`:
```python
"""Tests for SchemeAllowlist."""

from __future__ import annotations

import pytest

from grabatus_service_core.errors import UnsupportedSchemeError
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist


def test_allowlist_accepts_listed_scheme() -> None:
    allowlist = SchemeAllowlist(allowed={"gs", "bigquery"})

    allowlist.check("gs://bucket/path")  # no raise


def test_allowlist_rejects_unlisted_scheme() -> None:
    allowlist = SchemeAllowlist(allowed={"gs"})

    with pytest.raises(UnsupportedSchemeError, match="s3"):
        allowlist.check("s3://bucket/key")


def test_allowlist_normalizes_case() -> None:
    allowlist = SchemeAllowlist(allowed={"gs"})

    allowlist.check("GS://BUCKET/Path")


def test_allowlist_rejects_empty_uri() -> None:
    allowlist = SchemeAllowlist(allowed={"gs"})

    with pytest.raises(UnsupportedSchemeError):
        allowlist.check("")


def test_allowlist_from_env_string_parses_csv() -> None:
    allowlist = SchemeAllowlist.from_env_csv("gs,bigquery,secret")

    assert allowlist.allowed == frozenset({"gs", "bigquery", "secret"})


def test_allowlist_from_env_string_strips_whitespace() -> None:
    allowlist = SchemeAllowlist.from_env_csv("gs , bigquery , secret")

    assert allowlist.allowed == frozenset({"gs", "bigquery", "secret"})


def test_allowlist_from_env_string_lowercases() -> None:
    allowlist = SchemeAllowlist.from_env_csv("GS,BigQuery")

    assert allowlist.allowed == frozenset({"gs", "bigquery"})


def test_allowlist_from_env_empty_string_yields_empty_set() -> None:
    allowlist = SchemeAllowlist.from_env_csv("")

    assert allowlist.allowed == frozenset()
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/security/test_scheme_allowlist.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `SchemeAllowlist`**

`src/grabatus_service_core/security/scheme_allowlist.py`:
```python
"""SchemeAllowlist: enforces GBT_ALLOWED_SCHEMES at request boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Self

from grabatus_service_core.errors import UnsupportedSchemeError
from grabatus_service_core.security.uri_parser import parse_uri


@dataclass(frozen=True, slots=True)
class SchemeAllowlist:
    """Reject URIs whose scheme is not in ``allowed``.

    The allowlist is a closed set: the library default is narrow
    (gs, bigquery, secret) and configuration may only narrow it further.
    """

    allowed: frozenset[str]

    def __init__(self, allowed: Iterable[str]) -> None:
        object.__setattr__(self, "allowed", frozenset(s.lower() for s in allowed))

    def check(self, uri: str) -> None:
        parsed = parse_uri(uri)
        if parsed.scheme not in self.allowed:
            raise UnsupportedSchemeError(
                f"scheme={parsed.scheme!r} not in allowed schemes "
                f"{sorted(self.allowed)!r}, uri={uri!r}",
            )

    @classmethod
    def from_env_csv(cls, csv: str) -> Self:
        """Build an allowlist from a comma-separated env var value."""
        items = [piece.strip() for piece in csv.split(",") if piece.strip()]
        return cls(allowed=items)
```

- [ ] **Step 4: Update package init**

```python
"""Security primitives: URI parsing, scheme allowlist, host blocklist, tenant policy, JWT."""

from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.security.uri_parser import ParsedUri, parse_uri

__all__ = ["ParsedUri", "SchemeAllowlist", "parse_uri"]
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/security/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/security/ tests/unit/security/
git commit -m "feat(security): add SchemeAllowlist with env CSV factory"
```

---

### Task E3: Implement `HostBlocklist`

**Files:**
- Create: `src/grabatus_service_core/security/host_blocklist.py`
- Create: `tests/unit/security/test_host_blocklist.py`
- Modify: `src/grabatus_service_core/security/__init__.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/security/test_host_blocklist.py`:
```python
"""Tests for HostBlocklist."""

from __future__ import annotations

import pytest

from grabatus_service_core.errors import BlockedHostError
from grabatus_service_core.security.host_blocklist import HostBlocklist


def test_blocklist_allows_public_https_host() -> None:
    blocklist = HostBlocklist.production()

    blocklist.check("https://api.grabatus.com/webhook")  # no raise


@pytest.mark.parametrize(
    "uri",
    [
        "http://169.254.169.254/computeMetadata/v1/",
        "https://169.254.169.254/foo",
        "http://127.0.0.1:8080/x",
        "http://localhost/x",
        "http://10.0.0.5/x",
        "http://10.255.255.255/x",
        "http://example.internal/x",
        "http://services.local/x",
    ],
)
def test_blocklist_rejects_metadata_and_internal_hosts(uri: str) -> None:
    blocklist = HostBlocklist.production()

    with pytest.raises(BlockedHostError):
        blocklist.check(uri)


def test_blocklist_only_applies_to_http_schemes() -> None:
    blocklist = HostBlocklist.production()

    blocklist.check("gs://internal-bucket/path")  # no raise — not HTTP


def test_blocklist_allows_explicit_allowed_host() -> None:
    blocklist = HostBlocklist(
        allowed_hosts={"api.partner.com"},
    )

    blocklist.check("https://api.partner.com/x")


def test_blocklist_with_explicit_allowlist_rejects_others() -> None:
    blocklist = HostBlocklist(allowed_hosts={"api.partner.com"})

    with pytest.raises(BlockedHostError, match="api.other.com"):
        blocklist.check("https://api.other.com/x")


def test_blocklist_from_env_csv_parses_allowed_hosts() -> None:
    blocklist = HostBlocklist.from_env_csv("api.partner.com, api.grabatus.com")

    assert blocklist.allowed_hosts == frozenset(
        {"api.partner.com", "api.grabatus.com"},
    )


def test_blocklist_from_empty_env_uses_no_allowlist() -> None:
    blocklist = HostBlocklist.from_env_csv("")

    assert blocklist.allowed_hosts == frozenset()
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/security/test_host_blocklist.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `HostBlocklist`**

`src/grabatus_service_core/security/host_blocklist.py`:
```python
"""HostBlocklist: prevents SSRF and access to internal-only hosts."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Iterable, Self

from grabatus_service_core.errors import BlockedHostError
from grabatus_service_core.security.uri_parser import parse_uri


_HTTP_SCHEMES = frozenset({"http", "https"})
_BLOCKED_LITERAL_HOSTS = frozenset({"localhost"})
_BLOCKED_DOMAIN_SUFFIXES = (".internal", ".local")
_BLOCKED_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)


@dataclass(frozen=True, slots=True)
class HostBlocklist:
    """Reject HTTP URIs that point at metadata, loopback, RFC1918, or .internal hosts.

    When ``allowed_hosts`` is non-empty, it acts as an additional positive
    allowlist: only those hosts are accepted, regardless of blocklist
    matching. Non-HTTP schemes are not checked here — they go through
    other primitives.
    """

    allowed_hosts: frozenset[str]

    def __init__(self, allowed_hosts: Iterable[str] | None = None) -> None:
        items = frozenset(h.lower() for h in (allowed_hosts or ()))
        object.__setattr__(self, "allowed_hosts", items)

    @classmethod
    def production(cls) -> Self:
        """Default: blocklist active, no positive allowlist."""
        return cls()

    @classmethod
    def from_env_csv(cls, csv: str) -> Self:
        items = [piece.strip() for piece in csv.split(",") if piece.strip()]
        return cls(allowed_hosts=items)

    def check(self, uri: str) -> None:
        parsed = parse_uri(uri)
        if parsed.scheme not in _HTTP_SCHEMES:
            return
        host = self._extract_host(parsed.host)
        if self.allowed_hosts:
            if host not in self.allowed_hosts:
                raise BlockedHostError(
                    f"host={host!r} not in allowed_hosts "
                    f"{sorted(self.allowed_hosts)!r}, uri={uri!r}",
                )
            return
        self._raise_if_blocked(host=host, uri=uri)

    @staticmethod
    def _extract_host(netloc: str) -> str:
        return netloc.split(":", 1)[0].lower()

    @staticmethod
    def _raise_if_blocked(*, host: str, uri: str) -> None:
        if host in _BLOCKED_LITERAL_HOSTS:
            raise BlockedHostError(
                f"host={host!r} is in literal blocklist, uri={uri!r}",
            )
        if any(host.endswith(suffix) for suffix in _BLOCKED_DOMAIN_SUFFIXES):
            raise BlockedHostError(
                f"host={host!r} matches blocked suffix "
                f"{_BLOCKED_DOMAIN_SUFFIXES!r}, uri={uri!r}",
            )
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return
        for network in _BLOCKED_NETWORKS:
            if address in network:
                raise BlockedHostError(
                    f"host={host!r} resolves to blocked network "
                    f"{network!r}, uri={uri!r}",
                )
```

- [ ] **Step 4: Update package init**

```python
"""Security primitives: URI parsing, scheme allowlist, host blocklist, tenant policy, JWT."""

from grabatus_service_core.security.host_blocklist import HostBlocklist
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.security.uri_parser import ParsedUri, parse_uri

__all__ = [
    "HostBlocklist",
    "ParsedUri",
    "SchemeAllowlist",
    "parse_uri",
]
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/security/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/security/ tests/unit/security/
git commit -m "feat(security): add HostBlocklist preventing SSRF and internal-host access"
```

---

### Task E4: Implement `TenantPrefixPolicy`

**Files:**
- Create: `src/grabatus_service_core/security/tenant_prefix_policy.py`
- Create: `tests/unit/security/test_tenant_prefix_policy.py`
- Modify: `src/grabatus_service_core/security/__init__.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/security/test_tenant_prefix_policy.py`:
```python
"""Tests for TenantPrefixPolicy."""

from __future__ import annotations

import pytest

from grabatus_service_core.contract.identity import Identity
from grabatus_service_core.errors import UnauthorizedUriError
from grabatus_service_core.security.tenant_prefix_policy import TenantPrefixPolicy


def _identity(tenant: str = "grabatus", user: str = "999") -> Identity:
    return Identity.model_validate({"user_id": user, "tenant_id": tenant})


def test_policy_allows_uri_with_correct_tenant_prefix() -> None:
    policy = TenantPrefixPolicy(bucket_prefix="gbt-storage")

    policy.authorize(
        uri="gs://gbt-storage-grabatus/path/to/file.xlsx",
        identity=_identity(tenant="grabatus"),
    )


def test_policy_rejects_uri_for_different_tenant() -> None:
    policy = TenantPrefixPolicy(bucket_prefix="gbt-storage")

    with pytest.raises(UnauthorizedUriError, match="grabatus"):
        policy.authorize(
            uri="gs://gbt-storage-other-tenant/path/file.xlsx",
            identity=_identity(tenant="grabatus"),
        )


def test_policy_rejects_uri_with_unknown_bucket_prefix() -> None:
    policy = TenantPrefixPolicy(bucket_prefix="gbt-storage")

    with pytest.raises(UnauthorizedUriError, match="bucket"):
        policy.authorize(
            uri="gs://random-bucket/path/file.xlsx",
            identity=_identity(tenant="grabatus"),
        )


def test_policy_skips_secret_scheme() -> None:
    policy = TenantPrefixPolicy(bucket_prefix="gbt-storage")

    policy.authorize(
        uri="secret://gcp-secret-manager/bq-reader/1",
        identity=_identity(),
    )


def test_policy_skips_inline_scheme() -> None:
    policy = TenantPrefixPolicy(bucket_prefix="gbt-storage")

    policy.authorize(
        uri="inline://base64,SGVsbG8=",
        identity=_identity(),
    )


def test_policy_rejects_https_uri_when_no_explicit_allowance() -> None:
    policy = TenantPrefixPolicy(bucket_prefix="gbt-storage")

    with pytest.raises(UnauthorizedUriError, match="scheme"):
        policy.authorize(
            uri="https://api.partner.com/data",
            identity=_identity(),
        )


def test_policy_requires_user_path_segment_after_tenant_bucket() -> None:
    policy = TenantPrefixPolicy(
        bucket_prefix="gbt-storage", require_user_path_segment=True,
    )

    with pytest.raises(UnauthorizedUriError, match="user"):
        policy.authorize(
            uri="gs://gbt-storage-grabatus/global/file.xlsx",
            identity=_identity(user="999"),
        )

    policy.authorize(
        uri="gs://gbt-storage-grabatus/user_999/forecast/file.xlsx",
        identity=_identity(user="999"),
    )
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/security/test_tenant_prefix_policy.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `TenantPrefixPolicy`**

`src/grabatus_service_core/security/tenant_prefix_policy.py`:
```python
"""TenantPrefixPolicy: default URI authorization based on bucket+user prefix."""

from __future__ import annotations

from dataclasses import dataclass

from grabatus_service_core.contract.identity import Identity
from grabatus_service_core.errors import UnauthorizedUriError
from grabatus_service_core.security.uri_parser import parse_uri


_TENANT_AGNOSTIC_SCHEMES = frozenset({"secret", "inline"})
_BUCKET_SCHEMES = frozenset({"gs", "s3"})
_BIGQUERY_SCHEMES = frozenset({"bigquery"})


@dataclass(frozen=True, slots=True)
class TenantPrefixPolicy:
    """Default UriAuthorizationPort enforcing tenant + user prefixing.

    Bucket-style URIs (``gs://``, ``s3://``) must use a bucket whose name
    starts with ``<bucket_prefix>-<tenant_id>``. When ``require_user_path_segment``
    is True, the first path segment must equal ``user_<user_id>``.

    BigQuery URIs (``bigquery://project.dataset.table``) require the
    project segment to start with ``<bucket_prefix>-<tenant_id>``.

    ``secret://`` and ``inline://`` URIs are tenant-agnostic and pass.
    All other schemes are denied (HTTP allowed schemes are configured
    separately via ``HostBlocklist``).
    """

    bucket_prefix: str
    require_user_path_segment: bool = True

    def authorize(self, *, uri: str, identity: Identity) -> None:
        parsed = parse_uri(uri)
        scheme = parsed.scheme
        if scheme in _TENANT_AGNOSTIC_SCHEMES:
            return
        if scheme in _BUCKET_SCHEMES:
            self._check_bucket_uri(uri=uri, parsed_host=parsed.host,
                                   parsed_path=parsed.path, identity=identity)
            return
        if scheme in _BIGQUERY_SCHEMES:
            self._check_bigquery_uri(uri=uri, parsed_host=parsed.host,
                                     identity=identity)
            return
        raise UnauthorizedUriError(
            f"scheme={scheme!r} not authorized by TenantPrefixPolicy; "
            f"uri={uri!r}",
        )

    def _check_bucket_uri(
        self, *, uri: str, parsed_host: str, parsed_path: str, identity: Identity,
    ) -> None:
        expected_prefix = f"{self.bucket_prefix}-{identity.tenant_id}"
        if not parsed_host.startswith(expected_prefix):
            raise UnauthorizedUriError(
                f"bucket={parsed_host!r} does not start with "
                f"expected_prefix={expected_prefix!r} for tenant="
                f"{identity.tenant_id!r}; uri={uri!r}",
            )
        if self.require_user_path_segment:
            self._check_user_segment(
                path=parsed_path, user_id=identity.user_id, uri=uri,
            )

    def _check_bigquery_uri(
        self, *, uri: str, parsed_host: str, identity: Identity,
    ) -> None:
        expected_prefix = f"{self.bucket_prefix}-{identity.tenant_id}"
        project = parsed_host.split(".", 1)[0]
        if not project.startswith(expected_prefix):
            raise UnauthorizedUriError(
                f"bigquery project={project!r} does not start with "
                f"expected_prefix={expected_prefix!r}; uri={uri!r}",
            )

    @staticmethod
    def _check_user_segment(*, path: str, user_id: str, uri: str) -> None:
        segments = [seg for seg in path.split("/") if seg]
        expected_segment = f"user_{user_id}"
        if not segments or segments[0] != expected_segment:
            raise UnauthorizedUriError(
                f"path must start with user segment={expected_segment!r}, "
                f"got first_segment={segments[0] if segments else None!r}; "
                f"uri={uri!r}",
            )
```

- [ ] **Step 4: Update package init**

```python
"""Security primitives: URI parsing, scheme allowlist, host blocklist, tenant policy, JWT."""

from grabatus_service_core.security.host_blocklist import HostBlocklist
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.security.tenant_prefix_policy import TenantPrefixPolicy
from grabatus_service_core.security.uri_parser import ParsedUri, parse_uri

__all__ = [
    "HostBlocklist",
    "ParsedUri",
    "SchemeAllowlist",
    "TenantPrefixPolicy",
    "parse_uri",
]
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/security/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/security/ tests/unit/security/
git commit -m "feat(security): add TenantPrefixPolicy enforcing bucket+user prefix authorization"
```

---

### Task E5: Implement JWT helpers (encode/decode)

**Files:**
- Create: `src/grabatus_service_core/security/jwt_helpers.py`
- Create: `tests/unit/security/test_jwt_helpers.py`
- Modify: `src/grabatus_service_core/security/__init__.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/security/test_jwt_helpers.py`:
```python
"""Tests for JWT helpers."""

from __future__ import annotations

import time

import pytest

from grabatus_service_core.errors import WebhookAuthError
from grabatus_service_core.security.jwt_helpers import decode_hs256, encode_hs256


_KEY = b"test-secret-key-at-least-32-bytes-long-padding"


def test_encode_then_decode_round_trip() -> None:
    payload = {"request_id": "abc", "iat": int(time.time())}

    token = encode_hs256(payload=payload, secret=_KEY)
    decoded = decode_hs256(token=token, secret=_KEY)

    assert decoded["request_id"] == "abc"


def test_decode_rejects_token_signed_with_wrong_key() -> None:
    payload = {"request_id": "abc"}
    token = encode_hs256(payload=payload, secret=_KEY)

    with pytest.raises(WebhookAuthError, match="signature"):
        decode_hs256(token=token, secret=b"wrong-secret-key-padding-padding")


def test_decode_rejects_malformed_token() -> None:
    with pytest.raises(WebhookAuthError, match="malformed"):
        decode_hs256(token="not.a.token", secret=_KEY)


def test_decode_rejects_empty_token() -> None:
    with pytest.raises(WebhookAuthError, match="empty"):
        decode_hs256(token="", secret=_KEY)


def test_encode_rejects_short_secret() -> None:
    with pytest.raises(ValueError, match="secret"):
        encode_hs256(payload={"x": 1}, secret=b"short")


def test_encode_includes_alg_hs256_header() -> None:
    token = encode_hs256(payload={"x": 1}, secret=_KEY)
    header_segment = token.split(".")[0]

    import base64
    import json
    header_padded = header_segment + "=" * (-len(header_segment) % 4)
    decoded_header = json.loads(base64.urlsafe_b64decode(header_padded))

    assert decoded_header["alg"] == "HS256"
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/security/test_jwt_helpers.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `jwt_helpers.py`**

`src/grabatus_service_core/security/jwt_helpers.py`:
```python
"""JWT HS256 encode/decode helpers wrapping PyJWT.

Domain-side wrappers exist so the service runner never imports ``jwt``
directly; the wrappers translate PyJWT exceptions into our own
``WebhookAuthError`` with informative messages.
"""

from __future__ import annotations

from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError

from grabatus_service_core.errors import WebhookAuthError


_ALGORITHM = "HS256"
_MIN_SECRET_BYTES = 32


def encode_hs256(*, payload: dict[str, Any], secret: bytes) -> str:
    """Sign ``payload`` with HS256 and return a compact JWT string."""
    if len(secret) < _MIN_SECRET_BYTES:
        raise ValueError(
            f"HS256 secret must be at least {_MIN_SECRET_BYTES} bytes, "
            f"got len={len(secret)}",
        )
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_hs256(*, token: str, secret: bytes) -> dict[str, Any]:
    """Verify the HS256 signature and return the decoded payload."""
    if not token:
        raise WebhookAuthError(
            f"JWT token is empty, expected header.payload.signature; got token={token!r}",
        )
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except InvalidTokenError as exc:
        message = str(exc) or type(exc).__name__
        if "signature" in message.lower():
            raise WebhookAuthError(
                f"JWT signature verification failed: {message}",
            ) from exc
        raise WebhookAuthError(
            f"JWT token is malformed: {message}",
        ) from exc
    return dict(payload)
```

- [ ] **Step 4: Update package init**

```python
"""Security primitives: URI parsing, scheme allowlist, host blocklist, tenant policy, JWT."""

from grabatus_service_core.security.host_blocklist import HostBlocklist
from grabatus_service_core.security.jwt_helpers import decode_hs256, encode_hs256
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.security.tenant_prefix_policy import TenantPrefixPolicy
from grabatus_service_core.security.uri_parser import ParsedUri, parse_uri

__all__ = [
    "HostBlocklist",
    "ParsedUri",
    "SchemeAllowlist",
    "TenantPrefixPolicy",
    "decode_hs256",
    "encode_hs256",
    "parse_uri",
]
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/security/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/security/ tests/unit/security/
git commit -m "feat(security): add JWT HS256 encode/decode helpers wrapping PyJWT"
```

---

### Task E6: Run full coverage check on Phase E

**Files:** none modified.

- [ ] **Step 1: Run coverage on the security module**

Run: `uv run pytest tests/unit/security/ --cov=grabatus_service_core.security --cov-branch --cov-report=term-missing`
Expected: 100% line + branch coverage on every file under `security/`.

- [ ] **Step 2: Run full library coverage to confirm we are at 100% so far**

Run: `uv run pytest`
Expected: PASS, `--cov-fail-under=100` not violated.

- [ ] **Step 3: If any line is uncovered, add the missing test**

Identify the uncovered line(s) from `term-missing`. Add a focused test in the appropriate `tests/unit/security/test_*.py` to cover it. Re-run until 100%.

- [ ] **Step 4: No commit needed if no changes; otherwise**

```bash
git add tests/unit/security/
git commit -m "test(security): top up coverage to 100% line + branch"
```

---

## Phase F — Domain Test Fakes (`grabatus_service_core.testing`)

Phase F creates the public testing API that every downstream service will import. Each fake implements one of the Ports from Phase D, with a real (in-memory) behavior that is appropriate for fast unit tests. The package also ships factories that produce valid `BaseServiceContract[…]` instances with sensible defaults.

The Phase F tests verify two things: (1) each fake satisfies the `isinstance(fake, Port)` shape check, and (2) each fake has the documented behavior (e.g. `InMemoryStorage` round-trips bytes by URI, `RecordingWebhookNotifier` records every notify call).

### Task F1: Implement all fakes and the factories module

**Files:**
- Create: `src/grabatus_service_core/testing/__init__.py`
- Create: `src/grabatus_service_core/testing/clock.py`
- Create: `src/grabatus_service_core/testing/observability.py`
- Create: `src/grabatus_service_core/testing/storage.py`
- Create: `src/grabatus_service_core/testing/message.py`
- Create: `src/grabatus_service_core/testing/webhook.py`
- Create: `src/grabatus_service_core/testing/compute.py`
- Create: `src/grabatus_service_core/testing/secrets.py`
- Create: `src/grabatus_service_core/testing/authorization.py`
- Create: `src/grabatus_service_core/testing/job_dispatcher.py`
- Create: `src/grabatus_service_core/testing/factories.py`
- Create: `tests/unit/testing/__init__.py`
- Create: `tests/unit/testing/test_fakes_satisfy_ports.py`
- Create: `tests/unit/testing/test_fake_behavior.py`
- Create: `tests/unit/testing/test_factories.py`

This task is large but cohesive — every fake is a small (<60 LOC) class. We build it in five rounds: (1) fakes for infrastructure ports, (2) fakes for storage/message/webhook, (3) fakes for compute/secrets/authorization/dispatcher, (4) factories, (5) integration tests across all fakes.

- [ ] **Step 1: Write the shape test (verifies every fake satisfies its Port)**

`tests/unit/testing/test_fakes_satisfy_ports.py`:
```python
"""Each fake must satisfy its corresponding Port via isinstance."""

from __future__ import annotations

from grabatus_service_core.ports import (
    ClockPort,
    ComputeBackendPort,
    JobDispatcherPort,
    MessagePort,
    ObservabilityPort,
    SecretsPort,
    StoragePort,
    UriAuthorizationPort,
    WebhookPort,
)
from grabatus_service_core.testing import (
    AllowAllPolicy,
    FakeComputeBackend,
    FrozenClock,
    InMemoryJobDispatcher,
    InMemoryMessagePort,
    InMemorySecretsAdapter,
    InMemoryStorage,
    NullObservability,
    RecordingWebhookNotifier,
)


def test_frozen_clock_is_clock_port() -> None:
    assert isinstance(FrozenClock("2026-04-25T12:00:00Z"), ClockPort)


def test_null_observability_is_observability_port() -> None:
    assert isinstance(NullObservability(), ObservabilityPort)


def test_in_memory_job_dispatcher_is_job_dispatcher_port() -> None:
    assert isinstance(InMemoryJobDispatcher(), JobDispatcherPort)


def test_in_memory_storage_is_storage_port() -> None:
    assert isinstance(InMemoryStorage(), StoragePort)


def test_in_memory_message_port_is_message_port() -> None:
    assert isinstance(InMemoryMessagePort(), MessagePort)


def test_recording_webhook_notifier_is_webhook_port() -> None:
    assert isinstance(RecordingWebhookNotifier(), WebhookPort)


def test_fake_compute_backend_is_compute_backend_port() -> None:
    backend = FakeComputeBackend(
        required_input_roles=frozenset({"timeseries"}),
        optional_input_roles=frozenset(),
        output_roles=frozenset({"result"}),
        outputs={"result": b"x"},
    )
    assert isinstance(backend, ComputeBackendPort)


def test_in_memory_secrets_adapter_is_secrets_port() -> None:
    assert isinstance(InMemorySecretsAdapter(), SecretsPort)


def test_allow_all_policy_is_uri_authorization_port() -> None:
    assert isinstance(AllowAllPolicy(), UriAuthorizationPort)
```

- [ ] **Step 2: Write the behavior tests**

`tests/unit/testing/test_fake_behavior.py`:
```python
"""Behavior tests: each fake delivers what its docstring promises."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from grabatus_service_core.contract.callback import Callback
from grabatus_service_core.contract.identity import Identity
from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
from grabatus_service_core.contract.secret_ref import SecretRef
from grabatus_service_core.errors import (
    InputNotFoundError,
    UnsupportedSchemeError,
)
from grabatus_service_core.ports.values import (
    Credentials,
    LoadedInputs,
    RawMessage,
)
from grabatus_service_core.testing import (
    AllowAllPolicy,
    FakeComputeBackend,
    FrozenClock,
    InMemoryJobDispatcher,
    InMemoryMessagePort,
    InMemorySecretsAdapter,
    InMemoryStorage,
    NullObservability,
    RecordingWebhookNotifier,
)


def _input(role: str = "timeseries", uri: str = "gs://b/in.xlsx") -> InputSpec:
    return InputSpec.model_validate(
        {
            "role": role,
            "source_uri": uri,
            "format": "xlsx",
            "format_hints": {"format": "xlsx"},
        },
    )


def _output(role: str = "result", uri: str = "gs://b/out.json") -> OutputSpec:
    return OutputSpec.model_validate(
        {
            "role": role,
            "destination_uri": uri,
            "format": "json",
            "format_hints": {"format": "json"},
        },
    )


def _empty_creds() -> Credentials:
    return Credentials(token=b"", token_type="bearer")


def test_frozen_clock_returns_configured_time() -> None:
    clock = FrozenClock("2026-04-25T12:00:00Z")

    assert clock.now() == datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC)
    assert clock.monotonic() == 0.0


def test_frozen_clock_advance_changes_now_and_monotonic() -> None:
    clock = FrozenClock("2026-04-25T12:00:00Z")

    clock.advance(seconds=30)

    assert clock.now() == datetime(2026, 4, 25, 12, 0, 30, tzinfo=UTC)
    assert clock.monotonic() == 30.0


def test_null_observability_records_nothing_but_is_callable() -> None:
    obs = NullObservability()

    obs.log("event", x=1)
    obs.metric("m", 1.0, tag="v")
    with obs.span("span", attr="v") as span:
        assert span is None


def test_in_memory_storage_round_trips_bytes() -> None:
    storage = InMemoryStorage()
    receipt = storage.write(
        spec=_output(role="result", uri="gs://b/out.json"),
        payload=b"hello",
        credentials=_empty_creds(),
    )

    data = storage.read(
        spec=_input(role="result", uri="gs://b/out.json"),
        credentials=_empty_creds(),
    )

    assert receipt.bytes_written == 5
    assert data == b"hello"


def test_in_memory_storage_raises_for_missing_uri() -> None:
    storage = InMemoryStorage()

    with pytest.raises(InputNotFoundError, match="gs://b/missing"):
        storage.read(
            spec=_input(uri="gs://b/missing"),
            credentials=_empty_creds(),
        )


def test_in_memory_storage_can_be_seeded_via_constructor() -> None:
    storage = InMemoryStorage(seed={"gs://b/in.xlsx": b"seeded"})

    data = storage.read(spec=_input(uri="gs://b/in.xlsx"), credentials=_empty_creds())

    assert data == b"seeded"


def test_in_memory_message_port_round_trips_dict() -> None:
    port = InMemoryMessagePort()
    payload = {"k": "v", "n": 1}

    encoded = port.encode(payload)
    decoded = port.decode(RawMessage(payload=encoded))

    assert decoded == payload


def test_recording_webhook_notifier_records_every_call() -> None:
    notifier = RecordingWebhookNotifier()
    callback = Callback.model_validate(
        {"url": "https://x.com/wh", "auth_scheme": "jwt_hs256"},
    )

    ack1 = notifier.notify(callback=callback, payload={"a": 1})
    ack2 = notifier.notify(callback=callback, payload={"b": 2})

    assert ack1.http_status == 200
    assert ack2.http_status == 200
    assert len(notifier.calls) == 2
    assert notifier.calls[0].payload == {"a": 1}
    assert notifier.calls[1].payload == {"b": 2}


def test_recording_webhook_notifier_can_be_configured_to_fail() -> None:
    notifier = RecordingWebhookNotifier(default_status=503)
    callback = Callback.model_validate(
        {"url": "https://x.com/wh", "auth_scheme": "jwt_hs256"},
    )

    ack = notifier.notify(callback=callback, payload={})

    assert ack.http_status == 503


def test_fake_compute_backend_returns_configured_outputs() -> None:
    backend = FakeComputeBackend(
        required_input_roles=frozenset({"timeseries"}),
        optional_input_roles=frozenset(),
        output_roles=frozenset({"result_json"}),
        outputs={"result_json": b"forecast-bytes"},
        metadata={"version": "1.0"},
    )

    result = backend.run(
        inputs=LoadedInputs(by_role={"timeseries": b"data"}),
        parameters=None,
    )

    assert result.by_role["result_json"] == b"forecast-bytes"
    assert result.metadata["version"] == "1.0"


def test_in_memory_secrets_adapter_resolves_seeded_token() -> None:
    adapter = InMemorySecretsAdapter(
        seed={
            "secret://gsm/bq-reader/1": Credentials(
                token=b"abc123", token_type="bearer",
            ),
        },
    )

    creds = adapter.resolve(
        secret_ref=SecretRef.model_validate("secret://gsm/bq-reader/1"),
    )

    assert creds.token == b"abc123"


def test_in_memory_secrets_adapter_raises_for_unknown_ref() -> None:
    adapter = InMemorySecretsAdapter()

    with pytest.raises(Exception, match="secret"):  # CredentialResolutionError
        adapter.resolve(secret_ref=SecretRef.model_validate("secret://gsm/missing/1"))


def test_allow_all_policy_authorizes_anything() -> None:
    policy = AllowAllPolicy()

    policy.authorize(
        uri="gs://anything/anywhere",
        identity=Identity.model_validate({"user_id": "1", "tenant_id": "grabatus"}),
    )


def test_in_memory_job_dispatcher_records_dispatched_jobs() -> None:
    dispatcher = InMemoryJobDispatcher()
    rid = UUID("a3f9c21e-bf38-4e75-9a2f-c89b6c3f2d12")

    job = dispatcher.dispatch(job_name="worker-job", payload=b"x", request_id=rid)

    assert job.job_id.startswith("in-memory-")
    assert job.request_id == rid
    assert len(dispatcher.dispatched) == 1
    assert dispatcher.dispatched[0].payload == b"x"


def test_in_memory_storage_rejects_unsupported_scheme() -> None:
    storage = InMemoryStorage(supported_schemes=frozenset({"gs"}))

    with pytest.raises(UnsupportedSchemeError):
        storage.write(
            spec=_output(role="r", uri="ftp://b/x"),
            payload=b"x",
            credentials=_empty_creds(),
        )
```

- [ ] **Step 3: Write the factories test**

`tests/unit/testing/test_factories.py`:
```python
"""Tests for the contract factories used by service tests."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from grabatus_service_core.contract import BaseServiceContract
from grabatus_service_core.testing import (
    make_callback,
    make_contract,
    make_envelope,
    make_identity,
    make_input_spec,
    make_output_spec,
    make_references,
    make_service_descriptor,
)


class _SampleParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    period: int = 30
    mode: Literal["fast", "slow"] = "fast"


def test_make_envelope_returns_valid_envelope() -> None:
    env = make_envelope()

    assert env.protocol_version == "1.0"
    assert isinstance(env.request_id, UUID)


def test_make_envelope_overrides_request_id() -> None:
    rid = UUID("a3f9c21e-bf38-4e75-9a2f-c89b6c3f2d12")

    env = make_envelope(request_id=rid)

    assert env.request_id == rid


def test_make_identity_default() -> None:
    identity = make_identity()

    assert identity.tenant_id == "grabatus"


def test_make_input_spec_default() -> None:
    spec = make_input_spec()

    assert spec.role == "timeseries"
    assert spec.format == "xlsx"


def test_make_output_spec_default() -> None:
    spec = make_output_spec()

    assert spec.role == "result_json"
    assert spec.format == "json"


def test_make_references_default() -> None:
    refs = make_references()

    assert refs.parameter_id and refs.result_id


def test_make_service_descriptor_default() -> None:
    desc = make_service_descriptor()

    assert desc.name == "sample"


def test_make_callback_default_is_https() -> None:
    cb = make_callback()

    assert str(cb.url).startswith("https://")


def test_make_contract_default_is_valid() -> None:
    contract = make_contract(parameters=_SampleParameters())

    assert isinstance(contract, BaseServiceContract)
    assert len(contract.inputs) == 1
    assert len(contract.outputs) == 1


def test_make_contract_accepts_overrides() -> None:
    contract = make_contract(
        parameters=_SampleParameters(period=180, mode="slow"),
        identity=make_identity(tenant_id="other"),
    )

    assert contract.parameters.period == 180
    assert contract.identity.tenant_id == "other"
```

- [ ] **Step 4: Run tests to verify all fail**

Run: `uv run pytest tests/unit/testing/ -v`
Expected: FAIL — `grabatus_service_core.testing` not yet a package.

- [ ] **Step 5: Implement `FrozenClock`**

`src/grabatus_service_core/testing/clock.py`:
```python
"""FrozenClock: deterministic clock for tests."""

from __future__ import annotations

from datetime import datetime, timedelta


class FrozenClock:
    """Clock fixed at a configurable instant; ``advance`` mutates state."""

    def __init__(self, iso_string: str) -> None:
        self._now = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        self._monotonic = 0.0

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._monotonic

    def advance(self, *, seconds: float) -> None:
        self._now = self._now + timedelta(seconds=seconds)
        self._monotonic = self._monotonic + seconds
```

- [ ] **Step 6: Implement `NullObservability`**

`src/grabatus_service_core/testing/observability.py`:
```python
"""NullObservability: no-op implementation for tests."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator


class NullObservability:
    """Records nothing; satisfies ObservabilityPort for tests."""

    def log(self, event: str, **fields: Any) -> None:
        return None

    @contextmanager
    def span(self, name: str, **attrs: Any) -> Iterator[None]:
        yield None

    def metric(self, name: str, value: float, **tags: Any) -> None:
        return None
```

- [ ] **Step 7: Implement `InMemoryStorage`**

`src/grabatus_service_core/testing/storage.py`:
```python
"""InMemoryStorage: dict-backed storage for tests."""

from __future__ import annotations

from typing import Iterable, Mapping

from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
from grabatus_service_core.errors import (
    InputNotFoundError,
    UnsupportedSchemeError,
)
from grabatus_service_core.ports.values import Credentials, WriteReceipt


_DEFAULT_SUPPORTED_SCHEMES = frozenset({"gs", "s3", "file", "inline", "http", "https"})


class InMemoryStorage:
    """Round-trips bytes by URI in a private dict.

    Optionally constrained to a set of supported URI schemes; rejects
    others with ``UnsupportedSchemeError`` to mimic real adapter behavior.
    """

    def __init__(
        self,
        seed: Mapping[str, bytes] | None = None,
        *,
        supported_schemes: Iterable[str] | None = None,
    ) -> None:
        self._objects: dict[str, bytes] = dict(seed or {})
        self._supported_schemes = frozenset(
            supported_schemes if supported_schemes is not None else _DEFAULT_SUPPORTED_SCHEMES,
        )

    def read(self, *, spec: InputSpec, credentials: Credentials) -> bytes:
        del credentials  # accepted but ignored in fake
        uri = str(spec.source_uri)
        self._check_scheme(uri)
        if uri not in self._objects:
            raise InputNotFoundError(
                f"in-memory storage has no object at uri={uri!r}",
            )
        return self._objects[uri]

    def write(
        self, *, spec: OutputSpec, payload: bytes, credentials: Credentials,
    ) -> WriteReceipt:
        del credentials
        uri = str(spec.destination_uri)
        self._check_scheme(uri)
        self._objects[uri] = payload
        return WriteReceipt(
            uri=uri,
            bytes_written=len(payload),
            request_id_tag="in-memory",
        )

    def _check_scheme(self, uri: str) -> None:
        scheme = uri.split("://", 1)[0].lower()
        if scheme not in self._supported_schemes:
            raise UnsupportedSchemeError(
                f"InMemoryStorage does not support scheme={scheme!r}; "
                f"supported={sorted(self._supported_schemes)!r}; uri={uri!r}",
            )
```

- [ ] **Step 8: Implement `InMemoryMessagePort`**

`src/grabatus_service_core/testing/message.py`:
```python
"""InMemoryMessagePort: JSON-encoded round-trip without Pub/Sub envelope."""

from __future__ import annotations

import json
from typing import Any

from grabatus_service_core.ports.values import RawMessage


class InMemoryMessagePort:
    """Encode/decode dicts as raw UTF-8 JSON bytes — no Pub/Sub envelope."""

    def decode(self, raw: RawMessage) -> dict[str, Any]:
        decoded = json.loads(raw.payload.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError(
                f"InMemoryMessagePort.decode expected dict, got type="
                f"{type(decoded).__name__}",
            )
        return decoded

    def encode(self, envelope: dict[str, Any]) -> bytes:
        return json.dumps(envelope).encode("utf-8")
```

- [ ] **Step 9: Implement `RecordingWebhookNotifier`**

`src/grabatus_service_core/testing/webhook.py`:
```python
"""RecordingWebhookNotifier: records every notify call for inspection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from grabatus_service_core.contract.callback import Callback
from grabatus_service_core.ports.values import WebhookAck


@dataclass(frozen=True, slots=True)
class RecordedWebhookCall:
    callback: Callback
    payload: dict[str, Any]


@dataclass
class RecordingWebhookNotifier:
    """Captures every webhook call to ``calls`` for assertions."""

    default_status: int = 200
    default_body: str = "ok"
    calls: list[RecordedWebhookCall] = field(default_factory=list)

    def notify(
        self, *, callback: Callback, payload: dict[str, Any],
    ) -> WebhookAck:
        self.calls.append(RecordedWebhookCall(callback=callback, payload=dict(payload)))
        return WebhookAck(
            http_status=self.default_status, response_body=self.default_body,
        )
```

- [ ] **Step 10: Implement `FakeComputeBackend`**

`src/grabatus_service_core/testing/compute.py`:
```python
"""FakeComputeBackend: returns predefined output bytes."""

from __future__ import annotations

from typing import Any, ClassVar, Mapping

from grabatus_service_core.ports.values import ComputeResult, LoadedInputs


class FakeComputeBackend:
    """Test double for ComputeBackendPort with declarative outputs."""

    REQUIRED_INPUT_ROLES: ClassVar[frozenset[str]] = frozenset()
    OPTIONAL_INPUT_ROLES: ClassVar[frozenset[str]] = frozenset()
    OUTPUT_ROLES: ClassVar[frozenset[str]] = frozenset()

    def __init__(
        self,
        *,
        required_input_roles: frozenset[str],
        optional_input_roles: frozenset[str],
        output_roles: frozenset[str],
        outputs: Mapping[str, bytes],
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        # Per-instance class-level vars are valid via __class__.__setattr__
        type(self).REQUIRED_INPUT_ROLES = required_input_roles
        type(self).OPTIONAL_INPUT_ROLES = optional_input_roles
        type(self).OUTPUT_ROLES = output_roles
        self._outputs = dict(outputs)
        self._metadata = dict(metadata or {})

    def run(self, *, inputs: LoadedInputs, parameters: Any) -> ComputeResult:
        del inputs, parameters
        return ComputeResult(by_role=self._outputs, metadata=self._metadata)
```

> NOTE: mutating class attributes per instance is acceptable for a test fake; production `ComputeBackendPort` implementers declare class-level frozensets directly.

- [ ] **Step 11: Implement `InMemorySecretsAdapter`**

`src/grabatus_service_core/testing/secrets.py`:
```python
"""InMemorySecretsAdapter: dict-backed SecretsPort for tests."""

from __future__ import annotations

from typing import Mapping

from grabatus_service_core.contract.secret_ref import SecretRef
from grabatus_service_core.errors import CredentialResolutionError
from grabatus_service_core.ports.values import Credentials


class InMemorySecretsAdapter:
    """Resolves SecretRef → Credentials by URI lookup in a private dict."""

    def __init__(self, seed: Mapping[str, Credentials] | None = None) -> None:
        self._secrets: dict[str, Credentials] = dict(seed or {})

    def resolve(self, *, secret_ref: SecretRef) -> Credentials:
        uri = secret_ref.to_uri()
        if uri not in self._secrets:
            raise CredentialResolutionError(
                f"in-memory secrets adapter has no entry for secret_ref={uri!r}",
            )
        return self._secrets[uri]
```

- [ ] **Step 12: Implement `AllowAllPolicy`**

`src/grabatus_service_core/testing/authorization.py`:
```python
"""AllowAllPolicy: authorizes every URI; only for tests."""

from __future__ import annotations

from grabatus_service_core.contract.identity import Identity


class AllowAllPolicy:
    """No-op UriAuthorizationPort that authorizes any URI for any identity."""

    def authorize(self, *, uri: str, identity: Identity) -> None:
        del uri, identity
        return None
```

- [ ] **Step 13: Implement `InMemoryJobDispatcher`**

`src/grabatus_service_core/testing/job_dispatcher.py`:
```python
"""InMemoryJobDispatcher: records dispatched jobs without enqueuing real work."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from uuid import UUID

from grabatus_service_core.ports.job_dispatcher import DispatchedJob


@dataclass(frozen=True, slots=True)
class RecordedDispatch:
    job_name: str
    payload: bytes
    request_id: UUID


@dataclass
class InMemoryJobDispatcher:
    """Records every dispatch call; assigns sequential job IDs."""

    dispatched: list[RecordedDispatch] = field(default_factory=list)
    _counter: count[int] = field(default_factory=lambda: count(1))

    def dispatch(
        self, *, job_name: str, payload: bytes, request_id: UUID,
    ) -> DispatchedJob:
        self.dispatched.append(
            RecordedDispatch(
                job_name=job_name, payload=payload, request_id=request_id,
            ),
        )
        seq = next(self._counter)
        return DispatchedJob(job_id=f"in-memory-{seq:04d}", request_id=request_id)
```

- [ ] **Step 14: Implement `factories.py`**

`src/grabatus_service_core/testing/factories.py`:
```python
"""Factories for valid contract instances; reduce boilerplate in service tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel

from grabatus_service_core.contract import (
    BaseServiceContract,
    Callback,
    Envelope,
    Identity,
    InputSpec,
    OutputSpec,
    References,
    ServiceDescriptor,
)


_DEFAULT_REQUEST_ID = UUID("a3f9c21e-bf38-4e75-9a2f-c89b6c3f2d12")
_DEFAULT_CREATED_AT = datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC)

ParamsT = TypeVar("ParamsT", bound=BaseModel)


def make_envelope(
    *,
    request_id: UUID | None = None,
    created_at: datetime | None = None,
    origin: str = "web",
    protocol_version: str = "1.0",
) -> Envelope:
    return Envelope.model_validate(
        {
            "protocol_version": protocol_version,
            "request_id": str(request_id or _DEFAULT_REQUEST_ID),
            "created_at": (created_at or _DEFAULT_CREATED_AT).isoformat(),
            "origin": origin,
        },
    )


def make_identity(*, user_id: str = "999", tenant_id: str = "grabatus") -> Identity:
    return Identity.model_validate({"user_id": user_id, "tenant_id": tenant_id})


def make_references(
    *, parameter_id: str = "p-1", result_id: str = "r-1",
) -> References:
    return References.model_validate(
        {"parameter_id": parameter_id, "result_id": result_id},
    )


def make_service_descriptor(
    *, name: str = "sample", version: str = "1.0.0",
) -> ServiceDescriptor:
    return ServiceDescriptor.model_validate({"name": name, "version": version})


def make_input_spec(
    *,
    role: str = "timeseries",
    source_uri: str = "gs://gbt-storage-grabatus/user_999/in.xlsx",
    fmt: str = "xlsx",
    hints: dict[str, Any] | None = None,
) -> InputSpec:
    payload: dict[str, Any] = {
        "role": role,
        "source_uri": source_uri,
        "format": fmt,
        "format_hints": hints or {"format": fmt, "sheet": "Dados"},
    }
    return InputSpec.model_validate(payload)


def make_output_spec(
    *,
    role: str = "result_json",
    destination_uri: str = "gs://gbt-storage-grabatus/user_999/out.json",
    fmt: str = "json",
    hints: dict[str, Any] | None = None,
) -> OutputSpec:
    payload: dict[str, Any] = {
        "role": role,
        "destination_uri": destination_uri,
        "format": fmt,
        "format_hints": hints or {"format": fmt},
    }
    return OutputSpec.model_validate(payload)


def make_callback(
    *,
    url: str = "https://grabatus.com/webhook",
    auth_scheme: str = "jwt_hs256",
) -> Callback:
    return Callback.model_validate({"url": url, "auth_scheme": auth_scheme})


def make_contract(
    *,
    parameters: ParamsT,
    envelope: Envelope | None = None,
    identity: Identity | None = None,
    references: References | None = None,
    service: ServiceDescriptor | None = None,
    inputs: list[InputSpec] | None = None,
    outputs: list[OutputSpec] | None = None,
    callback: Callback | None = None,
) -> BaseServiceContract[ParamsT]:
    return BaseServiceContract[type(parameters)].model_validate(
        {
            "envelope": (envelope or make_envelope()).model_dump(mode="json"),
            "identity": (identity or make_identity()).model_dump(mode="json"),
            "references": (references or make_references()).model_dump(mode="json"),
            "service": (service or make_service_descriptor()).model_dump(mode="json"),
            "inputs": [
                spec.model_dump(mode="json")
                for spec in (inputs or [make_input_spec()])
            ],
            "outputs": [
                spec.model_dump(mode="json")
                for spec in (outputs or [make_output_spec()])
            ],
            "callback": (callback or make_callback()).model_dump(mode="json"),
            "parameters": parameters.model_dump(mode="json"),
        },
    )
```

- [ ] **Step 15: Wire the testing package init**

`src/grabatus_service_core/testing/__init__.py`:
```python
"""Public test fakes and factories. Imported by every downstream service test."""

from grabatus_service_core.testing.authorization import AllowAllPolicy
from grabatus_service_core.testing.clock import FrozenClock
from grabatus_service_core.testing.compute import FakeComputeBackend
from grabatus_service_core.testing.factories import (
    make_callback,
    make_contract,
    make_envelope,
    make_identity,
    make_input_spec,
    make_output_spec,
    make_references,
    make_service_descriptor,
)
from grabatus_service_core.testing.job_dispatcher import (
    InMemoryJobDispatcher,
    RecordedDispatch,
)
from grabatus_service_core.testing.message import InMemoryMessagePort
from grabatus_service_core.testing.observability import NullObservability
from grabatus_service_core.testing.secrets import InMemorySecretsAdapter
from grabatus_service_core.testing.storage import InMemoryStorage
from grabatus_service_core.testing.webhook import (
    RecordedWebhookCall,
    RecordingWebhookNotifier,
)

__all__ = [
    "AllowAllPolicy",
    "FakeComputeBackend",
    "FrozenClock",
    "InMemoryJobDispatcher",
    "InMemoryMessagePort",
    "InMemorySecretsAdapter",
    "InMemoryStorage",
    "NullObservability",
    "RecordedDispatch",
    "RecordedWebhookCall",
    "RecordingWebhookNotifier",
    "make_callback",
    "make_contract",
    "make_envelope",
    "make_identity",
    "make_input_spec",
    "make_output_spec",
    "make_references",
    "make_service_descriptor",
]
```

`tests/unit/testing/__init__.py`:
```
```

- [ ] **Step 16: Run all testing-package tests**

Run: `uv run pytest tests/unit/testing/ -v`
Expected: All tests PASS.

- [ ] **Step 17: Run full library coverage**

Run: `uv run pytest`
Expected: 100% line + branch on every module under `src/grabatus_service_core/`.

- [ ] **Step 18: Commit**

```bash
git add src/grabatus_service_core/testing/ tests/unit/testing/
git commit -m "feat(testing): add fakes and factories for downstream service tests"
```

---

## Phase G — Top-Level Public API and No-Cloud-Imports Smoke Test

### Task G1: Expose top-level public API and verify import surface

**Files:**
- Modify: `src/grabatus_service_core/__init__.py`
- Create: `tests/unit/test_public_api.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_public_api.py`:
```python
"""Validates the library's top-level public API and import surface."""

from __future__ import annotations

import importlib
import sys


_FORBIDDEN_TOP_LEVEL_IMPORTS = (
    "google.cloud.storage",
    "google.cloud.pubsub",
    "google.cloud.secretmanager",
    "google.cloud.run",
    "boto3",
    "fastapi",
    "uvicorn",
)


def test_importing_top_level_does_not_load_cloud_sdks() -> None:
    # Drop already-loaded modules (other tests may have loaded them) so we
    # can observe what a *fresh* import of grabatus_service_core pulls in.
    for module_name in list(sys.modules):
        if module_name.startswith("grabatus_service_core"):
            del sys.modules[module_name]
    importlib.import_module("grabatus_service_core")
    for forbidden in _FORBIDDEN_TOP_LEVEL_IMPORTS:
        assert forbidden not in sys.modules, (
            f"Top-level import of grabatus_service_core pulled in "
            f"{forbidden!r}, which is forbidden in Sub-Plan 1A."
        )


def test_top_level_exposes_version() -> None:
    import grabatus_service_core

    assert grabatus_service_core.__version__ == "0.1.0"


def test_top_level_re_exports_contract_classes() -> None:
    from grabatus_service_core import (
        BaseServiceContract,
        Envelope,
        Identity,
        InputSpec,
        OutputSpec,
    )

    assert BaseServiceContract is not None
    assert Envelope is not None
    assert Identity is not None
    assert InputSpec is not None
    assert OutputSpec is not None


def test_top_level_re_exports_errors() -> None:
    from grabatus_service_core import GrabatusServiceError, UnauthorizedUriError

    assert issubclass(UnauthorizedUriError, GrabatusServiceError)


def test_testing_subpackage_is_importable_separately() -> None:
    from grabatus_service_core import testing

    assert hasattr(testing, "InMemoryStorage")
    assert hasattr(testing, "make_contract")
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest tests/unit/test_public_api.py -v`
Expected: FAIL — top-level imports do not yet expose anything beyond `__version__`.

- [ ] **Step 3: Update top-level `__init__.py`**

`src/grabatus_service_core/__init__.py`:
```python
"""Grabatus Service Core: hexagonal library for Grabatus computational services.

Top-level imports here are deliberately limited to pure-Python domain
classes. Any module that requires a cloud SDK lives under ``adapters/``
(introduced in Sub-Plan 1B) and is imported only by services that wire
those adapters explicitly.
"""

from grabatus_service_core.contract import (
    BaseServiceContract,
    Callback,
    Envelope,
    FormatHints,
    Identity,
    InputSpec,
    OutputSpec,
    References,
    SecretRef,
    ServiceDescriptor,
)
from grabatus_service_core.errors import (
    BlockedHostError,
    ComputeError,
    ComputeTimeoutError,
    ContractError,
    CredentialResolutionError,
    FormatParsingError,
    GrabatusServiceError,
    InputNotFoundError,
    InputReadError,
    InvalidContractError,
    MalformedMessageError,
    OutputWriteError,
    SecurityError,
    StorageError,
    UnauthorizedUriError,
    UnsupportedProtocolVersionError,
    UnsupportedSchemeError,
    WebhookAuthError,
    WebhookError,
)

__version__ = "0.1.0"

__all__ = [
    "BaseServiceContract",
    "BlockedHostError",
    "Callback",
    "ComputeError",
    "ComputeTimeoutError",
    "ContractError",
    "CredentialResolutionError",
    "Envelope",
    "FormatHints",
    "FormatParsingError",
    "GrabatusServiceError",
    "Identity",
    "InputNotFoundError",
    "InputReadError",
    "InputSpec",
    "InvalidContractError",
    "MalformedMessageError",
    "OutputSpec",
    "OutputWriteError",
    "References",
    "SecretRef",
    "SecurityError",
    "ServiceDescriptor",
    "StorageError",
    "UnauthorizedUriError",
    "UnsupportedProtocolVersionError",
    "UnsupportedSchemeError",
    "WebhookAuthError",
    "WebhookError",
    "__version__",
]
```

- [ ] **Step 4: Run tests, full coverage**

Run: `uv run pytest`
Expected: All tests PASS, coverage 100%.

- [ ] **Step 5: Run all quality gates one final time**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src/ tests/
uv run bandit -r src/ -ll
uv run pre-commit run --all-files
```

Expected: All exit 0.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/__init__.py tests/unit/test_public_api.py
git commit -m "feat: expose top-level public API; assert no cloud SDK imports"
```

---

## Phase Z — Final Self-Review of Sub-Plan 1A

### Task Z1: Run all gates one last time

- [ ] **Step 1: Sync, lint, type, test, security**

```bash
uv sync --all-extras
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src/ tests/
uv run pytest --cov=grabatus_service_core --cov-branch --cov-fail-under=100
uv run bandit -r src/ -ll
uv run pip-audit
uv run pre-commit run --all-files
```

Expected: every command exits 0.

- [ ] **Step 2: Smoke import test**

```bash
uv run python -c "from grabatus_service_core import BaseServiceContract; from grabatus_service_core.testing import InMemoryStorage; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 3: Verify the spec acceptance criteria**

Re-read §6.8 of the design spec. Confirm by inspection:
- The `testing` subpackage exports every fake listed
- Each fake satisfies the corresponding Port via `isinstance` (already tested)
- A consumer can import the lib without loading any cloud SDK (already tested)

- [ ] **Step 4: Tag the milestone**

```bash
git tag -a 1A-domain-foundation-complete -m "Sub-Plan 1A complete: domain foundation"
```

(Push when convenient: `git push origin 1A-domain-foundation-complete`.)

---

## What's Next

Sub-Plan 1A is done. The library has a fully tested, fully typed, fully documented (via docstrings) domain layer. No I/O is wired yet — that's Sub-Plan 1B. The fakes from Phase F prove the abstractions are sound: they're real implementations that satisfy each Port.

Before starting Sub-Plan 1B:

1. Open the design spec (`docs/superpowers/specs/2026-04-25-grabatus-service-core-design.md`) and confirm the items in §6.1, §6.3, §6.4, §6.8 are all delivered.
2. Notify the maintainer to write Sub-Plan 1B (Adapters & Runner). 1B builds on 1A but does not edit any file in `contract/`, `ports/`, `errors/`, `security/`, or `testing/`.
3. Bump the working version in `pyproject.toml` to `0.1.0.dev1` (or similar) so 1B's commits have a distinct version label.
