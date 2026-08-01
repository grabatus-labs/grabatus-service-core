"""Snapshot test: the ModelReadout JSON Schema is byte-stable.

Any intentional change requires regenerating the snapshot via
``scripts/update_schema_snapshots.py``, which forces the reviewer to
acknowledge the schema change in the same pull request.
"""

from __future__ import annotations

import json
from pathlib import Path

from grabatus_service_core.contract.readout import ModelReadout

_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent / "snapshots" / "v1.1" / "model_readout.schema.json"
)


def test_model_readout_json_schema_matches_snapshot() -> None:
    expected = _SNAPSHOT_PATH.read_text(encoding="utf-8")
    actual = json.dumps(ModelReadout.model_json_schema(), indent=2, sort_keys=True) + "\n"

    assert actual == expected, (
        "ModelReadout JSON Schema drifted from snapshot. If the change is "
        "intentional, run `uv run python scripts/update_schema_snapshots.py` "
        "and commit."
    )
