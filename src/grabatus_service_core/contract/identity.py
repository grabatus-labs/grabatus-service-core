"""Identity: caller identification for multi-tenant authorization."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

_TENANT_SLUG_PATTERN = r"^[a-z0-9-]+$"


class Identity(BaseModel):
    """Who is making the request.

    The ``tenant_id`` slug drives URI authorization (a request scoped to
    tenant ``grabatus`` may only access buckets/datasets prefixed with
    ``grabatus``). Slug is restricted to lowercase letters, digits, and
    hyphens to prevent path-traversal and case-folding ambiguity.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1, max_length=64)
    tenant_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=_TENANT_SLUG_PATTERN,
    )
