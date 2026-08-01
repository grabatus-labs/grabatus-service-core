"""Fixtures for the readout unit tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.unit.contract.readout.builders import build_valid_readout

if TYPE_CHECKING:
    from grabatus_service_core.contract.readout.root import ModelReadout


@pytest.fixture
def valid_readout() -> ModelReadout:
    return build_valid_readout()
