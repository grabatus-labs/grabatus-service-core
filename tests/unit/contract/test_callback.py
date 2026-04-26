"""Tests for the Callback schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.callback import Callback


def test_callback_accepts_https_url_with_jwt_scheme() -> None:
    cb = Callback.model_validate(
        {"url": "https://grabatus.com/webhooks/svc", "auth_scheme": "jwt_hs256"},
    )

    assert str(cb.url) == "https://grabatus.com/webhooks/svc"
    assert cb.auth_scheme == "jwt_hs256"


def test_callback_rejects_http_url_in_production_default() -> None:
    with pytest.raises(ValidationError, match="https"):
        Callback.model_validate(
            {"url": "http://example.com/webhook", "auth_scheme": "jwt_hs256"},
        )


def test_callback_rejects_unknown_auth_scheme() -> None:
    with pytest.raises(ValidationError, match="auth_scheme"):
        Callback.model_validate(
            {"url": "https://x.com/wh", "auth_scheme": "bearer"},
        )


def test_callback_is_frozen() -> None:
    cb = Callback.model_validate(
        {"url": "https://x.com/wh", "auth_scheme": "jwt_hs256"},
    )

    with pytest.raises(ValidationError, match="frozen"):
        cb.auth_scheme = "other"  # type: ignore[misc]
