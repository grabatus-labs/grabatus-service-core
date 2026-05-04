# Integration contract

This document is the **canonical specification** of the protocol every
Grabatus computational service speaks: the Pub/Sub envelope the
platform sends in, the JWT-signed webhook the service sends back, and
the error taxonomy mapped onto both. It is the source of truth — any
disagreement between this file and an implementation is a bug in the
implementation.

The protocol is version 1.0. Breaking changes ship as a new
`protocol_version`; additive fields ship under the same version.

---

## Roles

```
┌──────────────────────┐     1. Pub/Sub envelope       ┌────────────────────┐
│  grabatus (Django)   │ ─────────────────────────────▶│  shared receiver   │
│  the platform        │                               │  (service-core)    │
└──────────────────────┘                               └─────────┬──────────┘
        ▲                                                        │ 2. dispatch
        │                                                        ▼
        │                                              ┌────────────────────┐
        │   3. JWT-signed webhook (HTTPS POST)         │  worker job        │
        └──────────────────────────────────────────────│  (e.g. forecasting)│
                                                       └────────────────────┘
```

The platform never talks to a worker directly. It publishes a Pub/Sub
message; the shared receiver routes it to the right worker; the
worker computes, persists outputs to GCS, and notifies the platform
via a JWT-signed webhook.

---

## 1. Pub/Sub envelope (platform → receiver)

### Transport shape

The receiver expects a standard GCP Pub/Sub push payload:

```json
{
  "message": {
    "data": "<base64-encoded UTF-8 JSON of the contract>",
    "messageId": "...",
    "publishTime": "..."
  },
  "subscription": "..."
}
```

`data` decodes to the **service contract** described below. Anything
else in `message` is metadata supplied by Pub/Sub and ignored by the
receiver.

### Service contract

```json
{
  "envelope": {
    "protocol_version": "1.0",
    "request_id": "<uuid v4>",
    "created_at": "<RFC 3339 with timezone>",
    "origin": "web | api | mcp | internal"
  },
  "identity": {
    "user_id": "<1..64 chars>",
    "tenant_id": "<lowercase + digits + hyphens, 1..64>"
  },
  "references": {
    "parameter_id": "<opaque platform id, 1..128>",
    "result_id":    "<opaque platform id, 1..128>"
  },
  "service": {
    "name":    "<lowercase slug, e.g. forecast>",
    "version": "<MAJOR.MINOR.PATCH>"
  },
  "inputs": [
    {
      "role":           "<lowercase, service-defined>",
      "source_uri":     "https://...  | gs://... | inline://...",
      "format":         "xlsx | csv | json | parquet | bigquery | inline",
      "format_hints":   { "...": "depends on format" },
      "compression":    "none | gzip | zstd",
      "credential_ref": null | { "secret_id": "...", "version": "latest" }
    }
  ],
  "outputs": [
    {
      "role":         "<lowercase, service-defined>",
      "target_uri":   "gs://...",
      "format":       "json | parquet | csv | xlsx",
      "format_hints": { "...": "depends" },
      "compression":  "none | gzip | zstd",
      "write_mode":   "overwrite | append | fail_if_exists"
    }
  ],
  "callback": {
    "url":         "https://<platform>/api/v1/webhooks/<service>/callback/",
    "auth_scheme": "jwt_hs256"
  },
  "parameters": {
    "...": "service-specific Pydantic schema"
  }
}
```

### Field semantics that are easy to get wrong

- `envelope.request_id` is the **idempotency key** end-to-end. The
  platform must reuse the same UUID when re-publishing after a
  retryable failure; the receiver de-dupes on it.
- `identity.tenant_id` drives URI authorization. A request scoped to
  `tenant_id = grabatus` may only read/write URIs whose path is
  prefixed with `grabatus`. Cross-tenant access is rejected before any
  I/O.
- `service.version` is **strict semver**. `"1.0"` or `"1.0.0-rc1"` are
  rejected. Use `"1.0.0"`.
- `callback.url` must be HTTPS and `auth_scheme` is constrained to
  `jwt_hs256` in v1.0.
- `inputs[].role` and `outputs[].role` are service-defined slugs (e.g.
  `timeseries`, `forecast`). The service declares which roles are
  required and which are optional; missing required roles are rejected
  with `InvalidContractError` before any I/O.
- `parameters` is **opaque to the protocol** — only the target service
  validates it. Errors there map to `InvalidContractError` with the
  Pydantic message attached.

### Tenancy rule for URIs

URIs in `inputs[].source_uri` and `outputs[].target_uri` must satisfy:

- Scheme is on the per-deployment allowlist (typically `gs`, `https`,
  `inline`).
- Host (for `gs://`/`https://`) is not on the blocklist.
- The path begins with the request's `tenant_id`. Concretely:
  - `gs://grabatus-uploads/<tenant_id>/...` ✓
  - `gs://grabatus-uploads/another-tenant/...` ✗ — rejected with
    `UnauthorizedUriError`.

---

## 2. Webhook callback (worker → platform)

### Transport

```
POST <callback.url>
Authorization: Bearer <JWT-HS256>
Content-Type: application/json
```

The HMAC key is **the shared `SERVICE_SECRET_KEY`** secret. The
platform and the service load the same value (Secret Manager on GCP,
environment variable locally). Rotate the secret in Secret Manager;
both sides pick it up at next process start.

JWT header: `{ "alg": "HS256", "typ": "JWT" }`. There is no `kid` and
no JWK rotation — the secret is the only signal.

### Success payload

```json
{
  "request_id": "<same uuid as the envelope>",
  "status":     "ok",
  "outputs": [
    {
      "role":       "<matches a contract output role>",
      "uri":        "gs://.../result.json.gz",
      "version_id": "<GCS object generation, optional>",
      "size_bytes": 12345,
      "etag":       "<optional>"
    }
  ],
  "metadata": {
    "...": "service-defined; opaque to the platform"
  }
}
```

The platform should:
1. Decode the JWT with `SERVICE_SECRET_KEY` and `algorithms=["HS256"]`.
   Reject any other algorithm.
2. Match `request_id` to the in-flight job; ignore unknown ones (a
   stray retry).
3. Read `outputs[].uri` to know where the results landed; do not
   re-derive the URI from any other source.

### Error payload

```json
{
  "request_id": "<same uuid>",
  "status":     "error",
  "error": {
    "code":    "<one of the codes in §3>",
    "message": "<human-readable; safe to display to operators>"
  }
}
```

Errors **also notify the webhook** — the platform must not assume
silence on failure. If the webhook itself fails, the receiver records
it, but the worker still considers the job done (no retry storm).

---

## 3. Error taxonomy

Every public error inherits `GrabatusServiceError` and carries a stable
`error_code` string. The full set, grouped by stage:

| Stage    | Code                              | Meaning                                           |
| -------- | --------------------------------- | ------------------------------------------------- |
| Decode   | `MalformedMessageError`           | Pub/Sub `message.data` is not valid JSON / b64.   |
| Contract | `InvalidContractError`            | Schema valid but a field rule fails.              |
| Contract | `UnknownServiceError`             | `service.name` is not in the deployment registry. |
| Contract | `UnsupportedProtocolVersionError` | `envelope.protocol_version` is not 1.0.           |
| Auth     | `UnauthorizedUriError`            | URI fails the tenant-prefix check.                |
| Auth     | `UnsupportedSchemeError`          | URI scheme is not on the allowlist.               |
| Auth     | `BlockedHostError`                | URI host is on the blocklist.                     |
| I/O      | `InputNotFoundError`              | Storage adapter could not find an input.          |
| I/O      | `InputReadError`                  | Read failed (network, decompress, parse).         |
| I/O      | `OutputWriteError`                | Write failed.                                     |
| I/O      | `FormatParsingError`              | Bytes did not parse as the declared format.       |
| Compute  | `ComputeError`                    | Service-specific compute failure.                 |
| Compute  | `ComputeTimeoutError`             | Compute exceeded its budget.                      |
| Webhook  | `WebhookAuthError`                | JWT signing/verification failed.                  |
| Webhook  | `WebhookError`                    | Network failure delivering the callback.          |

Codes are stable; copy them into the platform's switch/dispatch verbatim.
Human messages may evolve; do not match on them.

---

## 4. Versioning

- `protocol_version: "1.0"` is the only accepted value today.
- New optional fields are additive within the same version (Pydantic
  models are `extra="forbid"`, so adding a field is a breaking change
  to existing producers — the platform should always emit the latest
  fields and the service deployment must be upgraded first).
- A new version (`"2.0"`, etc.) ships when the schema breaks. The
  receiver will then accept both versions during a transition window
  documented at the top of `docs/CHANGELOG.md`.

The Pydantic models in `grabatus_service_core.contract` are the
machine-readable form of this document. When in doubt, defer to the
models — they validate everything stated above and a few invariants
that prose can't capture.
