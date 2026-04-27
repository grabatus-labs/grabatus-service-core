"""Fixture tests: every JSON sample under fixtures/v1.0 behaves as labelled.

``valid/*.json`` files must validate cleanly against ``SnapshotContract``.
``invalid/*.json`` files must raise ``ValidationError``. Adding a new
sample is the canonical way to lock in a regression: drop the JSON in
the right folder and the suite picks it up automatically.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.contract_compatibility._harness import SnapshotContract

_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "v1.0"
_VALID_DIR = _FIXTURE_ROOT / "valid"
_INVALID_DIR = _FIXTURE_ROOT / "invalid"


def _collect(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.json"))


@pytest.mark.parametrize(
    "fixture_path",
    _collect(_VALID_DIR),
    ids=lambda p: p.name,
)
def test_valid_fixture_validates_cleanly(fixture_path: Path) -> None:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    SnapshotContract.model_validate(payload)


@pytest.mark.parametrize(
    "fixture_path",
    _collect(_INVALID_DIR),
    ids=lambda p: p.name,
)
def test_invalid_fixture_raises_validation_error(fixture_path: Path) -> None:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    with pytest.raises(ValidationError):
        SnapshotContract.model_validate(payload)
