"""ServiceRegistry: maps envelope.service.name to the Cloud Run Job that runs it."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from grabatus_service_core.errors import UnknownServiceError

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class ServiceRegistry:
    """Immutable name -> worker_job_name lookup.

    Example:
        >>> registry = ServiceRegistry(by_name={"forecast": "grabatus-forecasting-worker"})
        >>> registry.resolve("forecast")
        'grabatus-forecasting-worker'
    """

    by_name: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "by_name", MappingProxyType(dict(self.by_name)))

    def resolve(self, service_name: str) -> str:
        """Return the worker job name registered for ``service_name``.

        Raises ``UnknownServiceError`` if no entry matches.
        """
        try:
            return self.by_name[service_name]
        except KeyError as exc:
            known = sorted(self.by_name)
            raise UnknownServiceError(
                f"service.name={service_name!r} not in registry; known: {known!r}",
            ) from exc

    @classmethod
    def from_env_string(cls, raw: str) -> ServiceRegistry:
        """Parse a comma-separated ``name:worker_job_name`` string.

        Example:
            >>> r = ServiceRegistry.from_env_string("forecast:fc,abtest:ab")
            >>> r.resolve("abtest")
            'ab'
        """
        if not raw.strip():
            return cls(by_name={})
        by_name: dict[str, str] = {}
        for item in raw.split(","):
            if ":" not in item:
                raise ValueError(
                    f"registry entry {item!r} malformed; expected 'name:worker'",
                )
            name, _, worker = item.partition(":")
            name = name.strip()
            worker = worker.strip()
            if not name or not worker:
                raise ValueError(
                    f"registry entry {item!r} has empty name or worker",
                )
            if name in by_name:
                raise ValueError(f"duplicate service name {name!r} in registry")
            by_name[name] = worker
        return cls(by_name=by_name)
