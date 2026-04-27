Running tests
=============

The full test suite runs in under 30 seconds locally and gates every
push.

The single command
------------------

.. code-block:: bash

   uv run pytest

This runs unit, integration, property, contract-compatibility, and
fuzz-harness smoke tests, with coverage measurement and the
``--cov-fail-under=100`` gate.

Slicing the suite
-----------------

.. code-block:: bash

   # Unit tests only — fastest signal during local TDD
   uv run pytest tests/unit -q

   # Integration tests (FastAPI ASGI roundtrip, end-to-end pipeline)
   uv run pytest tests/integration

   # Property tests with the default 200-example budget
   uv run pytest tests/property

   # Contract compatibility (JSON Schema snapshot + fixtures)
   uv run pytest tests/contract_compatibility

Quality gates
-------------

The same checks CI runs:

.. code-block:: bash

   uv run ruff check .
   uv run ruff format --check .
   uv run mypy --strict src/ tests/
   uv run bandit -r src/ -ll
   uv run pip-audit
   uv run pre-commit run --all-files

Coverage
--------

100% line + branch coverage is enforced. ``# pragma: no cover`` is
permitted only with an inline comment explaining why; the script
``scripts/check_pragma_comments.py`` (run in CI) fails on bare
pragmas.

Property tests
--------------

`hypothesis <https://hypothesis.readthedocs.io/>`_ runs with the
default profile (200 examples). To dial the budget up locally:

.. code-block:: bash

   uv run pytest tests/property --hypothesis-profile=ci  # 1000 examples
   uv run pytest tests/property -p no:randomly           # disable test reorder

Fuzz harnesses
--------------

The harnesses in ``tests/fuzz/`` are runnable on Linux only; the
``test_fuzz_harness_smoke.py`` test runs everywhere and verifies the
harnesses do not crash on representative bytes. To run the actual
fuzzer:

.. code-block:: bash

   uv run python tests/fuzz/fuzz_pubsub_decoder.py -atheris_runs=10000
   uv run python tests/fuzz/fuzz_contract_parser.py -atheris_runs=10000

The CI workflow runs each harness for a fixed budget on every push to
``main``.

Mutation testing
----------------

`mutmut <https://github.com/boxed/mutmut>`_ runs pre-merge only
(roughly 30 minutes). The floor is 95% mutation score per
:doc:`/adr/0005-100-percent-coverage`.

.. code-block:: bash

   uv run mutmut run
   uv run mutmut results
   uv run mutmut html
