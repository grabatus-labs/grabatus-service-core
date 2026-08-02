"""The published schema must carry the promises the prose makes.

The Django platform generates its integration from the snapshot, not from
the Pydantic models. Any constraint that lives only in the model is a
promise the machine-readable artefact does not keep — the same class of
divergence the Phase 1 review found in the prose.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from grabatus_service_core.contract.readout.artifacts import (
    ARTIFACT_URI_PATTERN,
    ArtifactDescription,
)

_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent / "snapshots" / "v1.1" / "model_readout.schema.json"
)


def _published_uri_schema() -> dict[str, object]:
    snapshot = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    schema: dict[str, object] = snapshot["$defs"]["ArtifactDescription"]["properties"]["uri"]
    return schema


def _artifact_payload(uri: str) -> dict[str, object]:
    return {
        "role": "rules_json",
        "uri": uri,
        "format": "json",
        "description": "irrelevante",
        "fields": [
            {
                "name": "lift",
                "type": "number",
                "unit": None,
                "interval_level": None,
                "meaning": "irrelevante",
                "read_as": "irrelevante",
            },
        ],
    }


def test_the_published_schema_carries_the_scheme_allowlist() -> None:
    assert _published_uri_schema()["pattern"] == ARTIFACT_URI_PATTERN


@pytest.mark.parametrize(
    "uri",
    [
        "data:text/plain,hi",
        "inline://payload",
        "https://example.com/rules.json",
        "file:///etc/passwd",
    ],
)
def test_the_published_pattern_rejects_what_the_model_rejects(uri: str) -> None:
    """A consumer validating only against the snapshot must reach the same verdict."""
    pattern = str(_published_uri_schema()["pattern"])
    assert re.match(pattern, uri) is None

    with pytest.raises(ValueError, match="scheme"):
        ArtifactDescription.model_validate(_artifact_payload(uri))


@pytest.mark.parametrize("scheme", ["gs", "bigquery", "secret"])
def test_the_published_pattern_accepts_every_allowed_scheme(scheme: str) -> None:
    """Narrower than the model would break services the model considers legal."""
    pattern = str(_published_uri_schema()["pattern"])
    assert re.match(pattern, f"{scheme}://bucket/path.json") is not None
