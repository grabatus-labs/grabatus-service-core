"""JWT HS256 encode/decode helpers wrapping PyJWT.

Domain-side wrappers exist so the service runner never imports ``jwt``
directly; the wrappers translate PyJWT exceptions into our own
``WebhookAuthError`` with informative messages.
"""

from __future__ import annotations

from typing import Any, cast

import jwt
from jwt.exceptions import InvalidTokenError

from grabatus_service_core.errors import WebhookAuthError

_ALGORITHM = "HS256"
_MIN_SECRET_BYTES = 32


def encode_hs256(*, payload: dict[str, Any], secret: bytes) -> str:
    """Sign ``payload`` with HS256 and return a compact JWT string."""
    if len(secret) < _MIN_SECRET_BYTES:
        raise ValueError(
            f"HS256 secret must be at least {_MIN_SECRET_BYTES} bytes, got len={len(secret)}",
        )
    # PyJWT 2.x returns str; the bundled type stubs still describe the 1.x bytes shape.
    return cast("str", jwt.encode(payload, secret, algorithm=_ALGORITHM))


def decode_hs256(*, token: str, secret: bytes) -> dict[str, Any]:
    """Verify the HS256 signature and return the decoded payload."""
    if not token:
        raise WebhookAuthError(
            f"JWT token is empty, expected header.payload.signature; got token={token!r}",
        )
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except InvalidTokenError as exc:
        message = str(exc) or type(exc).__name__
        if "signature" in message.lower():
            raise WebhookAuthError(
                f"JWT signature verification failed: {message}",
            ) from exc
        raise WebhookAuthError(
            f"JWT token is malformed: {message}",
        ) from exc
    return dict(payload)
