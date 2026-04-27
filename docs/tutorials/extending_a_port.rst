Extending a port
================

When you need a new transport, storage backend, or observability
target, do not edit the runner — write a new adapter for the
existing port. The runner only knows about Protocols.

When to extend a port
---------------------

* The new behaviour fits an existing Protocol's surface (read bytes
  by URI → write a new ``StoragePort`` adapter; deliver a notification
  → write a new ``WebhookPort`` adapter).
* The new behaviour does **not** require a new method or a new return
  type. If it does, you are adding a new port — see the next section.

Steps
-----

#. Read the Protocol in ``src/grabatus_service_core/ports/``.
   Note its method signatures and return types.
#. Create your adapter under ``src/grabatus_service_core/adapters/``
   (or in the consuming service's repo) implementing every method.
   Use ``typing.Protocol`` structural subtyping — no ``ABC``
   inheritance, no ``register`` calls.
#. Write unit tests with ``unittest.mock.patch`` against the cloud
   SDK's call site. Aim for 100% line + branch coverage on the new
   adapter file.
#. Add a property test if the adapter's behaviour has invariants
   over arbitrary inputs (round-trip equality, idempotency).
#. Wire the adapter at the ``bootstrap`` boundary — pass it via the
   ``adapters=`` dict to ``build_monolith_app``,
   ``build_receiver_app``, or ``build_worker_runner``.

Pydantic v2 gotchas
-------------------

When a port's value object is a Pydantic model, two constraints apply:

* ``from __future__ import annotations`` plus moving model imports
  under ``TYPE_CHECKING`` *breaks* Pydantic v2 model construction.
  Pydantic needs runtime access to the annotations. The
  ``contract/`` subpackage is exempted from ``TC001/TC002/TC003`` in
  ``pyproject.toml`` for this reason — extend the ignore list if you
  add a new contract module.
* Discriminated unions (``Annotated[A | B, Field(discriminator=...)]``)
  must use ``Literal`` tags on the discriminator field, not plain
  strings.

Adding a new port
-----------------

Adding a port is a bigger change because it shifts the runner's
dependency surface. Do it only when the new behaviour cannot be
expressed by an existing port. The steps:

#. Define the ``Protocol`` in ``src/grabatus_service_core/ports/``.
   Include a docstring stating the contract obligations.
#. Add a value object in ``ports/values.py`` if the port returns a
   richer type than ``bytes`` or ``dict``.
#. Update ``ServiceRunner`` to accept the new port via constructor
   injection.
#. Add the port to the ``adapters=`` dict in the ``bootstrap``
   factories.
#. Write at least one fake under ``src/grabatus_service_core/testing/``
   so downstream services can wire tests.
#. Open an ADR documenting why the existing surface was insufficient.
