"""Proof that a service can now satisfy the readout gate on its own.

Before ``ComputeContext`` existed, ``run()`` saw only ``inputs`` and
``parameters``, while the readout demanded five ids that live in the
contract. Every test that passed did so because the SDK's own fake emitted
synthetic ids. These tests use a backend written the way a service author
writes one — see :mod:`examples.forecast_service.compute`.
"""

from __future__ import annotations

import json
from typing import Any

from examples.forecast_service.compute import (
    RESULT_URI,
    MovingAverageBackend,
    MovingAverageParameters,
)

from grabatus_service_core.contract.base import BaseServiceContract
from grabatus_service_core.contract.readout.enums import READOUT_OUTPUT_ROLE
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
    make_input_spec,
    make_output_spec,
    make_service_descriptor,
)

_READOUT_URI = "gs://gbt-storage-grabatus/user_999/readout.json"
_RUN_AT = "2026-04-26T00:00:00Z"


def _storage() -> InMemoryStorage:
    return InMemoryStorage(seed={"gs://gbt-storage-grabatus/user_999/in.xlsx": b"raw"})


def _runner(storage: InMemoryStorage) -> ServiceRunner[MovingAverageParameters]:
    return build_runner(
        contract_type=BaseServiceContract[MovingAverageParameters],
        storage=storage,
        message=InMemoryMessagePort(),
        webhook=RecordingWebhookNotifier(),
        compute=MovingAverageBackend(),
        secrets=InMemorySecretsAdapter(seed={}),
        authorizer=AllowAllPolicy(),
        observability=NullObservability(),
        clock=FrozenClock(iso_string=_RUN_AT),
        job_dispatcher=InMemoryJobDispatcher(),
        scheme_allowlist=SchemeAllowlist(allowed=frozenset({"gs"})),
        mode=RuntimeMode.MONOLITH,
    )


def _contract() -> dict[str, Any]:
    return make_contract(
        parameters=MovingAverageParameters(horizon=3),
        envelope=make_envelope(protocol_version="1.1"),
        service=make_service_descriptor(name="grabatus-forecasting", version="2.1.0"),
        inputs=[make_input_spec(role="timeseries")],
        outputs=[
            make_output_spec(role="result_json", destination_uri=RESULT_URI),
            make_output_spec(
                role=READOUT_OUTPUT_ROLE,
                destination_uri=_READOUT_URI,
                fmt="json",
            ),
        ],
    ).model_dump(mode="json")


def _persisted_readout(storage: InMemoryStorage) -> dict[str, Any]:
    blob = storage.read(
        spec=make_input_spec(source_uri=_READOUT_URI),
        credentials=Credentials(token=b"", token_type="none"),
    )
    parsed: dict[str, Any] = json.loads(blob)
    return parsed


def test_a_service_written_by_hand_now_passes_the_readout_gate() -> None:
    storage = _storage()

    result = _runner(storage).execute(
        RawMessage(payload=json.dumps(_contract()).encode("utf-8")),
    )

    assert result.status == "ok", result.error
    assert result.receipts is not None
    assert READOUT_OUTPUT_ROLE in result.receipts.by_role


def test_the_persisted_readout_identifies_this_run_and_not_a_template() -> None:
    storage = _storage()
    contract = _contract()

    _runner(storage).execute(RawMessage(payload=json.dumps(contract).encode("utf-8")))

    readout = _persisted_readout(storage)
    assert readout["request"]["request_id"] == contract["envelope"]["request_id"]
    assert readout["request"]["tenant_id"] == contract["identity"]["tenant_id"]
    assert readout["request"]["result_id"] == contract["references"]["result_id"]
    assert readout["request"]["parameter_id"] == contract["references"]["parameter_id"]
    assert readout["request"]["origin"] == contract["envelope"]["origin"]
    assert readout["service"] == contract["service"]


def test_the_readout_timestamp_comes_from_the_injected_clock() -> None:
    """A backend calling datetime.now() would make its own readout untestable."""
    storage = _storage()

    _runner(storage).execute(RawMessage(payload=json.dumps(_contract()).encode("utf-8")))

    assert _persisted_readout(storage)["generated_at"].startswith("2026-04-26T00:00:00")


def test_the_readout_still_carries_what_the_service_computed() -> None:
    """The context supplies identity only — the conclusions remain the service's."""
    storage = _storage()

    _runner(storage).execute(RawMessage(payload=json.dumps(_contract()).encode("utf-8")))

    readout = _persisted_readout(storage)
    assert readout["findings"][0]["id"] == "level_001"
    assert "3 semanas" in readout["findings"][0]["statement"]
    assert readout["model"]["family"] == "time_series_forecast"
