"""Concrete contract used as the snapshot anchor and fixture target.

A snapshot of the *generic* ``BaseServiceContract`` is uninteresting
because the JSON Schema includes a ``ParamsT`` placeholder. The
snapshot tests pin a concrete subclass parameterized by an
``EmptySnapshotParameters`` model so the generated schema is fully
materialised and stable across runs.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from grabatus_service_core.contract.base import BaseServiceContract


class EmptySnapshotParameters(BaseModel):
    """Parameters payload with no fields, used by the snapshot harness."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SnapshotContract(BaseServiceContract[EmptySnapshotParameters]):
    """Concrete contract used by the snapshot tests."""
