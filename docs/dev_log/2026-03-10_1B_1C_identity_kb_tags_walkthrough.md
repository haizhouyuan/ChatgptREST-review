# 2026-03-10 Phase 1B + 1C Walkthrough

## Commits

- `9981eca`: fix: replace broken `.store()` calls with `stage_and_promote()`
- `527b678`: feat(1C): KB tag governance — schema, search, backfill

## 1B: Identity Audit Fix

### Bug: `MemoryManager` has no `.store()` method

3 production callers were silently failing (AttributeError swallowed by try/except):

| File | Line | What | Impact |
|------|------|------|--------|
| `graph.py` | 848,854 | quick_ask user/assistant turns | Never written to working memory |
| `runtime.py` | 481 | EventBus → Memory mirror | Dead code path |

### Fix

`.store(MemoryRecord(..., tier=T))` → `.stage_and_promote(MemoryRecord(...), T, reason)`.

This also activates 1A's `source.role` auto-inject for these paths.

## 1C: KB Tag Governance

### Schema Changes (`retrieval.py`)

- `tags TEXT NOT NULL DEFAULT ''` added to `kb_fts_meta`
- Migration: `ALTER TABLE ADD COLUMN` with graceful fallback
- `search()`: new `tags` param with OR-logic LIKE filtering

### Backfill (`scripts/backfill_kb_tags.py`)

Heuristic tagger with controlled vocabulary from `agent_roles.yaml`:

```
Total docs:      903
Tagged:          413 (45.7%)
Tag distribution:
  analysis: 215    research: 136   finagent: 102
  chatgptrest: 82  ops: 36         market: 25
  driver: 18       runbook: 17     mcp: 16
  infra: 12        education: 10
```

### Advisory Logging (`hub.py`)

`index_document()` logs INFO when docs indexed without tags. Fail-open.

## Verification

- Full test suite: all pass
- Backfill: dry-run + live verified
- GitNexus detect_changes: affected processes only Advisor flows (expected)
