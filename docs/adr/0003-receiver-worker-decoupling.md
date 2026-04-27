# ADR-0003 — Receiver / Worker decoupling

- **Status:** Accepted
- **Date:** 2026-04-26

## Context

Computational services often have two very different timing profiles in the same request:

1. **Receive** the Pub/Sub push (must ACK in 30 seconds or Pub/Sub redelivers).
2. **Compute** a forecast or optimization (may take 5–10 minutes).

Running both in the same Cloud Run instance forces the receiver process to keep its memory and CPU pinned to the worst-case compute size. Pub/Sub redelivery storms can also bring down the cluster: a slow compute step holds the HTTP connection past the ACK deadline, the message is redelivered, every replica picks up duplicates, and CPU saturates.

## Decision

The library supports **three runtime modes**, set via the `GBT_RUNTIME_MODE` environment variable:

- **`receiver`**: A Cloud Run *Service* that receives Pub/Sub pushes, validates the contract, dispatches a Cloud Run *Job* execution, and ACKs in <1 s.
- **`worker`**: A Cloud Run *Job* that runs the actual pipeline (load inputs, run compute, save outputs, notify webhook). Started by the receiver. No HTTP listener.
- **`monolith`**: Both in one process. Used for local development, the echo example, and small services where compute is fast.

The library's `bootstrap` package exposes `build_receiver_app`, `build_worker_runner`, and `build_monolith_app`. The same business code runs in any of the three modes by changing only the entry point.

## Alternatives Considered

- **Single Cloud Run service with long timeout:** Rejected — Cloud Run's max request timeout is 60 minutes, but Pub/Sub's max ACK deadline is 10 minutes, so long compute risks redelivery.
- **GKE with custom autoscaling:** Rejected — operational overhead does not justify the win for a small number of services.
- **Cloud Functions for the receiver:** Considered — Cloud Run is preferred for consistency with the worker (Cloud Run Jobs).

## Consequences

- Receivers stay small (CPU 1, memory 512 Mi). Workers can scale CPU/memory per job per service.
- Cost-efficient: workers consume resources only during compute, not at idle.
- Local development keeps the simplicity of one process via `monolith`.
- The cost is that a `JobDispatcherPort` adapter (`CloudRunJobsDispatcher`) is required, and developers must understand which mode they are in. The `Settings.runtime_mode` field makes this explicit and validated at startup.
