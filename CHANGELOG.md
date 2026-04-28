# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] — 2026-04-28

### Added
- `receiver/` module: `ServiceRegistry`, `SharedReceiverRunner`,
  `SharedReceiverAdapters`, `ReceiverExecutionResult`,
  `build_shared_receiver_app()`, and `cli.main` entry point published
  as the `grabatus-receiver` console script.
- `OpaqueServiceContract` (`contract/opaque.py`): receiver-side contract
  that validates envelope, identity, references, service, inputs,
  outputs, and callback while leaving `parameters` opaque so the worker
  can validate them with its own typed schema.
- `CompressedStorage` decorator (`adapters/storage_compressed.py`):
  honors `compression: gzip|zstd|none` on top of any inner
  `StoragePort`.
- `UnknownServiceError`: raised when `envelope.service.name` is not
  registered with a worker.
- `RuntimeMode.SHARED_RECEIVER`: new mode for the shared receiver
  process, returned by `runner.mode.value` for `/health/ready`.
- `RejectAllPolicy` (testing): companion to `AllowAllPolicy` for
  exercising the unauthorized-URI branch.
- `InMemoryServiceRegistry` (alias) and `make_opaque_contract` test
  factories, re-exported from `grabatus_service_core.testing`.
- `Settings.service_registry`, `Settings.gcp_project`,
  `Settings.gcp_region`, `Settings.bucket_prefix` fields, parsed from
  the corresponding `GBT_*` environment variables.
- `InputSpec.compression` field (mirrors `OutputSpec.compression`).
- `Dockerfile.receiver` (multi-stage, slim, non-root) and
  `.dockerignore` for the receiver Cloud Run Service image.
- New tutorial `docs/tutorials/deploying_the_shared_receiver.rst` and
  a "Shared Receiver" subsection in `docs/architecture.rst`.

### Changed
- `build_app()` now accepts any object satisfying the new `RunnerLike`
  Protocol (`.execute(raw)` and `.mode`). Both `ServiceRunner` and
  `SharedReceiverRunner` satisfy it.
- `_result_to_json` in `app/routes.py` handles both `ExecutionResult`
  (worker / monolith) and `ReceiverExecutionResult` (shared receiver)
  via duck-typed attribute lookups.

### Fixed
- `CloudRunJobsDispatcher` now constructs its `run_v2.JobsClient`
  lazily on the first `dispatch()` call instead of in `__init__`, so
  the receiver process can start in environments without GCP
  credentials (e.g. local Docker smoke tests, CI builds).

### Dependencies
- Added `zstandard >= 0.22` to runtime dependencies.

## [0.1.0] — TBD

Initial public release.
