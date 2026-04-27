Quickstart
==========

Build a working computational service in about fifty lines of code.
The example below mirrors ``examples/echo_service``: it accepts a
contract, copies the input bytes to the output URI, and posts a signed
webhook back. Replace the compute step with your own math and you have
a real service.

Install
-------

.. code-block:: bash

   uv add grabatus-service-core

Define your parameters
----------------------

.. code-block:: python

   from pydantic import BaseModel, ConfigDict

   class EchoParameters(BaseModel):
       model_config = ConfigDict(extra="forbid", frozen=True)

Implement the compute backend
-----------------------------

.. code-block:: python

   from grabatus_service_core.ports.compute_backend import ComputeBackendPort
   from grabatus_service_core.contract.base import BaseServiceContract
   from grabatus_service_core.ports.values import LoadedInput, ComputedOutput

   class EchoComputeBackend:
       def run(
           self,
           contract: BaseServiceContract[EchoParameters],
           inputs: dict[str, LoadedInput],
       ) -> dict[str, ComputedOutput]:
           payload = inputs["payload"]
           return {"echoed": ComputedOutput(payload=payload.bytes_)}

Wire it up
----------

.. code-block:: python

   from fastapi import FastAPI
   from grabatus_service_core.bootstrap import build_monolith_app
   from grabatus_service_core.contract.base import BaseServiceContract
   from grabatus_service_core.settings import Settings
   from grabatus_service_core.testing import (
       AllowAllPolicy,
       InMemoryJobDispatcher,
       InMemorySecretsAdapter,
       InMemoryStorage,
       NullObservability,
       RecordingWebhookNotifier,
   )
   from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort

   def build() -> FastAPI:
       settings = Settings()
       return build_monolith_app(
           settings=settings,
           contract_type=BaseServiceContract[EchoParameters],
           compute=EchoComputeBackend(),
           adapters={
               "storage": InMemoryStorage(seed={"inline://hello": b"hello"}),
               "message": PubSubMessagePort(),
               "webhook": RecordingWebhookNotifier(),
               "secrets": InMemorySecretsAdapter(seed={}),
               "authorizer": AllowAllPolicy(),
               "observability": NullObservability(),
               "job_dispatcher": InMemoryJobDispatcher(),
           },
       )

Run it
------

.. code-block:: bash

   GBT_RUNTIME_MODE=monolith \
   GBT_ENV=local \
   SERVICE_SECRET_KEY=dev-only \
   GBT_ALLOWED_SCHEMES=inline,https \
       uv run uvicorn examples.echo_service.app:build --factory --port 8080

What you get for free
---------------------

- Contract validation with typed errors.
- Multi-tenant URI authorization (``SchemeAllowlist`` +
  ``HostBlocklist`` + ``TenantPrefixPolicy`` by default).
- Retried, idempotent storage I/O.
- JWT-signed webhook delivery with ``traceparent`` propagation.
- Structured JSON logs, OTel traces, OTel metrics.
- 100% test coverage harness via in-memory fakes in
  ``grabatus_service_core.testing``.
