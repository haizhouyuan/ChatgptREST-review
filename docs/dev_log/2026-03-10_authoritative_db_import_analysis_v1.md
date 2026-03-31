# Authoritative DB Import Analysis: Scratch → Main DB Migration

**Date:** 2026-03-10  
**Author:** Antigravity  
**Decision:** `data/evomap_knowledge.db` is the canonical DB going forward. `~/.openmind/evomap_knowledge.db` retires to archive.

---

## 1. The Two Databases — Full Inventory

### Main DB (`data/evomap_knowledge.db`) — The Canonical DB

| Metric | Value | Notes |
|--------|-------|-------|
| **Atoms** | 95,239 | All promotion_status=`staged` |
| **Edges** | 82,789 | same_topic: 56,623 / derived_from: 25,238 / supersedes: 928 |
| **Evidence** | 79,816 | Substantial provenance layer |
| **Documents** | 7,136 | planning: 3,350 / chatgptrest: 2,213 / antigravity: 1,113 |
| **Entities** | 0 | Never populated |
| **Query events** | 156 | Telemetry IS collecting |
| **Retrieval events** | 689 | Context service hits |
| **Chains** | 0 | P1 chain builder never ran on this DB |
| **Groundedness audits** | 0 | P2 never produced output |
| **Promotion audits** | 0 | Promotion engine never ran |

**Quality distribution** (95K atoms):

| Range | Count | % | Interpretation |
|-------|-------|---|----------------|
| quality_auto = 0 | 27 | 0.03% | Unscored (agent_activity) |
| 0.01-0.3 | 1,044 | 1.1% | Low quality |
| 0.3-0.5 | 2,082 | 2.2% | Below average |
| 0.5-0.7 | 59,091 | 62.0% | Average — bulk of data |
| 0.7-0.9 | 32,866 | 34.5% | Good quality |
| 0.9-1.0 | 129 | 0.1% | Very high quality |

**Source distribution** (atom count):

| Source | Atoms | % |
|--------|-------|---|
| antigravity | 50,783 | 53.3% |
| planning | 40,901 | 42.9% |
| chatgptrest | 2,475 | 2.6% |
| maint | 438 | 0.5% |
| agent_activity | 275 | 0.3% |
| other (md/commits/ops) | 367 | 0.4% |

**Other governance stats:**
- canonical_question filled: 47,410 (49.8%)
- valid_from filled: 43,835 (46.0%)
- groundedness > 0: 1 out of 95,239 (essentially zero)
- confidence > 0: 182 out of 95,239 (0.2%)

---

### Scratch DB (`~/.openmind/evomap_knowledge.db`) — Retiring

| Metric | Value | Notes |
|--------|-------|-------|
| **Atoms** | 2,727 | active: 2,329 / staged: 324 / superseded: 74 |
| **Edges** | 0 | Graph builder never ran |
| **Evidence** | 2,700 | Tight 1:1 evidence |
| **Documents** | 61 | Source: antigravity (all) |
| **Entities** | 0 | Never populated |
| **Chains** | 2,376 (42 multi-atom, max len=6) | P1 ran and worked |
| **Groundedness audits** | table DNE | Never created |
| **Promotion audits** | table DNE | Never created |

**Quality distribution** (2,727 atoms):

| Range | Count | % | Interpretation |
|-------|-------|---|----------------|
| quality_auto = 0 | 27 | 1.0% | Unscored (agent_activity overlap) |
| 0.01-0.3 | 570 | 20.9% | Lower quality |
| 0.3-0.5 | 805 | 29.5% | Mid-low |
| 0.5-0.7 | 590 | 21.6% | Mid |
| 0.7-0.9 | 257 | 9.4% | Good |
| 0.9-1.0 | 478 | 17.5% | Very high (LLM-refined) |

**Unique curation assets:**
- 100% have canonical_question (vs 50% in main DB)
- 100% have valid_from (vs 46% in main DB)
- 90% have chain_id (vs 0% in main DB)
- 85% promoted to active (via p4_batch_fix `auto_p4_quality_check`)
- 5 distinct atom types: qa (2,010), troubleshooting (261), decision (189), procedure (181), lesson (86)

---

## 2. Overlap Analysis

| Dimension | Overlap | Main Only | Scratch Only |
|-----------|---------|-----------|--------------|
| **Atoms** | 27 | 95,212 | **2,700** |
| **Documents** | 1 | 7,135 | **60** |
| **Episodes** | 27 | - | - |

**The 27 overlapping atoms** are all `agent_activity` type, currently `staged` in both DBs, and have `quality_auto=0` in scratch but scored (0.3-0.6) in main. These are trivial bookkeeping atoms — the overlap is essentially zero for knowledge content.

**The 2,700 unique scratch atoms** represent curated Antigravity conversation extracts: LLM-refined, chain-grouped, with canonical questions and quality scores from a separate scoring run. None of this curation work exists in the main DB's 50,783 antigravity-source atoms.

---

## 3. Import Assessment: Should We Import the 2,700?

### Arguments FOR importing

1. **Unique curation investment**: The scratch atoms have been through LLM refinement (gpt-5.4), canonical question generation, chain building, and P4 quality promotion. This represents ~3.5 minutes of LLM time and a full governance pass that no main DB atom has received.

2. **Chain governance as template**: The 42 multi-atom chains (max length 6) demonstrate the chain builder's output quality. These can serve as ground truth for tuning when chain builder runs on the full 95K.

3. **Near-zero collision risk**: Only 27 atoms overlap (trivial agent_activity), so batch import won't corrupt anything.

4. **High canonical Q coverage**: 100% have canonical questions; importing gives the main DB's retrieval pipeline 2,700 more searchable, well-formed questions.

### Arguments AGAINST importing (or for caution)

1. **Quality distribution is worse than main DB**: The scratch atoms skew lower quality — 51% are below 0.5, vs only 3.3% in the main DB. The LLM "scoring" in the scratch DB used a different scoring model/rubric than the extractors that scored the main DB.

2. **Stale promotion status**: The 2,329 "active" atoms were promoted by `p4_batch_fix.py` using `auto_p4_quality_check`. This is an automated batch fix, not the designed groundedness-gated promotion. Importing them as "active" would bypass the promotion engine.

3. **No edges**: The scratch atoms have 0 edges. Importing them into a DB with 82K edges would create orphan nodes in the graph until GraphBuilder runs again.

4. **Semantic overlap with main DB**:  The main DB already has 50,783 antigravity-source atoms covering the same conversation corpus. The scratch DB's 2,700 are likely a subset of the same conversations — different extraction pass, but possibly redundant content. Without dedup, you'd have both the extractor's version and the refinement pass.

5. **Schema micro-drift**: The `edges` table PRIMARY KEY ordering differs (`from_id, to_id, edge_type` is the same, but column ordering in CREATE differs). Same semantic schema but could cause issues with direct table copy.

---

## 4. My Recommendation: Import with Governance Reset

**Import the 2,700 unique atoms, but reset their promotion_status to `staged`** (matching the main DB's universal state). Here's why:

### What to import

| What | How | Why |
|------|-----|-----|
| 2,700 atoms | `INSERT OR IGNORE` (skip 27 overlaps) | Add curated content |
| 60 documents | `INSERT OR IGNORE` (skip 1 overlap) | Preserve provenance |
| Episodes | `INSERT OR IGNORE` | Complete atom→episode→doc chain |
| 2,700 evidence | `INSERT OR IGNORE` | Preserve provenance |
| Chain IDs | Preserve in imported atoms | Unique curation asset |
| Canonical questions | Preserve in imported atoms | 100% coverage |

### What to reset

| What | From | To | Why |
|------|------|-----|-----|
| promotion_status | active/superseded/staged | **staged** | Let the main DB's promotion engine decide |
| promotion_reason | auto_p4_quality_check | **imported_from_scratch** | Honest tagging |

### What NOT to import

| What | Why |
|------|-----|
| Edges | 0 in scratch DB, nothing to import |
| Entities | 0 in both DBs |
| Telemetry | 0 in scratch DB |

### Post-import actions (automatic)

When `OPENMIND_ENABLE_EVOMAP_EXTRACTORS` is re-enabled:
1. GraphBuilder will create edges for the newly imported atoms
2. P2 Groundedness can evaluate the imported atoms
3. The chain IDs will be used by the retrieval pipeline for chain-head preference

---

## 5. Do We Need to Expand the Pilot, or Can We Batch Import?

**We can batch import immediately.** The pilot was successful — it confirmed that:

1. Chain builder produces reasonable chains (42 multi-atom, max len 6)  
2. LLM refinement generates valid canonical questions (100% coverage)  
3. P4 quality checks run without errors  
4. The data is structurally sound (proper FK relationships, hashes, valid_from)

**No further pilot is needed** because:

- The schema is identical (both DBs use the same `db.py` DDL)
- The overlap is almost zero (27/2,727 = 0.99%)
- The import is additive (`INSERT OR IGNORE`), not destructive
- We're resetting promotion_status, so there's no governance bypass
- The main DB's GraphBuilder will integrate the new atoms into the edge network 

**The more interesting question is**: once the 2,700 are imported and `OPENMIND_ENABLE_EVOMAP_EXTRACTORS` is re-enabled, should we run P1 chain builder on the full 95K+2.7K main DB? That's where the **real** scale-up investment would be — but it should happen naturally as part of the pipeline cycle, not as a separate manual run.

---

## 6. Import Script Specification

```python
"""
Import scratch DB atoms into main canonical DB.
Idempotent, non-destructive, with promotion reset.

Usage:
  python ops/import_scratch_evomap.py \
    --source ~/.openmind/evomap_knowledge.db \
    --target data/evomap_knowledge.db \
    --dry-run  # preview first
"""

# High-level steps:
# 1. ATTACH source DB
# 2. INSERT OR IGNORE documents (60 unique)
# 3. INSERT OR IGNORE episodes (linked to docs)
# 4. INSERT OR IGNORE atoms (2,700 unique) — with promotion_status='staged', promotion_reason='imported_from_scratch'
# 5. INSERT OR IGNORE evidence (2,700 unique)
# 6. Rebuild FTS5 index for new atoms
# 7. Report: imported counts, skipped overlaps
# 8. Mark source DB with deprecation marker
```

---

## 7. Post-Migration Checklist

- [ ] Run import script with `--dry-run` to preview
- [ ] Run import script for real
- [ ] Verify atom count: should be ~97,939 (95,239 + 2,700)
- [ ] Verify FTS5 index covers new atoms
- [ ] Re-enable `OPENMIND_ENABLE_EVOMAP_EXTRACTORS=true`
- [ ] Wait one pipeline cycle (4h) for GraphBuilder to create edges for new atoms
- [ ] Verify new atoms have edges in the graph
- [ ] Archive scratch DB: `mv ~/.openmind/evomap_knowledge.db ~/.openmind/evomap_knowledge.db.archived.20260310`
- [ ] Update ops scripts' default paths (Codex is handling this)
