"""Tests for the SecretRef value object."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.secret_ref import SecretRef


def test_secret_ref_parses_full_uri() -> None:
    ref = SecretRef.model_validate("secret://gcp-secret-manager/bq-reader/3")

    assert ref.provider == "gcp-secret-manager"
    assert ref.name == "bq-reader"
    assert ref.version == "3"


def test_secret_ref_parses_uri_without_version_defaults_to_latest() -> None:
    ref = SecretRef.model_validate("secret://gcp-secret-manager/bq-reader")

    assert ref.provider == "gcp-secret-manager"
    assert ref.name == "bq-reader"
    assert ref.version == "latest"


def test_secret_ref_rejects_non_secret_scheme() -> None:
    with pytest.raises(ValidationError, match="scheme"):
        SecretRef.model_validate("https://example.com/secret/v1")


def test_secret_ref_rejects_uri_missing_provider() -> None:
    with pytest.raises(ValidationError, match="provider"):
        SecretRef.model_validate("secret:///bq-reader/1")


def test_secret_ref_rejects_uri_missing_name() -> None:
    with pytest.raises(ValidationError, match="name"):
        SecretRef.model_validate("secret://gcp-secret-manager")


def test_secret_ref_to_uri_round_trip() -> None:
    original = "secret://gcp-secret-manager/bq-reader/3"

    ref = SecretRef.model_validate(original)

    assert ref.to_uri() == original


def test_secret_ref_to_uri_omits_default_latest() -> None:
    ref = SecretRef.model_validate("secret://gcp-secret-manager/bq-reader")

    assert ref.to_uri() == "secret://gcp-secret-manager/bq-reader"


def test_secret_ref_is_frozen() -> None:
    ref = SecretRef.model_validate("secret://gsm/bq/1")

    with pytest.raises(ValidationError, match="frozen"):
        ref.name = "other"  # type: ignore[misc]


def test_secret_ref_serializes_to_uri_string_in_json_mode() -> None:
    ref = SecretRef.model_validate("secret://gsm/bq/1")

    dumped_json = ref.model_dump(mode="json")

    assert dumped_json == "secret://gsm/bq/1"


def test_secret_ref_keeps_structured_fields_in_python_mode() -> None:
    ref = SecretRef.model_validate("secret://gsm/bq/1")

    dumped_py = ref.model_dump(mode="python")

    assert dumped_py == {"provider": "gsm", "name": "bq", "version": "1"}


def test_secret_ref_accepts_structured_dict_input() -> None:
    """The pre-validator passes through dict inputs untouched (no URI parsing)."""
    ref = SecretRef.model_validate(
        {"provider": "gsm", "name": "bq", "version": "1"},
    )

    assert ref.provider == "gsm"
    assert ref.name == "bq"
    assert ref.version == "1"
