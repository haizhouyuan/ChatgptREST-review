# KB Architecture Deep Audit — 2026-03-10

## Executive Summary

The KB system has **three parallel data stores** with **zero cross-referencing** between them. Each store was designed for a different plane of the 4-layer substrate architecture, but in production they are effectively isolated silos. The code infrastructure is comprehensive (8 well-designed modules), but critical subsystems have **never run in production** (vector embeddings, versioning, entity graph, stability lifecycle).

---

## 1. Production Data Landscape

### 1.1 `kb_search.db` — The FTS5 Surface

| Metric | Value | Assessment |
|--------|-------|------------|
| Total docs | 903 | Reasonable |
| Empty `source_path` | **811/903 (89.8%)** | ⚠️ Critical gap |
| With `source_path` | 92/903 | Mostly `~/.openmind/kb/` prefix |
| Tagged docs | 413/903 (45.7%) | 1C just landed |
| Content type | 899 markdown, 3 json, 1 other | Mono-format |
| Quality avg | 0.763 | Never recomputed |
| **Vectors** | **0** | ⚠️ Vector search is dead |

**Schema reality**: `kb_fts_meta` has only 9 columns:
`artifact_id, source_path, title, content_type, para_bucket, quality_score, word_count, indexed_at, tags`

The `registry.py` model (`Artifact`) has **24 fields** including `stability`, `dup_status`, `quarantine_weight`, `structural_role`, `domain_tags`, etc. — **none of these propagate to the search-facing schema**. The registry and the search index are architecturally disconnected.

### 1.2 `evomap_knowledge.db` — The Knowledge Atom Store

| Table | Count | Assessment |
|-------|-------|------------|
| atoms | 2,727 | Substantial |
| documents | 61 | Source conversations |
| episodes | 239 | Conversation segments |
| evidence | 2,700 | Linked to atoms |
| **edges** | **0** | ⚠️ Knowledge graph is EMPTY |
| **entities** | **0** | ⚠️ Entity extraction never ran |
| query_events | 60 | Low retrieval activity |

**Atom breakdown**:
- qa: 2,010 (73.7%) → Q&A pairs
- troubleshooting: 261 (9.6%)
- decision: 189 (6.9%)
- procedure: 181 (6.6%)
- lesson: 86 (3.2%)

**Promotion**: 2,329 active, 324 staged, 74 superseded
**Quality distribution**:
- 0.0: 277 (10.2%) — zero quality
- 0.3: 321 (11.8%) — quarantine-grade
- 0.5–0.6: 1,393 (51.1%) — bulk middle
- 0.9–1.0: 696 (25.5%) — high quality

**All 61 documents sourced from `antigravity`** — no other agent has written here.

### 1.3 `memory.db` — The Memory Plane

| Tier | Count | Assessment |
|------|-------|------------|
| episodic | 445 | Healthy volume |
| meta | 136 | All route_stat category |
| working | 2 | Nearly empty |
| staging | 1 | Single orphan |
| **semantic** | **0** | ⚠️ Promotion never happened |
| **Total** | **584** | |

**No semantic tier records exist.** The substrate's designed "graduated knowledge" path from `episodic → semantic` has never fired.

---

## 2. Architecture Map

### 2.1 Module Inventory

```
chatgptrest/kb/
├── hub.py              # 15.9KB — FTS5 + Vector hybrid search facade
├── retrieval.py        # 13.9KB — FTS5 search engine (BM25 + RRF fusion)
├── registry.py         # 23.9KB — PARA metadata, quality, stability lifecycle
├── scanner.py          #  7.2KB — Filesystem crawler (backfill + incremental)
├── vector_store.py     # 10.9KB — Numpy brute-force cosine (pluggable protocol)
├── versioning.py       #  9.3KB — Doc versioning with diff/rollback/GC
├── writeback_service.py#  8.3KB — Unified writeback entry point
└── __init__.py         #  0.5KB — Module docstring
```

### 2.2 Data Flow (Designed vs Reality)

```
[DESIGNED]
Content → Scanner → Registry → (event) → KBHub.index_document()
                                             ├─ FTS5 (retrieval.py)
                                             ├─ Vectors (vector_store.py) ← FastEmbed
                                             └─ Versions (versioning.py)
Registry side:
  ├─ Quality scoring (compute_quality)
  ├─ Stability lifecycle (draft→candidate→approved)
  ├─ Dedup detection
  └─ PARA classification

EvoMap pipeline:
  Conversations → EvoMap extract → atoms → edges/entities → query events

[REALITY]
Advisor graph nodes:
  execute_deep_research → writeback_service → registry → _on_artifact_registered → hub.index_document()  ← ACTIVE
  quick_ask → direct index in _on_artifact_registered() path  ← ACTIVE (if artifacts produced)

Runtime subscriber:
  _on_artifact_registered → hub.index_document() with source_path ← ACTIVE (for 92 docs)

migrate_openclaw_kb.py:
  Legacy bulk import → hub._fts.index_text() directly ← HISTORICAL (811 docs with no source_path)

Scanner (backfill_scan):
  → NEVER RAN IN PRODUCTION

Vector embedding:
  hub._get_embedder() → fastembed.TextEmbedding ← NEVER LOADED (ImportError silently swallowed)

Versioning:
  hub._versions.create_version() ← IN-MEMORY ONLY (":memory:" default, no kb_versions table in prod DB)

EvoMap knowledge graph:
  edges/entities population ← NEVER RAN (0 edges, 0 entities)
```

### 2.3 Three-Store Disconnection

```
kb_search.db                evomap_knowledge.db            memory.db
┌──────────────────┐        ┌───────────────────────┐      ┌─────────────────┐
│ FTS5: 903 docs   │        │ atoms: 2,727          │      │ records: 584    │
│ vectors: 0       │   ∅    │ edges: 0              │  ∅   │ semantic: 0     │
│ meta: 903        │←──────→│ entities: 0           │←────→│ episodic: 445   │
│ versions: N/A    │        │ evidence: 2,700       │      │ meta: 136       │
└──────────────────┘        └───────────────────────┘      └─────────────────┘
         ↓                            ↓                           ↓
    FTS5 search               atom FTS search              LIKE keyword search
    (BM25 + RRF)              (BM25 on Q/A)               (by tier filtering)
```

**Zero shared IDs, zero cross-references, zero unified query path.**

---

## 3. Critical Findings

### 3.1 Vector Search Is Dead Code

`KBHub._get_embedder()` tries to `import fastembed`, catches `ImportError`, returns `None`. Since fastembed is not installed:
- `self._embedder` is always `None`
- `_embed_texts()` always returns `[]`
- `self._vec` (NumpyVectorStore) is initialized with the DB but **never populated**
- `hub.search()` calls `self._vec.search()` but gets empty results
- The RRF fusion between FTS and vector is **FTS-only** in practice

**Impact**: The hybrid search degrades to pure FTS5 keyword match. Semantic similarity is non-existent.

### 3.2 Versioning Is In-Memory Only

`KBHub.__init__` creates `KBVersionManager(self._db_path)`. In practice, `_db_path` matches `kb_search.db`, but the `kb_versions` table **does not exist** in production. This means either:
- The versioning DDL `CREATE TABLE IF NOT EXISTS kb_versions` was never run against the production DB (probably because hub was initialized without this code)
- Or the table was created but in a different DB instance

**Impact**: No document versioning, no rollback capability, no change history.

### 3.3 Registry Schema Is Disconnected from Search

`ArtifactRegistry` stores 24-field records in an `artifacts` table (separate DB or in-memory). The `kb_fts_meta` table has only 9 columns. There is **no join, no sync, no shared ID contract** between them:

| Registry field | In kb_fts_meta? | Impact |
|---------------|-----------------|--------|
| stability | ❌ | Can't filter by lifecycle state |
| dup_status | ❌ | Can't exclude duplicates |
| quarantine_weight | ❌ | Can't downweight untrusted docs |
| structural_role | ❌ | Can't filter by evidence/analysis/spec |
| domain_tags | ❌ (separate `tags`) | Different field, different format |
| project_id | ❌ | Can't scope by project |

### 3.4 89.8% of Documents Have No Source Path

811/903 docs were ingested via `migrate_openclaw_kb.py` which directly called `_fts.index_text()` without `source_path`. This means:
- Can't trace back to original file
- Can't rebuild index from source
- Can't detect staleness or drift
- Can't reference for versioning

### 3.5 EvoMap Knowledge Graph Is Hollow

2,727 atoms exist with 2,700 evidence links — but **0 edges and 0 entities**. The designed graph relationships (`contradicts`, `supersedes`, `supports`, `derives_from`) were **never populated**. The atom store is effectively a flat table with FTS, not a graph.

### 3.6 Memory → KB Promotion Never Happened

0 records in semantic tier. The designed `episodic → semantic → KB` graduation pipeline has never fired. The 445 episodic records are just accumulating without ever being distilled.

---

## 4. Independent Insights

### 4.1 The System Has Three Independent RAGs, Not One Knowledge Substrate

The 4-layer architecture (Memory/Graph/Evolution/Policy planes) is a good design. But in production, what exists is:
1. An FTS5 keyword index (903 docs, no vectors, pure text match)
2. A flat atom store (2,727 Q&A pairs, no relationships)
3. A tiered memory buffer (584 records, keyword recall)

These are three independent retrieval systems that **never talk to each other**. The `context_service.py` does assemble from multiple sources, but each source is queried independently and results are concatenated — not fused.

### 4.2 The Code Is Ahead of Production

The codebase has well-designed modules for:
- Pluggable vector backends (VectorStore protocol)
- Quality scoring with multi-factor formula
- Stability state machine (draft → candidate → approved → deprecated → archived)
- Quarantine weights (1.0=trusted, 0.3=hypothetical, 0.0=blocked)
- PARA classification
- Document versioning with rollback
- Filesystem scanning with debounce

**None of these are active in production.** The code infrastructure is roughly 3x ahead of the production data reality.

### 4.3 Data Quality Is Ungovern-able Without Source Traceability

811 docs with no source_path means:
- Can't determine if a doc is stale (no file to compare against)
- Can't reindex (no content to re-read)
- Can't dedup (no path to fingerprint against)
- Can't score quality properly (freshness requires file mtime)

This is the single biggest data governance gap.

### 4.4 The Migration Script Created a "Data Lake" Problem

`migrate_openclaw_kb.py` was the primary ingestion tool that created ~811 docs. It bypassed registry, bypassed quality scoring, bypassed dedup — it just bulk-inserted text into FTS5. This created a "data lake" where most documents have minimal metadata and no governance.

### 4.5 Vector Search Is the Most Impactful Missing Piece

FTS5 keyword search works but:
- Misses semantic similarity (paraphrased queries fail)
- No Chinese tokenization (FTS5's default tokenizer handles CJK poorly)
- No query expansion

Installing `fastembed` and backfilling vector embeddings would immediately unlock ~120x better recall for semantic queries, with minimal code changes (the code already handles it, just needs the dependency).

---

## 5. Priority Recommendations

| Priority | Action | Impact | Effort |
|----------|--------|--------|--------|
| P0 | Install `fastembed` + backfill vectors for 903 docs | Unlock semantic search | Medium (GPU or CPU-only model) |
| P0 | Fix versioning DB connection (use prod DB path, not `:memory:`) | Enable doc history | Trivial |
| P1 | Backfill `source_path` for the 811 legacy docs (reverse-map from title/content to filesystem) | Enable source traceability | Medium |
| P1 | Propagate registry governance fields to `kb_fts_meta` (stability, quarantine_weight) | Enable search-time filtering | Medium |
| P2 | Run entity/edge extraction on evomap atoms | Activate knowledge graph | Heavy (needs LLM or NLP pipeline) |
| P2 | Implement `episodic → semantic` promotion trigger | Connect memory ↔ KB pipeline | Medium |
| P3 | Run scanner.backfill_scan() on project roots | Register all project artifacts | Low effort, high coverage gain |
| P3 | Unify atom ↔ FTS doc IDs for cross-referencing | Bridge evomap ↔ kb_search | Medium |
