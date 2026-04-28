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

Shared Receiver
---------------

A single Cloud Run Service receives Pub/Sub push messages for every
Grabatus computational service. It validates the envelope, authorizes
the URIs, looks up the right Cloud Run Job to handle the request, and
dispatches the work. The receiver itself never touches storage or
secrets.

Why one shared receiver instead of one per service?

* Adding a new service is one new worker plus one entry in the
  ``GBT_SERVICE_REGISTRY`` env var. No new receiver to deploy.
* The receiver has no business logic — it is pure infrastructure that
  validates the envelope schema (which is shared across services).
* One warm instance ($5–10/month) replaces N warm instances.

How the receiver decides which worker to invoke::

   envelope.service.name = "forecast"
                │
                ▼
   ServiceRegistry.resolve("forecast") → "grabatus-forecasting-worker"
                │
                ▼
   CloudRunJobsDispatcher.dispatch(
       job_name="grabatus-forecasting-worker",
       payload=<full validated contract bytes>,
       request_id=<envelope.request_id>,
   )

The registry is loaded once from ``GBT_SERVICE_REGISTRY`` at process
start. Adding a new service is one env-var update + restart::

   GBT_SERVICE_REGISTRY=forecast:grabatus-forecasting-worker,abtest:grabatus-abtest-worker

The receiver uses :class:`OpaqueServiceContract` (rather than a
service-specific contract type) because at envelope-decode time it
does not know which service the request is for. Parameters are
validated only by the worker, which uses its own typed Pydantic
``Parameters`` model.
