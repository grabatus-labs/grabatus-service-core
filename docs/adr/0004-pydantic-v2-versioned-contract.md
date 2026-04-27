# ADR-0004 — Pydantic v2 versioned contract

- **Status:** Accepted
- **Date:** 2026-04-26

## Context

The Grabatus platform needs a **single, versioned message contract** that every computational service speaks. The contract describes: caller identity, tenant scope, input/output references, callback URL and auth scheme, service-specific parameters, and a protocol version.

The contract crosses several boundaries: producers (Grabatus core API), Pub/Sub queues, receiver services, worker services, webhook callbacks, and JSON Schema documentation. Any divergence between these views causes silent data corruption.

We considered: Protobuf, Avro, JSON Schema only, Pydantic v2, hand-rolled `TypedDict`.

## Decision

We use **Pydantic v2** as the contract definition. The `BaseServiceContract[ParametersT]` generic in `src/grabatus_service_core/contract/` is a Pydantic model parameterized over the service-specific `parameters` field.

Versioning is explicit: `protocol_version: Literal["1.0"]`. Future breaking changes bump the major version (`"2.0"`) and a new contract type is introduced; the library accepts both during a deprecation window.

JSON Schema is generated from the model (`.model_json_schema()`) and snapshot-tested in `tests/contract_compatibility/`. External tooling (the Grabatus core API, documentation, third-party validators) consumes the snapshotted JSON Schema directly.

## Alternatives Considered

- **Protobuf:** Excellent for binary efficiency, but the JSON-over-Pub/Sub transport already commits us to text, and the codegen step adds friction. Pydantic models are pure Python and self-documenting.
- **Avro:** Great schema evolution semantics, but Python tooling is less mature and JSON Schema export from Avro is awkward.
- **JSON Schema only:** We would lose the runtime validation, type hints, and IDE support that Pydantic gives us for free.
- **`TypedDict`:** No runtime validation. Forces every consumer to validate by hand.

## Consequences

- IDE autocomplete and `mypy --strict` work end-to-end across services and core.
- Runtime validation catches malformed contracts at the entry point with typed exceptions (`ContractValidationError`).
- JSON Schema is exportable for documentation and contract-compatibility tests.
- Pydantic v2 is fast (Rust-based core) — validation is not a bottleneck.
- The cost is that Pydantic v2 has subtle pitfalls (`Optional` semantics, discriminated unions, `TYPE_CHECKING` import constraints under `from __future__ import annotations`) that we document in `tutorials/extending_a_port.rst` and enforce via per-file `ruff` ignores.
