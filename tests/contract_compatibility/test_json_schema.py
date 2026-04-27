"""Snapshot test: BaseServiceContract JSON Schema is byte-stable.

Any intentional change to the contract requires regenerating the
snapshot via ``scripts/update_schema_snapshots.py``. The CI suite
fails on any drift, forcing reviewers to acknowledge the schema
change in the same pull request as the code change.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.contract_compatibility._harness import SnapshotContract

_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent / "snapshots" / "v1.0" / "base_service_contract.schema.json"
)


def test_base_service_contract_json_schema_matches_snapshot() -> None:
    expected = _SNAPSHOT_PATH.read_text(encoding="utf-8")
    actual_schema = SnapshotContract.model_json_schema()
    actual = json.dumps(actual_schema, indent=2, sort_keys=True) + "\n"

    assert actual == expected, (
        "BaseServiceContract JSON Schema drifted from snapshot. "
        "If the change is intentional, run "
        "`uv run python scripts/update_schema_snapshots.py` and commit."
    )
