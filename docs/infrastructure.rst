Infrastructure (Terraform IaC)
==============================

The lib's GCP infrastructure is codified as Terraform under
``infra/``. The foundation stack owns everything that is shared
across services: the GitHub Actions ↔ GCP federation, the Docker
registry, the shared receiver Cloud Run Service, and the
cross-cutting alerts. Per-service worker stacks live in each
service's own repo and read foundation outputs through
``terraform_remote_state``.

Layout
------

::

    infra/
    ├── BOOTSTRAP.md           one-time GCS state bucket setup
    ├── README.md              operational overview
    ├── modules/
    │   ├── wif/                       GitHub Actions ↔ GCP federation
    │   ├── artifact_registry/         Docker repo + IAM
    │   ├── shared_receiver/           Cloud Run Service for the receiver
    │   └── alerts_common/             cross-cutting monitoring policies
    └── envs/
        ├── dev/foundation/
        ├── staging/foundation/
        └── production/foundation/

Each env's ``foundation/`` stack wires the four modules together.
Per-env values land in ``terraform.tfvars``; defaults live in
``variables.tf``.

Modules at a glance
-------------------

``wif``
   Creates one Workload Identity pool per project and one OIDC
   provider for ``token.actions.githubusercontent.com``. Then it
   creates one service account per ``(repo, role)`` pair. Every SA
   is bound by ``attribute.repository``; never by
   ``attribute.environment`` alone — that prevents another repo in
   the same owner from impersonating the SA via a same-named
   GitHub Environment. Production-grade SAs (the ``deploy-*`` ones)
   are still gated per env, but the gate is enforced at the
   GitHub Environment layer (required reviewers, deployment
   branches), not at WIF.

``artifact_registry``
   A single Docker repository under ``us-east1-docker.pkg.dev``
   shared by every service. ``release-*`` SAs get
   ``artifactregistry.writer``; ``deploy-*`` SAs get
   ``artifactregistry.reader``.

``shared_receiver``
   The Cloud Run v2 Service that runs the receiver image. The
   receiver's IAM is split in two halves:

   - it gets ``run.invoker`` on every worker Cloud Run Job it has
     to dispatch (``worker_jobs`` input), and
   - the Pub/Sub OIDC SA gets ``run.invoker`` on the receiver
     itself, so authenticated push subscriptions can call it.

   The Pub/Sub SA's email is sourced from the worker stack's
   remote state (see :ref:`apply-order` below); on the very
   first apply it is null and the binding is skipped, then a
   re-apply grants it.

``alerts_common``
   The monitoring policies that watch the receiver and the
   security incidents (failed auth, denied URIs). Per-service
   alert policies live next to the service worker.

.. _apply-order:

Apply order across repos
------------------------

Foundation and worker stacks reference each other through
``terraform_remote_state``, so the very first apply of an env is a
three-step dance. Subsequent applies use the steady-state defaults
and only need step 3.

#. **Foundation, bootstrap mode** — set
   ``read_forecasting_worker_state = false`` so the foundation does
   not try to read a worker state file that doesn't exist yet.
   The ``Deploy Infra (foundation)`` workflow exposes this as an
   input; the variable defaults to ``false`` so a forgotten
   bootstrap apply still works.
#. **Worker stack** — applies normally; reads foundation outputs
   (``receiver_url``, registry URL, deploy SA email) and publishes
   ``pubsub_invoker_email`` as an output.
#. **Foundation, steady state** — re-apply with
   ``read_forecasting_worker_state = true``. The foundation reads
   ``pubsub_invoker_email`` from the worker state and grants the
   receiver's ``run.invoker`` to it.

The full operational walkthrough, including ``gcloud`` commands for
the state buckets and the GitHub Environment variable contract,
lives in ``infra/BOOTSTRAP.md``.

CI / CD
-------

Two workflows manage the foundation:

``infra-ci.yml``
   Runs on every PR that touches ``infra/`` or the workflow
   itself. Stages: ``terraform fmt -check``, ``terraform validate``
   on each env stack, ``tflint`` on each module and env, and
   ``tfsec`` on the whole tree.

``deploy-infra.yml``
   Manual ``workflow_dispatch`` only — there is no auto-apply.
   Inputs: ``env`` (dev|staging|production), ``action`` (plan|apply),
   ``read_forecasting_worker_state`` (false on the bootstrap apply).
   The workflow authenticates to GCP through WIF, so no long-lived
   keys are stored. The ``environment:`` key on the job binds the
   run to a GitHub Environment, which is where required reviewers
   and deployment branches enforce production protection.

Operational details (the per-env ``terraform.tfvars`` examples,
the GitHub Environment variables, the ``gcloud`` commands for the
state buckets) live in ``infra/README.md`` and
``infra/BOOTSTRAP.md`` next to the code.
