"""Tests for HttpComputeBackend (mock httpx)."""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import httpx
import pytest

from grabatus_service_core.adapters.http_compute_backend import (
    HttpComputeBackend,
    make_http_compute_backend,
)
from grabatus_service_core.errors import ComputeError
from grabatus_service_core.ports.compute import ComputeBackendPort
from grabatus_service_core.ports.values import LoadedInputs
from grabatus_service_core.testing import make_compute_context

if TYPE_CHECKING:
    from collections.abc import Mapping

_TARGET_URL = "https://lambda.example.com/forecast"
_CONTEXT = make_compute_context()


def _backend(
    client: MagicMock,
    *,
    required: frozenset[str] = frozenset({"timeseries"}),
    optional: frozenset[str] = frozenset(),
    outputs: frozenset[str] = frozenset({"result_json"}),
) -> HttpComputeBackend:
    return make_http_compute_backend(
        target_url=_TARGET_URL,
        required_input_roles=required,
        optional_input_roles=optional,
        output_roles=outputs,
        client=client,
    )


def _response(
    *,
    status: int = 200,
    json_body: Any | None = None,
    json_error: BaseException | None = None,
) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status
    if json_error is not None:
        response.json.side_effect = json_error
    else:
        response.json.return_value = json_body
    return response


def _client_with(response: MagicMock) -> MagicMock:
    client = MagicMock()
    client.post.return_value = response
    return client


def _ok_body(
    outputs: Mapping[str, bytes],
    metadata: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    return {
        "outputs": {role: base64.b64encode(blob).decode("ascii") for role, blob in outputs.items()},
        "metadata": dict(metadata) if metadata is not None else {},
    }


def test_http_backend_satisfies_port() -> None:
    assert isinstance(_backend(MagicMock()), ComputeBackendPort)


def test_http_backend_returns_compute_result_on_2xx() -> None:
    body = _ok_body({"result_json": b'{"forecast":1}'}, metadata={"model": "prophet"})
    backend = _backend(_client_with(_response(json_body=body)))

    result = backend.run(
        inputs=LoadedInputs(by_role={"timeseries": b"raw-bytes"}),
        parameters=None,
        context=_CONTEXT,
    )

    assert result.by_role["result_json"] == b'{"forecast":1}'
    assert result.metadata["model"] == "prophet"


def test_http_backend_sends_inputs_as_base64() -> None:
    client = _client_with(_response(json_body=_ok_body({"result_json": b"x"})))
    backend = _backend(client)

    backend.run(
        inputs=LoadedInputs(by_role={"timeseries": b"hello"}),
        parameters={"horizon": 30},
        context=_CONTEXT,
    )

    body = client.post.call_args.kwargs["json"]
    assert body["inputs"]["timeseries"] == base64.b64encode(b"hello").decode("ascii")
    assert body["parameters"] == {"horizon": 30}
    assert client.post.call_args.args == (_TARGET_URL,)


def test_http_backend_forwards_the_run_identity_to_the_remote_backend() -> None:
    """An off-platform backend needs the same ids to build its readout."""
    client = _client_with(_response(json_body=_ok_body({"result_json": b"x"})))

    _backend(client).run(
        inputs=LoadedInputs(by_role={"timeseries": b"x"}),
        parameters=None,
        context=_CONTEXT,
    )

    sent = client.post.call_args.kwargs["json"]["context"]
    assert sent["request_id"] == _CONTEXT.request_id
    assert sent["tenant_id"] == _CONTEXT.tenant_id
    assert sent["service_version"] == _CONTEXT.service_version
    assert sent["generated_at"] == _CONTEXT.generated_at.isoformat()


def test_http_backend_sends_parameters_via_model_dump_when_available() -> None:
    class _Params:
        def model_dump(self) -> dict[str, Any]:
            return {"horizon": 7, "freq": "W"}

    client = _client_with(_response(json_body=_ok_body({"result_json": b"x"})))
    backend = _backend(client)

    backend.run(
        inputs=LoadedInputs(by_role={"timeseries": b"x"}),
        parameters=_Params(),
        context=_CONTEXT,
    )

    assert client.post.call_args.kwargs["json"]["parameters"] == {
        "horizon": 7,
        "freq": "W",
    }


def test_http_backend_translates_non_2xx_to_compute_error() -> None:
    backend = _backend(_client_with(_response(status=500)))

    with pytest.raises(ComputeError, match="non-2xx=500"):
        backend.run(
            inputs=LoadedInputs(by_role={"timeseries": b"x"}),
            parameters=None,
            context=_CONTEXT,
        )


def test_http_backend_translates_invalid_json_to_compute_error() -> None:
    backend = _backend(
        _client_with(_response(json_error=json.JSONDecodeError("not json", "", 0))),
    )

    with pytest.raises(ComputeError, match="not valid JSON"):
        backend.run(
            inputs=LoadedInputs(by_role={"timeseries": b"x"}),
            parameters=None,
            context=_CONTEXT,
        )


def test_http_backend_translates_non_object_response_to_compute_error() -> None:
    backend = _backend(_client_with(_response(json_body=["not", "a", "dict"])))

    with pytest.raises(ComputeError, match="must be a JSON object"):
        backend.run(
            inputs=LoadedInputs(by_role={"timeseries": b"x"}),
            parameters=None,
            context=_CONTEXT,
        )


def test_http_backend_translates_missing_outputs_field_to_compute_error() -> None:
    backend = _backend(_client_with(_response(json_body={"metadata": {}})))

    with pytest.raises(ComputeError, match="'outputs' object"):
        backend.run(
            inputs=LoadedInputs(by_role={"timeseries": b"x"}),
            parameters=None,
            context=_CONTEXT,
        )


def test_http_backend_translates_non_string_output_to_compute_error() -> None:
    backend = _backend(
        _client_with(_response(json_body={"outputs": {"result_json": 42}})),
    )

    with pytest.raises(ComputeError, match="must be a base64 string"):
        backend.run(
            inputs=LoadedInputs(by_role={"timeseries": b"x"}),
            parameters=None,
            context=_CONTEXT,
        )


def test_http_backend_translates_invalid_base64_output_to_compute_error() -> None:
    backend = _backend(
        _client_with(_response(json_body={"outputs": {"result_json": "not!base64$"}})),
    )

    with pytest.raises(ComputeError, match="not valid base64"):
        backend.run(
            inputs=LoadedInputs(by_role={"timeseries": b"x"}),
            parameters=None,
            context=_CONTEXT,
        )


def test_http_backend_translates_non_dict_metadata_to_compute_error() -> None:
    body = {
        "outputs": {"result_json": base64.b64encode(b"x").decode("ascii")},
        "metadata": "not-a-dict",
    }
    backend = _backend(_client_with(_response(json_body=body)))

    with pytest.raises(ComputeError, match="'metadata' must be an object"):
        backend.run(
            inputs=LoadedInputs(by_role={"timeseries": b"x"}),
            parameters=None,
            context=_CONTEXT,
        )


def test_http_backend_treats_missing_metadata_as_empty() -> None:
    body = {"outputs": {"result_json": base64.b64encode(b"x").decode("ascii")}}
    backend = _backend(_client_with(_response(json_body=body)))

    result = backend.run(
        inputs=LoadedInputs(by_role={"timeseries": b"x"}),
        parameters=None,
        context=_CONTEXT,
    )

    assert dict(result.metadata) == {}


def test_http_backend_retries_on_timeout_then_succeeds() -> None:
    ok_response = _response(json_body=_ok_body({"result_json": b"recovered"}))
    client = MagicMock()
    client.post.side_effect = [httpx.TimeoutException("slow"), ok_response]
    backend = _backend(client)

    result = backend.run(
        inputs=LoadedInputs(by_role={"timeseries": b"x"}),
        parameters=None,
        context=_CONTEXT,
    )

    assert result.by_role["result_json"] == b"recovered"
    assert client.post.call_count == 2


def test_http_backend_translates_other_httpx_error_to_compute_error() -> None:
    client = MagicMock()
    client.post.side_effect = httpx.HTTPError("boom")
    backend = _backend(client)

    with pytest.raises(ComputeError, match="boom"):
        backend.run(
            inputs=LoadedInputs(by_role={"timeseries": b"x"}),
            parameters=None,
            context=_CONTEXT,
        )


def test_make_http_compute_backend_isolates_role_declarations() -> None:
    a = _backend(MagicMock(), outputs=frozenset({"a_out"}))
    b = _backend(MagicMock(), outputs=frozenset({"b_out"}))

    assert frozenset({"a_out"}) == type(a).OUTPUT_ROLES
    assert frozenset({"b_out"}) == type(b).OUTPUT_ROLES


def test_http_backend_default_construction_has_empty_role_classvars() -> None:
    # Constructing the base class directly leaves ClassVars at their defaults;
    # the factory is the supported entry point.
    backend = HttpComputeBackend(target_url=_TARGET_URL, client=MagicMock())

    assert frozenset() == backend.REQUIRED_INPUT_ROLES
    assert frozenset() == backend.OPTIONAL_INPUT_ROLES
    assert frozenset() == backend.OUTPUT_ROLES
