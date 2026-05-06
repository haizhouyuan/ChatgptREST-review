# ADR-004: Path SLA Contract

**Status**: Draft v2
**Date**: 2026-03-08 (revised after Codex R3/R4 review)
**Depends on**: ADR-001 (State Model), ADR-003 (Identity)

## Context

v1 conflated vector index (write-time) with vector query (read-time).
`hub.py:index_document()` auto-embeds at ingest time, but `_NoEmbedKBHub`
only suppresses query-side embedding on hot path. The SLA must distinguish
these two operations.

## Decision

### Three Retrieval Tiers

| Tier | Trigger | Latency Target | Notes |
|------|---------|---------------|-------|
| **Hot** | `before_agent_start` / `/v2/context/resolve` | < 200ms (target, not contract) | Must be measured before hardening |
| **Warm** | `agent_end` / `/v2/memory/capture` / `/v2/knowledge/ingest` | < 2s (target) | Memory capture stays in SQLite; KB ingest may include index-time embedding |
| **Cold** | `/v2/advisor/ask` | < 5min (target) | Full capability |

> **Important**: These are **targets**, not **contracts**. They become contracts
> only after timing telemetry produces P95 baselines.

### Capability Matrix (Read vs Write)

| Capability | Hot READ | Warm WRITE | Cold READ/WRITE |
|-----------|----------|-----------|----------------|
| FTS5 keyword **query** | ✅ via `_NoEmbedKBHub` | N/A | ✅ |
| Vector embedding **query** | ❌ auto_embed=False | N/A | ✅ auto_embed=True |
| Vector embedding **index** | N/A | ✅ `index_document()` auto-embeds | ✅ |
| Working/episodic/semantic memory | ✅ | N/A | ✅ |
| EvoMap atom retrieval | ✅ | N/A | ✅ |
| repo_graph (GitNexus CLI) | ❌ degraded, skip | ❌ | ✅ opt-in |
| quality_gate evaluation | N/A | ✅ | ✅ |
| Graph mirror (`_mirror_into_graph`) | N/A | ✅ | N/A |

### Degradation Rules

| Source | Hot Path | Warm Path | Cold Path |
|--------|----------|-----------|-----------|
| Memory recall timeout | Return partial context | N/A | Return partial |
| FTS5 timeout | Log + skip KB sources | N/A | Log + skip |
| repo_graph failure | Already skipped | Already skipped | Return `{degraded: true}` |
| Graph mirror failure | N/A | Continue (already implemented) | N/A |
| Vector search unavailable | Already skipped | N/A | Fall back to FTS5 |

### Timing Telemetry (MUST implement before promoting targets to contracts)

```python
# After every hot-path resolve
TraceEvent.create(
    event_type="cognitive.resolve.timing",
    data={
        "tier": "hot",
        "total_ms": elapsed_ms,
        "sources_resolved": ["working", "episodic", "semantic", "kb_fts"],
        "sources_degraded": ["repo_graph"],
        "target_ms": 200,
        "over_target": elapsed_ms > 200,
    }
)
```

Once P95 data exists, replace "target" with "contract" in this ADR.

## Consequences

- Index-time embedding is allowed on warm path (current behavior preserved).
- Query-time embedding is cold-path only (current behavior preserved).
- SLA numbers are honest about being targets, not measured contracts.
- Timing telemetry is a prerequisite for hardening, not an afterthought.
