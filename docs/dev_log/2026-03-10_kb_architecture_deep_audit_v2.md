# KB Architecture Deep Audit — v2 (Corrected)

> v1 (`abdb3e3`) had 5 factual errors. This v2 corrects all 5 per independent code + production data verification.

## Corrections from v1

| v1 Claim | Reality | Evidence |
|----------|---------|----------|
| "Versioning is in-memory only" | ❌ Wrong. `hub.py:102` creates `*_versions.db`. `~/.openmind/kb_search_versions.db` has 89 versions / 87 docs | `ls -la ~/.openmind/kb_search_versions.db` |
| "fastembed not installed" | ❌ Wrong. `from fastembed import TextEmbedding` succeeds. Embedding works, dim=512 | Live test: `hub._get_embedder()` returns TextEmbedding |
| "Zero cross-referencing / zero shared IDs" | ❌ Overstated. Registry ↔ FTS: 43 shared `artifact_id`, 54 shared `source_path` | Direct DB join query |
| "811 docs = migrate_openclaw_kb.py's fault" | ❌ Oversimplified. Current migrate script (L123) passes `source_path`. 811 empty docs likely from an earlier version or different bulk import | Script code review |
| "No Chinese tokenization" | ❌ Too absolute. `unicode61` + `_prepare_fts_query()` CJK char splitting exists. Recall is weak, not zero | `retrieval.py:210-244` |

---

## Production Data (Verified Numbers)

### `kb_search.db`
- 903 docs total, 811 empty `source_path`, 92 with `source_path` — ✅ confirmed
- 413 tagged (45.7%) — ✅ after 1C backfill
- quality avg 0.763, content_type: 899 markdown — ✅
- **Vectors: 0** — ✅ but root cause is different from v1

### `kb_search_versions.db`
- 89 versions, 87 distinct docs — ✅ versioning IS active

### `kb_registry.db`
- 97 artifacts, **all quality_score=0**, **all stability='draft'** — ✅ governance fields never computed
- 43 artifact_ids overlap with FTS, 54 source_paths overlap

### `kb_vectors.db`
- exists but 0 vectors — ✅ vector store initialized, just never persisted

### `evomap_knowledge.db`
- 2,727 atoms / 61 docs / 239 episodes / 2,700 evidence — ✅
- **0 edges / 0 entities** — ✅ graph layer hollow
- 60 antigravity + 1 agent_activity docs (not "all from antigravity") — corrected

### `memory.db`
- 584 records: 445 episodic, 136 meta, 2 working, 1 staging — ✅
- **0 semantic** — ✅ promotion rules exist (`StagingGate`) but no runtime trigger for episodic→semantic

---

## True Root Causes

### Why 0 Vectors (P0)

The vector pipeline is **functional** — fastembed loads, embeddings compute (dim=512), `NumpyVectorStore` accepts `add()`. The failure is:

1. `hub.index_document()` calls `self._vec.add()` — this **only adds to in-memory numpy array**
2. `NumpyVectorStore.save()` writes the in-memory array to SQLite — but **`index_document()` never calls `save()`**
3. `hub.save()` exists (L393) but is never called from the `_on_artifact_registered()` callback
4. `hub.close()` (L403) calls `_vec.close()` which does `save()` — but only if `_dirty=True` and the process does a clean shutdown
5. **Result**: vectors go into memory, but are lost because nobody flushes them to disk between `add()` and process exit

**Fix**: Either (a) call `self._vec.save()` inside `index_document()` after batch add, or (b) add periodic flush in runtime, or (c) batch-save on graceful shutdown.

### Why Registry Governance Is Inert (P0)

- `ArtifactRegistry` has full `compute_quality()` (L580-L620) and `transition_stability()` (L630-L680) code
- But **no runtime caller** invokes these. `_on_artifact_registered()` only calls `hub.index_document()`
- Only `scanner.py:181-189` calls `update_quality()` — but scanner never runs in production
- **Result**: 97 artifacts, all quality=0, all stability=draft

### Why 0 Semantic Memory

- `StagingGate.can_promote()` to semantic requires `min_confidence >= 0.65` AND `min_occurrences >= 2`
- `promote()` and `stage_and_promote()` both work
- But the only callers target `episodic` or `meta` tier — nobody calls `promote(record_id, MemoryTier.SEMANTIC)`
- **Missing**: a periodic consolidation job that finds repeated episodic patterns and promotes to semantic

### Why 0 Evomap Edges/Entities

- `graph_builder.py` (12KB), `relations.py` (8KB), `chain_builder.py` (10KB) exist with full entity/edge extraction
- But these require LLM calls or explicit orchestration runs
- The `activity_ingest.py` ingests conversations → atoms/episodes/evidence, but **never calls graph_builder**
- **Missing**: an orchestration step that runs `graph_builder.extract_entities()` + `graph_builder.build_edges()` after atom ingestion

---

## The Real Architecture Gap: No Orchestration Runner

The pattern across all 4 problems is identical: **the subsystem code exists, but nobody calls it**.

```
                    ┌─ Vector save() ────── exists, no caller
                    ├─ Quality scoring ──── exists, no caller  
Advisor Runtime ────┤
                    ├─ Semantic promotion ─ exists, no caller
                    └─ Graph building ───── exists, no caller
```

What's missing is an **orchestration layer** — something like a periodic maintenance job or a post-request hook chain that triggers these subsystems. The individual components are well-designed; the wiring is incomplete.

---

## Comprehensive System Design: Agent-Facing Knowledge + Memory + Evolution

### Objective

Build a unified agent evolution system where:
1. **Every agent interaction automatically captures knowledge** (future data)
2. **Existing 903+2727+584 records are properly connected and made searchable** (existing data)
3. **Knowledge evolves through quality gates** (not just accumulates)
4. **Agents can recall with context-aware filtering** (not just keyword match)

### Architecture

```
                               ┌─────────────────────────┐
                               │   Agent Runtime Shell    │
                               │ (advisor/graph/report)   │
                               └──────────┬──────────────┘
                                          │ interactions
                                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Ingestion Pipeline                             │
│                                                                  │
│  ┌─────────────┐   ┌──────────────┐   ┌────────────────────┐    │
│  │ ActivityHook │   │ WritbackSvc  │   │ Scanner (periodic) │    │
│  │ (auto-cap)   │   │ (LLM output) │   │ (filesystem crawl) │    │
│  └──────┬──────┘   └──────┬───────┘   └────────┬───────────┘    │
│         │                  │                     │                │
│         └──────────────────┼─────────────────────┘                │
│                            ▼                                      │
│  ┌──────────────────────────────────────────────────────┐        │
│  │              Unified Indexer                          │        │
│  │  1. FTS5 index (retrieval.py)                        │        │
│  │  2. Vector embed + FLUSH (hub.py + fix)              │        │
│  │  3. Registry register + quality score (registry.py)  │        │
│  │  4. Version snapshot (versioning.py)                 │        │
│  │  5. EvoMap atom extract (activity_ingest.py)         │        │
│  └──────────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Evolution Pipeline (periodic)                  │
│                                                                  │
│  Phase A: Consolidation                                          │
│    - Memory: episodic → semantic promotion (StagingGate rules)   │
│    - KB: quality rescoring (registry.compute_quality)             │
│    - KB: stability lifecycle (draft → candidate → approved)      │
│    - Atoms: groundedness checker → promotion engine               │
│                                                                  │
│  Phase B: Graph Building                                         │
│    - Entity extraction from atoms (graph_builder)                │
│    - Edge building (contradicts/supersedes/supports/derives)     │
│    - Chain building (chain_builder)                              │
│    - Synthesis (synthesis.py → new atoms from patterns)          │
│                                                                  │
│  Phase C: Cross-Store Linking                                    │
│    - KB doc ↔ atom linking (shared artifact_id or content hash)  │
│    - Memory record ↔ KB doc linking (fingerprint → doc match)    │
│    - Vector index rebuild (periodic full re-embed)               │
└──────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Retrieval Layer                                │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐      │
│  │ FTS5 + Vec  │  │ Atom Search  │  │ Memory Recall      │      │
│  │ (hub.search)│  │ (evo/retr.)  │  │ (mm.recall)        │      │
│  └──────┬──────┘  └──────┬───────┘  └────────┬───────────┘      │
│         │                │                     │                  │
│         └────────────────┼─────────────────────┘                  │
│                          ▼                                        │
│          ┌───────────────────────────────────┐                   │
│          │  Context Assembler (unified RRF)  │                   │
│          │  - tag/role filtering             │                   │
│          │  - quality gating                 │                   │
│          │  - token budget management        │                   │
│          └───────────────────────────────────┘                   │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation Phases

#### Phase 1: Fix the Plumbing (immediate, no design changes)

**1A. Vector persistence fix** — 1 line change
```python
# hub.py index_document(), after the vec.add() loop:
if self._vec and self._vec._dirty:
    self._vec.save()
```

**1B. Vector backfill script** — new script
```python
# scripts/backfill_kb_vectors.py
# Re-embed all 903 FTS docs into kb_vectors.db
# Batch size 50, progress bar, can resume
```

**1C. Registry quality scoring activation** — wire in runtime
```python
# In _on_artifact_registered():
#   After hub.index_document(), call:
#   kb_reg.compute_quality(artifact)
#   kb_reg.transition_stability(artifact, 'candidate')  # if quality > threshold
```

#### Phase 2: Evolution Daemon (new, periodic runner)

A lightweight daemon/timer that runs every N hours:

```python
# ops/kb_evolution_daemon.py
class KBEvolutionDaemon:
    def run_cycle(self):
        # Phase A: Memory consolidation
        self._promote_mature_episodic()   # episodic → semantic
        
        # Phase B: KB governance
        self._rescore_quality()           # registry.compute_quality for all
        self._advance_stability()         # draft → candidate if quality > 0.7
        
        # Phase C: Evomap graph building
        self._extract_entities()          # graph_builder on new atoms
        self._build_edges()               # relations between atoms
        self._run_groundedness()          # verify factual claims
        
        # Phase D: Cross-store linking
        self._link_atoms_to_fts()         # map atom.doc_id ↔ fts doc
        self._link_memory_to_atoms()      # merge episodic → atoms
```

#### Phase 3: Existing Data Ingestion

**3A. Backfill source_paths** for 811 legacy docs
- Reverse-map: match title/content against filesystem (`~/.openmind/kb/` and OpenClaw workspace)
- For unmatched: mark as `orphan` stability, don't try to trace

**3B. Entity/edge extraction** on 2,727 atoms
- Use LLM (via existing `llm_bridge.py`) to extract entities from atom Q&A
- Build `contradicts`/`supersedes`/`supports` edges between atoms
- Run `groundedness_checker` on all `active` atoms

**3C. Memory → Semantic promotion sweep**
- Find episodic records with fingerprint count ≥ 2 and confidence ≥ 0.65
- Promote to semantic tier
- Cross-reference with KB docs by content similarity

#### Phase 4: Agent Evolution (OpenClaw EvoMap vision)

**4A. Auto-capture hook in advisor graph**
- After each `execute_*` node, auto-extract:
  - Q&A atom (from prompt + response)
  - Decision atom (from routing choice)
  - Lesson atom (from error recovery)
- Each atom tagged with `source.agent`, `source.role`, `source.session`

**4B. Periodic synthesis**
- `synthesis.py` already exists — run it monthly on active atoms
- Produces meta-atoms: "when asked about X, the agent consistently recommends Y"
- These become the agent's "evolved knowledge"

**4C. Quality feedback loop**
- Track which KB docs get retrieved and lead to good outcomes (user approval, no error)
- Feed back into quality_score: docs that help → score up, docs that mislead → score down
- This closes the evolution loop: capture → index → retrieve → evaluate → re-score

### Existing Data Migration Priority

| Data Source | Count | Action | Priority |
|------------|-------|--------|----------|
| FTS docs (903) | 903 | Vector backfill, source_path recovery | P0 |
| Evomap atoms (2,727) | 2,727 | Entity extraction, edge building | P1 |
| Memory episodic (445) | 445 | Semantic promotion sweep | P1 |
| Registry artifacts (97) | 97 | Quality scoring, stability transition | P0 |
| kb_versions (89) | 89 | Already working, no action needed | N/A |

### Future Data Auto-Capture

All future agent interactions should automatically:
1. **Index to FTS + vector** via existing `_on_artifact_registered` (with save fix)
2. **Extract atoms** via `activity_ingest.py` (already wired for advisor flows)
3. **Register to registry** with quality scoring (Phase 1C wiring)
4. **Stage memory** via `stage_and_promote` (1B already fixed)
5. **Tag with source identity** (1B `source.role` already landed)
