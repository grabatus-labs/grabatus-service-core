# ADR-0007 — Multi-tenant URI authorization from day one

- **Status:** Accepted
- **Date:** 2026-04-26

## Context

Computational services receive contracts containing URIs that point to user data (`gs://tenant-X/uploads/...`, `https://internal.svc/...`). Without authorization, a malicious or buggy contract from tenant A could reference tenant B's data, and the service would happily fetch or write it. Worse, URIs to internal infrastructure (`http://169.254.169.254/...`, the GCE metadata server) could exfiltrate cluster credentials.

Adding multi-tenancy retroactively is hard: every URI in the system has to be re-validated, every storage path inspected, every adapter audited. We need to bake authorization into the data flow from the first commit.

## Decision

The library defines a `UriAuthorizationPort` invoked at **step 3 of the pipeline** (immediately after contract validation, before any I/O). The default policy is **composable** and built from three primitives:

- **`SchemeAllowlist`**: only permitted URI schemes (e.g., `gs`, `https`, `inline`). Default-deny: any scheme not in the allowlist is rejected.
- **`HostBlocklist`**: explicitly forbidden hosts (e.g., `metadata.google.internal`, `169.254.169.254`, link-local ranges). Hardcoded defaults cover known SSRF targets.
- **`TenantPrefixPolicy`**: every URI's path must start with the tenant prefix derived from the contract's `identity.tenant_id`. Cross-tenant URIs are rejected.

Services may compose narrower policies (e.g., a forecasting service that only accepts `gs://` URIs and adds a custom allowlist of formats) but the library default never widens. Authorization runs **before** any network or storage call.

Authorization failures raise `UriAuthorizationError` with the offending URI and the rule that rejected it; the contract is not processed further.

## Alternatives Considered

- **No authorization, trust the queue producer:** Rejected — Pub/Sub messages can come from many sources, including malicious or buggy ones.
- **Authorization at the storage adapter:** Rejected — too late; the URI has already been parsed and possibly resolved (DNS, redirect chains).
- **Single-tenant first, multi-tenant later:** Rejected — retrofitting tenant isolation is expensive and dangerous, with no migration path that does not risk leakage during the transition.

## Consequences

- Cross-tenant data access is structurally prevented at the entry point of every service.
- Adding a new tenant requires no code change — only the contract's `identity.tenant_id` matters.
- Test fakes (`AllowAllPolicy`) make local dev simple while real deployments default-deny.
- The cost is that every URI in test fixtures must conform to a tenant prefix. The `examples/echo_service` and tutorials demonstrate the pattern. Composed policies are property-tested in `tests/property/test_uri_authorization_invariants.py` to ensure narrowing-only composition.
