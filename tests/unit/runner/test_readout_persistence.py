"""Protocol 1.1 makes the readout an output the platform can actually fetch.

Under 1.0 the readout is validated and then dropped — nothing declares where
to write it. These tests pin the difference.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel

from grabatus_service_core.contract.base import BaseServiceContract
from grabatus_service_core.contract.readout.enums import READOUT_OUTPUT_ROLE
from grabatus_service_core.errors import InvalidContractError
from grabatus_service_core.ports.values import Credentials, RawMessage
from grabatus_service_core.runner import RuntimeMode, ServiceRunner, build_runner
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.testing import (
    AllowAllPolicy,
    FrozenClock,
    InMemoryJobDispatcher,
    InMemoryMessagePort,
    InMemorySecretsAdapter,
    InMemoryStorage,
    NullObservability,
    RecordingWebhookNotifier,
    make_contract,
    make_envelope,
    make_fake_compute_backend,
    make_input_spec,
    make_output_spec,
)


class _Params(BaseModel):
    horizon: int


_READOUT_URI = "gs://gbt-storage-grabatus/user_999/readout.json"
_RESULT_URI = "gs://gbt-storage-grabatus/user_999/out.json"


def _storage() -> InMemoryStorage:
    return InMemoryStorage(seed={"gs://gbt-storage-grabatus/user_999/in.xlsx": b"raw"})


def _runner(storage: InMemoryStorage) -> ServiceRunner[_Params]:
    return build_runner(
        contract_type=BaseServiceContract[_Params],
        storage=storage,
        message=InMemoryMessagePort(),
        webhook=RecordingWebhookNotifier(),
        compute=make_fake_compute_backend(
            required_input_roles=frozenset({"timeseries"}),
            output_roles=frozenset({"result_json"}),
            outputs={"result_json": b"forecast-bytes"},
        ),
        secrets=InMemorySecretsAdapter(seed={}),
        authorizer=AllowAllPolicy(),
        observability=NullObservability(),
        clock=FrozenClock(iso_string="2026-04-26T00:00:00Z"),
        job_dispatcher=InMemoryJobDispatcher(),
        scheme_allowlist=SchemeAllowlist(allowed=frozenset({"gs"})),
        mode=RuntimeMode.MONOLITH,
    )


def _contract_dict(*, protocol_version: str, with_readout_output: bool) -> dict[str, Any]:
    outputs = [make_output_spec(destination_uri=_RESULT_URI)]
    if with_readout_output:
        outputs.append(
            make_output_spec(role=READOUT_OUTPUT_ROLE, destination_uri=_READOUT_URI, fmt="json"),
        )
    return make_contract(
        parameters=_Params(horizon=30),
        envelope=make_envelope(protocol_version=protocol_version),
        outputs=outputs,
    ).model_dump(mode="json")


def _raw(contract: dict[str, Any]) -> RawMessage:
    return RawMessage(payload=json.dumps(contract).encode("utf-8"))


def _read(storage: InMemoryStorage, uri: str) -> bytes:
    return storage.read(
        spec=make_input_spec(source_uri=uri),
        credentials=Credentials(token=b"", token_type="none"),
    )


def test_protocol_1_1_writes_the_readout_where_the_platform_can_fetch_it() -> None:
    storage = _storage()

    result = _runner(storage).execute(
        _raw(_contract_dict(protocol_version="1.1", with_readout_output=True)),
    )

    assert result.status == "ok"
    assert result.receipts is not None
    assert READOUT_OUTPUT_ROLE in result.receipts.by_role
    persisted = json.loads(_read(storage, _READOUT_URI))
    contract = _contract_dict(protocol_version="1.1", with_readout_output=True)
    # What the platform fetches must identify this run, not a canned example.
    assert persisted["request"]["request_id"] == contract["envelope"]["request_id"]
    assert persisted["service"]["name"] == contract["service"]["name"]


def test_protocol_1_1_rejects_a_contract_that_declares_no_readout_output() -> None:
    result = _runner(_storage()).execute(
        _raw(_contract_dict(protocol_version="1.1", with_readout_output=False)),
    )

    assert result.status == "error"
    assert isinstance(result.error, InvalidContractError)
    assert READOUT_OUTPUT_ROLE in str(result.error)


def test_protocol_1_0_still_runs_and_still_writes_no_readout() -> None:
    storage = _storage()

    result = _runner(storage).execute(
        _raw(_contract_dict(protocol_version="1.0", with_readout_output=False)),
    )

    assert result.status == "ok"
    assert result.receipts is not None
    assert READOUT_OUTPUT_ROLE not in result.receipts.by_role


def test_protocol_1_0_rejects_a_contract_that_declares_a_readout_output() -> None:
    """1.0 has no readout role; declaring one is a contract the SDK cannot honour."""
    result = _runner(_storage()).execute(
        _raw(_contract_dict(protocol_version="1.0", with_readout_output=True)),
    )

    assert result.status == "error"
    assert isinstance(result.error, InvalidContractError)


@pytest.mark.parametrize("protocol_version", ["1.0", "1.1"])
def test_the_service_never_declares_the_readout_in_its_own_output_roles(
    protocol_version: str,
) -> None:
    """The SDK owns the role, so a service that never heard of it still complies."""
    backend = make_fake_compute_backend(
        required_input_roles=frozenset({"timeseries"}),
        output_roles=frozenset({"result_json"}),
        outputs={"result_json": b"forecast-bytes"},
    )

    assert READOUT_OUTPUT_ROLE not in backend.OUTPUT_ROLES

    storage = _storage()
    result = _runner(storage).execute(
        _raw(
            _contract_dict(
                protocol_version=protocol_version,
                with_readout_output=protocol_version == "1.1",
            ),
        ),
    )

    assert result.status == "ok"
