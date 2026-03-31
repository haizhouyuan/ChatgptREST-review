# ADR-002: Ingress Contract

**Status**: Draft v2
**Date**: 2026-03-08 (revised after Codex R3/R4 review)
**Depends on**: ADR-001 (State Model)

## Context

v1 required all shells to write via HTTP `/v2/` APIs exclusively. Review
identified this as conflating transport with contract. The real requirement
is that all writes go through the same domain service with the same
admission/audit/identity/idempotency rules, regardless of transport.

## Decision

### Transport-Agnostic Service Boundary

The contract is at the **domain service** level, not the HTTP route level:

```
External shells (OpenClaw, CLI)      Internal callers (Antigravity, advisor graph)
        │                                      │
        ▼                                      ▼
   HTTP /v2/ routes                    Python direct import
        │                                      │
        └──────────────┬───────────────────────┘
                       ▼
              Domain Services (the REAL boundary)
              ┌─────────────────────────────────┐
              │ CaptureEvalService              │ ← auto-capture evaluation
              │ KnowledgeIngestService           │ ← explicit knowledge ingest
              │ TelemetryIngestService           │ ← execution feedback
              │ ContextResolver                  │ ← retrieval
              └─────────────────────────────────┘
                       │
              Same rules regardless of caller:
              • Identity validation (ADR-003)
              • Quality gate / admission check
              • Audit trail (event emission)
              • Idempotency (trace_id based)
```

Both HTTP and in-process calls are **legal transports** as long as they
route through the domain service.

### Object-Type-to-Service Routing (per ADR-001)

| Object Type | Entry Service | Target Store |
|------------|--------------|-------------|
| profile_memory | `CaptureEvalService` → `memory_manager.stage_and_promote(SEMANTIC)` | semantic memory |
| episodic_feedback | `TelemetryIngestService` → `memory_manager.stage_and_promote(EPISODIC)` | episodic memory |
| governed_claim | `KnowledgeIngestService` → `_mirror_into_graph()` | EvoMap CANDIDATE |
| evidence_artifact | `KnowledgeIngestService` → `writeback_service.writeback()` | KB Artifact |

### New Service: CaptureEvalService

Replaces client-side `shouldCapture()`, `CAPTURE_PATTERNS`,
`looksLikePromptInjection()` from `openmind-memory/index.ts`.

```python
class CaptureEvalService:
    def evaluate(self, texts: list[str], session_id: str,
                 agent_id: str, source: str) -> list[CaptureEvaluation]:
        """Server-side capture evaluation.

        Returns per-text evaluation with:
        - worth_capturing: bool
        - object_type: profile_memory | governed_claim | skip
        - reason: str
        - confidence: float
        - injection_risk: bool
        """
```

### Prohibited Patterns

| Pattern | Why | Correct Alternative |
|---------|-----|-------------------|
| Shell imports `memory_manager` and calls `store()` directly | Bypasses identity, audit, quality gate | Call domain service (HTTP or Python) |
| Shell calls `writeback_service` directly for KB write | Bypasses admission check | Use `KnowledgeIngestService` |
| Shell contains capture evaluation logic | Logic duplication across shells | Use `CaptureEvalService` |

## Consequences

- Shells become thin transport adapters.
- Adding a new shell requires zero business logic duplication.
- In-process callers (Antigravity, advisor) don't pay HTTP overhead.
- All writes go through the same audit trail regardless of transport.
