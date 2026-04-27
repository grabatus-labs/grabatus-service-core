"""Smoke tests: fuzz harnesses import and accept arbitrary bytes safely.

These tests run on every push (including non-Linux) and verify that
the harness ``fuzz_one_input`` functions never raise on representative
samples of arbitrary bytes. Atheris itself is Linux-only and is not
imported by these tests.
"""

from __future__ import annotations

import pytest

from tests.fuzz import fuzz_contract_parser, fuzz_pubsub_decoder

_FUZZ_SAMPLES = [
    b"",
    b"\x00",
    b"\xff" * 32,
    b"{}",
    b'{"message":{"data":"!!!"}}',
    b'{"message":{"data":""}}',
    b'{"not":"a-pubsub-envelope"}',
    b'{"message":42}',
    b"not-json-at-all",
    b"\xc3\x28",
]


@pytest.mark.parametrize("payload", _FUZZ_SAMPLES)
def test_pubsub_fuzz_input_never_raises_unexpected(payload: bytes) -> None:
    fuzz_pubsub_decoder.fuzz_one_input(payload)


@pytest.mark.parametrize("payload", _FUZZ_SAMPLES)
def test_contract_fuzz_input_never_raises_unexpected(payload: bytes) -> None:
    fuzz_contract_parser.fuzz_one_input(payload)
