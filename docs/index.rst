grabatus-service-core
=====================

The shared core library that every Grabatus computational service is built on.

It encapsulates the **Pub/Sub → compute → Storage write → JWT webhook**
pipeline as a hexagonal Ports & Adapters architecture, so a new service
needs only:

- A Pydantic ``Parameters`` model.
- A ``ComputeBackendPort`` implementation.
- About fifty lines of bootstrap.

Everything else — contract validation, multi-tenant URI authorization,
secret resolution, retries, observability, JWT-signed webhook delivery —
is provided by the library and exercised by 100% line + branch test
coverage.

.. toctree::
   :maxdepth: 2
   :caption: Getting started

   quickstart
   tutorials/building_a_new_service
   tutorials/extending_a_port
   tutorials/running_tests
   tutorials/deploying_the_shared_receiver

.. toctree::
   :maxdepth: 2
   :caption: Concepts

   architecture
   security
   observability
   infrastructure

.. toctree::
   :maxdepth: 2
   :caption: Decisions

   adr_index

Indices
-------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
