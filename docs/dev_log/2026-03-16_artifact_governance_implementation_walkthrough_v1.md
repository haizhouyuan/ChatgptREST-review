# Walkthrough — Artifact Governance Full Implementation

## Summary

Implemented all phases of the artifact governance blueprint v2 in 7 commits. **72/72 tests pass (0.57s)**.

## Phase 0: Manifest Schema (`3698129`)

| File | Purpose |
|---|---|
| `docs/contracts/artifact-manifest-v1.schema.json` | JSON Schema 2020-12 with 5 required + 12 optional fields |
| `chatgptrest/governance/manifest.py` | `validate_manifest()` + `generate_job_manifest()` + CLI |
| `tests/test_governance_manifest.py` | 19 tests |

Verified against real job dir — generates valid manifest from `request.json`.

## Phase 1a: Batch Wrappers (`7a8a78c`)

| Operation | Wraps |
|---|---|
| `batch_kb_quality_rescore` | `ArtifactRegistry.update_quality()` |
| `batch_kb_stability_transition` | `ArtifactRegistry.transition_stability()` |
| `batch_kb_prune` | `KBPruner.run()` |
| `batch_memory_expire` | `MemoryManager.expire_records()` |
| `batch_memory_consolidate` | `MemoryManager.promote()` |
| `batch_retention_enforce` | File-system budget enforcement |

All default `dry_run=True`, JSONL audit. 19 tests.

## Phase 1b: Manifest Backfill (`55e82b6`)

`ops/manifest_backfill.py` — scans 7490 job dirs in 0.23s. Modes: `--count-only`, `--dry-run`, `--apply`, `--force`, `--limit`. 7 tests.

## Phase 2: Governance Daemon (`0c747ff`)

`ops/artifact_governance_daemon.py` — 6 independent stages:

1. **manifest_audit** — verify manifests exist + validate
2. **retention_enforce** — budget-driven archive
3. **kb_governance** — quality rescore + stability transition + prune
4. **memory_governance** — expire + consolidate
5. **review_governance** — overdue review detection
6. **promotion_check** — identify promotion-ready candidates

CLI: `--stage`, `--dry-run`/`--apply`, `--output-dir`. 15 tests.

## Phase 3: Controlled Promotion (`4522314`)

`chatgptrest/governance/promotion.py`:
- `PromotionGate` — quality ≥ 0.8, quarantine weight ≥ 0.7, candidate age ≥ 7d
- `promote_artifact()` — single check + apply with audit trail
- `batch_promote()` — scan all candidates
- CLI: `check` / `batch` subcommands

12 tests.

## Commits

| Hash | Description |
|---|---|
| `cfd6eee` | docs: blueprint v2 + review |
| `3698129` | feat: Phase 0 — manifest schema |
| `7a8a78c` | feat: Phase 1a — batch wrappers |
| `55e82b6` | feat: Phase 1b — manifest backfill |
| `0c747ff` | feat: Phase 2 — governance daemon |
| `4522314` | feat: Phase 3 — controlled promotion |
