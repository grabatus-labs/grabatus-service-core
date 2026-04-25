"""Tests for the Envelope schema."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.envelope import Envelope


def _valid_envelope_dict() -> dict[str, object]:
    return {
        "protocol_version": "1.0",
        "request_id": "a3f9c21e-bf38-4e75-9a2f-c89b6c3f2d12",
        "created_at": "2026-04-25T14:32:10Z",
        "origin": "web",
    }


def test_envelope_accepts_valid_payload() -> None:
    env = Envelope.model_validate(_valid_envelope_dict())

    assert env.protocol_version == "1.0"
    assert isinstance(env.request_id, UUID)
    assert env.created_at == datetime(2026, 4, 25, 14, 32, 10, tzinfo=UTC)
    assert env.origin == "web"


def test_envelope_rejects_unknown_protocol_version() -> None:
    payload = _valid_envelope_dict() | {"protocol_version": "0.9"}

    with pytest.raises(ValidationError, match="protocol_version"):
        Envelope.model_validate(payload)


@pytest.mark.parametrize("origin", ["web", "api", "mcp", "internal"])
def test_envelope_accepts_all_known_origins(origin: str) -> None:
    payload = _valid_envelope_dict() | {"origin": origin}

    env = Envelope.model_validate(payload)

    assert env.origin == origin


def test_envelope_rejects_unknown_origin() -> None:
    payload = _valid_envelope_dict() | {"origin": "telegram"}

    with pytest.raises(ValidationError, match="origin"):
        Envelope.model_validate(payload)


def test_envelope_rejects_naive_created_at() -> None:
    payload = _valid_envelope_dict() | {"created_at": "2026-04-25T14:32:10"}

    with pytest.raises(ValidationError, match="created_at"):
        Envelope.model_validate(payload)


def test_envelope_rejects_extra_fields() -> None:
    payload = _valid_envelope_dict() | {"unknown_field": "boom"}

    with pytest.raises(ValidationError, match="extra"):
        Envelope.model_validate(payload)


def test_envelope_is_frozen() -> None:
    env = Envelope.model_validate(_valid_envelope_dict())

    with pytest.raises(ValidationError, match="frozen"):
        env.protocol_version = "2.0"  # type: ignore[misc]


def test_envelope_round_trips_through_json() -> None:
    raw = Envelope.model_validate(_valid_envelope_dict()).model_dump_json()
    restored = Envelope.model_validate_json(raw)

    assert restored == Envelope.model_validate(_valid_envelope_dict())
