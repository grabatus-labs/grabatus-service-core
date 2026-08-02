"""Uniqueness and referential integrity inside a single readout.

Every case here was accepted before these validators existed. The
narrative one is the worst: it hands the LLM an instruction it can only
obey by inventing the finding, while the guardrails in the same document
forbid inventing anything.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.root import ModelReadout

if TYPE_CHECKING:
    from grabatus_service_core.contract.readout.root import ModelReadout as Readout


def _payload(readout: Readout) -> dict[str, Any]:
    dumped: dict[str, Any] = readout.model_dump(mode="json")
    return dumped


def test_two_findings_cannot_share_an_id(valid_readout: Readout) -> None:
    payload = _payload(valid_readout)
    payload["findings"] = [payload["findings"][0], payload["findings"][0]]

    with pytest.raises(ValidationError, match="rule_001"):
        ModelReadout.model_validate(payload)


def test_two_artifacts_cannot_share_a_role(valid_readout: Readout) -> None:
    payload = _payload(valid_readout)
    payload["artifacts"] = [payload["artifacts"][0], payload["artifacts"][0]]

    with pytest.raises(ValidationError, match="rules_json"):
        ModelReadout.model_validate(payload)


def test_two_input_digests_cannot_share_a_role(valid_readout: Readout) -> None:
    payload = _payload(valid_readout)
    digests = payload["reproducibility"]["input_digests"]
    payload["reproducibility"]["input_digests"] = [digests[0], digests[0]]

    with pytest.raises(ValidationError, match="transactions"):
        ModelReadout.model_validate(payload)


def test_the_narrative_order_cannot_name_a_finding_that_does_not_exist(
    valid_readout: Readout,
) -> None:
    payload = _payload(valid_readout)
    payload["explanation_guide"]["recommended_narrative_order"] = ["rule_999"]

    with pytest.raises(ValidationError, match="rule_999"):
        ModelReadout.model_validate(payload)


def test_the_error_names_the_findings_that_do_exist(valid_readout: Readout) -> None:
    """Without the known ids the service cannot tell a typo from a missing finding."""
    payload = _payload(valid_readout)
    payload["explanation_guide"]["recommended_narrative_order"] = ["rule_999"]

    with pytest.raises(ValidationError, match="rule_001"):
        ModelReadout.model_validate(payload)


def test_a_partially_valid_narrative_order_is_still_rejected(valid_readout: Readout) -> None:
    """One real id does not license the invented one beside it."""
    payload = _payload(valid_readout)
    payload["explanation_guide"]["recommended_narrative_order"] = ["rule_001", "rule_999"]

    with pytest.raises(ValidationError, match="rule_999"):
        ModelReadout.model_validate(payload)


def test_an_empty_narrative_order_is_accepted(valid_readout: Readout) -> None:
    """Not naming an order is a choice; naming a phantom is a defect."""
    payload = _payload(valid_readout)
    payload["explanation_guide"]["recommended_narrative_order"] = []

    assert ModelReadout.model_validate(payload).explanation_guide.recommended_narrative_order == ()
