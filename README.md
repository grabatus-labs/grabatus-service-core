# grabatus-service-core

**The shared backbone of every Grabatus computational service.**

Pub/Sub envelope, multi-tenant URI security, JWT-signed webhooks,
retries, structured observability — written once, audited once,
reused by every service. New services bring only the math.

---

## What you get

- A **versioned protocol** spoken by the platform and every service
  ([contract](docs/integration_contract.md)).
- A **hexagonal runtime** — Ports and Adapters — that turns a queue
  message into validated inputs, runs your compute, and persists
  signed outputs through 8 deterministic steps.
- A **shared receiver** Cloud Run Service that fronts every worker
  through Pub/Sub push, so individual services scale to zero
  without losing the warm-path latency.
- **100 % test coverage** (line + branch), `mypy --strict`, `bandit`,
  `pip-audit`, fuzz harnesses on the wire-format parsers, and tflint
  on the IaC. Everything is enforced in CI.

## Add a new service in three pieces

```python
class MyParameters(pydantic.BaseModel):
    horizon_days: int

class MyBackend:
    REQUIRED_INPUT_ROLES = frozenset({"timeseries"})
    OPTIONAL_INPUT_ROLES = frozenset()
    OUTPUT_ROLES         = frozenset({"forecast"})

    def compute(self, *, inputs, parameters: MyParameters):
        ...

app = build_app(
    runner=ServiceRunner(compute=MyBackend(), ...adapters),
    observability=NullObservability(),
)
```

The library does the rest — contract validation, URI authorization,
secret resolution, storage I/O, webhook signing, retries,
observability. See the
[New service tutorial](docs/tutorials/building_a_new_service.rst) for
the full walkthrough.

## Quick start

Requires Python 3.12 and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
uv run pre-commit install
uv run pytest
```

To preview the docs site locally:

```bash
uv run sphinx-build -W -b html docs docs/_build/html/en
open docs/_build/html/en/index.html
```

## Architecture at a glance

```
queue ─▶ Decode ─▶ Validate ─▶ Authorize ─▶ Resolve creds ─▶
        Load ─▶ Compute ─▶ Save ─▶ Webhook
```

Every step is a port; every port has a real adapter (GCS, Secret
Manager, Cloud Run Jobs, HTTP, OTel) and an in-memory adapter
shipped in `grabatus_service_core.testing`. Tests run the full
pipeline without GCP credentials.

Read the
[architecture chapter](docs/architecture.rst) for the deep dive and
the [ADRs](docs/adr_index.rst) for the trade-offs.

## Documentation

| | |
| --- | --- |
| **Quick start** | [docs/quickstart.rst](docs/quickstart.rst) |
| **Architecture** | [docs/architecture.rst](docs/architecture.rst) |
| **Integration contract** | [docs/integration_contract.md](docs/integration_contract.md) |
| **Security model** | [docs/security.rst](docs/security.rst) |
| **Observability** | [docs/observability.rst](docs/observability.rst) |
| **Infrastructure (Terraform)** | [docs/infrastructure.rst](docs/infrastructure.rst) |
| **Decisions (ADRs)** | [docs/adr_index.rst](docs/adr_index.rst) |

The full Sphinx site is built in CI (English + Portuguese) and
published from `main`.

## Status

`v0.x` — interface still allowed to evolve. Pinned by every consumer
through a Git tag. The protocol itself is `v1.0` and frozen for
additive changes only (see
[integration contract §4](docs/integration_contract.md#4-versioning)).

## License

Proprietary. © Grabatus.
