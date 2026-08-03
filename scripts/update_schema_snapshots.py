"""Regenerate the pinned JSON Schema snapshots under ``tests/contract_compatibility/snapshots/``.

Run this when (and only when) a contract is intentionally changed.
The CI test suite reads the snapshot files and fails on any drift.

Usage::

    uv run python scripts/update_schema_snapshots.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.contract_compatibility._harness import SnapshotContract  # noqa: E402

from grabatus_service_core.contract.readout import ModelReadout  # noqa: E402

_SNAPSHOT_ROOT = _REPO_ROOT / "tests" / "contract_compatibility" / "snapshots"

_TARGETS: tuple[tuple[type[BaseModel], Path], ...] = (
    (SnapshotContract, _SNAPSHOT_ROOT / "v1.0" / "base_service_contract.schema.json"),
    (ModelReadout, _SNAPSHOT_ROOT / "v1.1" / "model_readout.schema.json"),
)


def _render_schema(model: type[BaseModel]) -> str:
    return json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    for model, path in _TARGETS:
        path.parent.mkdir(parents=True, exist_ok=True)
        rendered = _render_schema(model)
        path.write_text(rendered, encoding="utf-8")
        print(f"wrote {path} ({len(rendered)} bytes)")
    return 0


if __name__ == "__main__":  # pragma: no cover  # CLI entry only
    raise SystemExit(main())
