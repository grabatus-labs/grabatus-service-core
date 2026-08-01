"""Every JSON sample under fixtures/v1.1/readout behaves as labelled.

``valid/*.json`` must validate cleanly; ``invalid/*.json`` must raise.
Adding a sample is the canonical way to lock in a regression.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout import ModelReadout

_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "v1.1" / "readout"


def _collect(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.json"))


@pytest.mark.parametrize("fixture_path", _collect(_FIXTURE_ROOT / "valid"), ids=lambda p: p.name)
def test_valid_fixture_validates_cleanly(fixture_path: Path) -> None:
    ModelReadout.model_validate(json.loads(fixture_path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("fixture_path", _collect(_FIXTURE_ROOT / "invalid"), ids=lambda p: p.name)
def test_invalid_fixture_raises_validation_error(fixture_path: Path) -> None:
    with pytest.raises(ValidationError):
        ModelReadout.model_validate(json.loads(fixture_path.read_text(encoding="utf-8")))
