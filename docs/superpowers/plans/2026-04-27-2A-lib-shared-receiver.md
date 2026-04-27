# Plan 2A: Lib enhancements — shared receiver, OpaqueServiceContract, CompressedStorage

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `grabatus-service-core` v0.2.0 with a shared receiver module (single Cloud Run Service serving every Grabatus computational service), an opaque parameters contract, and a compression decorator over storage adapters — without breaking any existing v0.1.0 behavior.

**Architecture:** Additive, hexagonal. New `receiver/` module contains a `ServiceRegistry` domain utility and a `SharedReceiverRunner` that reuses existing `decode`/`validate`/`authorize` step functions. The receiver dispatches to the right Cloud Run Job based on `service.name`. `OpaqueServiceContract` lets the receiver validate envelope/identity/I/O without locking down `parameters` (the worker validates those). `CompressedStorage` is a decorator that honors `OutputSpec.compression` (gzip/zstd) on top of any inner `StoragePort`.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, structlog, uvicorn, pytest, hypothesis, mutmut. Same toolchain as the existing lib (no new top-level dependencies except `zstandard` for the zstd codec).

---

## Repository

This plan operates on the `grabatus-service-core` repository at `/Users/rodolpho/Projects/grabatus-project/grabatus-service-core/`. All paths in this plan are relative to that repo root.

## File Structure

### New source files

| File | Responsibility |
|------|----------------|
| `src/grabatus_service_core/receiver/__init__.py` | Public exports of the receiver module |
| `src/grabatus_service_core/receiver/registry.py` | `ServiceRegistry` immutable domain utility + `from_env_string` parser |
| `src/grabatus_service_core/receiver/runner.py` | `SharedReceiverRunner`, `ReceiverExecutionResult`, `SharedReceiverAdapters` |
| `src/grabatus_service_core/receiver/app.py` | `build_shared_receiver_app()` factory (FastAPI) |
| `src/grabatus_service_core/receiver/cli.py` | `main()` entry point invoked by `grabatus-receiver` console script |
| `src/grabatus_service_core/contract/opaque.py` | `OpaqueParameters`, `OpaqueServiceContract` alias |
| `src/grabatus_service_core/adapters/storage_compressed.py` | `CompressedStorage` decorator (gzip/zstd) |
| `Dockerfile.receiver` | Multi-stage image for the shared receiver Cloud Run Service |

### Modified source files

| File | Change |
|------|--------|
| `src/grabatus_service_core/errors/contract.py` | Add `UnknownServiceError` (subclass of `ContractError`) |
| `src/grabatus_service_core/settings.py` | Add `service_registry: ServiceRegistry` field with a `field_validator` that parses `GBT_SERVICE_REGISTRY` |
| `src/grabatus_service_core/testing/__init__.py` | Re-export `InMemoryServiceRegistry`, `make_opaque_contract` |
| `src/grabatus_service_core/testing/factories.py` | Add `make_opaque_contract(...)` factory |
| `src/grabatus_service_core/app/factory.py` | Make `build_app` accept any runner that exposes `.execute(raw)` and `.mode` |
| `pyproject.toml` | Bump version to `0.2.0`; add `[project.scripts]` entry; add `zstandard>=0.22` to runtime deps |
| `CHANGELOG.md` | Add `[0.2.0]` section |
| `docs/index.rst` | Link new tutorial in the toctree (English only; default Sphinx theme is for new service docs only — this lib already uses Furo, keep it) |
| `docs/architecture.rst` | Add `Shared Receiver` subsection |
| `docs/tutorials/deploying_the_shared_receiver.rst` | New tutorial (English, simple language, examples) |

### New test files

| File | Coverage |
|------|----------|
| `tests/unit/receiver/__init__.py` | Marker package |
| `tests/unit/receiver/test_registry.py` | `ServiceRegistry` resolution, `from_env_string` parsing, frozenness |
| `tests/unit/receiver/test_runner.py` | `SharedReceiverRunner` happy path + every error branch |
| `tests/unit/receiver/test_app.py` | `build_shared_receiver_app` returns a wired FastAPI; `/health/live` 200; `/run_service` POST routes through runner |
| `tests/unit/receiver/test_cli.py` | `cli.main()` reads settings and runs uvicorn (subprocess-style with monkeypatch) |
| `tests/unit/contract/test_opaque.py` | `OpaqueServiceContract` validates envelope/I-O but accepts any `parameters` shape |
| `tests/unit/adapters/test_storage_compressed.py` | `CompressedStorage` round-trips gzip; round-trips zstd; passes through when `compression="none"`; raises on corrupt compressed input |
| `tests/unit/errors/test_unknown_service_error.py` | `UnknownServiceError` carries the right `error_code`, `http_status`, `retriable` |
| `tests/integration/test_shared_receiver_e2e.py` | FastAPI `TestClient` posts a real Pub/Sub envelope; `InMemoryJobDispatcher` records the dispatch |
| `tests/property/test_shared_receiver.py` | Hypothesis: arbitrary registry contents always either resolve or raise `UnknownServiceError` |
| `tests/property/test_storage_compressed.py` | Hypothesis: `read(write(payload)) == payload` for any random bytes, any codec |

---

## Self-contained checkpoints

The plan is split into **8 checkpoints** that each leave the repo in a green-CI state. Commit at every checkpoint. After all 8: the lib is ready for v0.2.0 release.

| # | Checkpoint | Files touched |
|---|------------|----------------|
| 1 | `UnknownServiceError` + `ServiceRegistry` | errors, receiver/registry.py, tests |
| 2 | `OpaqueServiceContract` | contract/opaque.py, tests |
| 3 | `CompressedStorage` decorator | adapters/storage_compressed.py, tests |
| 4 | `SharedReceiverRunner` core | receiver/runner.py, tests |
| 5 | Settings integration + test factories | settings.py, testing/, tests |
| 6 | `build_shared_receiver_app` + routes | receiver/app.py, app/factory.py, tests |
| 7 | CLI + Dockerfile.receiver | receiver/cli.py, pyproject.toml, Dockerfile.receiver, tests |
| 8 | Documentation + CHANGELOG + final mutation gate | docs/, CHANGELOG.md |

---

# Checkpoint 1 — `UnknownServiceError` and `ServiceRegistry`

## Task 1.1: Add `UnknownServiceError` to the contract error hierarchy

**Files:**
- Modify: `src/grabatus_service_core/errors/contract.py`
- Test: `tests/unit/errors/test_unknown_service_error.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/errors/test_unknown_service_error.py`:

```python
"""Verify UnknownServiceError carries the right ClassVar metadata."""

from grabatus_service_core.errors import UnknownServiceError
from grabatus_service_core.errors.contract import ContractError


def test_unknown_service_error_is_a_contract_error() -> None:
    assert issubclass(UnknownServiceError, ContractError)


def test_unknown_service_error_metadata() -> None:
    assert UnknownServiceError.error_code == "unknown_service"
    assert UnknownServiceError.http_status == 200
    assert UnknownServiceError.retriable is False


def test_unknown_service_error_message_round_trip() -> None:
    err = UnknownServiceError("service.name='ghost' not in registry")
    assert "ghost" in str(err)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/errors/test_unknown_service_error.py -v
```

Expected: `ImportError` because `UnknownServiceError` is not yet exported.

- [ ] **Step 3: Add `UnknownServiceError` to the contract error module**

Edit `src/grabatus_service_core/errors/contract.py` — add at the bottom of the file:

```python
class UnknownServiceError(ContractError):
    """Raised when the receiver's registry has no worker for envelope.service.name."""

    error_code = "unknown_service"
```

- [ ] **Step 4: Re-export from the errors package**

Open `src/grabatus_service_core/errors/__init__.py` and append `UnknownServiceError` to both the import-from-contract block and the `__all__` list (preserve alphabetical order if the file is alphabetised).

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/unit/errors/test_unknown_service_error.py -v
```

Expected: 3 tests pass.

- [ ] **Step 6: Run the full test suite to confirm no regression**

```bash
uv run pytest -x
```

Expected: every existing test still passes.

- [ ] **Step 7: Commit**

```bash
git add src/grabatus_service_core/errors/contract.py \
        src/grabatus_service_core/errors/__init__.py \
        tests/unit/errors/test_unknown_service_error.py
git commit -m "feat(errors): add UnknownServiceError for shared receiver"
```

---

## Task 1.2: Create `ServiceRegistry` domain utility

**Files:**
- Create: `src/grabatus_service_core/receiver/__init__.py`
- Create: `src/grabatus_service_core/receiver/registry.py`
- Create: `tests/unit/receiver/__init__.py`
- Create: `tests/unit/receiver/test_registry.py`

- [ ] **Step 1: Write the failing tests for `ServiceRegistry.resolve`**

Create `tests/unit/receiver/__init__.py` (empty file).

Create `tests/unit/receiver/test_registry.py`:

```python
"""Verify ServiceRegistry resolution + frozenness + parsing."""

import pytest

from grabatus_service_core.errors import UnknownServiceError
from grabatus_service_core.receiver.registry import ServiceRegistry


def test_resolve_returns_worker_job_name_for_known_service() -> None:
    registry = ServiceRegistry(by_name={"forecast": "grabatus-forecasting-worker"})
    assert registry.resolve("forecast") == "grabatus-forecasting-worker"


def test_resolve_raises_unknown_service_error_for_missing_name() -> None:
    registry = ServiceRegistry(by_name={"forecast": "fc-worker"})
    with pytest.raises(UnknownServiceError) as exc_info:
        registry.resolve("ghost")
    assert "ghost" in str(exc_info.value)
    assert "forecast" in str(exc_info.value)  # known services listed for diagnostics


def test_resolve_on_empty_registry_raises_unknown_service_error() -> None:
    registry = ServiceRegistry(by_name={})
    with pytest.raises(UnknownServiceError):
        registry.resolve("anything")


def test_registry_resolves_one_of_multiple_services() -> None:
    registry = ServiceRegistry(
        by_name={
            "forecast": "fc-worker",
            "abtest": "ab-worker",
            "optimize": "opt-worker",
        },
    )
    assert registry.resolve("abtest") == "ab-worker"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/receiver/test_registry.py -v
```

Expected: `ModuleNotFoundError: No module named 'grabatus_service_core.receiver'`.

- [ ] **Step 3: Create the receiver package**

Create `src/grabatus_service_core/receiver/__init__.py`:

```python
"""Shared receiver: stateless front door for all Grabatus computational services."""

from grabatus_service_core.receiver.registry import ServiceRegistry

__all__ = ["ServiceRegistry"]
```

- [ ] **Step 4: Implement `ServiceRegistry.resolve`**

Create `src/grabatus_service_core/receiver/registry.py`:

```python
"""ServiceRegistry: maps envelope.service.name to the Cloud Run Job that runs it."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from grabatus_service_core.errors import UnknownServiceError


@dataclass(frozen=True, slots=True)
class ServiceRegistry:
    """Immutable name -> worker_job_name lookup.

    Example:
        >>> registry = ServiceRegistry(by_name={"forecast": "grabatus-forecasting-worker"})
        >>> registry.resolve("forecast")
        'grabatus-forecasting-worker'
    """

    by_name: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "by_name", MappingProxyType(dict(self.by_name)))

    def resolve(self, service_name: str) -> str:
        """Return the worker job name registered for ``service_name``.

        Raises ``UnknownServiceError`` if no entry matches.
        """
        try:
            return self.by_name[service_name]
        except KeyError as exc:
            known = sorted(self.by_name)
            raise UnknownServiceError(
                f"service.name={service_name!r} not in registry; known: {known!r}",
            ) from exc
```

- [ ] **Step 5: Run tests to verify resolve passes**

```bash
uv run pytest tests/unit/receiver/test_registry.py -v
```

Expected: 4 tests pass.

- [ ] **Step 6: Add tests for `from_env_string`**

Append to `tests/unit/receiver/test_registry.py`:

```python
def test_from_env_string_single_entry() -> None:
    registry = ServiceRegistry.from_env_string("forecast:fc-worker")
    assert registry.resolve("forecast") == "fc-worker"


def test_from_env_string_multiple_entries() -> None:
    registry = ServiceRegistry.from_env_string("forecast:fc-worker,abtest:ab-worker")
    assert registry.resolve("forecast") == "fc-worker"
    assert registry.resolve("abtest") == "ab-worker"


def test_from_env_string_strips_whitespace() -> None:
    registry = ServiceRegistry.from_env_string(" forecast : fc-worker , abtest : ab-worker ")
    assert registry.resolve("forecast") == "fc-worker"
    assert registry.resolve("abtest") == "ab-worker"


def test_from_env_string_empty_string_yields_empty_registry() -> None:
    registry = ServiceRegistry.from_env_string("")
    assert registry.by_name == {}


def test_from_env_string_rejects_entry_without_colon() -> None:
    with pytest.raises(ValueError, match=r"expected 'name:worker'"):
        ServiceRegistry.from_env_string("forecast")


def test_from_env_string_rejects_duplicate_service_name() -> None:
    with pytest.raises(ValueError, match=r"duplicate service name"):
        ServiceRegistry.from_env_string("forecast:fc1,forecast:fc2")


def test_from_env_string_rejects_empty_worker_name() -> None:
    with pytest.raises(ValueError, match=r"empty"):
        ServiceRegistry.from_env_string("forecast:")
```

- [ ] **Step 7: Run tests to verify they fail**

```bash
uv run pytest tests/unit/receiver/test_registry.py -v
```

Expected: 7 new tests fail with `AttributeError: type object 'ServiceRegistry' has no attribute 'from_env_string'`.

- [ ] **Step 8: Implement `from_env_string`**

Edit `src/grabatus_service_core/receiver/registry.py`. Add a `classmethod` after `resolve`:

```python
    @classmethod
    def from_env_string(cls, raw: str) -> "ServiceRegistry":
        """Parse a comma-separated ``name:worker_job_name`` string.

        Example:
            >>> r = ServiceRegistry.from_env_string("forecast:fc,abtest:ab")
            >>> r.resolve("abtest")
            'ab'
        """
        if not raw.strip():
            return cls(by_name={})
        by_name: dict[str, str] = {}
        for item in raw.split(","):
            if ":" not in item:
                raise ValueError(
                    f"registry entry {item!r} malformed; expected 'name:worker'",
                )
            name, _, worker = item.partition(":")
            name = name.strip()
            worker = worker.strip()
            if not name or not worker:
                raise ValueError(
                    f"registry entry {item!r} has empty name or worker",
                )
            if name in by_name:
                raise ValueError(f"duplicate service name {name!r} in registry")
            by_name[name] = worker
        return cls(by_name=by_name)
```

- [ ] **Step 9: Run tests to verify they pass**

```bash
uv run pytest tests/unit/receiver/test_registry.py -v
```

Expected: all 11 tests pass.

- [ ] **Step 10: Add the frozenness test**

Append to `tests/unit/receiver/test_registry.py`:

```python
def test_registry_by_name_is_immutable() -> None:
    """Mutating the source dict after construction must not affect the registry."""
    source = {"forecast": "fc-worker"}
    registry = ServiceRegistry(by_name=source)
    source["forecast"] = "tampered"
    assert registry.resolve("forecast") == "fc-worker"


def test_registry_dataclass_is_frozen() -> None:
    registry = ServiceRegistry(by_name={"forecast": "fc-worker"})
    with pytest.raises((AttributeError, TypeError)):
        registry.by_name = {}  # type: ignore[misc]
```

- [ ] **Step 11: Run tests to verify they pass**

```bash
uv run pytest tests/unit/receiver/test_registry.py -v
```

Expected: all 13 tests pass (the `MappingProxyType` + `frozen=True` give us both behaviors).

- [ ] **Step 12: Run the full suite**

```bash
uv run pytest -x
```

Expected: green.

- [ ] **Step 13: Commit**

```bash
git add src/grabatus_service_core/receiver/ tests/unit/receiver/
git commit -m "feat(receiver): ServiceRegistry domain utility"
```

---

# Checkpoint 2 — `OpaqueServiceContract`

## Task 2.1: Create the opaque parameters contract

**Files:**
- Create: `src/grabatus_service_core/contract/opaque.py`
- Create: `tests/unit/contract/test_opaque.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/contract/test_opaque.py`:

```python
"""Verify OpaqueServiceContract validates envelope/I-O but not parameters shape."""

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.opaque import (
    OpaqueParameters,
    OpaqueServiceContract,
)
from grabatus_service_core.testing.factories import (
    make_callback,
    make_envelope,
    make_identity,
    make_input_spec,
    make_output_spec,
    make_references,
    make_service_descriptor,
)


def _build_payload(parameters: dict) -> dict:
    return {
        "envelope": json.loads(make_envelope().model_dump_json()),
        "identity": json.loads(make_identity().model_dump_json()),
        "references": json.loads(make_references().model_dump_json()),
        "service": json.loads(make_service_descriptor().model_dump_json()),
        "inputs": [json.loads(make_input_spec().model_dump_json())],
        "outputs": [json.loads(make_output_spec().model_dump_json())],
        "callback": json.loads(make_callback().model_dump_json()),
        "parameters": parameters,
    }


def test_opaque_contract_accepts_arbitrary_parameters_dict() -> None:
    payload = _build_payload({"anything": 1, "even_nested": {"and": ["arrays"]}})
    contract = OpaqueServiceContract.model_validate(payload)
    assert contract.parameters.model_dump()["anything"] == 1


def test_opaque_contract_accepts_empty_parameters_dict() -> None:
    payload = _build_payload({})
    contract = OpaqueServiceContract.model_validate(payload)
    assert contract.parameters.model_dump() == {}


def test_opaque_contract_still_rejects_missing_envelope() -> None:
    payload = _build_payload({"x": 1})
    del payload["envelope"]
    with pytest.raises(ValidationError, match=r"envelope"):
        OpaqueServiceContract.model_validate(payload)


def test_opaque_contract_still_rejects_zero_inputs() -> None:
    payload = _build_payload({"x": 1})
    payload["inputs"] = []
    with pytest.raises(ValidationError, match=r"at least 1"):
        OpaqueServiceContract.model_validate(payload)


def test_opaque_parameters_round_trips_unknown_fields() -> None:
    params = OpaqueParameters.model_validate({"foo": "bar", "n": 42})
    dumped = params.model_dump()
    assert dumped == {"foo": "bar", "n": 42}


def test_opaque_parameters_is_frozen() -> None:
    params = OpaqueParameters.model_validate({"x": 1})
    with pytest.raises(ValidationError):
        params.x = 2  # type: ignore[attr-defined]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/contract/test_opaque.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `OpaqueParameters` and the contract alias**

Create `src/grabatus_service_core/contract/opaque.py`:

```python
"""OpaqueServiceContract: receiver-side contract that does not validate parameters.

The shared receiver does not know which service it is dispatching to until it
reads ``envelope.service.name``. So it must accept *any* parameters dict and
let the worker validate the parameters with its own typed schema.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from grabatus_service_core.contract.base import BaseServiceContract


class OpaqueParameters(BaseModel):
    """Parameters as a free-form mapping; only the worker validates the shape."""

    model_config = ConfigDict(extra="allow", frozen=True)


OpaqueServiceContract = BaseServiceContract[OpaqueParameters]
"""Type alias used by the shared receiver for envelope-only validation."""
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/contract/test_opaque.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 5: Run the full suite**

```bash
uv run pytest -x
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/contract/opaque.py \
        tests/unit/contract/test_opaque.py
git commit -m "feat(contract): OpaqueServiceContract for receiver-side validation"
```

---

# Checkpoint 3 — `CompressedStorage` decorator

## Task 3.1: Implement gzip round-trip via decorator

**Files:**
- Create: `src/grabatus_service_core/adapters/storage_compressed.py`
- Create: `tests/unit/adapters/test_storage_compressed.py`
- Modify: `pyproject.toml` (add `zstandard>=0.22` dependency)

- [ ] **Step 1: Add `zstandard` to runtime dependencies**

Edit `pyproject.toml`. In the `[project] dependencies` list, add `"zstandard>=0.22"` (alphabetical order).

```bash
uv lock
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/adapters/test_storage_compressed.py`:

```python
"""CompressedStorage: gzip/zstd round-trip on top of any inner StoragePort."""

import gzip

import pytest

from grabatus_service_core.adapters.storage_compressed import CompressedStorage
from grabatus_service_core.errors import OutputWriteError
from grabatus_service_core.testing.storage import InMemoryStorage
from grabatus_service_core.testing.factories import (
    make_input_spec,
    make_output_spec,
)
from grabatus_service_core.ports.values import Credentials


_NO_CREDS = Credentials(token=b"", token_type="none")


def test_no_compression_is_a_pass_through() -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    spec = make_output_spec(compression="none")
    receipt = decorator.write(
        spec=spec,
        payload=b"hello",
        credentials=_NO_CREDS,
    )
    assert inner.contents[str(spec.destination_uri)] == b"hello"
    assert receipt.bytes_written == 5


def test_gzip_write_stores_compressed_bytes() -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    spec = make_output_spec(compression="gzip")
    decorator.write(
        spec=spec,
        payload=b"the quick brown fox jumps over the lazy dog",
        credentials=_NO_CREDS,
    )
    stored = inner.contents[str(spec.destination_uri)]
    assert stored != b"the quick brown fox jumps over the lazy dog"
    assert gzip.decompress(stored) == b"the quick brown fox jumps over the lazy dog"


def test_gzip_read_decompresses_stored_bytes() -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    out_spec = make_output_spec(compression="gzip")
    decorator.write(
        spec=out_spec,
        payload=b"payload",
        credentials=_NO_CREDS,
    )
    in_spec = make_input_spec(
        source_uri=out_spec.destination_uri,
    )  # adjust if helper differs; see fixture comment
    # NOTE: make_input_spec must accept a `compression` kwarg (Task 3.2 below
    # extends the factory) — for this test, we set it directly.
    in_spec_with_compression = in_spec.model_copy(update={"compression": "gzip"})
    out = decorator.read(
        spec=in_spec_with_compression,
        credentials=_NO_CREDS,
    )
    assert out == b"payload"


def test_gzip_read_raises_on_corrupt_input() -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    spec = make_output_spec(compression="gzip")
    inner.contents[str(spec.destination_uri)] = b"not gzip data"
    in_spec = make_input_spec(source_uri=spec.destination_uri)
    in_spec_with_compression = in_spec.model_copy(update={"compression": "gzip"})
    with pytest.raises(OutputWriteError, match=r"gzip"):
        decorator.read(spec=in_spec_with_compression, credentials=_NO_CREDS)


def test_zstd_round_trips_via_decorator() -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    out_spec = make_output_spec(compression="zstd")
    decorator.write(
        spec=out_spec,
        payload=b"zstandard test",
        credentials=_NO_CREDS,
    )
    in_spec = make_input_spec(source_uri=out_spec.destination_uri)
    in_spec_zstd = in_spec.model_copy(update={"compression": "zstd"})
    assert decorator.read(spec=in_spec_zstd, credentials=_NO_CREDS) == b"zstandard test"


def test_receipt_bytes_written_reflects_compressed_size() -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    spec = make_output_spec(compression="gzip")
    payload = b"x" * 10_000  # very compressible
    receipt = decorator.write(
        spec=spec,
        payload=payload,
        credentials=_NO_CREDS,
    )
    assert receipt.bytes_written < len(payload)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/unit/adapters/test_storage_compressed.py -v
```

Expected: `ImportError` for `CompressedStorage`. Also possibly that `make_input_spec` and `make_output_spec` need a `compression` kwarg (handled in Task 3.2).

- [ ] **Step 4: Implement the `CompressedStorage` decorator**

Create `src/grabatus_service_core/adapters/storage_compressed.py`:

```python
"""CompressedStorage: a StoragePort decorator that honors OutputSpec.compression.

The decorator transparently compresses payloads before delegating writes to
``inner.write()`` and decompresses payloads after delegating reads to
``inner.read()``. The ``compression`` field on ``InputSpec`` and ``OutputSpec``
selects the codec.

Codecs supported:
- ``"none"`` — pass through (no transformation)
- ``"gzip"`` — Python stdlib ``gzip`` (compresslevel=9)
- ``"zstd"`` — ``zstandard`` library (level=10)

Example:
    >>> from grabatus_service_core.adapters.storage_gcs import GcsStorage
    >>> raw = GcsStorage(...)
    >>> storage = CompressedStorage(inner=raw)
"""

from __future__ import annotations

import gzip
from typing import TYPE_CHECKING

import zstandard as zstd

from grabatus_service_core.errors import (
    InputReadError,
    OutputWriteError,
)

if TYPE_CHECKING:
    from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
    from grabatus_service_core.ports.storage import StoragePort
    from grabatus_service_core.ports.values import Credentials, WriteReceipt


_GZIP_LEVEL = 9
_ZSTD_LEVEL = 10


class CompressedStorage:
    """Decorator that adds gzip/zstd codec support to any inner StoragePort."""

    def __init__(self, *, inner: StoragePort) -> None:
        self._inner = inner

    def read(self, *, spec: InputSpec, credentials: Credentials) -> bytes:
        raw = self._inner.read(spec=spec, credentials=credentials)
        compression = getattr(spec, "compression", "none")
        if compression == "none":
            return raw
        if compression == "gzip":
            try:
                return gzip.decompress(raw)
            except OSError as exc:
                raise InputReadError(
                    f"failed to gzip-decompress payload from "
                    f"uri={spec.source_uri!s}: {exc}",
                ) from exc
        if compression == "zstd":
            try:
                return zstd.ZstdDecompressor().decompress(raw)
            except zstd.ZstdError as exc:
                raise InputReadError(
                    f"failed to zstd-decompress payload from "
                    f"uri={spec.source_uri!s}: {exc}",
                ) from exc
        raise InputReadError(  # pragma: no cover — unreachable; Pydantic narrows the type
            f"unknown compression={compression!r}",
        )

    def write(
        self,
        *,
        spec: OutputSpec,
        payload: bytes,
        credentials: Credentials,
    ) -> WriteReceipt:
        if spec.compression == "none":
            transformed = payload
        elif spec.compression == "gzip":
            transformed = gzip.compress(payload, compresslevel=_GZIP_LEVEL)
        elif spec.compression == "zstd":
            transformed = zstd.ZstdCompressor(level=_ZSTD_LEVEL).compress(payload)
        else:
            raise OutputWriteError(  # pragma: no cover — Pydantic narrows the type
                f"unknown compression={spec.compression!r}",
            )
        return self._inner.write(
            spec=spec,
            payload=transformed,
            credentials=credentials,
        )
```

Note: the `pragma: no cover` comments are justified because Pydantic narrows `compression: Literal["none", "gzip", "zstd"]` — any other value would have failed contract validation upstream. The `scripts/check_pragma_comments.py` tool already accepts inline justification comments.

- [ ] **Step 5: Verify `make_input_spec` accepts `compression`**

Open `src/grabatus_service_core/testing/factories.py`. If `make_input_spec` doesn't already accept a `compression` kwarg, add it:

```python
def make_input_spec(
    *,
    role: str = "timeseries",
    source_uri: str = "gs://test-bucket/inputs/series.xlsx",
    format: DataFormat = "xlsx",
    format_hints: FormatHints | None = None,
    compression: Compression = "none",
    credential_ref: SecretRef | None = None,
) -> InputSpec:
    ...
```

(Adjust the existing factory's body to pass `compression` through to `InputSpec`.)

If `InputSpec` doesn't currently have a `compression` field, this is the moment to add it. Inspect `src/grabatus_service_core/contract/io_spec.py` — at present (verified during plan writing) `InputSpec` has only `OutputSpec.compression`. Add `compression: Compression = "none"` to `InputSpec` symmetrically. Add a regression test:

```python
# tests/unit/contract/test_io_spec_input_compression.py
from grabatus_service_core.contract.io_spec import InputSpec
from grabatus_service_core.testing.factories import make_input_spec


def test_input_spec_default_compression_is_none() -> None:
    spec: InputSpec = make_input_spec()
    assert spec.compression == "none"


def test_input_spec_accepts_gzip_compression() -> None:
    spec: InputSpec = make_input_spec(compression="gzip")
    assert spec.compression == "gzip"
```

- [ ] **Step 6: Re-run the storage_compressed tests**

```bash
uv run pytest tests/unit/adapters/test_storage_compressed.py -v
uv run pytest tests/unit/contract/test_io_spec_input_compression.py -v
```

Expected: green.

- [ ] **Step 7: Run the full test suite**

```bash
uv run pytest -x
```

Expected: green. Existing snapshot test `tests/contract/...` of the JSON Schema must be updated — do that explicitly:

```bash
uv run pytest tests/contract -v
```

If the JSON Schema snapshot test fails because `InputSpec.compression` is now in the schema, regenerate the snapshot following the existing convention (e.g. `pytest --snapshot-update` or whatever the lib uses) and **review the diff manually** to confirm only `compression` was added.

- [ ] **Step 8: Commit**

```bash
git add src/grabatus_service_core/adapters/storage_compressed.py \
        src/grabatus_service_core/contract/io_spec.py \
        src/grabatus_service_core/testing/factories.py \
        tests/unit/adapters/test_storage_compressed.py \
        tests/unit/contract/test_io_spec_input_compression.py \
        tests/contract/  # if snapshot updated
        pyproject.toml uv.lock
git commit -m "feat(adapters): CompressedStorage decorator (gzip/zstd)"
```

---

## Task 3.2: Property test `read(write(payload)) == payload`

**Files:**
- Create: `tests/property/test_storage_compressed.py`

- [ ] **Step 1: Write the property test**

Create `tests/property/test_storage_compressed.py`:

```python
"""Property: any payload survives a write/read round-trip via any codec."""

from hypothesis import given
from hypothesis import strategies as st

from grabatus_service_core.adapters.storage_compressed import CompressedStorage
from grabatus_service_core.ports.values import Credentials
from grabatus_service_core.testing.factories import make_input_spec, make_output_spec
from grabatus_service_core.testing.storage import InMemoryStorage


_NO_CREDS = Credentials(token=b"", token_type="none")


@given(payload=st.binary(min_size=0, max_size=4096))
def test_gzip_round_trips_arbitrary_bytes(payload: bytes) -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    out_spec = make_output_spec(compression="gzip")
    decorator.write(spec=out_spec, payload=payload, credentials=_NO_CREDS)
    in_spec = make_input_spec(
        source_uri=out_spec.destination_uri,
    ).model_copy(update={"compression": "gzip"})
    assert decorator.read(spec=in_spec, credentials=_NO_CREDS) == payload


@given(payload=st.binary(min_size=0, max_size=4096))
def test_zstd_round_trips_arbitrary_bytes(payload: bytes) -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    out_spec = make_output_spec(compression="zstd")
    decorator.write(spec=out_spec, payload=payload, credentials=_NO_CREDS)
    in_spec = make_input_spec(
        source_uri=out_spec.destination_uri,
    ).model_copy(update={"compression": "zstd"})
    assert decorator.read(spec=in_spec, credentials=_NO_CREDS) == payload


@given(payload=st.binary(min_size=0, max_size=4096))
def test_no_compression_round_trips_arbitrary_bytes(payload: bytes) -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    out_spec = make_output_spec(compression="none")
    decorator.write(spec=out_spec, payload=payload, credentials=_NO_CREDS)
    in_spec = make_input_spec(
        source_uri=out_spec.destination_uri,
    ).model_copy(update={"compression": "none"})
    assert decorator.read(spec=in_spec, credentials=_NO_CREDS) == payload
```

- [ ] **Step 2: Run the property tests**

```bash
uv run pytest tests/property/test_storage_compressed.py -v
```

Expected: all 3 properties pass under Hypothesis (default 100 examples each).

- [ ] **Step 3: Commit**

```bash
git add tests/property/test_storage_compressed.py
git commit -m "test(property): CompressedStorage round-trip invariants"
```

---

# Checkpoint 4 — `SharedReceiverRunner` core

## Task 4.1: Define value objects and adapters bundle

**Files:**
- Create: `src/grabatus_service_core/receiver/runner.py` (initial scaffold — value objects only)
- Create: `tests/unit/receiver/test_runner.py`

- [ ] **Step 1: Write the failing test for `ReceiverExecutionResult` shape**

Create `tests/unit/receiver/test_runner.py`:

```python
"""SharedReceiverRunner: value objects + execute happy path + every error branch."""

from uuid import UUID, uuid4

import pytest

from grabatus_service_core.errors import (
    InvalidContractError,
    MalformedMessageError,
    UnauthorizedUriError,
    UnknownServiceError,
)
from grabatus_service_core.receiver.registry import ServiceRegistry
from grabatus_service_core.receiver.runner import (
    ReceiverExecutionResult,
    SharedReceiverAdapters,
    SharedReceiverRunner,
)


def test_receiver_execution_result_holds_status_and_request_id() -> None:
    rid = uuid4()
    result = ReceiverExecutionResult(
        request_id=rid,
        status="ok",
        dispatched_job_id="job-123",
        error=None,
    )
    assert result.request_id == rid
    assert result.status == "ok"
    assert result.dispatched_job_id == "job-123"
    assert result.error is None


def test_receiver_execution_result_is_frozen() -> None:
    result = ReceiverExecutionResult(
        request_id=uuid4(),
        status="ok",
        dispatched_job_id="j",
        error=None,
    )
    with pytest.raises((AttributeError, TypeError)):
        result.status = "error"  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/receiver/test_runner.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create `runner.py` with the value objects**

Create `src/grabatus_service_core/receiver/runner.py`:

```python
"""SharedReceiverRunner: validates envelope, dispatches to the right worker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from uuid import UUID

if TYPE_CHECKING:
    from grabatus_service_core.errors import GrabatusServiceError
    from grabatus_service_core.ports.authorization import UriAuthorizationPort
    from grabatus_service_core.ports.clock import ClockPort
    from grabatus_service_core.ports.job_dispatcher import JobDispatcherPort
    from grabatus_service_core.ports.message import MessagePort
    from grabatus_service_core.ports.observability import ObservabilityPort
    from grabatus_service_core.receiver.registry import ServiceRegistry
    from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist


@dataclass(frozen=True, slots=True)
class ReceiverExecutionResult:
    """Outcome of dispatching one Pub/Sub envelope through the shared receiver."""

    request_id: UUID
    status: Literal["ok", "error"]
    dispatched_job_id: str | None
    error: GrabatusServiceError | None


@dataclass(frozen=True, slots=True)
class SharedReceiverAdapters:
    """Bundle of ports the shared receiver needs.

    Grouped into a dataclass so the factory signature stays clean.
    """

    message: MessagePort
    authorizer: UriAuthorizationPort
    job_dispatcher: JobDispatcherPort
    observability: ObservabilityPort
    clock: ClockPort
```

(`SharedReceiverRunner` itself is added in the next task.)

- [ ] **Step 4: Add a stub `SharedReceiverRunner` so the import succeeds**

Append to `src/grabatus_service_core/receiver/runner.py`:

```python
@dataclass(frozen=True, slots=True)
class SharedReceiverRunner:
    """Receiver pipeline: decode → validate → authorize → dispatch."""

    adapters: SharedReceiverAdapters
    scheme_allowlist: SchemeAllowlist
    registry: ServiceRegistry

    # Method body added in Task 4.2
```

- [ ] **Step 5: Run tests to verify the value-object tests pass**

```bash
uv run pytest tests/unit/receiver/test_runner.py::test_receiver_execution_result_holds_status_and_request_id \
              tests/unit/receiver/test_runner.py::test_receiver_execution_result_is_frozen -v
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/receiver/runner.py tests/unit/receiver/test_runner.py
git commit -m "feat(receiver): value objects for SharedReceiverRunner"
```

---

## Task 4.2: Implement `SharedReceiverRunner.execute` happy path

**Files:**
- Modify: `src/grabatus_service_core/receiver/runner.py` (add `execute` method)
- Modify: `tests/unit/receiver/test_runner.py`

- [ ] **Step 1: Append the happy-path test**

Append to `tests/unit/receiver/test_runner.py`:

```python
import json
from base64 import b64encode

from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
from grabatus_service_core.contract.opaque import OpaqueServiceContract
from grabatus_service_core.ports.values import RawMessage
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.testing import (
    AllowAllPolicy,
    FrozenClock,
    InMemoryJobDispatcher,
    NullObservability,
)
from grabatus_service_core.testing.factories import make_contract


def _build_pubsub_raw_message(contract: OpaqueServiceContract) -> RawMessage:
    inner = contract.model_dump(mode="json")
    payload = json.dumps({"message": {"data": b64encode(json.dumps(inner).encode()).decode()}})
    return RawMessage(payload=payload.encode("utf-8"))


def test_execute_happy_path_dispatches_to_correct_worker() -> None:
    contract = make_contract(parameters={"any": "thing"}, service_name="forecast")
    raw = _build_pubsub_raw_message(contract)

    dispatcher = InMemoryJobDispatcher()
    runner = SharedReceiverRunner(
        adapters=SharedReceiverAdapters(
            message=PubSubMessagePort(),
            authorizer=AllowAllPolicy(),
            job_dispatcher=dispatcher,
            observability=NullObservability(),
            clock=FrozenClock(now="2026-04-27T12:00:00Z"),
        ),
        scheme_allowlist=SchemeAllowlist(allowed={"gs", "bigquery", "secret"}),
        registry=ServiceRegistry(by_name={"forecast": "grabatus-forecasting-worker"}),
    )

    result = runner.execute(raw)

    assert result.status == "ok"
    assert result.error is None
    assert result.request_id == contract.envelope.request_id
    # dispatcher recorded the call with the right job_name
    assert len(dispatcher.dispatched) == 1
    assert dispatcher.dispatched[0].job_name == "grabatus-forecasting-worker"


def test_execute_serializes_full_validated_contract_into_payload() -> None:
    contract = make_contract(parameters={"x": 1}, service_name="forecast")
    raw = _build_pubsub_raw_message(contract)

    dispatcher = InMemoryJobDispatcher()
    runner = SharedReceiverRunner(
        adapters=SharedReceiverAdapters(
            message=PubSubMessagePort(),
            authorizer=AllowAllPolicy(),
            job_dispatcher=dispatcher,
            observability=NullObservability(),
            clock=FrozenClock(now="2026-04-27T12:00:00Z"),
        ),
        scheme_allowlist=SchemeAllowlist(allowed={"gs", "bigquery", "secret"}),
        registry=ServiceRegistry(by_name={"forecast": "grabatus-forecasting-worker"}),
    )

    runner.execute(raw)

    dispatched_payload = dispatcher.dispatched[0].payload
    parsed = json.loads(dispatched_payload.decode("utf-8"))
    assert parsed["service"]["name"] == "forecast"
    assert parsed["parameters"] == {"x": 1}
```

Note: `make_contract` may not currently take a `service_name` kwarg. If not, extend it (or use `make_service_descriptor(name="forecast")` and pass through). Also `make_contract` currently builds a `BaseServiceContract[FakeParameters]`; adapt it to accept `parameters: dict` and use `OpaqueServiceContract` when called this way (a small extension to the factory). The test code above assumes that extension; document it explicitly:

```python
# In src/grabatus_service_core/testing/factories.py — extend make_contract:
def make_contract(
    *,
    parameters: dict | BaseModel | None = None,
    service_name: str = "test-service",
    ...
):
    ...
```

- [ ] **Step 2: Run the happy-path test to verify it fails**

```bash
uv run pytest tests/unit/receiver/test_runner.py::test_execute_happy_path_dispatches_to_correct_worker -v
```

Expected: `AttributeError` because `execute` is not implemented.

- [ ] **Step 3: Implement `execute`**

Edit `src/grabatus_service_core/receiver/runner.py` — replace the `# Method body added in Task 4.2` placeholder with:

```python
    def execute(self, raw: RawMessage) -> ReceiverExecutionResult:
        """Decode → validate → authorize → resolve registry → dispatch."""
        from grabatus_service_core.contract.opaque import OpaqueServiceContract
        from grabatus_service_core.errors import GrabatusServiceError
        from grabatus_service_core.runner.steps import (
            authorize,
            decode,
            validate,
        )

        request_id: UUID | None = None
        with self.adapters.observability.span("shared_receiver.execute"):
            try:
                parsed = decode(raw=raw, message=self.adapters.message)
                validated = validate(
                    parsed=parsed, contract_type=OpaqueServiceContract,
                )
                request_id = validated.contract.envelope.request_id
                authorized = authorize(
                    validated=validated,
                    authorizer=self.adapters.authorizer,
                    scheme_allowlist=self.scheme_allowlist,
                )
                worker_job = self.registry.resolve(authorized.contract.service.name)
                payload_bytes = json.dumps(
                    authorized.contract.model_dump(mode="json"),
                ).encode("utf-8")
                dispatched = self.adapters.job_dispatcher.dispatch(
                    job_name=worker_job,
                    payload=payload_bytes,
                    request_id=request_id,
                )
                return ReceiverExecutionResult(
                    request_id=request_id,
                    status="ok",
                    dispatched_job_id=dispatched.job_id,
                    error=None,
                )
            except GrabatusServiceError as exc:
                self.adapters.observability.metric(
                    "shared_receiver.errors",
                    1.0,
                    error_code=exc.error_code,
                )
                return ReceiverExecutionResult(
                    request_id=request_id or _PLACEHOLDER_REQUEST_ID,
                    status="error",
                    dispatched_job_id=None,
                    error=exc,
                )
```

Then add at the bottom of the file:

```python
import json  # placed at the top in actual code; shown here for context
from grabatus_service_core.ports.values import RawMessage  # adjust as needed

_PLACEHOLDER_REQUEST_ID = UUID("00000000-0000-0000-0000-000000000000")
```

(Reorganize imports to the top of the file properly. The local import inside `execute` is not strictly needed if the cyclic-import concern is absent; refactor as required.)

- [ ] **Step 4: Run the happy-path tests**

```bash
uv run pytest tests/unit/receiver/test_runner.py::test_execute_happy_path_dispatches_to_correct_worker \
              tests/unit/receiver/test_runner.py::test_execute_serializes_full_validated_contract_into_payload -v
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/grabatus_service_core/receiver/runner.py \
        src/grabatus_service_core/testing/factories.py \
        tests/unit/receiver/test_runner.py
git commit -m "feat(receiver): SharedReceiverRunner.execute happy path"
```

---

## Task 4.3: Implement every error branch of `execute`

**Files:**
- Modify: `tests/unit/receiver/test_runner.py`

- [ ] **Step 1: Add error branch tests**

Append to `tests/unit/receiver/test_runner.py`:

```python
def _make_runner(*, registry: ServiceRegistry | None = None) -> SharedReceiverRunner:
    return SharedReceiverRunner(
        adapters=SharedReceiverAdapters(
            message=PubSubMessagePort(),
            authorizer=AllowAllPolicy(),
            job_dispatcher=InMemoryJobDispatcher(),
            observability=NullObservability(),
            clock=FrozenClock(now="2026-04-27T12:00:00Z"),
        ),
        scheme_allowlist=SchemeAllowlist(allowed={"gs", "bigquery", "secret"}),
        registry=registry or ServiceRegistry(by_name={"forecast": "fc-worker"}),
    )


def test_execute_returns_error_for_malformed_message() -> None:
    runner = _make_runner()
    raw = RawMessage(payload=b"not-json")

    result = runner.execute(raw)

    assert result.status == "error"
    assert isinstance(result.error, MalformedMessageError)
    assert result.dispatched_job_id is None
    # When the message is malformed, the request_id is the placeholder UUID.
    assert result.request_id == UUID("00000000-0000-0000-0000-000000000000")


def test_execute_returns_error_for_invalid_contract() -> None:
    runner = _make_runner()
    payload = json.dumps({
        "message": {
            "data": b64encode(json.dumps({"missing": "envelope"}).encode()).decode(),
        },
    })
    raw = RawMessage(payload=payload.encode("utf-8"))

    result = runner.execute(raw)

    assert result.status == "error"
    assert isinstance(result.error, InvalidContractError)


def test_execute_returns_unknown_service_error_when_name_not_in_registry() -> None:
    contract = make_contract(parameters={"x": 1}, service_name="ghost-service")
    raw = _build_pubsub_raw_message(contract)
    runner = _make_runner(registry=ServiceRegistry(by_name={"forecast": "fc-worker"}))

    result = runner.execute(raw)

    assert result.status == "error"
    assert isinstance(result.error, UnknownServiceError)
    assert "ghost-service" in str(result.error)
    assert result.dispatched_job_id is None


def test_execute_returns_error_when_authorizer_rejects_uri() -> None:
    from grabatus_service_core.testing.authorization import RejectAllPolicy

    contract = make_contract(parameters={"x": 1}, service_name="forecast")
    raw = _build_pubsub_raw_message(contract)
    # Use a deny-all authorizer for this branch.
    runner = SharedReceiverRunner(
        adapters=SharedReceiverAdapters(
            message=PubSubMessagePort(),
            authorizer=RejectAllPolicy(),
            job_dispatcher=InMemoryJobDispatcher(),
            observability=NullObservability(),
            clock=FrozenClock(now="2026-04-27T12:00:00Z"),
        ),
        scheme_allowlist=SchemeAllowlist(allowed={"gs", "bigquery", "secret"}),
        registry=ServiceRegistry(by_name={"forecast": "fc-worker"}),
    )

    result = runner.execute(raw)

    assert result.status == "error"
    assert isinstance(result.error, UnauthorizedUriError)
```

If `RejectAllPolicy` does not exist in `testing/authorization.py`, add it (a 5-line companion to `AllowAllPolicy`):

```python
# src/grabatus_service_core/testing/authorization.py
class RejectAllPolicy:
    def authorize(self, *, uri: str, identity: Identity) -> None:
        raise UnauthorizedUriError(f"RejectAllPolicy denies uri={uri!r}")
```

Re-export from `testing/__init__.py`.

- [ ] **Step 2: Run the error tests**

```bash
uv run pytest tests/unit/receiver/test_runner.py -v
```

Expected: all error-branch tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/grabatus_service_core/testing/authorization.py \
        src/grabatus_service_core/testing/__init__.py \
        tests/unit/receiver/test_runner.py
git commit -m "test(receiver): error branches of SharedReceiverRunner.execute"
```

---

# Checkpoint 5 — Settings + test factories

## Task 5.1: Wire `service_registry` into `Settings`

**Files:**
- Modify: `src/grabatus_service_core/settings.py`
- Modify: `tests/unit/test_settings.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/unit/test_settings.py`:

```python
def test_settings_parses_service_registry_env_var(monkeypatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.setenv("GBT_SERVICE_REGISTRY", "forecast:fc-worker,abtest:ab-worker")

    settings = Settings()

    assert settings.service_registry.resolve("forecast") == "fc-worker"
    assert settings.service_registry.resolve("abtest") == "ab-worker"


def test_settings_default_service_registry_is_empty(monkeypatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.delenv("GBT_SERVICE_REGISTRY", raising=False)

    settings = Settings()

    assert settings.service_registry.by_name == {}


def test_settings_rejects_malformed_registry_string(monkeypatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.setenv("GBT_SERVICE_REGISTRY", "not-a-pair")

    with pytest.raises(Exception, match=r"expected 'name:worker'"):
        Settings()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_settings.py -v
```

Expected: `AttributeError` or `ValidationError` because `service_registry` is not a field.

- [ ] **Step 3: Add the field + validator**

Edit `src/grabatus_service_core/settings.py`. Add the import at the top:

```python
from grabatus_service_core.receiver.registry import ServiceRegistry
```

Add the field inside the `Settings` class (alongside the other fields):

```python
    service_registry: Annotated[ServiceRegistry, NoDecode] = Field(
        default_factory=lambda: ServiceRegistry(by_name={}),
    )
```

Append a validator after `_split_csv`:

```python
    @field_validator("service_registry", mode="before")
    @classmethod
    def _parse_service_registry(cls, value: object) -> object:
        if isinstance(value, str):
            return ServiceRegistry.from_env_string(value)
        return value
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_settings.py -v
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/grabatus_service_core/settings.py tests/unit/test_settings.py
git commit -m "feat(settings): GBT_SERVICE_REGISTRY → ServiceRegistry"
```

---

## Task 5.2: Public test factories

**Files:**
- Modify: `src/grabatus_service_core/testing/__init__.py`
- Modify: `src/grabatus_service_core/testing/factories.py`
- Create: `tests/unit/testing/test_factories_opaque.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/testing/test_factories_opaque.py`:

```python
"""make_opaque_contract: factory used by downstream service tests."""

from grabatus_service_core.contract.opaque import OpaqueServiceContract
from grabatus_service_core.testing import make_opaque_contract


def test_make_opaque_contract_default_is_a_valid_contract() -> None:
    contract: OpaqueServiceContract = make_opaque_contract()
    assert contract.service.name == "test-service"
    # parameters default to an empty mapping
    assert contract.parameters.model_dump() == {}


def test_make_opaque_contract_accepts_parameters_dict() -> None:
    contract: OpaqueServiceContract = make_opaque_contract(parameters={"x": 1})
    assert contract.parameters.model_dump() == {"x": 1}


def test_make_opaque_contract_accepts_service_name_override() -> None:
    contract: OpaqueServiceContract = make_opaque_contract(service_name="forecast")
    assert contract.service.name == "forecast"


def test_in_memory_service_registry_round_trips() -> None:
    from grabatus_service_core.testing import InMemoryServiceRegistry

    registry = InMemoryServiceRegistry(by_name={"forecast": "fc"})
    assert registry.resolve("forecast") == "fc"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/testing/test_factories_opaque.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Add `make_opaque_contract` to `testing/factories.py`**

Edit `src/grabatus_service_core/testing/factories.py`. Append:

```python
from grabatus_service_core.contract.opaque import (
    OpaqueParameters,
    OpaqueServiceContract,
)


def make_opaque_contract(
    *,
    parameters: dict | None = None,
    service_name: str = "test-service",
    **kwargs,
) -> OpaqueServiceContract:
    """Factory for an OpaqueServiceContract used in receiver tests.

    Example:
        >>> contract = make_opaque_contract(parameters={"foo": "bar"}, service_name="forecast")
        >>> contract.service.name
        'forecast'
    """
    return OpaqueServiceContract(
        envelope=kwargs.get("envelope") or make_envelope(),
        identity=kwargs.get("identity") or make_identity(),
        references=kwargs.get("references") or make_references(),
        service=kwargs.get("service") or make_service_descriptor(name=service_name),
        inputs=kwargs.get("inputs") or [make_input_spec()],
        outputs=kwargs.get("outputs") or [make_output_spec()],
        callback=kwargs.get("callback") or make_callback(),
        parameters=OpaqueParameters.model_validate(parameters or {}),
    )
```

(`make_service_descriptor` may need a `name` kwarg — extend it if missing.)

- [ ] **Step 4: Add `InMemoryServiceRegistry` alias**

Edit `src/grabatus_service_core/testing/__init__.py`. Add:

```python
from grabatus_service_core.receiver.registry import (
    ServiceRegistry as InMemoryServiceRegistry,
)
from grabatus_service_core.testing.factories import make_opaque_contract
```

(`ServiceRegistry` is already in-memory by construction, so the alias is purely a naming convention for tests.)

Update `__all__`:

```python
__all__ = [
    ...,
    "InMemoryServiceRegistry",
    "make_opaque_contract",
]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/testing/test_factories_opaque.py -v
```

Expected: green.

- [ ] **Step 6: Run the full suite**

```bash
uv run pytest -x
```

Expected: green.

- [ ] **Step 7: Commit**

```bash
git add src/grabatus_service_core/testing/factories.py \
        src/grabatus_service_core/testing/__init__.py \
        tests/unit/testing/test_factories_opaque.py
git commit -m "feat(testing): InMemoryServiceRegistry + make_opaque_contract"
```

---

# Checkpoint 6 — `build_shared_receiver_app` + routes

## Task 6.1: Generalize `build_app` to accept any runner

**Files:**
- Modify: `src/grabatus_service_core/app/factory.py`
- Modify: `src/grabatus_service_core/app/routes.py`
- Modify: `tests/unit/app/test_factory.py` (if it exists; otherwise add to existing)

- [ ] **Step 1: Write the failing test**

The change must let `build_app(runner=...)` accept a runner whose `mode` may not be a `RuntimeMode` (e.g., the `SharedReceiverRunner` doesn't have a mode in the same sense). Add a regression test (assuming `tests/unit/app/test_factory.py` exists; if not, create it):

```python
"""build_app accepts any runner exposing .execute(raw) and an optional .mode."""

from grabatus_service_core.app.factory import build_app
from grabatus_service_core.testing import NullObservability


class _MinimalRunner:
    mode = "shared-receiver"

    def execute(self, raw):  # noqa: ANN001 — duck-typed for the test
        raise NotImplementedError("not exercised by build_app")


def test_build_app_accepts_a_minimal_runner() -> None:
    app = build_app(runner=_MinimalRunner(), observability=NullObservability())
    assert app.title == "grabatus-service-core"
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/unit/app/test_factory.py -v
```

Expected: existing strict typing on `runner: ServiceRunner[ParamsT]` may flag this in mypy, but at runtime it should already work (FastAPI doesn't introspect). If mypy complains, we need to widen the type to a Protocol.

- [ ] **Step 3: Introduce a `RunnerLike` protocol**

Edit `src/grabatus_service_core/app/factory.py`:

```python
"""build_app: assemble a FastAPI instance around any runner with .execute()."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from fastapi import FastAPI

from grabatus_service_core.app.exception_handler import register_exception_handlers
from grabatus_service_core.app.middleware import install_request_context_middleware
from grabatus_service_core.app.routes import make_router

if TYPE_CHECKING:
    from grabatus_service_core.ports.observability import ObservabilityPort
    from grabatus_service_core.ports.values import RawMessage


@runtime_checkable
class RunnerLike(Protocol):
    """Anything build_app can wrap. Both ServiceRunner and SharedReceiverRunner satisfy this."""

    def execute(self, raw: RawMessage) -> object: ...


def build_app(
    *,
    runner: RunnerLike,
    observability: ObservabilityPort,
) -> FastAPI:
    """Return a fully wired FastAPI app bound to the supplied runner."""
    app = FastAPI(title="grabatus-service-core", version="0.2.0")
    app.state.runner = runner
    app.state.observability = observability
    install_request_context_middleware(app)
    app.include_router(make_router())
    register_exception_handlers(app)
    return app
```

- [ ] **Step 4: Update `routes.py` to handle `ReceiverExecutionResult`**

Edit `src/grabatus_service_core/app/routes.py`. The `_result_to_json` function currently expects an `ExecutionResult`; extend it to also handle `ReceiverExecutionResult`:

```python
def _result_to_json(result) -> dict[str, Any]:  # union type; runtime-dispatched
    body: dict[str, Any] = {
        "status": result.status,
        "request_id": str(result.request_id),
    }
    if getattr(result, "error", None) is not None:
        body["error"] = _error_to_json(result.error)
    # ServiceRunner result fields:
    if getattr(result, "receipts", None) is not None:
        body["outputs"] = [
            {"role": role, "uri": r.uri, "bytes_written": r.bytes_written}
            for role, r in result.receipts.by_role.items()
        ]
    if getattr(result, "metadata", None):
        body["metadata"] = dict(result.metadata)
    if getattr(result, "webhook_ack", None) is not None:
        body["webhook_ack"] = {
            "http_status": result.webhook_ack.http_status,
            "response_body": result.webhook_ack.response_body,
        }
    # SharedReceiverRunner result field:
    if getattr(result, "dispatched_job_id", None) is not None:
        body["dispatched_job_id"] = result.dispatched_job_id
    return body
```

- [ ] **Step 5: Run tests to verify the change**

```bash
uv run pytest tests/unit/app -v
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/app/factory.py \
        src/grabatus_service_core/app/routes.py \
        tests/unit/app/
git commit -m "refactor(app): generalize build_app to accept SharedReceiverRunner"
```

---

## Task 6.2: Implement `build_shared_receiver_app`

**Files:**
- Create: `src/grabatus_service_core/receiver/app.py`
- Create: `tests/unit/receiver/test_app.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/receiver/test_app.py`:

```python
"""build_shared_receiver_app: end-to-end FastAPI wiring."""

import json
from base64 import b64encode

from fastapi.testclient import TestClient

from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
from grabatus_service_core.receiver.app import build_shared_receiver_app
from grabatus_service_core.receiver.registry import ServiceRegistry
from grabatus_service_core.receiver.runner import SharedReceiverAdapters
from grabatus_service_core.settings import Settings
from grabatus_service_core.testing import (
    AllowAllPolicy,
    FrozenClock,
    InMemoryJobDispatcher,
    NullObservability,
    make_opaque_contract,
)


def _settings(monkeypatch) -> Settings:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.setenv("GBT_SERVICE_REGISTRY", "forecast:fc-worker")
    return Settings()


def test_health_live_returns_ok(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    adapters = SharedReceiverAdapters(
        message=PubSubMessagePort(),
        authorizer=AllowAllPolicy(),
        job_dispatcher=InMemoryJobDispatcher(),
        observability=NullObservability(),
        clock=FrozenClock(now="2026-04-27T12:00:00Z"),
    )
    app = build_shared_receiver_app(settings=settings, adapters=adapters)
    client = TestClient(app)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_run_service_dispatches_via_registry(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    dispatcher = InMemoryJobDispatcher()
    adapters = SharedReceiverAdapters(
        message=PubSubMessagePort(),
        authorizer=AllowAllPolicy(),
        job_dispatcher=dispatcher,
        observability=NullObservability(),
        clock=FrozenClock(now="2026-04-27T12:00:00Z"),
    )
    app = build_shared_receiver_app(settings=settings, adapters=adapters)
    client = TestClient(app)

    contract = make_opaque_contract(parameters={"x": 1}, service_name="forecast")
    inner = contract.model_dump(mode="json")
    pubsub_envelope = {
        "message": {
            "data": b64encode(json.dumps(inner).encode("utf-8")).decode("ascii"),
        },
    }

    response = client.post("/run_service", json=pubsub_envelope)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "dispatched_job_id" in body
    assert len(dispatcher.dispatched) == 1
    assert dispatcher.dispatched[0].job_name == "fc-worker"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/receiver/test_app.py -v
```

Expected: `ImportError` for `build_shared_receiver_app`.

- [ ] **Step 3: Implement `build_shared_receiver_app`**

Create `src/grabatus_service_core/receiver/app.py`:

```python
"""build_shared_receiver_app: FastAPI factory for the shared receiver."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grabatus_service_core.adapters.clock import SystemClock
from grabatus_service_core.app import build_app
from grabatus_service_core.receiver.runner import (
    SharedReceiverAdapters,
    SharedReceiverRunner,
)
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist

if TYPE_CHECKING:
    from fastapi import FastAPI

    from grabatus_service_core.settings import Settings


def build_shared_receiver_app(
    *,
    settings: Settings,
    adapters: SharedReceiverAdapters,
) -> FastAPI:
    """Wire a FastAPI app around a SharedReceiverRunner.

    Example:
        >>> from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
        >>> from grabatus_service_core.testing import (
        ...     AllowAllPolicy, FrozenClock, InMemoryJobDispatcher, NullObservability,
        ... )
        >>> settings = Settings()  # reads env vars
        >>> adapters = SharedReceiverAdapters(
        ...     message=PubSubMessagePort(),
        ...     authorizer=AllowAllPolicy(),
        ...     job_dispatcher=InMemoryJobDispatcher(),
        ...     observability=NullObservability(),
        ...     clock=FrozenClock(now="2026-04-27T12:00:00Z"),
        ... )
        >>> app = build_shared_receiver_app(settings=settings, adapters=adapters)
    """
    runner = SharedReceiverRunner(
        adapters=adapters,
        scheme_allowlist=SchemeAllowlist(allowed=set(settings.allowed_schemes)),
        registry=settings.service_registry,
    )
    return build_app(runner=runner, observability=adapters.observability)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/receiver/test_app.py -v
```

Expected: green.

- [ ] **Step 5: Re-export from `receiver/__init__.py`**

Edit `src/grabatus_service_core/receiver/__init__.py`:

```python
"""Shared receiver: stateless front door for all Grabatus computational services."""

from grabatus_service_core.receiver.app import build_shared_receiver_app
from grabatus_service_core.receiver.registry import ServiceRegistry
from grabatus_service_core.receiver.runner import (
    ReceiverExecutionResult,
    SharedReceiverAdapters,
    SharedReceiverRunner,
)

__all__ = [
    "ReceiverExecutionResult",
    "ServiceRegistry",
    "SharedReceiverAdapters",
    "SharedReceiverRunner",
    "build_shared_receiver_app",
]
```

- [ ] **Step 6: Commit**

```bash
git add src/grabatus_service_core/receiver/ tests/unit/receiver/test_app.py
git commit -m "feat(receiver): build_shared_receiver_app FastAPI factory"
```

---

## Task 6.3: Integration test (TestClient + InMemoryJobDispatcher)

**Files:**
- Create: `tests/integration/test_shared_receiver_e2e.py`

- [ ] **Step 1: Write the integration test**

Create `tests/integration/test_shared_receiver_e2e.py`:

```python
"""End-to-end shared receiver: HTTP push → dispatch."""

import json
from base64 import b64encode

import pytest
from fastapi.testclient import TestClient

from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
from grabatus_service_core.receiver.app import build_shared_receiver_app
from grabatus_service_core.receiver.runner import SharedReceiverAdapters
from grabatus_service_core.settings import Settings
from grabatus_service_core.testing import (
    AllowAllPolicy,
    FrozenClock,
    InMemoryJobDispatcher,
    NullObservability,
    make_opaque_contract,
)


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("GBT_RUNTIME_MODE", "receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.setenv(
        "GBT_SERVICE_REGISTRY",
        "forecast:grabatus-forecasting-worker,abtest:grabatus-abtest-worker",
    )
    settings = Settings()  # type: ignore[call-arg]  # pydantic-settings reads env
    return build_shared_receiver_app(
        settings=settings,
        adapters=SharedReceiverAdapters(
            message=PubSubMessagePort(),
            authorizer=AllowAllPolicy(),
            job_dispatcher=InMemoryJobDispatcher(),
            observability=NullObservability(),
            clock=FrozenClock(now="2026-04-27T12:00:00Z"),
        ),
    )


def _build_pubsub_payload(contract) -> dict:
    return {
        "message": {
            "data": b64encode(
                json.dumps(contract.model_dump(mode="json")).encode("utf-8"),
            ).decode("ascii"),
        },
    }


def test_e2e_forecast_envelope_dispatches_to_forecast_worker(app) -> None:
    client = TestClient(app)

    contract = make_opaque_contract(parameters={"x": 1}, service_name="forecast")
    response = client.post("/run_service", json=_build_pubsub_payload(contract))

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    dispatcher = app.state.runner.adapters.job_dispatcher
    assert dispatcher.dispatched[0].job_name == "grabatus-forecasting-worker"


def test_e2e_abtest_envelope_dispatches_to_abtest_worker(app) -> None:
    client = TestClient(app)

    contract = make_opaque_contract(parameters={"x": 1}, service_name="abtest")
    response = client.post("/run_service", json=_build_pubsub_payload(contract))

    assert response.status_code == 200
    dispatcher = app.state.runner.adapters.job_dispatcher
    assert dispatcher.dispatched[0].job_name == "grabatus-abtest-worker"


def test_e2e_unknown_service_is_rejected_gracefully(app) -> None:
    client = TestClient(app)

    contract = make_opaque_contract(parameters={"x": 1}, service_name="ghost")
    response = client.post("/run_service", json=_build_pubsub_payload(contract))

    assert response.status_code == 200  # Pub/Sub ack — do not retry
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["error_code"] == "unknown_service"
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/integration/test_shared_receiver_e2e.py -v
```

Expected: green.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_shared_receiver_e2e.py
git commit -m "test(integration): shared receiver end-to-end via TestClient"
```

---

## Task 6.4: Property test for registry × envelope generation

**Files:**
- Create: `tests/property/test_shared_receiver.py`

- [ ] **Step 1: Write the property test**

Create `tests/property/test_shared_receiver.py`:

```python
"""Hypothesis: any registry × envelope combination either dispatches or errors clearly."""

from hypothesis import given
from hypothesis import strategies as st

from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
from grabatus_service_core.errors import UnknownServiceError
from grabatus_service_core.receiver.registry import ServiceRegistry
from grabatus_service_core.receiver.runner import (
    SharedReceiverAdapters,
    SharedReceiverRunner,
)
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.testing import (
    AllowAllPolicy,
    FrozenClock,
    InMemoryJobDispatcher,
    NullObservability,
    make_opaque_contract,
)
import json
from base64 import b64encode


_SERVICE_NAMES = st.text(
    alphabet=st.characters(min_codepoint=ord("a"), max_codepoint=ord("z")),
    min_size=1,
    max_size=20,
)
_REGISTRY_PAIRS = st.dictionaries(
    keys=_SERVICE_NAMES,
    values=st.text(min_size=1, max_size=40),
    min_size=0,
    max_size=5,
)


@given(registry_dict=_REGISTRY_PAIRS, envelope_service=_SERVICE_NAMES)
def test_dispatch_is_deterministic_with_respect_to_registry(
    registry_dict, envelope_service,
) -> None:
    contract = make_opaque_contract(service_name=envelope_service, parameters={})
    raw_payload = json.dumps({
        "message": {
            "data": b64encode(
                json.dumps(contract.model_dump(mode="json")).encode("utf-8"),
            ).decode("ascii"),
        },
    }).encode("utf-8")

    from grabatus_service_core.ports.values import RawMessage

    runner = SharedReceiverRunner(
        adapters=SharedReceiverAdapters(
            message=PubSubMessagePort(),
            authorizer=AllowAllPolicy(),
            job_dispatcher=InMemoryJobDispatcher(),
            observability=NullObservability(),
            clock=FrozenClock(now="2026-04-27T12:00:00Z"),
        ),
        scheme_allowlist=SchemeAllowlist(allowed={"gs", "bigquery", "secret"}),
        registry=ServiceRegistry(by_name=registry_dict),
    )

    result = runner.execute(RawMessage(payload=raw_payload))

    if envelope_service in registry_dict:
        assert result.status == "ok"
        assert result.dispatched_job_id is not None
    else:
        assert result.status == "error"
        assert isinstance(result.error, UnknownServiceError)
```

- [ ] **Step 2: Run the property test**

```bash
uv run pytest tests/property/test_shared_receiver.py -v
```

Expected: green (Hypothesis exercises ~100 random combinations).

- [ ] **Step 3: Commit**

```bash
git add tests/property/test_shared_receiver.py
git commit -m "test(property): shared receiver dispatch invariants"
```

---

# Checkpoint 7 — CLI + Dockerfile

## Task 7.1: `cli.main()` entry point

**Files:**
- Create: `src/grabatus_service_core/receiver/cli.py`
- Create: `tests/unit/receiver/test_cli.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/receiver/test_cli.py`:

```python
"""cli.main: bootstraps adapters, builds app, hands to uvicorn."""

import pytest


def test_main_reads_settings_and_runs_uvicorn(monkeypatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.setenv("GBT_SERVICE_REGISTRY", "forecast:fc")
    monkeypatch.setenv("GBT_GCP_PROJECT", "grabatus")
    monkeypatch.setenv("GBT_GCP_REGION", "us-east1")
    monkeypatch.setenv("PORT", "8080")

    captured: dict = {}

    def _fake_run(app, *, host: str, port: int) -> None:
        captured["app"] = app
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setattr("uvicorn.run", _fake_run)

    # Stub the CloudRunJobsDispatcher so we don't touch GCP.
    from grabatus_service_core.testing import InMemoryJobDispatcher

    monkeypatch.setattr(
        "grabatus_service_core.receiver.cli.CloudRunJobsDispatcher",
        lambda **kwargs: InMemoryJobDispatcher(),
    )

    from grabatus_service_core.receiver.cli import main

    main()

    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 8080
    # The wired app must be a FastAPI with our title.
    assert captured["app"].title == "grabatus-service-core"


def test_main_defaults_port_to_8080_when_env_unset(monkeypatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.setenv("GBT_SERVICE_REGISTRY", "forecast:fc")
    monkeypatch.setenv("GBT_GCP_PROJECT", "grabatus")
    monkeypatch.setenv("GBT_GCP_REGION", "us-east1")
    monkeypatch.delenv("PORT", raising=False)

    captured: dict = {}

    def _fake_run(app, *, host: str, port: int) -> None:
        captured["port"] = port

    from grabatus_service_core.testing import InMemoryJobDispatcher

    monkeypatch.setattr("uvicorn.run", _fake_run)
    monkeypatch.setattr(
        "grabatus_service_core.receiver.cli.CloudRunJobsDispatcher",
        lambda **kwargs: InMemoryJobDispatcher(),
    )

    from grabatus_service_core.receiver.cli import main

    main()

    assert captured["port"] == 8080
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/receiver/test_cli.py -v
```

Expected: `ImportError` for `cli.main`.

- [ ] **Step 3: Settings additions for `gcp_project` and `gcp_region`**

Note that the test uses `GBT_GCP_PROJECT` and `GBT_GCP_REGION`. Inspect `Settings`. If they're missing, add fields:

```python
    gcp_project: str | None = Field(default=None)
    gcp_region: str | None = Field(default=None)
```

Add a corresponding `test_settings.py` regression test:

```python
def test_settings_reads_gcp_project_and_region(monkeypatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.setenv("GBT_GCP_PROJECT", "grabatus")
    monkeypatch.setenv("GBT_GCP_REGION", "us-east1")
    settings = Settings()
    assert settings.gcp_project == "grabatus"
    assert settings.gcp_region == "us-east1"
```

- [ ] **Step 4: Implement `cli.main`**

Create `src/grabatus_service_core/receiver/cli.py`:

```python
"""Entry point invoked by the ``grabatus-receiver`` console script."""

from __future__ import annotations

import os

import uvicorn

from grabatus_service_core.adapters.clock import SystemClock
from grabatus_service_core.adapters.job_dispatcher_cloud_run import (
    CloudRunJobsDispatcher,
)
from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
from grabatus_service_core.adapters.observability_otel import (
    OpenTelemetryObservability,
)
from grabatus_service_core.adapters.tenant_prefix_policy import TenantPrefixPolicy
from grabatus_service_core.receiver.app import build_shared_receiver_app
from grabatus_service_core.receiver.runner import SharedReceiverAdapters
from grabatus_service_core.settings import Settings


def main() -> None:
    """Read env-driven settings, build the receiver app, hand off to uvicorn.

    Example local invocation::

        GBT_RUNTIME_MODE=receiver \\
        GBT_ENV=local \\
        SERVICE_SECRET_KEY=dev \\
        GBT_SERVICE_REGISTRY=forecast:grabatus-forecasting-worker \\
        GBT_GCP_PROJECT=grabatus \\
        GBT_GCP_REGION=us-east1 \\
        grabatus-receiver
    """
    settings = Settings()  # type: ignore[call-arg]  # pydantic-settings reads env
    adapters = SharedReceiverAdapters(
        message=PubSubMessagePort(),
        authorizer=TenantPrefixPolicy(),
        job_dispatcher=CloudRunJobsDispatcher(
            project=settings.gcp_project,
            region=settings.gcp_region,
        ),
        observability=OpenTelemetryObservability(),
        clock=SystemClock(),
    )
    app = build_shared_receiver_app(settings=settings, adapters=adapters)
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104 — Cloud Run requires 0.0.0.0
```

(`TenantPrefixPolicy` may not yet exist in `adapters/`. If not, the user-supplied `AllowAllPolicy` from `testing/` is the production fallback for now — defer the production policy to the same plan checkpoint as before in the spec.)

- [ ] **Step 5: Add CLI script to `pyproject.toml`**

Edit `pyproject.toml`. Add:

```toml
[project.scripts]
grabatus-receiver = "grabatus_service_core.receiver.cli:main"
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/unit/receiver/test_cli.py -v
```

Expected: green.

- [ ] **Step 7: Commit**

```bash
git add src/grabatus_service_core/receiver/cli.py \
        src/grabatus_service_core/settings.py \
        pyproject.toml uv.lock \
        tests/unit/receiver/test_cli.py \
        tests/unit/test_settings.py
git commit -m "feat(receiver): grabatus-receiver CLI entry point"
```

---

## Task 7.2: `Dockerfile.receiver`

**Files:**
- Create: `Dockerfile.receiver`

- [ ] **Step 1: Create the Dockerfile**

Create `Dockerfile.receiver` at the repo root:

```dockerfile
# Multi-stage build for the shared receiver Cloud Run Service.
# Image: grabatus-service-core:vX.Y.Z

FROM python:3.12-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
RUN pip install uv
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
RUN uv build --wheel --out-dir /tmp/wheels

FROM python:3.12-slim AS runtime
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 1000 grabatus
USER grabatus
WORKDIR /home/grabatus
COPY --from=builder /tmp/wheels/ /tmp/wheels/
RUN pip install --user /tmp/wheels/*.whl && rm -rf /tmp/wheels
ENV PATH="/home/grabatus/.local/bin:${PATH}"
EXPOSE 8080
CMD ["grabatus-receiver"]
```

- [ ] **Step 2: Build the image locally**

```bash
docker build -f Dockerfile.receiver -t grabatus-service-core:dev .
```

Expected: build succeeds, image ~150-200 MiB.

- [ ] **Step 3: Smoke-test the container**

```bash
docker run --rm \
  -e GBT_RUNTIME_MODE=receiver \
  -e GBT_ENV=local \
  -e SERVICE_SECRET_KEY=dev \
  -e GBT_SERVICE_REGISTRY=forecast:fc-worker \
  -e GBT_GCP_PROJECT=grabatus \
  -e GBT_GCP_REGION=us-east1 \
  -p 8080:8080 \
  grabatus-service-core:dev &
sleep 3
curl -fsS http://localhost:8080/health/live
docker kill $(docker ps -q --filter ancestor=grabatus-service-core:dev)
```

Expected: `curl` returns `{"status":"ok"}`. (The container will fail to dispatch jobs because GCP credentials are absent, but `/health/live` doesn't need them.)

If startup fails because `CloudRunJobsDispatcher.__init__` requires real credentials, the smoke test reveals a gap: the constructor should defer credential acquisition to the first `dispatch` call. Fix in `adapters/job_dispatcher_cloud_run.py` if needed.

- [ ] **Step 4: Trivy scan**

```bash
trivy image --severity HIGH,CRITICAL --exit-code 1 grabatus-service-core:dev
```

Expected: zero HIGH or CRITICAL vulnerabilities.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile.receiver
git commit -m "build: Dockerfile.receiver for shared receiver image"
```

---

# Checkpoint 8 — Documentation, CHANGELOG, version bump, mutation gate

## Task 8.1: Architecture documentation

**Files:**
- Modify: `docs/architecture.rst`
- Create: `docs/tutorials/deploying_the_shared_receiver.rst`
- Modify: `docs/index.rst`

Per the user's documentation preferences (saved as memory `feedback_documentation.md`): English only, simple language, examples in confusing places, default Sphinx theme. The lib's existing Furo + i18n setup is preserved (changing it is out of scope), but **new content** added in this task is English-only with extra examples.

- [ ] **Step 1: Add the architecture subsection**

Append to `docs/architecture.rst`:

```rst
Shared Receiver
~~~~~~~~~~~~~~~

A single Cloud Run Service receives Pub/Sub push messages for every
Grabatus computational service. It validates the envelope, authorizes
the URIs, looks up the right Cloud Run Job to handle the request, and
dispatches the work. The receiver itself never touches storage or
secrets.

Why one shared receiver instead of one receiver per service?

* Adding a new service is one new worker plus one entry in the
  ``GBT_SERVICE_REGISTRY`` env var. No new receiver to deploy.
* Receiver code has no business logic — it is pure infrastructure that
  validates the envelope schema (which is shared across services).
* One warm instance ($5–10/month) replaces N warm instances.

How the receiver decides which worker to invoke::

   envelope.service.name = "forecast"
                │
                ▼
   ServiceRegistry.resolve("forecast") → "grabatus-forecasting-worker"
                │
                ▼
   CloudRunJobsDispatcher.dispatch(
       job_name="grabatus-forecasting-worker",
       payload=<full validated contract bytes>,
       request_id=<envelope.request_id>,
   )

The registry is loaded once from the ``GBT_SERVICE_REGISTRY``
environment variable at process start. To add a new service,
update the env var and restart::

   GBT_SERVICE_REGISTRY=forecast:grabatus-forecasting-worker,abtest:grabatus-abtest-worker
```

- [ ] **Step 2: Create the deployment tutorial**

Create `docs/tutorials/deploying_the_shared_receiver.rst`:

```rst
Deploying the Shared Receiver
=============================

The shared receiver is a Cloud Run Service built from
``Dockerfile.receiver`` in this repository. Deploy it once per GCP
project; every Grabatus computational service routes through it.

Prerequisites
-------------

* A GCP project with Cloud Run, Pub/Sub, and Secret Manager enabled.
* A worker Cloud Run Job already deployed (e.g.
  ``grabatus-forecasting-worker``).
* A Pub/Sub topic and push subscription that point at the receiver
  URL.

Build and push the image
------------------------

.. code-block:: bash

   docker build -f Dockerfile.receiver -t \
     us-east1-docker.pkg.dev/grabatus/services/grabatus-service-core:v0.2.0 .
   docker push \
     us-east1-docker.pkg.dev/grabatus/services/grabatus-service-core:v0.2.0

Deploy to Cloud Run
-------------------

.. code-block:: bash

   gcloud run deploy grabatus-receiver \\
     --image=us-east1-docker.pkg.dev/grabatus/services/grabatus-service-core:v0.2.0 \\
     --region=us-east1 \\
     --service-account=grabatus-receiver@grabatus.iam.gserviceaccount.com \\
     --min-instances=1 \\
     --max-instances=10 \\
     --concurrency=80 \\
     --timeout=60s \\
     --set-env-vars=GBT_RUNTIME_MODE=receiver,GBT_ENV=production,GBT_GCP_PROJECT=grabatus,GBT_GCP_REGION=us-east1 \\
     --set-env-vars=GBT_SERVICE_REGISTRY=forecast:grabatus-forecasting-worker

Add a new service
-----------------

Update the registry env var on the existing receiver service. No new
deploy required:

.. code-block:: bash

   gcloud run services update grabatus-receiver \\
     --region=us-east1 \\
     --update-env-vars=GBT_SERVICE_REGISTRY=forecast:grabatus-forecasting-worker,abtest:grabatus-abtest-worker

After ``gcloud`` finishes (about 30 seconds), the receiver is ready
to dispatch ``abtest`` envelopes to the new worker.

Verify the deployment
---------------------

.. code-block:: bash

   curl -fsS https://grabatus-receiver-<hash>.a.run.app/health/live
   # → {"status":"ok"}

Send a synthetic envelope (development only — production traffic
arrives via Pub/Sub):

.. code-block:: bash

   gcloud pubsub topics publish forecast-trigger \\
     --message='{"envelope":{...},"identity":{...},"service":{"name":"forecast",...},...}'

Observe the dispatch in the receiver logs::

   gcloud logging read 'resource.type=cloud_run_revision AND
     resource.labels.service_name=grabatus-receiver' --limit=20

Troubleshooting
---------------

``error_code: unknown_service``
   The envelope's ``service.name`` is not in the registry. Update
   ``GBT_SERVICE_REGISTRY`` and redeploy.

``error_code: unauthorized_uri``
   A URI in the envelope failed the authorization policy. Check the
   tenant prefix and bucket scoping.

``error_code: malformed_message``
   The Pub/Sub data field is not valid base64-encoded JSON. Check
   the publisher.
```

- [ ] **Step 3: Link the new pages from `docs/index.rst`**

Edit `docs/index.rst`. In the appropriate `toctree` block, add `tutorials/deploying_the_shared_receiver`. Preserve the existing structure.

- [ ] **Step 4: Build the docs**

```bash
uv run sphinx-build -W -b html docs/ docs/_build/
```

Expected: zero warnings, zero errors.

- [ ] **Step 5: Commit**

```bash
git add docs/architecture.rst \
        docs/tutorials/deploying_the_shared_receiver.rst \
        docs/index.rst
git commit -m "docs: shared receiver architecture + deployment tutorial"
```

---

## Task 8.2: CHANGELOG and version bump

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `pyproject.toml`

- [ ] **Step 1: Update CHANGELOG**

Edit `CHANGELOG.md`. Replace the `## [Unreleased]` section with a new `## [0.2.0] — 2026-04-27` (or whatever today's date is at completion time):

```markdown
## [Unreleased]

## [0.2.0] — 2026-04-27

### Added
- `receiver/` module: `ServiceRegistry`, `SharedReceiverRunner`,
  `build_shared_receiver_app()`, `cli.main` entry point.
- `OpaqueServiceContract`: receiver-side contract that validates
  envelope/identity/I-O without locking down `parameters`.
- `CompressedStorage` decorator: gzip and zstd codecs over any inner
  `StoragePort`.
- `UnknownServiceError`: raised when `envelope.service.name` is not
  registered with a worker.
- `InMemoryServiceRegistry` and `make_opaque_contract` test helpers.
- `Dockerfile.receiver` and the `grabatus-receiver` console script.
- `Settings.service_registry`, `Settings.gcp_project`,
  `Settings.gcp_region` fields.
- `InputSpec.compression` field (mirrors `OutputSpec.compression`).

### Changed
- `build_app()` now accepts any `RunnerLike` protocol (both
  `ServiceRunner` and `SharedReceiverRunner` satisfy it).
- `_result_to_json` in routes handles `ReceiverExecutionResult` in
  addition to `ExecutionResult`.

### Dependencies
- Added `zstandard >= 0.22` to runtime dependencies.

## [0.1.0] — TBD
```

- [ ] **Step 2: Bump version in `pyproject.toml`**

Edit `pyproject.toml`. Change `version = "0.1.0"` to `version = "0.2.0"`. Re-run `uv lock` to refresh the lock file.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md pyproject.toml uv.lock
git commit -m "chore: bump version to 0.2.0"
```

---

## Task 8.3: Final mutation gate

**Files:**
- (no source changes — this is a verification step)

- [ ] **Step 1: Run the full test suite**

```bash
uv run pytest -x
```

Expected: green.

- [ ] **Step 2: Run coverage check**

```bash
uv run pytest --cov-fail-under=100
```

Expected: 100% line and branch coverage.

- [ ] **Step 3: Run the pragma comment audit**

```bash
uv run python scripts/check_pragma_comments.py
```

Expected: every `# pragma: no cover` and `# pragma: no mutate` has an inline justification comment.

- [ ] **Step 4: Run mutation testing**

```bash
uv run mutmut run --runner "uv run pytest tests/unit tests/property -x -q"
```

This may take 30+ minutes for the entire library.

- [ ] **Step 5: Verify mutation score**

```bash
uv run python scripts/check_mutation_score.py --min=95
```

Expected: mutation score ≥ 95% (lib gate, unchanged from v0.1.0).

If mutants survive, inspect each:
- If the mutant is genuinely undetectable, mark it explicitly with `# pragma: no mutate — equivalent: <proof>` in the source.
- If the mutant reveals a missing assertion, add the assertion to the appropriate test.
- If the mutant reveals dead code, remove the dead code.

- [ ] **Step 6: Build Sphinx docs and re-verify**

```bash
uv run sphinx-build -W -b html docs/ docs/_build/
```

Expected: zero warnings.

- [ ] **Step 7: Trivy scan of the receiver image**

```bash
docker build -f Dockerfile.receiver -t grabatus-service-core:v0.2.0-rc .
trivy image --severity HIGH,CRITICAL --exit-code 1 grabatus-service-core:v0.2.0-rc
```

Expected: clean scan.

- [ ] **Step 8: Final commit (if any documentation tweaks emerged)**

```bash
git status
# If any files were touched during the gate runs:
git add -A
git commit -m "chore: tidy up after final v0.2.0 quality gates"
```

- [ ] **Step 9: Tag locally**

```bash
git tag -a v0.2.0 -m "v0.2.0: shared receiver, OpaqueServiceContract, CompressedStorage"
```

(Do NOT push the tag yet — that triggers the Release workflow, which is Phase 2 of Plano 2 and outside this plan's scope.)

- [ ] **Step 10: Final state check**

```bash
git log --oneline -20
git status
```

Expected: clean working tree, ~25-35 new commits ahead of `main`, tag `v0.2.0` pointing at HEAD.

---

# Done

The lib is now ready for Phase 2 of Plano 2 (release infrastructure: GitHub Actions Release workflow + Artifact Registry push + Workload Identity Federation), which gets its own plan document.

**Definition of done for Plan 2A:**
- All 8 checkpoints' commits are on the branch.
- `uv run pytest -x` is green.
- 100% line and branch coverage.
- ≥ 95% mutation score.
- `sphinx-build -W` builds clean.
- Trivy scan on the receiver image is clean.
- Tag `v0.2.0` exists locally.
- Both `grabatus-service-core/` and `services/grabatus-forecasting/` (the latter via its `[tool.uv.sources]` editable path) can `import grabatus_service_core.receiver` without errors.
