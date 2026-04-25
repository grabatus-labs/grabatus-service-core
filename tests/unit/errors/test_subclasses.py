"""Tests for the concrete exception subclasses."""

from __future__ import annotations

import pytest

from grabatus_service_core.errors import (
    BlockedHostError,
    ComputeError,
    ComputeTimeoutError,
    ContractError,
    CredentialResolutionError,
    FormatParsingError,
    GrabatusServiceError,
    InputNotFoundError,
    InputReadError,
    InvalidContractError,
    MalformedMessageError,
    OutputWriteError,
    SecurityError,
    StorageError,
    UnauthorizedUriError,
    UnsupportedProtocolVersionError,
    UnsupportedSchemeError,
    WebhookAuthError,
    WebhookError,
)


@pytest.mark.parametrize(
    ("cls", "expected_code", "expected_retriable"),
    [
        (MalformedMessageError, "malformed_message", False),
        (InvalidContractError, "invalid_contract", False),
        (UnsupportedProtocolVersionError, "unsupported_protocol_version", False),
        (UnsupportedSchemeError, "unsupported_scheme", False),
        (UnauthorizedUriError, "unauthorized_uri", False),
        (BlockedHostError, "blocked_host", False),
        (CredentialResolutionError, "credential_resolution_failed", True),
        (InputNotFoundError, "input_not_found", False),
        (InputReadError, "input_read_failed", True),
        (OutputWriteError, "output_write_failed", True),
        (FormatParsingError, "format_parsing_failed", False),
        (ComputeError, "compute_failed", False),
        (ComputeTimeoutError, "compute_timeout", False),
        (WebhookError, "webhook_failed", True),
        (WebhookAuthError, "webhook_auth_failed", False),
    ],
)
def test_error_class_has_expected_attributes(
    cls: type[GrabatusServiceError],
    expected_code: str,
    expected_retriable: bool,
) -> None:
    assert cls.error_code == expected_code
    assert cls.http_status == 200
    assert cls.retriable is expected_retriable


def test_contract_subclasses_inherit_from_contract_error() -> None:
    assert issubclass(MalformedMessageError, ContractError)
    assert issubclass(InvalidContractError, ContractError)
    assert issubclass(UnsupportedProtocolVersionError, ContractError)


def test_security_subclasses_inherit_from_security_error() -> None:
    assert issubclass(UnsupportedSchemeError, SecurityError)
    assert issubclass(UnauthorizedUriError, SecurityError)
    assert issubclass(BlockedHostError, SecurityError)
    assert issubclass(CredentialResolutionError, SecurityError)


def test_storage_subclasses_inherit_from_storage_error() -> None:
    assert issubclass(InputNotFoundError, StorageError)
    assert issubclass(InputReadError, StorageError)
    assert issubclass(OutputWriteError, StorageError)
    assert issubclass(FormatParsingError, StorageError)


def test_compute_timeout_inherits_from_compute_error() -> None:
    assert issubclass(ComputeTimeoutError, ComputeError)


def test_webhook_auth_inherits_from_webhook_error() -> None:
    assert issubclass(WebhookAuthError, WebhookError)


def test_all_errors_inherit_from_base() -> None:
    classes: list[type[GrabatusServiceError]] = [
        ContractError,
        SecurityError,
        StorageError,
        ComputeError,
        WebhookError,
    ]
    for cls in classes:
        assert issubclass(cls, GrabatusServiceError)


def test_error_message_includes_offending_value() -> None:
    err = UnauthorizedUriError(
        "unauthorized URI for tenant='grabatus', got bucket='other-tenant'",
        context={"tenant": "grabatus", "got_bucket": "other-tenant"},
    )
    assert "tenant='grabatus'" in str(err)
    assert err.context["got_bucket"] == "other-tenant"
