"""Tests for TenantPrefixPolicy."""

from __future__ import annotations

import pytest

from grabatus_service_core.contract.identity import Identity
from grabatus_service_core.errors import UnauthorizedUriError
from grabatus_service_core.security.tenant_prefix_policy import TenantPrefixPolicy


def _identity(tenant: str = "grabatus", user: str = "999") -> Identity:
    return Identity.model_validate({"user_id": user, "tenant_id": tenant})


def test_policy_allows_uri_with_correct_tenant_prefix() -> None:
    policy = TenantPrefixPolicy(
        bucket_prefix="gbt-storage",
        require_user_path_segment=False,
    )

    policy.authorize(
        uri="gs://gbt-storage-grabatus/path/to/file.xlsx",
        identity=_identity(tenant="grabatus"),
    )


def test_policy_rejects_uri_for_different_tenant() -> None:
    policy = TenantPrefixPolicy(bucket_prefix="gbt-storage")

    with pytest.raises(UnauthorizedUriError, match="grabatus"):
        policy.authorize(
            uri="gs://gbt-storage-other-tenant/path/file.xlsx",
            identity=_identity(tenant="grabatus"),
        )


def test_policy_rejects_uri_with_unknown_bucket_prefix() -> None:
    policy = TenantPrefixPolicy(bucket_prefix="gbt-storage")

    with pytest.raises(UnauthorizedUriError, match="bucket"):
        policy.authorize(
            uri="gs://random-bucket/path/file.xlsx",
            identity=_identity(tenant="grabatus"),
        )


def test_policy_skips_secret_scheme() -> None:
    policy = TenantPrefixPolicy(bucket_prefix="gbt-storage")

    policy.authorize(
        uri="secret://gcp-secret-manager/bq-reader/1",
        identity=_identity(),
    )


def test_policy_skips_inline_scheme() -> None:
    policy = TenantPrefixPolicy(bucket_prefix="gbt-storage")

    policy.authorize(
        uri="inline://base64,SGVsbG8=",
        identity=_identity(),
    )


def test_policy_rejects_https_uri_when_no_explicit_allowance() -> None:
    policy = TenantPrefixPolicy(bucket_prefix="gbt-storage")

    with pytest.raises(UnauthorizedUriError, match="scheme"):
        policy.authorize(
            uri="https://api.partner.com/data",
            identity=_identity(),
        )


def test_policy_requires_user_path_segment_after_tenant_bucket() -> None:
    policy = TenantPrefixPolicy(
        bucket_prefix="gbt-storage",
        require_user_path_segment=True,
    )

    with pytest.raises(UnauthorizedUriError, match="user"):
        policy.authorize(
            uri="gs://gbt-storage-grabatus/global/file.xlsx",
            identity=_identity(user="999"),
        )

    policy.authorize(
        uri="gs://gbt-storage-grabatus/user_999/forecast/file.xlsx",
        identity=_identity(user="999"),
    )


def test_policy_requires_at_least_one_path_segment_when_user_required() -> None:
    """Branch coverage: empty path with require_user_path_segment=True."""
    policy = TenantPrefixPolicy(
        bucket_prefix="gbt-storage",
        require_user_path_segment=True,
    )

    with pytest.raises(UnauthorizedUriError, match="user"):
        policy.authorize(
            uri="gs://gbt-storage-grabatus/",
            identity=_identity(user="999"),
        )


def test_policy_allows_bigquery_with_matching_tenant_prefix() -> None:
    policy = TenantPrefixPolicy(bucket_prefix="gbt-storage")

    policy.authorize(
        uri="bigquery://gbt-storage-grabatus.dataset.table",
        identity=_identity(tenant="grabatus"),
    )


def test_policy_rejects_bigquery_with_wrong_project_prefix() -> None:
    policy = TenantPrefixPolicy(bucket_prefix="gbt-storage")

    with pytest.raises(UnauthorizedUriError, match="bigquery"):
        policy.authorize(
            uri="bigquery://other-project.dataset.table",
            identity=_identity(tenant="grabatus"),
        )
