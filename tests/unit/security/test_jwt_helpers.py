"""Tests for JWT helpers."""

from __future__ import annotations

import base64
import json
import time

import pytest

from grabatus_service_core.errors import WebhookAuthError
from grabatus_service_core.security.jwt_helpers import decode_hs256, encode_hs256

_KEY = b"test-secret-key-at-least-32-bytes-long-padding"


def test_encode_then_decode_round_trip() -> None:
    payload = {"request_id": "abc", "iat": int(time.time())}

    token = encode_hs256(payload=payload, secret=_KEY)
    decoded = decode_hs256(token=token, secret=_KEY)

    assert decoded["request_id"] == "abc"


def test_decode_rejects_token_signed_with_wrong_key() -> None:
    payload = {"request_id": "abc"}
    token = encode_hs256(payload=payload, secret=_KEY)

    with pytest.raises(WebhookAuthError, match="signature"):
        decode_hs256(
            token=token,
            secret=b"wrong-secret-key-padding-padding",
        )


def test_decode_rejects_malformed_token() -> None:
    with pytest.raises(WebhookAuthError, match="malformed"):
        decode_hs256(token="not.a.token", secret=_KEY)


def test_decode_rejects_empty_token() -> None:
    with pytest.raises(WebhookAuthError, match="empty"):
        decode_hs256(token="", secret=_KEY)


def test_encode_rejects_short_secret() -> None:
    with pytest.raises(ValueError, match="secret"):
        encode_hs256(payload={"x": 1}, secret=b"short")


def test_encode_includes_alg_hs256_header() -> None:
    token = encode_hs256(payload={"x": 1}, secret=_KEY)
    header_segment = token.split(".")[0]
    header_padded = header_segment + "=" * (-len(header_segment) % 4)
    decoded_header = json.loads(base64.urlsafe_b64decode(header_padded))

    assert decoded_header["alg"] == "HS256"
