Deploying the Shared Receiver
=============================

The shared receiver is a Cloud Run Service built from
``Dockerfile.receiver`` in this repository. Deploy it once per GCP
project; every Grabatus computational service routes through it.

Prerequisites
-------------

* A GCP project with Cloud Run, Pub/Sub, and Secret Manager enabled.
* A worker Cloud Run Job already deployed (e.g. ``grabatus-forecasting-worker``).
* A Pub/Sub topic and push subscription pointing at the receiver URL.

Build and push the image
------------------------

.. code-block:: bash

   docker build -f Dockerfile.receiver \
     -t us-east1-docker.pkg.dev/grabatus/services/grabatus-service-core:v0.2.0 .

   docker push \
     us-east1-docker.pkg.dev/grabatus/services/grabatus-service-core:v0.2.0

Deploy to Cloud Run
-------------------

.. code-block:: bash

   gcloud run deploy grabatus-receiver \
     --image=us-east1-docker.pkg.dev/grabatus/services/grabatus-service-core:v0.2.0 \
     --region=us-east1 \
     --service-account=grabatus-receiver@grabatus.iam.gserviceaccount.com \
     --min-instances=1 \
     --max-instances=10 \
     --concurrency=80 \
     --timeout=60s \
     --set-env-vars=GBT_RUNTIME_MODE=shared-receiver,GBT_ENV=production \
     --set-env-vars=GBT_GCP_PROJECT=grabatus,GBT_GCP_REGION=us-east1 \
     --set-env-vars=GBT_BUCKET_PREFIX=gbt-storage \
     --set-env-vars=GBT_SERVICE_REGISTRY=forecast:grabatus-forecasting-worker

Add a new service
-----------------

Update the registry env var on the existing receiver. No new image
needed:

.. code-block:: bash

   gcloud run services update grabatus-receiver \
     --region=us-east1 \
     --update-env-vars=GBT_SERVICE_REGISTRY=forecast:grabatus-forecasting-worker,abtest:grabatus-abtest-worker

After ``gcloud`` finishes (around 30 seconds), the receiver dispatches
``abtest`` envelopes to the new worker.

Verify the deployment
---------------------

.. code-block:: bash

   curl -fsS https://grabatus-receiver-<hash>.a.run.app/health/live
   # → {"status":"ok"}

Send a synthetic envelope (development only — production traffic
arrives via Pub/Sub):

.. code-block:: bash

   gcloud pubsub topics publish forecast-trigger \
     --message='{"envelope":{...},"identity":{...},"service":{"name":"forecast",...},...}'

Observe the dispatch in the receiver logs:

.. code-block:: bash

   gcloud logging read 'resource.type=cloud_run_revision AND
     resource.labels.service_name=grabatus-receiver' --limit=20

Local development
-----------------

Run the receiver locally with stub adapters (no GCP credentials
needed):

.. code-block:: bash

   docker run --rm \
     -e GBT_RUNTIME_MODE=shared-receiver \
     -e GBT_ENV=local \
     -e SERVICE_SECRET_KEY=dev \
     -e GBT_GCP_PROJECT=grabatus \
     -e GBT_SERVICE_REGISTRY=forecast:grabatus-forecasting-worker \
     -p 8080:8080 \
     grabatus-service-core:dev

   curl -fsS http://localhost:8080/health/live

The Cloud Run Jobs client is constructed lazily on the first
``dispatch`` call, so the receiver starts cleanly without GCP creds
in scope.

Troubleshooting
---------------

``error_code: unknown_service``
   The envelope's ``service.name`` is not in the registry. Update
   ``GBT_SERVICE_REGISTRY`` and redeploy.

``error_code: unauthorized_uri``
   A URI in the envelope failed the authorization policy. Check the
   tenant prefix and bucket scoping configured by
   :class:`TenantPrefixPolicy`.

``error_code: malformed_message``
   The Pub/Sub data field is not valid base64-encoded JSON. Check
   the publisher.
