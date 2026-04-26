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
    # Snapshot sys.modules so we can restore it and avoid polluting other tests.
    original_modules = dict(sys.modules)
    try:
        # Drop already-loaded modules — both grabatus_service_core itself and the
        # forbidden cloud SDKs (other tests may have loaded them) — so we can
        # observe what a *fresh* import of grabatus_service_core pulls in.
        for module_name in list(sys.modules):
            if module_name.startswith("grabatus_service_core") or any(
                module_name == forbidden or module_name.startswith(forbidden + ".")
                for forbidden in _FORBIDDEN_TOP_LEVEL_IMPORTS
            ):
                del sys.modules[module_name]
        importlib.import_module("grabatus_service_core")
        for forbidden in _FORBIDDEN_TOP_LEVEL_IMPORTS:
            assert forbidden not in sys.modules, (
                f"Top-level import of grabatus_service_core pulled in "
                f"{forbidden!r}, which is forbidden in Sub-Plan 1A."
            )
    finally:
        sys.modules.clear()
        sys.modules.update(original_modules)


def test_top_level_exposes_version() -> None:
    import grabatus_service_core  # noqa: PLC0415

    assert grabatus_service_core.__version__ == "0.1.0"


def test_top_level_re_exports_contract_classes() -> None:
    from grabatus_service_core import (  # noqa: PLC0415
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
    from grabatus_service_core import (  # noqa: PLC0415
        GrabatusServiceError,
        UnauthorizedUriError,
    )

    assert issubclass(UnauthorizedUriError, GrabatusServiceError)


def test_testing_subpackage_is_importable_separately() -> None:
    from grabatus_service_core import testing  # noqa: PLC0415

    assert hasattr(testing, "InMemoryStorage")
    assert hasattr(testing, "make_contract")
