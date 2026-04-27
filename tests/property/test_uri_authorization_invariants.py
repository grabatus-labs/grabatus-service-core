"""Property tests: URI authorization invariants.

These hold for every tenant_id and every URI shape:

- ``SchemeAllowlist`` is closed: a scheme either is permitted or raises.
- ``TenantPrefixPolicy`` rejects any bucket-style URI whose host does
  not start with ``<bucket_prefix>-<tenant_id>``.
- The ``inline://`` and ``secret://`` schemes are tenant-agnostic and
  always pass ``TenantPrefixPolicy``.
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from grabatus_service_core.contract.identity import Identity
from grabatus_service_core.errors import (
    UnauthorizedUriError,
    UnsupportedSchemeError,
)
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.security.tenant_prefix_policy import (
    TenantPrefixPolicy,
)

_KNOWN_SCHEMES = ("gs", "s3", "https", "http", "inline", "secret", "bigquery")
_TENANT_SLUG = re.compile(r"^[a-z0-9-]+$")

_tenant_slug_strategy = st.from_regex(_TENANT_SLUG, fullmatch=True).filter(
    lambda s: 1 <= len(s) <= 32,
)


@given(
    allowed=st.sets(st.sampled_from(_KNOWN_SCHEMES), min_size=1),
    candidate=st.sampled_from(_KNOWN_SCHEMES),
)
def test_scheme_allowlist_membership_decides_authorization(
    allowed: set[str],
    candidate: str,
) -> None:
    policy = SchemeAllowlist(allowed=allowed)
    uri = f"{candidate}://example/host/path"

    if candidate in allowed:
        policy.check(uri)
    else:
        with pytest.raises(UnsupportedSchemeError):
            policy.check(uri)


@given(
    bucket_prefix=_tenant_slug_strategy,
    tenant_id=_tenant_slug_strategy,
    other_tenant=_tenant_slug_strategy,
    user_id=st.text(
        alphabet=st.characters(min_codepoint=0x61, max_codepoint=0x7A),
        min_size=1,
        max_size=8,
    ),
)
def test_tenant_prefix_policy_rejects_cross_tenant_buckets(
    bucket_prefix: str,
    tenant_id: str,
    other_tenant: str,
    user_id: str,
) -> None:
    if other_tenant == tenant_id:
        return
    identity = Identity(user_id=user_id, tenant_id=tenant_id)
    policy = TenantPrefixPolicy(bucket_prefix=bucket_prefix)
    cross_uri = f"gs://{bucket_prefix}-{other_tenant}/user_{user_id}/file.bin"

    with pytest.raises(UnauthorizedUriError):
        policy.authorize(uri=cross_uri, identity=identity)


@given(
    bucket_prefix=_tenant_slug_strategy,
    tenant_id=_tenant_slug_strategy,
    user_id=st.text(
        alphabet=st.characters(min_codepoint=0x61, max_codepoint=0x7A),
        min_size=1,
        max_size=8,
    ),
    suffix=st.text(
        alphabet=st.characters(min_codepoint=0x61, max_codepoint=0x7A),
        min_size=0,
        max_size=8,
    ),
)
def test_tenant_prefix_policy_accepts_correctly_prefixed_buckets(
    bucket_prefix: str,
    tenant_id: str,
    user_id: str,
    suffix: str,
) -> None:
    identity = Identity(user_id=user_id, tenant_id=tenant_id)
    policy = TenantPrefixPolicy(bucket_prefix=bucket_prefix)
    bucket = f"{bucket_prefix}-{tenant_id}{suffix}"
    uri = f"gs://{bucket}/user_{user_id}/path/object.bin"

    policy.authorize(uri=uri, identity=identity)


@given(
    bucket_prefix=_tenant_slug_strategy,
    tenant_id=_tenant_slug_strategy,
    user_id=st.text(
        alphabet=st.characters(min_codepoint=0x61, max_codepoint=0x7A),
        min_size=1,
        max_size=8,
    ),
    rest=st.text(min_size=0, max_size=32),
    scheme=st.sampled_from(["secret", "inline"]),
)
def test_tenant_agnostic_schemes_always_pass_tenant_policy(
    bucket_prefix: str,
    tenant_id: str,
    user_id: str,
    rest: str,
    scheme: str,
) -> None:
    identity = Identity(user_id=user_id, tenant_id=tenant_id)
    policy = TenantPrefixPolicy(bucket_prefix=bucket_prefix)
    uri = f"{scheme}://something/{rest}"

    policy.authorize(uri=uri, identity=identity)
