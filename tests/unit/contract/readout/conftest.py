"""Fixtures for the readout unit tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grabatus_service_core.testing.readout import make_model_readout

if TYPE_CHECKING:
    from grabatus_service_core.contract.readout.root import ModelReadout


@pytest.fixture
def valid_readout() -> ModelReadout:
    return make_model_readout()
