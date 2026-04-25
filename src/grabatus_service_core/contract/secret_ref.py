"""SecretRef: typed reference to a secret in a remote secret manager."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

_SECRET_SCHEME = "secret"  # noqa: S105 # nosec B105 # pragma: allowlist secret
_DEFAULT_VERSION = "latest"
_PATH_PARTS_WITH_VERSION = 2


class SecretRef(BaseModel):
    """Typed reference to a secret stored in a secret manager.

    Wire format: ``secret://<provider>/<name>[/<version>]``. Examples::

        secret://gcp-secret-manager/bq-reader/3
        secret://gcp-secret-manager/webhook-signing-key  # implies latest

    The ``SecretsPort`` resolves a ``SecretRef`` to actual credential bytes
    at runtime. The reference itself is safe to log — it does not contain
    the secret value.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(default=_DEFAULT_VERSION, min_length=1, max_length=32)

    @model_validator(mode="before")
    @classmethod
    def _parse_uri(cls, value: Any) -> Any:  # noqa: ANN401
        if isinstance(value, str):
            return cls._parse_secret_uri(value)
        return value

    @staticmethod
    def _parse_secret_uri(uri: str) -> dict[str, str]:
        parsed = urlparse(uri)
        if parsed.scheme != _SECRET_SCHEME:
            raise ValueError(
                f"SecretRef requires scheme='{_SECRET_SCHEME}://', "
                f"got scheme={parsed.scheme!r}",
            )
        provider = parsed.netloc
        if not provider:
            raise ValueError(
                f"SecretRef requires a provider after 'secret://', " f"got uri={uri!r}",
            )
        path = parsed.path.lstrip("/")
        if not path:
            raise ValueError(
                f"SecretRef requires a secret name in the path, got uri={uri!r}",
            )
        parts = path.split("/", 1)
        name = parts[0]
        version = parts[1] if len(parts) == _PATH_PARTS_WITH_VERSION else _DEFAULT_VERSION
        return {"provider": provider, "name": name, "version": version}

    def to_uri(self) -> str:
        """Render this reference back to its canonical URI form."""
        if self.version == _DEFAULT_VERSION:
            return f"{_SECRET_SCHEME}://{self.provider}/{self.name}"
        return f"{_SECRET_SCHEME}://{self.provider}/{self.name}/{self.version}"

    @model_serializer(when_used="json")
    def _serialize_for_json(self) -> str:
        # JSON output collapses to the URI form so the contract round-trips
        # through wire format. Python-mode dumping retains the structured
        # fields (provider/name/version) which is what tests typically need.
        return self.to_uri()
