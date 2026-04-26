"""Tests for the 8 pipeline step functions."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from pydantic import BaseModel

from grabatus_service_core.contract.base import BaseServiceContract
from grabatus_service_core.contract.secret_ref import SecretRef
from grabatus_service_core.errors import (
    ComputeError,
    CredentialResolutionError,
    InputReadError,
    InvalidContractError,
    MalformedMessageError,
    OutputWriteError,
    UnauthorizedUriError,
    UnsupportedProtocolVersionError,
    UnsupportedSchemeError,
    WebhookError,
)
from grabatus_service_core.ports.values import (
    ComputeResult,
    Credentials,
    LoadedInputs,
    RawMessage,
    WebhookAck,
)
from grabatus_service_core.runner.state import (
    AuthorizedContract,
    CredentialBundle,
    ParsedEnvelope,
    ValidatedContract,
)
from grabatus_service_core.runner.steps import (
    authorize,
    decode,
    load_inputs,
    notify_webhook,
    resolve_credentials,
    run_compute,
    save_outputs,
    validate,
)
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.testing import (
    AllowAllPolicy,
    InMemoryMessagePort,
    InMemorySecretsAdapter,
    InMemoryStorage,
    RecordingWebhookNotifier,
    make_callback,
    make_contract,
    make_envelope,
    make_input_spec,
    make_output_spec,
)


class _Params(BaseModel):
    horizon: int = 30


# ---------- decode ----------


def test_decode_returns_parsed_envelope_with_dict_payload() -> None:
    contract_dict = {"hello": "world"}
    raw = RawMessage(payload=json.dumps(contract_dict).encode("utf-8"))

    parsed = decode(raw=raw, message=InMemoryMessagePort())

    assert dict(parsed.payload) == contract_dict


def test_decode_propagates_malformed_message_error() -> None:
    message = MagicMock()
    message.decode.side_effect = MalformedMessageError("bad")

    with pytest.raises(MalformedMessageError):
        decode(raw=RawMessage(payload=b""), message=message)


# ---------- validate ----------


def _valid_payload() -> dict[str, Any]:
    contract = make_contract(parameters=_Params(horizon=30))
    return contract.model_dump(mode="json")


def test_validate_returns_validated_contract_for_well_formed_payload() -> None:
    parsed = ParsedEnvelope(payload=_valid_payload())

    validated = validate(parsed=parsed, contract_type=BaseServiceContract[_Params])

    assert validated.contract.parameters.horizon == 30


def test_validate_translates_pydantic_error_to_invalid_contract_error() -> None:
    parsed = ParsedEnvelope(payload={"missing": "everything"})

    with pytest.raises(InvalidContractError, match="Pydantic validation"):
        validate(parsed=parsed, contract_type=BaseServiceContract[_Params])


def test_validate_rejects_unsupported_protocol_version() -> None:
    payload = _valid_payload()
    payload["envelope"]["protocol_version"] = "9.9"
    parsed = ParsedEnvelope(payload=payload)

    with pytest.raises(UnsupportedProtocolVersionError, match="protocol_version"):
        validate(parsed=parsed, contract_type=BaseServiceContract[_Params])


# ---------- authorize ----------


def _allowlist() -> SchemeAllowlist:
    return SchemeAllowlist(allowed={"gs", "https"})


def test_authorize_passes_when_all_uris_are_allowed_and_authorized() -> None:
    contract = make_contract(parameters=_Params())
    validated = ValidatedContract(contract=contract)

    authorized = authorize(
        validated=validated,
        authorizer=AllowAllPolicy(),
        scheme_allowlist=_allowlist(),
    )

    assert authorized.contract is contract


def test_authorize_raises_unsupported_scheme_for_unknown_scheme() -> None:
    contract = make_contract(
        parameters=_Params(),
        inputs=[
            make_input_spec(
                source_uri="ftp://nope/in.csv", fmt="csv", hints={"format": "csv", "delimiter": ","}
            )
        ],
    )
    validated = ValidatedContract(contract=contract)

    with pytest.raises(UnsupportedSchemeError):
        authorize(
            validated=validated,
            authorizer=AllowAllPolicy(),
            scheme_allowlist=_allowlist(),
        )


def test_authorize_propagates_authorization_failure() -> None:
    contract = make_contract(parameters=_Params())
    validated = ValidatedContract(contract=contract)
    blocking = MagicMock()
    blocking.authorize.side_effect = UnauthorizedUriError("nope")

    with pytest.raises(UnauthorizedUriError):
        authorize(
            validated=validated,
            authorizer=blocking,
            scheme_allowlist=_allowlist(),
        )


def test_authorize_checks_outputs_too() -> None:
    contract = make_contract(
        parameters=_Params(),
        outputs=[make_output_spec(destination_uri="ftp://nope/out.json")],
    )
    validated = ValidatedContract(contract=contract)

    with pytest.raises(UnsupportedSchemeError):
        authorize(
            validated=validated,
            authorizer=AllowAllPolicy(),
            scheme_allowlist=_allowlist(),
        )


# ---------- resolve_credentials ----------


def _ref(name: str = "gcs-reader", version: str = "1") -> SecretRef:
    return SecretRef.model_validate(f"secret://gsm/{name}/{version}")


def test_resolve_credentials_fills_input_and_output_roles() -> None:
    contract = make_contract(
        parameters=_Params(),
        inputs=[make_input_spec()],
        outputs=[make_output_spec()],
    )
    authorized = AuthorizedContract(contract=contract)
    secrets = InMemorySecretsAdapter(seed={})

    bundle = resolve_credentials(authorized=authorized, secrets=secrets)

    assert "timeseries" in bundle.inputs
    assert "result_json" in bundle.outputs


def test_resolve_credentials_returns_none_creds_when_no_credential_ref() -> None:
    contract = make_contract(
        parameters=_Params(),
        inputs=[make_input_spec()],
    )
    authorized = AuthorizedContract(contract=contract)
    secrets = MagicMock()

    bundle = resolve_credentials(authorized=authorized, secrets=secrets)

    assert bundle.inputs["timeseries"].token == b""
    assert bundle.inputs["timeseries"].token_type == "none"
    secrets.resolve.assert_not_called()


def test_resolve_credentials_calls_secrets_when_credential_ref_present() -> None:
    contract = make_contract(
        parameters=_Params(),
        inputs=[make_input_spec()],
    )
    # Inject credential_ref via a copy with model_copy()
    spec_with_ref = contract.inputs[0].model_copy(update={"credential_ref": _ref()})
    contract = contract.model_copy(update={"inputs": [spec_with_ref]})
    authorized = AuthorizedContract(contract=contract)
    secrets = InMemorySecretsAdapter(
        seed={"secret://gsm/gcs-reader/1": Credentials(token=b"k", token_type="bearer")},
    )

    bundle = resolve_credentials(authorized=authorized, secrets=secrets)

    assert bundle.inputs["timeseries"].token == b"k"


def test_resolve_credentials_propagates_credential_resolution_error() -> None:
    contract = make_contract(
        parameters=_Params(),
        inputs=[make_input_spec()],
    )
    spec_with_ref = contract.inputs[0].model_copy(update={"credential_ref": _ref()})
    contract = contract.model_copy(update={"inputs": [spec_with_ref]})
    authorized = AuthorizedContract(contract=contract)
    secrets = MagicMock()
    secrets.resolve.side_effect = CredentialResolutionError("missing")

    with pytest.raises(CredentialResolutionError):
        resolve_credentials(authorized=authorized, secrets=secrets)


# ---------- load_inputs ----------


def _none_creds() -> Credentials:
    return Credentials(token=b"", token_type="none")


def test_load_inputs_reads_each_input_role() -> None:
    contract = make_contract(
        parameters=_Params(),
        inputs=[make_input_spec()],
    )
    authorized = AuthorizedContract(contract=contract)
    bundle = CredentialBundle(inputs={"timeseries": _none_creds()}, outputs={})
    storage = InMemoryStorage(
        seed={"gs://gbt-storage-grabatus/user_999/in.xlsx": b"raw-bytes"},
    )

    inputs = load_inputs(authorized=authorized, credentials=bundle, storage=storage)

    assert inputs.by_role["timeseries"] == b"raw-bytes"


def test_load_inputs_propagates_storage_error() -> None:
    contract = make_contract(
        parameters=_Params(),
        inputs=[make_input_spec()],
    )
    authorized = AuthorizedContract(contract=contract)
    bundle = CredentialBundle(inputs={"timeseries": _none_creds()}, outputs={})
    storage = MagicMock()
    storage.read.side_effect = InputReadError("boom")

    with pytest.raises(InputReadError):
        load_inputs(authorized=authorized, credentials=bundle, storage=storage)


# ---------- run_compute ----------


def test_run_compute_invokes_compute_with_inputs_and_parameters() -> None:
    contract = make_contract(parameters=_Params(horizon=7))
    authorized = AuthorizedContract(contract=contract)
    inputs = LoadedInputs(by_role={"timeseries": b"x"})
    compute = MagicMock()
    expected = ComputeResult(by_role={"result_json": b"out"}, metadata={})
    compute.run.return_value = expected

    result = run_compute(authorized=authorized, inputs=inputs, compute=compute)

    assert result is expected
    compute.run.assert_called_once_with(inputs=inputs, parameters=contract.parameters)


def test_run_compute_propagates_compute_error() -> None:
    contract = make_contract(parameters=_Params())
    authorized = AuthorizedContract(contract=contract)
    inputs = LoadedInputs(by_role={"timeseries": b"x"})
    compute = MagicMock()
    compute.run.side_effect = ComputeError("boom")

    with pytest.raises(ComputeError):
        run_compute(authorized=authorized, inputs=inputs, compute=compute)


# ---------- save_outputs ----------


def test_save_outputs_writes_each_output_role() -> None:
    contract = make_contract(
        parameters=_Params(),
        outputs=[make_output_spec()],
    )
    authorized = AuthorizedContract(contract=contract)
    bundle = CredentialBundle(inputs={}, outputs={"result_json": _none_creds()})
    result = ComputeResult(by_role={"result_json": b"forecast"}, metadata={})
    storage = InMemoryStorage()

    receipts = save_outputs(
        authorized=authorized,
        credentials=bundle,
        result=result,
        storage=storage,
    )

    assert "result_json" in receipts.by_role
    assert receipts.by_role["result_json"].bytes_written == len(b"forecast")


def test_save_outputs_propagates_output_write_error() -> None:
    contract = make_contract(
        parameters=_Params(),
        outputs=[make_output_spec()],
    )
    authorized = AuthorizedContract(contract=contract)
    bundle = CredentialBundle(inputs={}, outputs={"result_json": _none_creds()})
    result = ComputeResult(by_role={"result_json": b"x"}, metadata={})
    storage = MagicMock()
    storage.write.side_effect = OutputWriteError("boom")

    with pytest.raises(OutputWriteError):
        save_outputs(
            authorized=authorized,
            credentials=bundle,
            result=result,
            storage=storage,
        )


# ---------- notify_webhook ----------


def test_notify_webhook_invokes_webhook_with_callback_and_payload() -> None:
    callback = make_callback()
    webhook = RecordingWebhookNotifier()
    payload = {"status": "ok", "request_id": "abc"}

    ack = notify_webhook(callback=callback, payload=payload, webhook=webhook)

    assert isinstance(ack, WebhookAck)
    assert webhook.calls[0].payload == payload


def test_notify_webhook_propagates_webhook_error() -> None:
    webhook = MagicMock()
    webhook.notify.side_effect = WebhookError("boom")

    with pytest.raises(WebhookError):
        notify_webhook(
            callback=make_callback(),
            payload={"x": 1},
            webhook=webhook,
        )


# ---------- glue test: full state propagation in happy path ----------


def test_request_id_is_preserved_through_validate() -> None:
    rid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    contract = make_contract(parameters=_Params(), envelope=make_envelope(request_id=rid))
    payload = contract.model_dump(mode="json")

    validated = validate(
        parsed=ParsedEnvelope(payload=payload),
        contract_type=BaseServiceContract[_Params],
    )

    assert validated.contract.envelope.request_id == rid
