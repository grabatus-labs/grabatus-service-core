"""Callback: how the service notifies the platform when work completes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator

AuthScheme = Literal["jwt_hs256"]


class Callback(BaseModel):
    """Webhook destination the service notifies after the pipeline finishes.

    Only HTTPS URLs are accepted. The signing scheme is constrained to a
    closed set; ``jwt_hs256`` is the only scheme supported in v1.0.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: HttpUrl
    auth_scheme: AuthScheme

    @field_validator("url")
    @classmethod
    def _require_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError(
                f"Callback url must use https scheme, got {value.scheme!r}",
            )
        return value
