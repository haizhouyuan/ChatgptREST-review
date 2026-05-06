# ADR-001: State Model Contract

**Status**: Draft v2
**Date**: 2026-03-08 (revised after Codex R3/R4 review)
**Supersedes**: ADR-001 v1

## Context

OpenMind stores cognitive data in multiple representations. The v1 ADR
proposed a universal three-layer promotion chain (Memory → EvoMap → KB).
Review identified this as over-simplified: not all cognitive data is a
"knowledge claim" that benefits from governance. Different object types
have different lifecycle needs.

## Decision

### Object Taxonomy (define types FIRST, stores SECOND)

| Object Type | Definition | Examples |
|------------|-----------|---------|
| **profile_memory** | Persistent user preferences and identity facts | "I prefer dark mode", "My timezone is UTC+8" |
| **episodic_feedback** | Execution outcomes and session-scoped history | tool success/failure, workflow results, user feedback |
| **governed_claim** | Knowledge assertions requiring quality governance | "Module X uses pattern Y", extracted lessons, research conclusions |
| **evidence_artifact** | Raw evidence documents and reference material | Research reports, captured conversations, ingested files |

### Store Mapping

| Object Type | Primary Store | Trust Level | Lifecycle |
|------------|--------------|-------------|-----------|
| **profile_memory** | `memory_manager` (semantic tier) | MEDIUM — user-attested | Persist until overwritten. No promotion needed. |
| **episodic_feedback** | `memory_manager` (episodic tier) | LOW — raw signal | TTL-based expiry. Feeds policy/telemetry. |
| **governed_claim** | EvoMap `Atom` (STAGED→CANDIDATE→ACTIVE) | LOW→HIGH via governance | Promotion pipeline with groundedness gate. |
| **evidence_artifact** | KB `Artifact` (direct writeback) | MEDIUM — raw evidence | Persist as reference. NOT an Atom. |

### Promotion Paths (only where applicable)

```
governed_claim pathway:
  Ingest → EvoMap STAGED → quality gate → CANDIDATE
    → groundedness check → ACTIVE
    → (optional) high-score publish → KB Artifact

evidence_artifact pathway:
  Ingest → quality gate → KB Artifact (direct)
  No EvoMap. The artifact is evidence, not a claim.

profile_memory pathway:
  Capture → semantic memory (direct)
  No promotion. Durable in-place.

episodic_feedback pathway:
  Telemetry → episodic memory
  No promotion. TTL-based.
  Feeds: policy hints, EvoMap observer signals.
```

### Anti-patterns (MUST NOT)

1. **Force user preferences through EvoMap** — "I like dark mode" does not need groundedness checking.
2. **Treat raw evidence as Atom** — A research report is a reference document, not a claim to be promoted.
3. **Store episodic feedback as durable knowledge** — Execution telemetry has TTL, it's signal not truth.
4. **Shell bypasses domain service** — All writes must go through the appropriate domain service (see ADR-002).

### Promotion Thresholds (defaults, configurable)

Applies only to **governed_claim** pathway:

| Transition | Default Threshold | Config Key |
|-----------|-------------------|-----------|
| STAGED → CANDIDATE | `quality_auto >= 0.3, value_auto >= 0.2` | `evomap.promotion.staged_to_candidate` |
| CANDIDATE → ACTIVE | `enforce_promotion_gate()` passes | `evomap.promotion.groundedness_gate` |
| ACTIVE → KB publish | `quality_auto >= 0.7, groundedness >= 0.6` | `evomap.promotion.active_to_kb` |

> These defaults have no calibration data yet. They should be adjusted
> based on production observation once timing telemetry is in place.

## Consequences

- Object type determines store, not a universal hierarchy.
- Only governed_claims go through EvoMap promotion.
- Evidence artifacts enter KB directly as reference material.
- User preferences persist without governance overhead.
- Adding new object types requires defining store + lifecycle, not fitting into a promotion chain.
