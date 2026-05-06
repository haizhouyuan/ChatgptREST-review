# Planning Agent Knowledge Architecture — Independent Audit

**Auditor**: Antigravity (atomic code read + GitNexus + live DB analysis)
**Date**: 2026-04-02
**Scope**: 5 review documents + all referenced source modules + live EvoMap DB + live release bundle

---

## Documents Reviewed

| # | Document | Verdict |
|---|----------|---------|
| 1 | `second_opinion_packet_planning_agent_and_knowledge_validation_v2.md` | Entry point; structurally sound |
| 2 | `planning_knowledge_effectiveness_validation_v2.md` | Claims broadly correct, but **one critical gap missed** |
| 3 | `planning_knowledge_gap_closure_and_rebuild_decision_v1.md` | Decision logic sound; gap severity underestimated |
| 4 | `planning_knowledge_capability_value_matrix_v1.md` | Tier ranking correct; operational readiness overstated |
| 5 | `planning_unified_logical_task_layer_v1.md` | Design document only — **zero code implementation exists** |

---

## Executive Summary

> [!IMPORTANT]
> **Strategy verdict: "补齐优先，不重构" is correct.** The architecture is fundamentally sound. However, the review packet **significantly underestimates the severity of the current gaps**. What was presented as "freshness staleness" is actually a **total data plane disconnect** — the runtime pack's atoms don't exist in the EvoMap DB at all, making the runtime gate return 0 hits for 100% of queries.

### Critical Findings

| ID | Severity | Finding | Evidence |
|----|----------|---------|----------|
| F1 | **P0 BLOCKER** | Pack atoms (226) use `at_c_*` ID scheme; EvoMap DB uses `at_<uuid>`. Zero overlap → **0% gate pass rate** | Live DB query: `not_in_db: 226` |
| F2 | **P0** | No `planning_review` meta in EvoMap DB documents (0 of 61 docs) | `json_extract(meta_json, '$.planning_review') IS NOT NULL` → 0 rows |
| F3 | **P1** | Pack is 530+ hours stale (Mar 11 → Apr 2). No auto-refresh pipeline exists | `grep auto.*promotion` → 0 results; no cron/scheduler found |
| F4 | **P1** | Unified Logical Task Layer (`task_id`, `LogicalTask`) has **zero code implementation** | `grep logical_task_key\|TaskRuntime\|LogicalTask` → 0 results in `chatgptrest/` |
| F5 | **P2** | Acceptance validation uses only 4 golden queries — too narrow for daily planning coverage | `query_count: 4` in release manifest |

---

## Detailed Analysis

### 1. Runtime Pack Search Pipeline (planning_runtime_pack_search.py)

**Code Path** (from GitNexus `proc_190_advisor_recall`):
```
ContextAssembler.build()
  → search_planning_runtime_pack(query, top_k)
    → resolve_ready_planning_runtime_pack_bundle()
    → _fetch_pack_rows(pack_dir)         # reads docs.tsv, atoms.tsv, retrieval_pack.json
    → _tokenize(query) + _score()        # simple keyword matching
    → _fetch_db_rows(evomap_db, atom_ids) # JOIN atoms → episodes → documents
    → _passes_runtime_gate(row, cfg)     # promotion + stability + quality + groundedness
```

**The Fatal Break**: Step 5 (`_fetch_db_rows`) does a `WHERE atom_id IN (...)` lookup using pack-format IDs (`at_c_b4c1c9c76533_1_1`) against a DB that only contains UUID-format IDs (`at_00071add555d4ff8b96f53ad9fc9d1db`). Result: **zero rows returned, zero results pass gate, search always returns `[]`**.

```python
# planning_runtime_pack_search.py:124-134
def _passes_runtime_gate(row: dict[str, Any], cfg: RetrievalConfig) -> bool:
    if str(row.get("promotion_status") or "") not in cfg.allowed_promotion_status:
        return False
    if float(row.get("quality_auto") or 0.0) < cfg.min_quality:
        return False
    groundedness = row.get("groundedness")
    if groundedness is not None and float(groundedness or 0.0) < 0.5:
        return False
    return True
```

This gate logic is **correct in design** — it just never fires because no rows reach it.

### 2. Work Memory Manager (work_memory_manager.py)

**Verdict: Production-ready.** GitNexus confirms this is a standalone write/read path that doesn't depend on the broken pack pipeline.

Key evidence:
- `build_active_context()` constructs context from `active_project`, `decision_ledger`, `post_call_triage`, `handoff_card` scopes
- Write path is durable (SQLite-backed via MemoryManager)
- Identity scoping (session_id, account_id, agent_id, role_id, thread_id) is properly implemented
- No coupling to the broken pack search path

**One concern**: The work memory importer (`WorkMemoryImporter`) is structurally sound but has no automated ingress trigger — manifests must be manually submitted. This is acceptable for the current stability goal but will bottleneck scale.

### 3. Context Service Integration (context_service.py)

The context service's planning integration is well-designed:

```python
# Lines 862-904: Planning pack injection in _LocalOnlyContextAssembler.build()
planning_role_priority = str(role_id or "").strip().lower() == "planning"
priority_mode = "planning_role_explicit_highest" if planning_role_priority else "default_runtime_chain"
# Priority 0 (absolute top) when role_id == "planning"
```

```python
# Lines 476-495: Prompt prefix composition in _compose_prompt_prefix()
if planning_section and planning_priority_mode == "planning_role_explicit_highest":
    sections.append(planning_section)  # FIRST, before everything
```

**This design is correct** — the planning pack gets `priority=0` (highest) when `role_id="planning"`. But since `search_planning_runtime_pack()` always returns `[]`, the `planning_block` is always `None`, and this entire priority logic never activates.

### 4. EvoMap Retrieval Pipeline (retrieval.py)

The EvoMap retrieval pipeline is clean and well-gated:
- `USER_HOT_PATH` surface only allows `ACTIVE` promotion status (line 116)
- FTS5 → pre-filter → quality gate → time decay → diversify → limit
- Auto-rescore runs once per process for zero-quality atoms

**However**, there's also a timing concern: `_ensure_rescored()` does a global `SELECT COUNT(*)` + potential batch UPDATE on first call, which explains why our live test hung (it was rescoring 2700+ atoms on the hot path).

### 5. Unified Logical Task Layer

**This exists only as a design document** (`planning_unified_logical_task_layer_v1.md`, 444 lines). My code search confirms:

```
grep -r "logical_task_key|TaskRuntime|LogicalTask" chatgptrest/ → 0 results
```

The document describes `task_id` as the source of truth for planning continuity, with L0-L3 memory scopes and checkpoint semantics. None of this is implemented. The review packet's claim that the "Unified Logical Task Layer validates" should be read as "the design is reviewed and approved" — **not** "the code exists and works".

---

## Verification of Review Packet Claims

| Claim (from review docs) | My Verification | Status |
|---------------------------|-----------------|--------|
| "Work memory is production-ready" | Confirmed via code read + GitNexus context analysis | ✅ Accurate |
| "Runtime pack structure is sound but stale" | **Understated** — pack is not just stale, it's disconnected from DB | ⚠️ Misleading |
| "Ready=false due to freshness" | Pack manifest says `ready_for_explicit_consumption: true`; actual failure is ID mismatch | ❌ Incorrect diagnosis |
| "KB/Vector/Graph should be supporting, not primary" | Tier ranking correct; but KB has 61 docs with zero planning meta | ✅ Verdict correct |
| "Only 4 golden queries" | Confirmed; insufficient for daily planning coverage | ✅ Accurate |
| "Automated pipeline not yet integrated" | Confirmed; no cron/scheduler/auto-promotion code exists | ✅ Accurate |
| "Unified task layer provides continuity" | Design doc only; zero implementation | ❌ Overstated |

---

## Live Database Evidence

### Global EvoMap Atom Distribution
```
Promotion status:
  active:     2329 atoms (avg groundedness: 0.994)
  staged:      324 atoms (282 with groundedness < 0.5)
  superseded:   74 atoms

Groundedness distribution:
  perfect 1.0:  2255 (82.7%)
  below 0.5:     398 (14.6%)
  0.5 to 1.0:     74 (2.7%)
```

### Planning Runtime Pack vs EvoMap DB
```
Pack atoms:     226 (format: at_c_<hash>_<n>_<n>)
DB atoms:      2727 (format: at_<uuid>)
Overlap:          0 (0.0%)
Planning-review tagged documents in DB: 0 of 61
```

> [!CAUTION]
> **The planning review plane generated atoms into the pack TSV files but never ingested them into the EvoMap SQLite database.** The pack search function (`_fetch_db_rows`) does a DB lookup that will always return empty because the atoms simply don't exist in the DB.

---

## Remediation Plan

### P0: Fix the Data Plane Disconnect (1 day)

Two approaches, choose one:

**Option A (Recommended): Ingest pack atoms into EvoMap DB**
- Write a migration script that reads `atoms.tsv` + `docs.tsv` from the pack, creates proper EvoMap `documents` → `episodes` → `atoms` records in the DB, with:
  - `meta_json` containing `planning_review` metadata
  - `promotion_status = 'active'` (since pack was already review-approved)
  - `groundedness = 1.0` (pack atoms are grounded in source documents)
- Re-run the release readiness checker to validate

**Option B: Bypass DB lookup for pack-only search**
- Modify `search_planning_runtime_pack()` to score and return results purely from the pack TSV files, without the `_fetch_db_rows()` + `_passes_runtime_gate()` step
- Faster but loses the quality/promotion/groundedness governance gates

### P1: Refresh Pack + Add Automation (3 days)

1. **Rebuild the pack** with current planning data (the existing pack references Mar 11 data)
2. **Create a scheduled pack refresh** — even a simple weekly cron that runs `planning_review_plane.bootstrap()` + validation + bundle creation
3. **Expand golden queries** from 4 to at least 15-20, covering:
   - Budget/financial planning queries
   - Organizational structure queries
   - Market analysis queries
   - Competitive intelligence queries
   - Project status/milestone queries

### P1: Fix Auto-Rescore Hot-Path Block

- Move `_ensure_rescored()` out of the hot retrieval path. It currently runs on first `retrieve()` call and can block for seconds while doing batch updates on 2700+ atoms
- Either: run it in a background thread, or make it a separate maintenance script

### P2: Implement Logical Task Layer

- The design document is sound but implementation hasn't started
- Minimum viable: implement `task_id` persistence in the advisor session, checkpoint save/restore, and memory scope binding
- This is correctly classified as P2 — work memory provides sufficient continuity for now

---

## Architectural Verdict

```
┌─────────────────────────────────────────────────────────┐
│                    STRATEGY: 补齐优先                      │
│                                                         │
│  ✅ Work Memory Manager    → PRODUCTION-READY            │
│  ✅ Context Service        → INTEGRATION CORRECT         │
│  ✅ EvoMap Retrieval       → PIPELINE SOUND              │
│  ✅ Governance/Acceptance  → DESIGN ADEQUATE             │
│                                                         │
│  🔴 Runtime Pack Search   → BROKEN (0% hit rate)        │
│     Root cause: atom ID namespace mismatch               │
│     Fix: P0, 1 day, migration script                     │
│                                                         │
│  🟡 Pack Freshness        → STALE (530+ hours)          │
│  🟡 Auto-Promotion        → NOT IMPLEMENTED              │
│  🟡 Logical Task Layer    → DESIGN ONLY                  │
│  🟡 Acceptance Coverage   → TOO NARROW (4 queries)       │
└─────────────────────────────────────────────────────────┘
```

**Bottom line**: The review packet's strategic conclusion ("补齐优先，不重构") is **correct and well-reasoned**. The architecture doesn't need a rebuild. But the P0 data plane disconnect means the planning runtime pack is currently providing **zero value** in production. This single fix — ingesting pack atoms into the EvoMap DB with proper IDs and metadata — would immediately activate the entire planning priority chain that's already correctly wired in the context service.

---

## Files Analyzed

| File | Lines Read | Key Findings |
|------|-----------|--------------|
| [planning_runtime_pack_search.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_runtime_pack_search.py) | 1-250 (full) | ID mismatch root cause at `_fetch_db_rows` |
| [retrieval.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/retrieval.py) | 1-516 (full) | Clean pipeline; auto-rescore blocks hot path |
| [context_service.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py) | 185-984 | Priority logic correct but never activates |
| [work_memory_manager.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_manager.py) | (previous session) | Production-ready confirmed |
| [work_memory_importer.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_importer.py) | (previous session) | Manual-only ingress |
| [acceptance.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/governance/acceptance.py) | 1-310 (full) | 6-dimension scorecard present |
| [planning_review_plane.py](file:///vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_review_plane.py) | (previous session) | Bootstrap creates pack but doesn't ingest to DB |
| Live EvoMap DB (`evomap_knowledge.db`) | Direct SQL queries | Zero planning-review docs; ID format mismatch confirmed |
| Release bundle manifest | JSON analysis | Claims `ready_for_explicit_consumption: true` despite data disconnect |

**GitNexus processes analyzed**: `proc_190_advisor_recall`, `proc_192_memory_capture`, `proc_102_advisor_consult`, `proc_146_advise`
