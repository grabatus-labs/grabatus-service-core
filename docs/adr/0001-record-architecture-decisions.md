# ADR-0001 — Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-04-26
- **Deciders:** Grabatus engineering

## Context

The Grabatus computational services platform involves long-lived architectural decisions that need to be remembered, justified, and revisited as the system evolves. New contributors need to understand *why* the system is shaped the way it is, not just what it looks like today. Without a written record, the rationale for past decisions tends to be lost in chat history, PR comments, or individual memory.

## Decision

We adopt **Architecture Decision Records (ADRs)** as defined by Michael Nygard. Every cross-cutting architectural decision is captured in `docs/adr/NNNN-slug.md` (English, canonical) and mirrored in `docs/adr/NNNN-slug.pt-BR.md` (Portuguese).

Each record uses the sections **Context, Decision, Consequences** (and optionally **Alternatives Considered**), is short (one page when possible), and is **immutable**: when a decision is changed, a new ADR is added that supersedes the old one. The superseded record's status is updated to `Superseded by ADR-XXXX` but its body is preserved.

ADRs are written and reviewed in the same pull request as the code that implements them.

## Consequences

- New contributors can read `docs/adr/` and understand the project's architectural shape in under an hour.
- Technical debate happens once, in writing, instead of repeating across chats.
- The decision history is auditable and survives team turnover.
- Mirroring in Portuguese makes the rationale accessible to the entire Grabatus team without depending on translation tools.
- The cost is the discipline of writing an ADR for each significant decision; small decisions (naming, formatting, library micro-versions) are excluded.
