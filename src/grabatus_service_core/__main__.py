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

from grabatus_service_core.ports.values import RawMessage

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
    payload_str = os.environ.get(_PAYLOAD_ENV_VAR)
    if payload_str is None:
        raise EntryPointError(
            f"{_PAYLOAD_ENV_VAR} env var is required for worker mode",
        )
    raw = RawMessage(payload=payload_str.encode("utf-8"))
    result = runner.execute(raw)
    return 0 if result.status == "ok" else 1


def _load_compute_factory() -> Any:  # noqa: ANN401  # pragma: no cover  # service-side
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
