# Architecture Decision Records

Long-lived architectural decisions for `grabatus-service-core`. Each record is short, immutable, and follows Michael Nygard's format.

When a decision changes, do **not** edit the existing ADR — add a new one that supersedes it.

| ID  | Title (EN) | Title (PT-BR) | Status |
| --- | ---------- | ------------- | ------ |
| 0001 | [Record architecture decisions](0001-record-architecture-decisions.md) | [Registrar decisões arquiteturais](0001-record-architecture-decisions.pt-BR.md) | Accepted |
| 0002 | [Hexagonal Ports & Adapters](0002-hexagonal-ports-and-adapters.md) | [Hexagonal Ports & Adapters](0002-hexagonal-ports-and-adapters.pt-BR.md) | Accepted |
| 0003 | [Receiver / Worker decoupling](0003-receiver-worker-decoupling.md) | [Desacoplamento Receiver / Worker](0003-receiver-worker-decoupling.pt-BR.md) | Accepted |
| 0004 | [Pydantic v2 versioned contract](0004-pydantic-v2-versioned-contract.md) | [Contrato versionado em Pydantic v2](0004-pydantic-v2-versioned-contract.pt-BR.md) | Accepted |
| 0005 | [100% line + branch coverage with justified pragmas](0005-100-percent-coverage.md) | [Cobertura 100% linha + branch com pragmas justificados](0005-100-percent-coverage.pt-BR.md) | Accepted |
| 0006 | [Workload Identity Federation for GitHub → GCP](0006-workload-identity-federation.md) | [Workload Identity Federation para GitHub → GCP](0006-workload-identity-federation.pt-BR.md) | Accepted |
| 0007 | [Multi-tenant URI authorization from day one](0007-multi-tenant-uri-authorization.md) | [Autorização de URI multi-tenant desde o dia zero](0007-multi-tenant-uri-authorization.pt-BR.md) | Accepted |

## Convention

- `NNNN-slug.md` is the **canonical English** record.
- `NNNN-slug.pt-BR.md` is its **Portuguese (Brazilian)** mirror; both must agree on facts.
- ADRs are reviewed in the same PR as the code that implements them.
- Status values: `Proposed`, `Accepted`, `Superseded by ADR-XXXX`, `Deprecated`.
