# EvoMap: Current Implementation vs OpenClaw Original — Gap Analysis (v2)

**Date:** 2026-03-10  
**Author:** Antigravity  
**Revision:** v2 — corrects 5 high-severity factual errors from v1 based on Codex peer review  

> [!CAUTION]
> v1 analyzed the **wrong database** (`~/.openmind/evomap_knowledge.db`, the old scratch DB) instead of the runtime default (`data/evomap_knowledge.db`). This invalidated multiple core conclusions. v2 is based on verified data from both databases.

---

## v1 → v2 Corrections Log

| # | v1 Claim | Codex Correction | v2 Verified Status |
|---|---------|-----------------|-------------------|
| 1 | "0 edges, 0 telemetry" | Main DB has 82,789 edges, 156 query events, 689 retrieval events | ✅ Confirmed — v1 queried wrong DB |
| 2 | "Zero evolution features wired into runtime" | `runtime.py:552-678` has full EvoMap pipeline gated by `OPENMIND_ENABLE_EVOMAP_EXTRACTORS` | ✅ Confirmed — orchestration exists but env flag not enabled |
| 3 | "Retrieval not invoked by advisor/context" | `context_service.py:558-564` calls `evomap_retrieve()` | ✅ Confirmed — retrieval IS connected |
| 4 | "2,329 active atoms set by chain builder" | Chain builder only sets candidate/superseded/staged. Active atoms from `p4_batch_fix.py` (`auto_p4_quality_check`) | ✅ Confirmed — `~/.openmind` DB shows `promotion_reason='auto_p4_quality_check'` for all 2,329 active |
| 5 | "Problem is purely orchestration gap" | Core issue is **dual-DB divergence**: runtime uses `data/evomap_knowledge.db`, ops scripts use `~/.openmind/evomap_knowledge.db` | ✅ Confirmed — two DBs have completely different data |

---

## Executive Summary (Corrected)

The EvoMap implementation is **architecturally comprehensive** and has **partial runtime orchestration**. The system is not "dead code" — the runtime pipeline, graph builder, and retrieval are wired and have produced real data. However, several critical evolution subsystems still have **zero production output**, and a **dual-database divergence** creates a confusing observability landscape.

---

## The Two Databases: A Critical Distinction

| Property | `data/evomap_knowledge.db` (runtime) | `~/.openmind/evomap_knowledge.db` (scratch/ops) |
|----------|--------------------------------------|------------------------------------------------|
| **Used by** | `runtime.py`, `context_service.py`, API endpoints | `ops/run_atom_refinement.py`, `p4_batch_fix.py` |
| **Atoms** | 95,239 (all `staged`) | 2,727 (2,329 active, 324 staged, 74 superseded) |
| **Edges** | 82,789 | 0 |
| **Entities** | 0 | 0 |
| **Query events** | 156 | 0 |
| **Retrieval events** | 689 | 0 |
| **Groundedness audits** | 0 | table doesn't exist |
| **Promotion audits** | 0 | table doesn't exist |
| **Extractors ran** | Yes (ChatFollowup, MaintRunbook, NoteSection, CommitKD0, Antigravity, Activity) | No (manual refinement only) |
| **Graph builder ran** | Yes (82,789 edges) | No |
| **P1 chain builder ran** | Unclear (all 95K are staged) | Yes (2,376 chains, 74 superseded) |
| **P2 groundedness ran** | No (0 audits) | No |

> [!IMPORTANT]
> The ops scripts (`run_atom_refinement.py`, `p4_batch_fix.py`) default to `~/.openmind/evomap_knowledge.db` while the runtime defaults to `data/evomap_knowledge.db`. These two databases have diverged completely. This is not an orchestration gap — it's a **path contract divergence**.

---

## Current Production State: What Actually Works

### ✅ Working & Producing Data

| Feature | Evidence | Code Path |
|---------|----------|-----------|
| **Knowledge Extraction** (6 extractors) | 95,239 atoms in main DB | `runtime.py:555-638` |
| **Graph Builder** (structural edges) | 82,789 edges in main DB | `runtime.py:611-616` calls `GraphBuilder.build_all()` |
| **Retrieval Pipeline** | 156 queries, 689 retrieval events | `context_service.py:558-564`, `routes_consult.py:151,578` |
| **Atom Refinement** | Active in pipeline | `runtime.py:643-652` |
| **Memory Promotion** (`stage_and_promote()`) | Just landed (1B) | `memory_manager.py` |
| **KB Vector Persistence** | Just fixed | `hub.py` |
| **KB Registry Quality Scoring** | Hot path code wired, existing data not backfilled | `registry.py:327,384` |

### ⚠️ Wired But Not Enabled in Current Deployment

| Feature | Why Not Running | Gate |
|---------|----------------|------|
| **Full EvoMap Pipeline** (extractors + graph + refiner + P2) | Env flag off | `OPENMIND_ENABLE_EVOMAP_EXTRACTORS=false` |
| **P2 Groundedness** (path/service/staleness/symbol) | Part of the gated pipeline | Same env flag |

### ❌ No Production Output (Genuinely Not Running)

| Feature | Code Status | Production Evidence |
|---------|-------------|-------------------|
| **Entity Extraction** | Schema exists, no extractor populates it | entities=0 in both DBs |
| **P2 Groundedness Audits** | Code complete, in pipeline | groundedness_audit=0 in main DB |
| **Promotion Audits** | Code complete, promotion engine never invoked | promotion_audit=0 in main DB |
| **Macro-Atom Synthesis** | 464 lines, NOT in runtime pipeline | No synthesis atoms found |
| **Sandbox** (experimentation + merge) | 570 lines, no CLI/UI triggers | No sandboxes.json |
| **Evolution Queue + Executor** | 330+239 lines, no evolution_queue.db | Never used |
| **Telemetry Feedback Loop** | Has recording, missing feedback collection | answer_feedback=0 |
| **Knowledge Supersession (in main DB)** | All 95,239 atoms are "staged" | P1 chain builder not run on main DB |

---

## What OpenClaw Envisioned vs Current Reality (Corrected)

| Feature | OpenClaw Vision | Current Status | Effectiveness |
|---------|----------------|----------------|---------------|
| **Knowledge extraction** (multi-source) | Core design goal | ✅ 6 extractors wired, 95K atoms | **Working but gated** |
| **Graph building** (structural edges) | WP4 | ✅ 82,789 edges produced | **Working but gated** |
| **Retrieval** (FTS + quality gating) | Retrieval pipeline | ✅ Connected to context service | **Working** |
| **Knowledge self-curation** (auto-score, promote, demote) | Core design goal | ⚠️ Code exists, P2/promotion never audit-trail | **Partial** |
| **Groundedness verification** | WP2 | ⚠️ Code in pipeline, 0 audits produced | **Not effective yet** |
| **Knowledge supersession** | WP1/P1 | ⚠️ Works on scratch DB (74 superseded), not run on main DB | **Partial** |
| **Knowledge synthesis** | WP5 | ❌ Not in runtime pipeline, never ran | **0% effective** |
| **Evolution planning** | WP3 | ❌ Never used | **0% effective** |
| **Sandbox experimentation** | WP6 | ❌ Never used | **0% effective** |
| **Retrieval quality feedback loop** | Telemetry design | ⚠️ Query/retrieval telemetry exists, feedback missing | **Partial** |
| **Entity-based knowledge navigation** | Entity extraction | ❌ 0 entities in both DBs | **0% effective** |
| **Semantic memory promotion** | Memory system | ✅ Just landed (1B) | **Just wired** |

---

## The Three Real Problems (Corrected)

### Problem 1: Dual-Database Divergence

This is the **most damaging issue**. Two completely separate knowledge stores with different data, different schemas, and different evolutionary state:

- `data/evomap_knowledge.db` (95K atoms, 82K edges, all staged, no chain/promotion)
- `~/.openmind/evomap_knowledge.db` (2.7K atoms, 0 edges, chain-built, p4-promoted)

The ops scripts that perform governance (refinement, P1 chains, P4 quality checks) operate on the scratch DB, while the runtime that builds the graph and serves retrieval uses the repo DB. **Neither side benefits from the other's work.**

### Problem 2: Gated Pipeline Not Enabled

The `OPENMIND_ENABLE_EVOMAP_EXTRACTORS` flag gates the entire pipeline. The pipeline includes:
1. 6 extractors (ChatFollowup, MaintRunbook, NoteSection, CommitKD0, Antigravity, Activity)
2. GraphBuilder
3. AtomRefiner
4. P2 Groundedness

When enabled, all of these run on a 4-hour cycle in a daemon thread. When disabled (current deployment), none run. The 82,789 edges and 95,239 atoms were presumably created during a previous period when the flag was enabled.

### Problem 3: Missing Evolution Subsystems in Pipeline

Even when the pipeline IS enabled, it does NOT include:
- **Synthesis** (`MacroAtomSynthesizer`) — not called anywhere in `runtime.py`
- **P1 Chain Builder** — not called in the runtime pipeline
- **Evolution Queue/Executor** — no submit mechanism
- **Sandbox** — no workflow
- **Entity Extraction** — schema exists but no extractor populates `entities` table
- **Telemetry Feedback** — query/retrieval events recorded but no feedback collection

---

## Honest Assessment (Corrected)

**My v1 analysis was significantly wrong** because I audited the wrong database. The real situation is more nuanced than "complete code but zero orchestration."

**What's actually true:**
1. The runtime orchestration exists and has historically produced significant data (82K edges, 95K atoms)
2. Retrieval IS connected to the advisor/context service
3. The code quality is genuinely good across all modules
4. Several subsystems (synthesis, evolution queue, sandbox) are genuinely unconnected
5. The dual-DB divergence is a real and serious problem
6. Groundedness and promotion auditing have never produced output even in the main DB

**What I got wrong in v1:**
1. Claimed "zero orchestration" — wrong, runtime pipeline exists
2. Claimed "0 edges, 0 telemetry" — wrong, queried the wrong DB
3. Claimed "chain builder set active" — wrong, it was `p4_batch_fix.py`
4. Claimed "retrieval not connected" — wrong, context_service calls it
5. Framed the problem as "purely orchestration" — it's primarily a dual-DB divergence

**Recommended priority:**
1. **P0**: Resolve dual-DB divergence — decide which DB is canonical and consolidate
2. **P0**: Re-enable `OPENMIND_ENABLE_EVOMAP_EXTRACTORS` (or understand why it was disabled)
3. **P1**: Run P1 chain builder on the main DB (95K staged atoms need chain grouping)
4. **P1**: Add synthesis to the runtime pipeline
5. **P2**: Build entity extraction into extractors
6. **P2**: Implement telemetry feedback collection

---

## Appendix: Verified Data Queries

```sql
-- Main runtime DB: data/evomap_knowledge.db
SELECT 'atoms', COUNT(*) FROM atoms;        -- 95,239
SELECT 'edges', COUNT(*) FROM edges;        -- 82,789
SELECT 'entities', COUNT(*) FROM entities;  -- 0
SELECT 'query_events', COUNT(*) FROM query_events;        -- 156
SELECT 'retrieval_events', COUNT(*) FROM retrieval_events; -- 689
SELECT promotion_status, COUNT(*) FROM atoms GROUP BY promotion_status;
  -- staged|95239
SELECT COUNT(*) FROM groundedness_audit;  -- 0
SELECT COUNT(*) FROM promotion_audit;     -- 0

-- Old scratch DB: ~/.openmind/evomap_knowledge.db
SELECT promotion_status, COUNT(*) FROM atoms GROUP BY promotion_status;
  -- active|2329, staged|324, superseded|74
SELECT promotion_reason, COUNT(*) FROM atoms WHERE promotion_status='active' GROUP BY promotion_reason;
  -- auto_p4_quality_check|2329
SELECT COUNT(*) FROM edges;    -- 0
SELECT COUNT(*) FROM entities; -- 0
```
