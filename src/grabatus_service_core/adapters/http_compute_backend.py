"""HttpComputeBackend: forward run requests to an external HTTP endpoint.

Legacy adapter for services whose compute is hosted off-platform (the
canonical case is the Grabatus forecasting AWS Lambda). New services
should implement :class:`ComputeBackendPort` directly; this adapter
exists so the existing Lambda fleet can plug into the runner without
rewriting them.

Wire envelope (JSON):

    request:  {"inputs": {<role>: <base64>}, "parameters": <obj>}
    response: {"outputs": {<role>: <base64>}, "metadata": <obj>}
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import TYPE_CHECKING, Any, ClassVar, cast

import httpx

from grabatus_service_core.adapters.retry import with_retry
from grabatus_service_core.errors import ComputeError
from grabatus_service_core.ports.values import ComputeResult

if TYPE_CHECKING:
    from grabatus_service_core.ports.values import LoadedInputs


_HTTP_OK_LOWER_BOUND = 200
_HTTP_OK_UPPER_BOUND = 300
_DEFAULT_TIMEOUT_SECONDS = 600.0
_RETRIABLE_HTTP_ERRORS: tuple[type[BaseException], ...] = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)


def make_http_compute_backend(
    *,
    target_url: str,
    required_input_roles: frozenset[str],
    output_roles: frozenset[str],
    optional_input_roles: frozenset[str] = frozenset(),
    client: httpx.Client | None = None,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> HttpComputeBackend:
    """Build an HttpComputeBackend whose role frozensets are configured per-call.

    Mirrors :func:`make_fake_compute_backend` from ``testing/compute.py``:
    each call creates a fresh subclass so different services can declare
    distinct role sets in the same process without leaking state.
    """
    cls_namespace: dict[str, Any] = {
        "REQUIRED_INPUT_ROLES": required_input_roles,
        "OPTIONAL_INPUT_ROLES": optional_input_roles,
        "OUTPUT_ROLES": output_roles,
    }
    configured_cls = cast(
        "type[HttpComputeBackend]",
        type("HttpComputeBackend_Configured", (HttpComputeBackend,), cls_namespace),
    )
    return configured_cls(
        target_url=target_url,
        client=client,
        timeout_seconds=timeout_seconds,
    )


class HttpComputeBackend:
    """Forward compute requests to an external HTTP endpoint."""

    REQUIRED_INPUT_ROLES: ClassVar[frozenset[str]] = frozenset()
    OPTIONAL_INPUT_ROLES: ClassVar[frozenset[str]] = frozenset()
    OUTPUT_ROLES: ClassVar[frozenset[str]] = frozenset()

    def __init__(
        self,
        *,
        target_url: str,
        client: httpx.Client | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._target_url = target_url
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._timeout = timeout_seconds

    @with_retry(retry_on=_RETRIABLE_HTTP_ERRORS)
    def run(self, *, inputs: LoadedInputs, parameters: Any) -> ComputeResult:  # noqa: ANN401
        body = self._encode_request(inputs, parameters)
        try:
            response = self._client.post(
                self._target_url,
                json=body,
                timeout=self._timeout,
            )
        except _RETRIABLE_HTTP_ERRORS:
            raise
        except httpx.HTTPError as exc:
            raise ComputeError(
                f"HttpComputeBackend POST to {self._target_url!r} failed: {exc}",
            ) from exc
        if not (_HTTP_OK_LOWER_BOUND <= response.status_code < _HTTP_OK_UPPER_BOUND):
            raise ComputeError(
                f"HttpComputeBackend non-2xx={response.status_code} from {self._target_url!r}",
            )
        return self._decode_response(response)

    def _encode_request(
        self,
        inputs: LoadedInputs,
        parameters: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        encoded_inputs = {
            role: base64.b64encode(blob).decode("ascii") for role, blob in inputs.by_role.items()
        }
        model_dump = getattr(parameters, "model_dump", None)
        params_payload = model_dump() if callable(model_dump) else parameters
        return {"inputs": encoded_inputs, "parameters": params_payload}

    def _decode_response(self, response: httpx.Response) -> ComputeResult:
        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise ComputeError(
                f"HttpComputeBackend response from {self._target_url!r} is not valid JSON: {exc}",
            ) from exc
        if not isinstance(body, dict):
            raise ComputeError(
                f"HttpComputeBackend response from {self._target_url!r} "
                f"must be a JSON object, got {type(body).__name__}",
            )
        outputs_field = body.get("outputs")
        if not isinstance(outputs_field, dict):
            raise ComputeError(
                f"HttpComputeBackend response from {self._target_url!r} "
                f"must contain an 'outputs' object",
            )
        decoded_outputs = self._decode_outputs(outputs_field)
        metadata_field = body.get("metadata", {})
        if not isinstance(metadata_field, dict):
            raise ComputeError(
                f"HttpComputeBackend response 'metadata' must be an object, "
                f"got {type(metadata_field).__name__}",
            )
        return ComputeResult(by_role=decoded_outputs, metadata=metadata_field)

    @staticmethod
    def _decode_outputs(outputs_field: dict[str, Any]) -> dict[str, bytes]:
        decoded: dict[str, bytes] = {}
        for role, encoded in outputs_field.items():
            if not isinstance(encoded, str):
                raise ComputeError(
                    f"HttpComputeBackend response output role={role!r} "
                    f"must be a base64 string, got {type(encoded).__name__}",
                )
            try:
                decoded[role] = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ComputeError(
                    f"HttpComputeBackend response output role={role!r} is not valid base64: {exc}",
                ) from exc
        return decoded
