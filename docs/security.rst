Security
========

Every service that uses this library inherits the security defaults
described below. Services may compose **narrower** policies but the
library default never widens.

Threat model
------------

Adversaries we worry about:

* **Untrusted contract producers**: a buggy or compromised service
  posts a contract that targets another tenant's data, a private
  metadata server, or an internal-only host.
* **Webhook endpoint forgery**: a downstream consumer cannot tell our
  webhook from someone else's HTTP POST.
* **Long-lived CI credentials**: a leaked GitHub Secrets entry grants
  GCP access for as long as nobody rotates it.

Adversaries we do **not** model:

* Compromised library maintainers (covered by code review and signed
  releases, outside this document).
* Side-channel timing attacks on JWT verification (out of scope —
  PyJWT's ``hmac.compare_digest`` is constant-time).

URI authorization
-----------------

URI authorization runs at **step 3 of the pipeline**, before any
network or storage call. It is composed of three primitives:

``SchemeAllowlist``
    A closed allowlist (default-deny) of URI schemes. Default for the
    library is narrow (``gs``, ``bigquery``, ``secret``); services
    may further restrict.

``HostBlocklist``
    Hardcoded denylist of known SSRF targets (``metadata.google.internal``,
    ``169.254.169.254``, link-local ranges) plus optional service-specific
    additions.

``TenantPrefixPolicy``
    Bucket and BigQuery URIs must use a host whose name starts with
    ``<bucket_prefix>-<tenant_id>``. Cross-tenant URIs are rejected
    with ``UnauthorizedUriError``.

Read :doc:`adr/0007-multi-tenant-uri-authorization` for the design
trade-offs and a known caveat on tenant-id prefix collision (covered
by ``tests/property/test_uri_authorization_invariants.py``).

Webhook signing
---------------

Webhook payloads are signed with a JWT (``HS256``) using a per-service
secret resolved from Secret Manager via ``SecretsPort``. The secret
identifier is in the contract's ``callback.auth_scheme`` field; the
secret value is fetched with the worker's service-account credentials,
not from the contract.

The signing payload includes the contract's ``request_id`` as the
JWT ``jti`` claim, allowing downstream consumers to deduplicate
deliveries.

CI credentials
--------------

GitHub Actions authenticates to GCP via Workload Identity Federation,
not service account JSON. Setup is documented in
:doc:`adr/0006-workload-identity-federation` and operationalised in
``infra/wif/`` (separate repository).

Secrets in code
---------------

* ``detect-secrets`` runs as a pre-commit hook against every staged
  file. The baseline is committed at ``.secrets.baseline``.
* ``bandit`` runs in CI with severity gate ``-ll`` (medium and above).
* No environment variable is logged at any level. Structured logs
  list the resolved secret reference (e.g., ``secret://...``) but
  never the value.
