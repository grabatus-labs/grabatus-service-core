Quickstart
==========

A Grabatus service is one class. The SDK decodes the contract, authorizes
every URI, resolves credentials, reads the inputs, writes the outputs and
signs the webhook. What you write is the computation — and the
``model_readout`` that explains it.

The complete, running version of what follows is
``examples/forecast_service``.

Install
-------

.. code-block:: bash

   uv add grabatus-service-core

Declare your parameters
-----------------------

.. code-block:: python

   from pydantic import BaseModel

   class ForecastParameters(BaseModel):
       horizon: int

Implement the compute backend
-----------------------------

The three ``ClassVar`` sets are what the runner checks before any I/O
happens: a contract that does not supply ``timeseries``, or that declares
an output your service never produces, fails before a single byte is read.

.. code-block:: python

   from typing import ClassVar

   from grabatus_service_core.contract.readout import READOUT_OUTPUT_ROLE
   from grabatus_service_core.ports.compute_context import ComputeContext
   from grabatus_service_core.ports.values import ComputeResult, LoadedInputs

   class ForecastBackend:
       REQUIRED_INPUT_ROLES: ClassVar[frozenset[str]] = frozenset({"timeseries"})
       OPTIONAL_INPUT_ROLES: ClassVar[frozenset[str]] = frozenset()
       OUTPUT_ROLES: ClassVar[frozenset[str]] = frozenset({"result_json"})

       def run(
           self,
           *,
           inputs: LoadedInputs,
           parameters: ForecastParameters,
           context: ComputeContext,
       ) -> ComputeResult:
           forecast = my_math(inputs.by_role["timeseries"], parameters.horizon)
           readout = build_readout(forecast, context)
           return ComputeResult(
               by_role={
                   "result_json": forecast,
                   READOUT_OUTPUT_ROLE: readout.model_dump_json().encode("utf-8"),
               },
               metadata={},
           )

Note what ``OUTPUT_ROLES`` does **not** list: ``model_readout``. That role
belongs to the SDK, which adds it to the expected set on your behalf.

Explain the result
------------------

The readout is mandatory from protocol 1.1 on, and it is what makes the
service useful to a client rather than only to a programmer. It carries
what the numbers mean, who the answer is for, and what must never be
concluded from them — so an LLM can present the result without inventing
anything around it.

Everything identifying the run comes from ``context``. Assembling those
blocks by hand, or reaching for ``datetime.now()``, is how a readout ends
up describing a different run — which the runner rejects:

.. code-block:: python

   from grabatus_service_core.contract.readout import ModelReadout

   def build_readout(forecast: bytes, context: ComputeContext) -> ModelReadout:
       return ModelReadout(
           generated_at=context.generated_at,
           request=context.readout_request(),
           service=context.readout_service(),
           service_knowledge=...,   # what your service is, written once
           model=...,               # what was fitted, and what it cannot answer
           data=...,                # shape and quality of the input
           artifacts=...,           # a data dictionary for each file you wrote
           findings=...,            # the conclusions you stand behind
           diagnostics=...,
           overall_quality=...,
           caveats=...,
           explanation_guide=...,   # build_explanation_guide(...)
           reproducibility=...,
       )

See ``examples/forecast_service/compute.py`` for each of those filled in,
and ``docs/integration_contract.md`` §5 for the field-level reference.

Wire it up
----------

.. code-block:: python

   from fastapi import FastAPI

   from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
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

   def build() -> FastAPI:
       settings = Settings()
       return build_monolith_app(
           settings=settings,
           contract_type=BaseServiceContract[ForecastParameters],
           compute=ForecastBackend(),
           adapters={
               "storage": InMemoryStorage(seed={}),
               "message": PubSubMessagePort(),
               "webhook": RecordingWebhookNotifier(),
               "secrets": InMemorySecretsAdapter(seed={}),
               "authorizer": AllowAllPolicy(),
               "observability": NullObservability(),
               "job_dispatcher": InMemoryJobDispatcher(),
           },
       )

The adapters above are the in-memory ones, for local runs. Production
swaps ``storage``, ``secrets`` and ``authorizer`` for their GCP
counterparts without touching your backend.

Run it
------

.. code-block:: bash

   GBT_RUNTIME_MODE=monolith \
   GBT_ENV=local \
   SERVICE_SECRET_KEY=dev-only \
   GBT_ALLOWED_SCHEMES=gs,https \
       uv run uvicorn examples.forecast_service.app:build --factory --port 8080

Test it
-------

``grabatus_service_core.testing`` ships the fakes and factories the SDK
uses on itself, so a service test needs no cloud and no fixtures of its
own:

.. code-block:: python

   from grabatus_service_core.testing import make_compute_context

   def test_the_backend_explains_its_own_result() -> None:
       result = ForecastBackend().run(
           inputs=LoadedInputs(by_role={"timeseries": b"..."}),
           parameters=ForecastParameters(horizon=3),
           context=make_compute_context(),
       )

       assert READOUT_OUTPUT_ROLE in result.by_role

What you get for free
---------------------

- Contract validation with typed errors.
- Multi-tenant URI authorization (``SchemeAllowlist`` +
  ``HostBlocklist`` + ``TenantPrefixPolicy`` by default).
- Retried, idempotent storage I/O.
- A readout gate: a run nobody could explain never reaches storage.
- JWT-signed webhook delivery with ``traceparent`` propagation.
- Structured JSON logs, OTel traces, OTel metrics.
