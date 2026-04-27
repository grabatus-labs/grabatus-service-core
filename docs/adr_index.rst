Architecture Decision Records
=============================

Long-lived architectural decisions for ``grabatus-service-core``.
Each record is short, immutable, and follows Michael Nygard's
*Context, Decision, Consequences* format.

When a decision changes, the existing ADR is **not** edited — a new
ADR is added that supersedes the old one. The superseded ADR's status
is updated to ``Superseded by ADR-XXXX`` but the body is preserved.

.. toctree::
   :maxdepth: 1
   :caption: English (canonical)

   adr/0001-record-architecture-decisions
   adr/0002-hexagonal-ports-and-adapters
   adr/0003-receiver-worker-decoupling
   adr/0004-pydantic-v2-versioned-contract
   adr/0005-100-percent-coverage
   adr/0006-workload-identity-federation
   adr/0007-multi-tenant-uri-authorization

.. toctree::
   :maxdepth: 1
   :caption: Português (Brasil)

   adr/0001-record-architecture-decisions.pt-BR
   adr/0002-hexagonal-ports-and-adapters.pt-BR
   adr/0003-receiver-worker-decoupling.pt-BR
   adr/0004-pydantic-v2-versioned-contract.pt-BR
   adr/0005-100-percent-coverage.pt-BR
   adr/0006-workload-identity-federation.pt-BR
   adr/0007-multi-tenant-uri-authorization.pt-BR
