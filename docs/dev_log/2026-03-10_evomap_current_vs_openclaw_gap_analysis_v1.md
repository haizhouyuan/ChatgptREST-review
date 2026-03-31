# EvoMap: Current Implementation vs OpenClaw Original — Gap Analysis

**Date:** 2026-03-10  
**Author:** Antigravity  
**Scope:** Complete code + production data audit of `chatgptrest/evomap/` + `chatgptrest/kb/`

---

## Executive Summary

The current EvoMap implementation is **architecturally comprehensive** — every evolution subsystem designed in the OpenClaw vision has been coded. However, **zero of the evolution features are wired into runtime orchestration**. The code exists in isolation; the pipelines have never been triggered in production.

| Aspect | Code Status | Production Status | Verdict |
|--------|-------------|-------------------|---------|
| **Ingestion** (Document → Episode → Atom) | ✅ Complete | ✅ Running (2,727 atoms, 239 episodes, 61 docs) | **Working** |
| **Atom Refinement** (LLM scoring + canonical Q) | ✅ Complete | ✅ Ran (2,450 scored atoms) | **Working** |
| **P1 Chain Builder** (valid_from + supersession) | ✅ Complete | ✅ Ran once (2,376 chains, 74 superseded) | **Working** |
| **P2 Groundedness** (path/service/staleness/symbol) | ✅ Complete (526 lines) | ❌ Never triggered (0 audits, table not created) | **Dead code** |
| **Promotion Engine** (5-stage FSM + audit trail) | ✅ Complete (273 lines) | ❌ Never used by runtime (2,329 "active" atoms were set by chain builder, not promotion engine) | **Dead code** |
| **Graph Builder** (atom edges: SAME_TOPIC, DERIVED, SUPERSEDES) | ✅ Complete (341 lines) | ❌ 0 edges in production | **Dead code** |
| **Entity Extraction** | ✅ Schema exists | ❌ 0 entities in production | **Dead code** |
| **Synthesis** (macro-atom clustering + LLM/heuristic) | ✅ Complete (464 lines) | ❌ Never triggered | **Dead code** |
| **Sandbox** (isolated experimentation + merge) | ✅ Complete (570 lines) | ❌ Never used | **Dead code** |
| **Telemetry** (query events, retrieval events, feedback) | ✅ Complete (491 lines) | ❌ Tables exist but 0 rows | **Dead code** |
| **Evolution Queue** (plan submit/approve/execute) | ✅ Complete (330 + 239 lines) | ❌ No `evolution_queue.db` exists | **Dead code** |
| **Retrieval** (FTS + quality gating + relevance scoring) | ✅ Complete (394 lines) | ⚠️ Available but not actively used by router | **Idle** |
| **KB Vector Persistence** | ✅ Fixed (hub.py `save()` call) | ✅ Fixed by Codex (recent commits) | **Just fixed** |
| **KB Registry Quality Scoring** | ✅ Fixed (registry.py `compute_quality()`) | ✅ Fixed by Codex (recent commits) | **Just fixed** |
| **Memory Promotion** (`stage_and_promote()`) | ✅ Implemented | ✅ Codex wired in 1B | **Just landed** |

---

## Detailed Comparison: What OpenClaw Envisioned vs What Actually Runs

### 1. The Original OpenClaw EvoMap Vision (from Issue #99 WPs + Pro consultation)

The original design was a **6-Work-Package evolution system**:

| WP | Name | Purpose |
|----|------|---------|
| WP1 | Knowledge Extraction | Document → Episode → Atom with LLM refinement |
| WP2 | Promotion & Groundedness | 5-stage FSM with mandatory groundedness gate before ACTIVE |
| WP3 | Evolution Plans | Approval queue + plan executor for coordinated changes |
| WP4 | Graph Building | Structural edges between atoms (SAME_TOPIC, DERIVED_FROM, SUPERSEDES) |
| WP5 | Macro-Atom Synthesis | Cluster related atoms → generate summary atoms |
| WP6 | Sandbox | Isolated experimentation with merge-back |

**Plus supporting infrastructure:**
- Telemetry (query/retrieval/feedback events)
- Retrieval pipeline (FTS + quality gate + scoring)
- Evidence tracking (2,700 evidence fragments)
- Chain builder (canonical question dedup + supersession)

### 2. What Actually Runs in Production

Only **WP1 (Extraction) and part of P1 (chain building)** have ever been executed:

```
Document → Episode → Atom → LLM Refine → Chain Build → [STOP]
                                                         ↓
                                                   (Everything below
                                                    never triggers)
                                                         ↓
                                          Groundedness → Promotion → Graph
                                                                      ↓
                                                              Synthesis → Sandbox
                                                                      ↓
                                                              Telemetry → Evolution Plans
```

### 3. The Root Cause: Missing Orchestration Layer

Every module is self-contained and well-implemented. The problem is **no daemon or timer wires them together**:

- `run_p2_groundedness(db)` exists in `groundedness_checker.py` but is never called
- `MacroAtomSynthesizer(db).run()` exists in `synthesis.py` but is never called  
- `GraphBuilder(db).build_all()` exists in `graph_builder.py` but is never called
- `TelemetryRecorder(db).init_schema()` exists but the retrieval pipeline doesn't invoke it
- `ApprovalQueue` and `PlanExecutor` exist but no UI or CLI submits plans
- `EvoMapSandbox` exists but no workflow creates experiments

The ops scripts that DO exist (`ops/run_atom_refinement.py`) only handle ingestion + P1. There is no `ops/run_evomap_evolution.py` or systemd timer for the evolution pipeline.

---

## Specific Feature-Level Gap Assessment

### ✅ Features That Work Well

1. **Knowledge Ingestion Pipeline**: Document → Episode → Atom flow is solid. 2,727 atoms extracted with proper provenance.

2. **LLM Refinement**: `atom_refiner.py` + `distiller.py` + `llm_bridge.py` handle scoring, canonical question generation, and quality assessment. 2,450 atoms successfully scored.

3. **P1 Chain Builder**: `chain_builder.py` correctly groups atoms by canonical question, assigns chain ranks, marks superseded atoms. 42 multi-atom chains with proper ordering.

4. **Schema Design**: The 6-table schema (`documents`, `episodes`, `atoms`, `entities`, `edges`, `evidence`) is well-designed with proper indices, FTS5 support, and content hashing.

5. **Promotion FSM**: The state machine (`staged → candidate → active → superseded → archived`) is correctly implemented with transition validation and immutable audit trail.

### ⚠️ Features Implemented But Never Tested in Production

1. **P2 Groundedness Checker** (526 lines)
   - 4-dimension verification: path existence, systemd service, staleness, code symbol AST check
   - Weighted scoring with dynamic weight assignment
   - Batch runner for candidate atoms
   - **Gap**: `groundedness_audit` table was never created, batch runner never invoked

2. **Graph Builder** (341 lines)
   - 3-pass structural edge builder: SAME_TOPIC (token overlap), DERIVED_FROM (similar Q different A), SUPERSEDES (chain-based)
   - **Gap**: 0 edges exist despite 2,727 atoms, meaning the builder was never run

3. **Macro-Atom Synthesis** (464 lines)
   - Union-find cluster detection via canonical question grouping + edge expansion
   - Both heuristic (no LLM) and LLM-assisted synthesis paths
   - Auto-creates DERIVED_FROM edges from summary to source atoms
   - **Gap**: No clusters found because no edges exist (chicken-and-egg with graph builder)

4. **Sandbox** (570 lines)
   - Full lifecycle: create → experiment → diff → merge_back → cleanup
   - Transactional bundle merge with per-atom SAVEPOINT
   - Conflict detection via content hash
   - Status reset on merge (forces re-promotion)
   - **Gap**: No sandbox directory, no `sandboxes.json`

5. **Evolution Queue + Executor** (330 + 239 lines)
   - Full approval workflow: draft → pending_approval → approved → executing → completed
   - Plan operations: create_atom, update_atom, promote, quarantine, supersede
   - Dry-run support, SAVEPOINT-wrapped execution, audit logging
   - **Gap**: No `evolution_queue.db`, no plans ever submitted

6. **Telemetry** (491 lines)
   - 3-table telemetry: query_events, retrieval_events, answer_feedback
   - 6 gap metrics: coverage, confidence margin, acceptance rate, miss rate, stale-hit rate, utilization
   - Frustration index per atom
   - Routing quality stats per domain/intent
   - **Gap**: Tables exist but 0 rows — retrieval pipeline doesn't call recorder

7. **Retrieval Pipeline** (`retrieval.py`, 394 lines)
   - FTS5 search → quality gate → groundedness filter → relevance scoring
   - Deduplication via chain-head preference
   - Scored atom ranking with quality × relevance weighting
   - **Gap**: Not invoked by the advisor router/context service

---

## What Codex Recently Fixed (Context for This Analysis)

Codex's recent work addressed two orthogonal P0 problems:

1. **KB Vector Persistence** (`hub.py`): Vectors were generated but lost because `index_document()` didn't call `_vec.save()`. Fixed by adding immediate persistence.

2. **Registry Quality Scoring** (`registry.py`): `register_file()` wasn't calling `compute_quality()`, so all registered artifacts had `quality_score=0.0`. Fixed by integrating quality computation.

3. **Memory Promotion via `stage_and_promote()`** (1B): Wired `source.role` into the memory stage flow and ensured dedup merge branches update source metadata.

These are KB-layer fixes, not EvoMap evolution-layer fixes. The EvoMap orchestration gap remains entirely unaddressed.

---

## The Critical Missing Piece: An Evolution Daemon

What's needed to activate the evolution pipeline:

```python
# Pseudo-code for ops/run_evomap_evolution.py

def run_evolution_cycle(db_path):
    """One complete evolution cycle."""
    db = KnowledgeDB(db_path)
    db.connect()
    
    # Phase 1: Structural preparation
    report_p1 = run_p1_migration(db)          # chain_builder.py — already works
    
    # Phase 2: Groundedness verification
    stats_p2 = run_p2_groundedness(db)        # groundedness_checker.py — never called
    
    # Phase 3: Graph building
    gb = GraphBuilder(db)
    stats_graph = gb.build_all()              # graph_builder.py — never called
    
    # Phase 4: Synthesis
    synth = MacroAtomSynthesizer(db)
    stats_synth = synth.run()                 # synthesis.py — never called
    
    # Phase 5: Telemetry reporting
    telemetry = TelemetryRecorder(db)
    telemetry.init_schema()
    gap_metrics = telemetry.get_gap_metrics()  # telemetry.py — never called
    
    db.close()
```

---

## Comparison with the OpenClaw "Desired Evolution Features"

| Feature | OpenClaw Vision | Current Status | Effectiveness |
|---------|----------------|----------------|---------------|
| **Knowledge self-curation** (auto-score, promote, demote) | Core design goal | Code exists, not running | ❌ 0% effective |
| **Groundedness verification** (verify claims against system state) | WP2 | Code exists, never ran | ❌ 0% effective |
| **Knowledge supersession** (newer replaces older on same topic) | WP1/P1 | ✅ Working (74 superseded) | ✅ ~80% effective |
| **Knowledge synthesis** (aggregate micro-atoms to macro-insights) | WP5 | Code exists, never ran | ❌ 0% effective |
| **Evolution planning** (coordinated knowledge changes with approval) | WP3 | Code exists, never used | ❌ 0% effective |
| **Sandbox experimentation** (test before committing to live) | WP6 | Code exists, never used | ❌ 0% effective |
| **Retrieval quality feedback loop** (learn from usage patterns) | Telemetry design | Code exists, 0 data | ❌ 0% effective |
| **Graph-based knowledge navigation** (traverse related knowledge) | WP4 | 0 edges, 0 entities | ❌ 0% effective |
| **Semantic memory promotion** (episodic → semantic via quality gates) | Memory system | ✅ Just landed (1B) | ⚠️ Just wired, needs validation |
| **Vector-enhanced retrieval** (embedding similarity search) | KB hybrid RAG | ✅ Just fixed (persistence) | ⚠️ Vectors persist but not integrated into EvoMap retrieval |

---

## Honest Assessment

**The code quality is genuinely good.** The modules are well-structured, properly isolated, have appropriate error handling, use SAVEPOINT transactions, and follow sound software engineering patterns. This is not a case of bad code — it's a case of excellent code that was never wired into a running system.

**The gap is entirely one of orchestration**, not implementation. If someone simply:
1. Creates an `ops/run_evomap_evolution.py` script
2. Sets up a systemd timer to run it periodically
3. Connects the EvoMap retrieval pipeline to the advisor's context service

...the entire evolution system would come online. The individual subsystems have been tested via unit tests and are ready. They just need a conductor.

**Estimated effort to activate:** 2-3 focused work sessions to:
- Write the evolution daemon script (~200 lines)
- Create the systemd timer
- Wire retrieval into the advisor context lookup
- Run the first full P2→Graph→Synthesis cycle on the 2,727 existing atoms
- Validate results and adjust thresholds

**Risk if activated blindly:** Low. The code has conservative defaults (groundedness threshold 0.7, min cluster size 3, TTL-based sandbox cleanup). The biggest risk is that graph builder token-overlap heuristics may create noisy SAME_TOPIC edges — but synthesis already filters by `min_avg_quality`.
