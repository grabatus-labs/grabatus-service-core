"""Pure step functions for the service runner pipeline.

Each step takes immutable state and returns immutable state. Failures
surface as typed :class:`GrabatusServiceError` subclasses raised by the
underlying Port; the orchestrator catches them and produces an
``ExecutionResult`` with status="error".

Steps are pure with respect to the state they consume — they do not
mutate ports or state. They do however invoke side-effecting Ports
(``StoragePort.read``, ``ComputeBackendPort.run``, etc.).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from grabatus_service_core.contract.readout.enums import READOUT_OUTPUT_ROLE
from grabatus_service_core.contract.readout.root import ModelReadout
from grabatus_service_core.contract.version import SUPPORTED_PROTOCOL_VERSIONS
from grabatus_service_core.errors import (
    InvalidContractError,
    InvalidReadoutError,
    MissingReadoutError,
    UnsupportedProtocolVersionError,
)
from grabatus_service_core.ports.values import (
    Credentials,
    LoadedInputs,
)
from grabatus_service_core.runner.state import (
    AuthorizedContract,
    CredentialBundle,
    ParsedEnvelope,
    ValidatedContract,
    WriteReceipts,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from grabatus_service_core.contract.base import (
        BaseServiceContract,
        ParamsT,
    )
    from grabatus_service_core.contract.callback import Callback
    from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
    from grabatus_service_core.ports.authorization import UriAuthorizationPort
    from grabatus_service_core.ports.compute import ComputeBackendPort
    from grabatus_service_core.ports.message import MessagePort
    from grabatus_service_core.ports.secrets import SecretsPort
    from grabatus_service_core.ports.storage import StoragePort
    from grabatus_service_core.ports.values import (
        ComputeResult,
        RawMessage,
        WebhookAck,
        WriteReceipt,
    )
    from grabatus_service_core.ports.webhook import WebhookPort
    from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist


_NULL_TOKEN_TYPE = "none"  # noqa: S105  # nosec B105 — placeholder for "no creds needed"


def decode(*, raw: RawMessage, message: MessagePort) -> ParsedEnvelope:
    """Step 1 — decode the broker envelope to a contract dict."""
    return ParsedEnvelope(payload=message.decode(raw))


def validate(
    *,
    parsed: ParsedEnvelope,
    contract_type: type[BaseServiceContract[ParamsT]],
) -> ValidatedContract[ParamsT]:
    """Step 2 — Pydantic-validate the dict against the service contract type.

    Pre-checks ``envelope.protocol_version`` against the runner's supported
    set so an out-of-range version raises ``UnsupportedProtocolVersionError``
    rather than the generic ``InvalidContractError`` that Pydantic would
    otherwise surface.
    """
    payload = dict(parsed.payload)
    envelope = payload.get("envelope")
    if isinstance(envelope, dict):
        version = envelope.get("protocol_version")
        if isinstance(version, str) and version not in SUPPORTED_PROTOCOL_VERSIONS:
            raise UnsupportedProtocolVersionError(
                f"unsupported protocol_version={version!r}; "
                f"supported={sorted(SUPPORTED_PROTOCOL_VERSIONS)!r}",
            )
    try:
        contract = contract_type.model_validate(payload)
    except ValidationError as exc:
        raise InvalidContractError(
            f"contract failed Pydantic validation: {exc}",
        ) from exc
    return ValidatedContract(contract=contract)


def authorize(
    *,
    validated: ValidatedContract[ParamsT],
    authorizer: UriAuthorizationPort,
    scheme_allowlist: SchemeAllowlist,
) -> AuthorizedContract[ParamsT]:
    """Step 3 — apply ``SchemeAllowlist`` and ``UriAuthorizationPort`` to every URI."""
    contract = validated.contract
    for input_spec in contract.inputs:
        scheme_allowlist.check(str(input_spec.source_uri))
        authorizer.authorize(uri=str(input_spec.source_uri), identity=contract.identity)
    for output_spec in contract.outputs:
        scheme_allowlist.check(str(output_spec.destination_uri))
        authorizer.authorize(
            uri=str(output_spec.destination_uri),
            identity=contract.identity,
        )
    return AuthorizedContract(contract=contract)


def resolve_credentials(
    *,
    authorized: AuthorizedContract[ParamsT],
    secrets: SecretsPort,
) -> CredentialBundle:
    """Step 4 — resolve every spec's ``credential_ref`` to ``Credentials``."""
    return CredentialBundle(
        inputs=_resolve_for_specs(secrets, authorized.contract.inputs),
        outputs=_resolve_for_specs(secrets, authorized.contract.outputs),
    )


def load_inputs(
    *,
    authorized: AuthorizedContract[ParamsT],
    credentials: CredentialBundle,
    storage: StoragePort,
) -> LoadedInputs:
    """Step 5 — read each input spec via the storage port (sequential)."""
    by_role: dict[str, bytes] = {}
    for input_spec in authorized.contract.inputs:
        by_role[input_spec.role] = storage.read(
            spec=input_spec,
            credentials=credentials.inputs[input_spec.role],
        )
    return LoadedInputs(by_role=by_role)


def run_compute(
    *,
    authorized: AuthorizedContract[ParamsT],
    inputs: LoadedInputs,
    compute: ComputeBackendPort,
) -> ComputeResult:
    """Step 6 — invoke the service compute backend."""
    return compute.run(inputs=inputs, parameters=authorized.contract.parameters)


def validate_readout(*, result: ComputeResult) -> ModelReadout:
    """Step 7 — refuse a result that no LLM could explain without inventing.

    The readout is the only artifact carrying what the numbers mean. A run
    that produces none is a run whose output nobody can be told about, so it
    fails here rather than reaching storage.
    """
    payload = result.by_role.get(READOUT_OUTPUT_ROLE)
    if payload is None:
        raise MissingReadoutError(
            f"compute produced no {READOUT_OUTPUT_ROLE!r} output; "
            f"got roles {sorted(result.by_role)!r}",
        )
    try:
        return ModelReadout.model_validate_json(payload)
    except ValidationError as exc:
        raise InvalidReadoutError(
            f"{READOUT_OUTPUT_ROLE!r} does not satisfy the readout schema: {exc}",
        ) from exc


def save_outputs(
    *,
    authorized: AuthorizedContract[ParamsT],
    credentials: CredentialBundle,
    result: ComputeResult,
    storage: StoragePort,
) -> WriteReceipts:
    """Step 7 — persist each declared output via the storage port (sequential)."""
    by_role: dict[str, WriteReceipt] = {}
    for output_spec in authorized.contract.outputs:
        by_role[output_spec.role] = storage.write(
            spec=output_spec,
            payload=result.by_role[output_spec.role],
            credentials=credentials.outputs[output_spec.role],
        )
    return WriteReceipts(by_role=by_role)


def notify_webhook(
    *,
    callback: Callback,
    payload: dict[str, Any],
    webhook: WebhookPort,
) -> WebhookAck:
    """Step 8 — POST a JWT-signed payload to the platform webhook."""
    return webhook.notify(callback=callback, payload=payload)


def _resolve_for_specs(
    secrets: SecretsPort,
    specs: Sequence[InputSpec] | Sequence[OutputSpec],
) -> dict[str, Credentials]:
    resolved: dict[str, Credentials] = {}
    for spec in specs:
        if spec.credential_ref is None:
            resolved[spec.role] = Credentials(token=b"", token_type=_NULL_TOKEN_TYPE)
        else:
            resolved[spec.role] = secrets.resolve(secret_ref=spec.credential_ref)
    return resolved
