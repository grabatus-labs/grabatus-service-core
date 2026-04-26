"""InlineStorage: read tiny payloads embedded directly in inline:// URIs.

Wire format: ``inline://<encoding>,<data>`` where ``encoding`` is one of
``base64`` or ``utf8``. Reading inline outputs is undefined and raises.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from grabatus_service_core.errors import (
    FormatParsingError,
    InputReadError,
    OutputWriteError,
    UnsupportedSchemeError,
)

if TYPE_CHECKING:
    from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
    from grabatus_service_core.ports.values import Credentials, WriteReceipt

_INLINE_SCHEME = "inline"
_BASE64_ENCODING = "base64"
_UTF8_ENCODING = "utf8"


class InlineStorage:
    """Decode inline:// URIs to raw bytes; write is not supported."""

    def read(self, *, spec: InputSpec, credentials: Credentials) -> bytes:
        del credentials
        uri = str(spec.source_uri)
        return _decode_inline_uri(uri)

    def write(
        self,
        *,
        spec: OutputSpec,
        payload: bytes,
        credentials: Credentials,
    ) -> WriteReceipt:
        del payload, credentials
        uri = str(spec.destination_uri)
        raise OutputWriteError(
            f"InlineStorage does not support writing; destination_uri={uri!r}",
        )


def _decode_inline_uri(uri: str) -> bytes:
    scheme, _, rest = uri.partition("://")
    if scheme != _INLINE_SCHEME:
        raise UnsupportedSchemeError(
            f"InlineStorage requires scheme={_INLINE_SCHEME!r}, got uri={uri!r}",
        )
    encoding, _, data = rest.partition(",")
    if not data:
        raise InputReadError(
            f"InlineStorage URI is missing data after the comma; uri={uri!r}",
        )
    if encoding == _BASE64_ENCODING:
        try:
            return base64.b64decode(data, validate=True)
        except (ValueError, TypeError) as exc:
            raise FormatParsingError(
                f"InlineStorage base64 payload failed to decode: {exc}",
            ) from exc
    if encoding == _UTF8_ENCODING:
        return data.encode("utf-8")
    raise UnsupportedSchemeError(
        f"InlineStorage encoding={encoding!r} not supported; use 'base64' or 'utf8'; uri={uri!r}",
    )
