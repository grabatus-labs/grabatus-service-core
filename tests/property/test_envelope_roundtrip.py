"""Property tests: Envelope JSON round-trip and tenant slug invariants.

The Envelope is the gateway to every contract. If JSON round-trip ever
loses data, every downstream service silently misbehaves; if Identity
accepts an unsafe tenant slug, multi-tenant isolation breaks.
"""

from __future__ import annotations

import re
from datetime import UTC

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from grabatus_service_core.contract.envelope import Envelope
from grabatus_service_core.contract.identity import Identity

_TENANT_SLUG = re.compile(r"^[a-z0-9-]+$")
_ORIGINS = ("web", "api", "mcp", "internal")
_PROTOCOL = "1.0"


_tenant_slug_strategy = st.from_regex(_TENANT_SLUG, fullmatch=True).filter(
    lambda s: 1 <= len(s) <= 64,
)
_user_id_strategy = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=64,
)


@given(
    request_id=st.uuids(version=4),
    created_at=st.datetimes(timezones=st.just(UTC)),
    origin=st.sampled_from(_ORIGINS),
)
def test_envelope_roundtrips_through_json(
    request_id: object,
    created_at: object,
    origin: str,
) -> None:
    original = Envelope(
        protocol_version=_PROTOCOL,
        request_id=request_id,  # type: ignore[arg-type]
        created_at=created_at,  # type: ignore[arg-type]
        origin=origin,  # type: ignore[arg-type]
    )

    serialized = original.model_dump_json()
    reparsed = Envelope.model_validate_json(serialized)

    assert reparsed == original
    assert reparsed.model_dump_json() == serialized


@given(
    tenant_id=_tenant_slug_strategy,
    user_id=_user_id_strategy,
)
def test_identity_accepts_only_valid_tenant_slugs(
    tenant_id: str,
    user_id: str,
) -> None:
    identity = Identity(user_id=user_id, tenant_id=tenant_id)

    assert identity.tenant_id == tenant_id
    assert _TENANT_SLUG.match(identity.tenant_id) is not None


@given(
    tenant_id=st.text(min_size=1, max_size=64).filter(
        lambda s: _TENANT_SLUG.match(s) is None,
    ),
)
def test_identity_rejects_non_slug_tenant_ids(tenant_id: str) -> None:
    with pytest.raises(ValidationError):
        Identity(user_id="u", tenant_id=tenant_id)
