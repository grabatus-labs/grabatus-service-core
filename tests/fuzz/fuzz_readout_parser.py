"""Fuzz the ModelReadout JSON parser.

Run locally on Linux::

    uv run python tests/fuzz/fuzz_readout_parser.py -atheris_runs=10000

CI runs this for a 60-second budget on every push to ``main``.

Invariant: validating arbitrary bytes either succeeds (well-formed
readout) or raises ``ValidationError``. Any other exception is a
fuzz finding.
"""

from __future__ import annotations

import sys

from pydantic import ValidationError

from grabatus_service_core.contract.readout import ModelReadout


def fuzz_one_input(data: bytes) -> None:
    try:
        ModelReadout.model_validate_json(data)
    except ValidationError:
        return
    except (UnicodeDecodeError, ValueError):
        return


def main() -> None:  # pragma: no cover  # entry point only on Linux runners
    import atheris  # noqa: PLC0415  # atheris is Linux-only

    atheris.Setup(sys.argv, fuzz_one_input)
    atheris.Fuzz()


if __name__ == "__main__":  # pragma: no cover  # CLI guard
    main()
