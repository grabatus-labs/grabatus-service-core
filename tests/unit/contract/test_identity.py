"""Tests for the Identity schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.identity import Identity


def test_identity_accepts_valid_user_and_tenant() -> None:
    identity = Identity.model_validate({"user_id": "999", "tenant_id": "grabatus"})

    assert identity.user_id == "999"
    assert identity.tenant_id == "grabatus"


@pytest.mark.parametrize(
    "tenant_id",
    ["Grabatus", "grabatus_v2", "grabatus.client", "grabatus client", ""],
)
def test_identity_rejects_invalid_tenant_id(tenant_id: str) -> None:
    with pytest.raises(ValidationError, match="tenant_id"):
        Identity.model_validate({"user_id": "999", "tenant_id": tenant_id})


@pytest.mark.parametrize("tenant_id", ["grabatus", "client-a", "tenant-123"])
def test_identity_accepts_valid_tenant_slugs(tenant_id: str) -> None:
    identity = Identity.model_validate({"user_id": "999", "tenant_id": tenant_id})

    assert identity.tenant_id == tenant_id


def test_identity_rejects_empty_user_id() -> None:
    with pytest.raises(ValidationError, match="user_id"):
        Identity.model_validate({"user_id": "", "tenant_id": "grabatus"})


def test_identity_rejects_oversized_user_id() -> None:
    with pytest.raises(ValidationError, match="user_id"):
        Identity.model_validate({"user_id": "x" * 65, "tenant_id": "grabatus"})


def test_identity_is_frozen() -> None:
    identity = Identity.model_validate({"user_id": "1", "tenant_id": "grabatus"})

    with pytest.raises(ValidationError, match="frozen"):
        identity.user_id = "2"  # type: ignore[misc]


def test_identity_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="extra"):
        Identity.model_validate(
            {"user_id": "1", "tenant_id": "grabatus", "role": "admin"},
        )
