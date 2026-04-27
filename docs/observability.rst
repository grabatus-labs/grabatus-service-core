Observability
=============

Three signals: structured logs, distributed traces, and metrics.

Logs
----

The library ships a ``configure_structlog`` helper that routes
`structlog <https://www.structlog.org>`_ through the stdlib ``logging``
module so that every emitter — ours, FastAPI's, library code we don't
own — produces the same JSON shape.

The default renderer emits:

.. code-block:: json

   {
     "timestamp": "2026-04-26T00:00:00Z",
     "level": "info",
     "event": "compute_finished",
     "request_id": "11111111-1111-4111-8111-111111111111",
     "tenant_id": "grabatus",
     "service": "echo",
     "duration_ms": 42
   }

The ``request_id`` field is bound from a context variable populated by
``RequestContextMiddleware`` so every log line within a request shares
the same correlation key.

Traces
------

Tracing uses OpenTelemetry. ``setup_opentelemetry(env, sample_rate)``
returns an ``OpenTelemetryHandle`` that holds the ``TracerProvider``
and the ``MeterProvider``; the handle's ``shutdown`` method is
idempotent and safe to call from FastAPI's lifespan hook.

When the env detects Cloud Run, the SDK loads
``opentelemetry-exporter-cloud-trace`` and
``opentelemetry-exporter-cloud-monitoring`` lazily so local
development does not require those packages.

Outbound HTTP requests (webhook delivery) inject the W3C
``traceparent`` header before sending. Downstream consumers can join
their span tree to ours by reading that header.

Metrics
-------

The library defines seven canonical metric names in
``grabatus_service_core.observability.metrics``:

* ``requests_total``
* ``request_duration_seconds``
* ``compute_duration_seconds``
* ``storage_bytes_read``
* ``storage_bytes_written``
* ``webhook_failures_total``
* ``circuit_breaker_state``

Counters and histograms are routed by name suffix
(``.total``/``.failures`` → counter, default → histogram) inside
``OpenTelemetryObservability.metric``. Every service inherits the
same dashboards by emitting these names without configuration.

Local-dev defaults
------------------

In monolith mode, ``NullObservability`` is wired into the runner so
that tests do not depend on a tracer or meter being available. Real
deployments swap it for ``OpenTelemetryObservability`` at the
``bootstrap`` factory boundary.
