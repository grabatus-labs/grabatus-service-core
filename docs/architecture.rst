Architecture
============

``grabatus-service-core`` is a **hexagonal** library: the domain and
the adapters live on opposite sides of a port boundary. Read
:doc:`adr/0002-hexagonal-ports-and-adapters` for the rationale.

The 8-step pipeline
-------------------

Every request goes through the same ``ServiceRunner`` pipeline,
regardless of which compute service is on top:

#. **Decode** the raw queue message into a JSON payload
   (``MessagePort.decode``).
#. **Validate** the payload against ``BaseServiceContract`` and the
   service-specific ``Parameters`` model.
#. **Authorize** every URI in the contract via ``UriAuthorizationPort``
   *before* any I/O — see :doc:`security`.
#. **Resolve credentials** referenced in the contract via
   ``SecretsPort``.
#. **Load inputs** via ``StoragePort.read``, with retries and
   per-format hints.
#. **Run compute** via the service-specific ``ComputeBackendPort``.
#. **Save outputs** via ``StoragePort.write``.
#. **Notify** the configured webhook URL with a JWT-signed payload
   (``WebhookPort.notify``).

Failures are typed (``GrabatusServiceError`` and 14 subclasses) and
mapped to deterministic webhook payloads. The pipeline never panics:
any unexpected exception is caught at the FastAPI exception handler
and reported as ``internal_error``.

Three runtime modes
-------------------

Set via ``GBT_RUNTIME_MODE``:

``receiver``
    A Cloud Run *Service* that ACKs Pub/Sub pushes in <1 s and
    dispatches a Cloud Run *Job* execution.

``worker``
    A Cloud Run *Job* that runs the pipeline. Started by the receiver.

``monolith``
    Both in one process. Used for local development, the echo example,
    and small services.

See :doc:`adr/0003-receiver-worker-decoupling`.

Where things live
-----------------

.. code-block:: text

   src/grabatus_service_core/
   ├── contract/        # Pydantic v2 contract (BaseServiceContract)
   ├── ports/           # typing.Protocol definitions (the hexagonal edge)
   ├── adapters/        # GCS, Pub/Sub, JWT webhook, OTel, ...
   ├── runner/          # ServiceRunner + 8-step pipeline
   ├── security/        # SchemeAllowlist, HostBlocklist, TenantPrefixPolicy
   ├── observability/   # structlog setup, OTel SDK setup, metric names
   ├── bootstrap/       # build_receiver_app / build_worker_runner / build_monolith_app
   ├── app/             # FastAPI factory, routes, middleware, exception handlers
   ├── settings.py      # pydantic-settings (GBT_* env vars)
   ├── errors/          # typed exception hierarchy
   ├── testing/         # in-memory fakes for downstream tests
   └── __main__.py      # entry point with run_worker_once helper

Test layers
-----------

``tests/unit``
    <100 ms each, in-memory fakes only. ~70% of total tests.

``tests/integration``
    Full FastAPI ASGI roundtrip, end-to-end runner pipeline, no
    network. Seconds.

``tests/property``
    `hypothesis <https://hypothesis.readthedocs.io/>`_-based
    invariants over the contract and security primitives.

``tests/fuzz``
    `atheris <https://github.com/google/atheris>`_ harnesses for the
    Pub/Sub decoder and contract parser. Linux-only.

``tests/contract_compatibility``
    JSON Schema snapshot of ``BaseServiceContract`` plus parametrised
    valid/invalid fixture sweeps.
