"""Property: any registry x envelope dispatch outcome is deterministic."""

from __future__ import annotations

import json
from base64 import b64encode

from hypothesis import given
from hypothesis import strategies as st

from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
from grabatus_service_core.errors import UnknownServiceError
from grabatus_service_core.ports.values import RawMessage
from grabatus_service_core.receiver.registry import ServiceRegistry
from grabatus_service_core.receiver.runner import (
    SharedReceiverAdapters,
    SharedReceiverRunner,
)
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.testing import (
    AllowAllPolicy,
    FrozenClock,
    InMemoryJobDispatcher,
    NullObservability,
    make_opaque_contract,
)

# Match ServiceDescriptor.name pattern: ^[a-z][a-z0-9_-]*$ with max_length=64
_SERVICE_NAMES = st.from_regex(r"^[a-z][a-z0-9_-]{0,63}$", fullmatch=True)
_WORKER_NAMES = st.text(min_size=1, max_size=30)
_REGISTRY_PAIRS = st.dictionaries(
    keys=_SERVICE_NAMES,
    values=_WORKER_NAMES,
    min_size=0,
    max_size=5,
)


def _runner_with(registry: ServiceRegistry) -> SharedReceiverRunner:
    return SharedReceiverRunner(
        adapters=SharedReceiverAdapters(
            message=PubSubMessagePort(),
            authorizer=AllowAllPolicy(),
            job_dispatcher=InMemoryJobDispatcher(),
            observability=NullObservability(),
            clock=FrozenClock(iso_string="2026-04-27T12:00:00Z"),
        ),
        scheme_allowlist=SchemeAllowlist(allowed={"gs", "bigquery", "secret"}),
        registry=registry,
    )


def _raw_for(service_name: str) -> RawMessage:
    contract = make_opaque_contract(parameters={}, service_name=service_name)
    inner = json.dumps(contract.model_dump(mode="json")).encode("utf-8")
    wrapper = {"message": {"data": b64encode(inner).decode("ascii")}}
    return RawMessage(payload=json.dumps(wrapper).encode("utf-8"))


@given(registry_dict=_REGISTRY_PAIRS, envelope_service=_SERVICE_NAMES)
def test_dispatch_is_deterministic_with_respect_to_registry(
    registry_dict: dict[str, str],
    envelope_service: str,
) -> None:
    """Verify dispatch outcome depends only on registry membership."""
    runner = _runner_with(ServiceRegistry(by_name=registry_dict))
    raw = _raw_for(envelope_service)

    result = runner.execute(raw)

    if envelope_service in registry_dict:
        assert result.status == "ok"
        assert result.dispatched_job_id is not None
        assert result.error is None
    else:
        assert result.status == "error"
        assert isinstance(result.error, UnknownServiceError)
        assert result.dispatched_job_id is None
