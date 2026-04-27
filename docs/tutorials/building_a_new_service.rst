Building a new service
======================

This tutorial walks through writing a complete computational service
from an empty directory to a passing integration test. The example
implements a "double" service that multiplies a CSV column by two —
about as simple as a real service gets.

1. Bootstrap the package
------------------------

.. code-block:: bash

   uv init grabatus-double-service
   cd grabatus-double-service
   uv add grabatus-service-core
   uv add --dev pytest pytest-asyncio httpx

2. Define the parameters
------------------------

.. code-block:: python

   # src/double_service/parameters.py
   from pydantic import BaseModel, ConfigDict, Field

   class DoubleParameters(BaseModel):
       model_config = ConfigDict(extra="forbid", frozen=True)

       column: str = Field(min_length=1, max_length=64)

3. Implement the compute backend
--------------------------------

.. code-block:: python

   # src/double_service/compute.py
   from io import BytesIO
   import pandas as pd
   from grabatus_service_core.contract.base import BaseServiceContract
   from grabatus_service_core.ports.values import LoadedInput, ComputedOutput
   from .parameters import DoubleParameters

   class DoubleComputeBackend:
       def run(
           self,
           contract: BaseServiceContract[DoubleParameters],
           inputs: dict[str, LoadedInput],
       ) -> dict[str, ComputedOutput]:
           df = pd.read_csv(BytesIO(inputs["data"].bytes_))
           df[contract.parameters.column] *= 2
           buffer = BytesIO()
           df.to_csv(buffer, index=False)
           return {"result": ComputedOutput(payload=buffer.getvalue())}

4. Wire up the FastAPI app
--------------------------

.. code-block:: python

   # src/double_service/app.py
   from fastapi import FastAPI
   from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
   from grabatus_service_core.bootstrap import build_monolith_app
   from grabatus_service_core.contract.base import BaseServiceContract
   from grabatus_service_core.settings import Settings
   from grabatus_service_core.testing import (
       AllowAllPolicy, InMemoryJobDispatcher, InMemorySecretsAdapter,
       InMemoryStorage, NullObservability, RecordingWebhookNotifier,
   )
   from .compute import DoubleComputeBackend
   from .parameters import DoubleParameters

   def build() -> FastAPI:
       settings = Settings()
       return build_monolith_app(
           settings=settings,
           contract_type=BaseServiceContract[DoubleParameters],
           compute=DoubleComputeBackend(),
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

5. Write the integration test
-----------------------------

Compose the contract, post it to ``/run_service``, assert the
``RecordingWebhookNotifier`` received a JWT-signed callback. See
``tests/integration/test_echo_service.py`` in the core repo for the
full pattern.

6. Switch to real adapters in production
----------------------------------------

The only difference between local and production is the
``adapters=`` dict at ``build_monolith_app``. Replace
``InMemoryStorage`` with ``GcsStorage``, ``RecordingWebhookNotifier``
with ``JwtWebhookNotifier``, and so on. The compute code does not
change — the port boundary makes it unaware of which adapter it is
talking to.
