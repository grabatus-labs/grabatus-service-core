"""Regenerate the pinned JSON Schema snapshots under ``tests/contract_compatibility/snapshots/``.

Run this when (and only when) the contract is intentionally changed.
The CI test suite reads the snapshot files and fails on any drift.

Usage::

    uv run python scripts/update_schema_snapshots.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.contract_compatibility._harness import SnapshotContract  # noqa: E402

_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent
    / "tests"
    / "contract_compatibility"
    / "snapshots"
    / "v1.0"
    / "base_service_contract.schema.json"
)


def _render_schema() -> str:
    schema = SnapshotContract.model_json_schema()
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main() -> int:
    _SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rendered = _render_schema()
    _SNAPSHOT_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {_SNAPSHOT_PATH} ({len(rendered)} bytes)")
    return 0


if __name__ == "__main__":  # pragma: no cover  # CLI entry only
    raise SystemExit(main())
