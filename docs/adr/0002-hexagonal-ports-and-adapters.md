# ADR-0002 — Hexagonal Ports & Adapters

- **Status:** Accepted
- **Date:** 2026-04-26

## Context

The forecasting service today mixes business logic with infrastructure concerns: the same module reads from GCS, calls AWS Lambda, signs JWTs, and dispatches Pub/Sub messages. Tests require monkeypatching cloud SDKs at runtime, and the same plumbing has to be repeated by every new computational service (forecasting, optimization, Bayesian, simulation).

We need a structural pattern that:

1. Isolates business code (compute logic) from infrastructure (cloud SDKs, transport, persistence).
2. Lets tests run against in-memory fakes without monkeypatching.
3. Lets future services reuse the entire pipeline by just providing a compute backend.

## Decision

We adopt the **Ports & Adapters** pattern (Cockburn, 2005), also known as Hexagonal Architecture. The core defines `typing.Protocol`-based **ports**:

- `StoragePort` (read/write bytes by URI)
- `MessagePort` (decode raw queue messages)
- `WebhookPort` (deliver signed callbacks)
- `ComputeBackendPort` (execute the service-specific math)
- `SecretsPort` (resolve runtime credentials)
- `UriAuthorizationPort` (gate every URI before I/O)
- `ObservabilityPort` (logs, traces, metrics)
- `ClockPort` (testable time)
- `JobDispatcherPort` (start asynchronous jobs)

The core is fully agnostic to specific cloud SDKs. **Adapters** (e.g., `GcsStorage`, `PubSubMessagePort`, `JwtWebhookNotifier`, `OpenTelemetryObservability`) implement the ports against real infrastructure. **Test fakes** (e.g., `InMemoryStorage`, `RecordingWebhookNotifier`, `AllowAllPolicy`) implement the same ports.

The `ServiceRunner` orchestrates the 8-step pipeline (decode → validate → authorize → resolve credentials → load inputs → run compute → save outputs → notify webhook) by composing port references — never SDK references.

## Alternatives Considered

- **Layered architecture (n-tier):** Rejected — layering allows infrastructure leaks across boundaries because it does not enforce a directional dependency rule.
- **Service mesh / sidecar pattern:** Rejected — solves a deployment problem, not a code-organization problem.
- **Inheritance-based base classes:** Rejected — `Protocol` provides duck-typed interfaces with zero runtime cost and no MRO surprises.

## Consequences

- Adapters can be replaced (e.g., GCS → S3, Pub/Sub → Kafka) by writing a new adapter; no core code changes.
- Tests run with in-memory fakes — no Docker, no cloud SDK in the test process for unit tests.
- New computational services implement only `ComputeBackendPort` and reuse the entire orchestration pipeline.
- The cost is an extra layer of indirection: each adapter adds one file and one Protocol per port. The win in testability and reusability vastly outweighs this.
