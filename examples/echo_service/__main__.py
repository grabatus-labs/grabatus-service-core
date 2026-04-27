"""Run the echo service via uvicorn."""

from __future__ import annotations

import uvicorn

from examples.echo_service import build

if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(build(), host="0.0.0.0", port=8080)  # noqa: S104
