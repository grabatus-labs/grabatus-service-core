"""Tests for GoogleSecretManagerAdapter and EnvVarSecretsAdapter."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from google.api_core import exceptions as gcp_exceptions

from grabatus_service_core.adapters.secrets_env import EnvVarSecretsAdapter
from grabatus_service_core.adapters.secrets_gsm import GoogleSecretManagerAdapter
from grabatus_service_core.contract.secret_ref import SecretRef
from grabatus_service_core.errors import CredentialResolutionError
from grabatus_service_core.ports.secrets import SecretsPort


def _ref(uri: str = "secret://gsm/bq-reader/3") -> SecretRef:
    return SecretRef.model_validate(uri)


def _client_returning(payload_data: bytes) -> MagicMock:
    response = MagicMock()
    response.payload.data = payload_data
    client = MagicMock()
    client.access_secret_version.return_value = response
    return client


def test_gsm_adapter_satisfies_port() -> None:
    adapter = GoogleSecretManagerAdapter(project_id="p", client=MagicMock())
    assert isinstance(adapter, SecretsPort)


def test_gsm_adapter_returns_credentials_for_known_secret() -> None:
    client = _client_returning(b"super-secret")
    adapter = GoogleSecretManagerAdapter(project_id="grabatus", client=client)

    creds = adapter.resolve(secret_ref=_ref())

    assert creds.token == b"super-secret"
    name_arg = client.access_secret_version.call_args.kwargs["name"]
    assert name_arg == "projects/grabatus/secrets/bq-reader/versions/3"


def test_gsm_adapter_translates_not_found_to_credential_error() -> None:
    client = MagicMock()
    client.access_secret_version.side_effect = gcp_exceptions.NotFound("missing")
    adapter = GoogleSecretManagerAdapter(project_id="p", client=client)

    with pytest.raises(CredentialResolutionError, match="no version"):
        adapter.resolve(secret_ref=_ref())


def test_gsm_adapter_translates_other_api_error() -> None:
    client = MagicMock()
    client.access_secret_version.side_effect = gcp_exceptions.Forbidden("denied")
    adapter = GoogleSecretManagerAdapter(project_id="p", client=client)

    with pytest.raises(CredentialResolutionError, match="access failed"):
        adapter.resolve(secret_ref=_ref())


def test_gsm_adapter_retries_on_transient_error_then_succeeds() -> None:
    response = MagicMock()
    response.payload.data = b"recovered"
    client = MagicMock()
    client.access_secret_version.side_effect = [
        gcp_exceptions.ServiceUnavailable("503"),
        response,
    ]
    adapter = GoogleSecretManagerAdapter(project_id="p", client=client)

    creds = adapter.resolve(secret_ref=_ref())

    assert creds.token == b"recovered"
    assert client.access_secret_version.call_count == 2


def test_env_adapter_satisfies_port() -> None:
    assert isinstance(EnvVarSecretsAdapter(environ={}), SecretsPort)


def test_env_adapter_returns_value_when_var_present() -> None:
    adapter = EnvVarSecretsAdapter(environ={"WEBHOOK_KEY": "abcdef"})

    creds = adapter.resolve(
        secret_ref=SecretRef.model_validate("secret://env/WEBHOOK_KEY"),
    )

    assert creds.token == b"abcdef"
    assert creds.token_type == "env"


def test_env_adapter_raises_when_var_missing() -> None:
    adapter = EnvVarSecretsAdapter(environ={})

    with pytest.raises(CredentialResolutionError, match="is not set"):
        adapter.resolve(secret_ref=SecretRef.model_validate("secret://env/MISSING"))


def test_env_adapter_rejects_non_env_provider() -> None:
    adapter = EnvVarSecretsAdapter(environ={"X": "y"})

    with pytest.raises(CredentialResolutionError, match="provider"):
        adapter.resolve(secret_ref=SecretRef.model_validate("secret://gsm/X"))


def test_env_adapter_uses_os_environ_when_no_explicit_environ() -> None:
    # Smoke test: just ensure it constructs without explicit dict.
    adapter = EnvVarSecretsAdapter()

    # PATH is reliably set on every test runner.
    creds = adapter.resolve(
        secret_ref=SecretRef.model_validate("secret://env/PATH"),
    )
    assert creds.token  # non-empty bytes
