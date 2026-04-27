"""Fuzz the Pub/Sub raw envelope decoder.

Run locally on Linux::

    uv run python tests/fuzz/fuzz_pubsub_decoder.py -atheris_runs=10000

CI runs this for a 60-second budget on every push to ``main``.

Invariant: the decoder either returns a ``dict`` (well-formed payload)
or raises ``MalformedMessageError`` (rejected payload). Any other
exception is a fuzz finding.
"""

from __future__ import annotations

import sys

from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
from grabatus_service_core.errors import MalformedMessageError
from grabatus_service_core.ports.values import RawMessage

_decoder = PubSubMessagePort()


def fuzz_one_input(data: bytes) -> None:
    try:
        _decoder.decode(RawMessage(payload=data))
    except MalformedMessageError:
        return


def main() -> None:  # pragma: no cover  # entry point only on Linux runners
    import atheris  # noqa: PLC0415  # atheris is Linux-only

    atheris.Setup(sys.argv, fuzz_one_input)
    atheris.Fuzz()


if __name__ == "__main__":  # pragma: no cover  # CLI guard
    main()
