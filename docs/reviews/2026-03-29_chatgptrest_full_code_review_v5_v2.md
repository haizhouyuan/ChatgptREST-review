# 2026-03-29 ChatgptREST Full Code Review v5 v2

> Supersedes freshness of `2026-03-29_chatgptrest_full_code_review_v5_v1.md`
> Reviewed code baseline: `HEAD=78162ca`
> Freshness assessed at: `2026-03-29T16:37:51+08:00`
> Applicability window: valid until a later review or a code change touching `routes_agent_v3.py`, `routes_jobs.py`, `job_store.py`, `prompt_policy.py`, `dashboard/service.py`, `finbot.py`, `observability/__init__.py`, or `pyproject.toml`

## 1. What Changed Since v1

This addendum records which v1 findings were fixed immediately after the review and which remain open.

### Resolved after v1

- `CRITICAL-1` public `agent_v3` clarify regression
  - Fixed by commit `36d1036`
  - `scenario_pack` payload on the public route now preserves the strategist-sensitive fields needed for clarify routing: `clarify_questions` and `watch_policy`
  - Regressions now pass:
    - `tests/test_agent_v3_route_work_sample_validation.py`
    - `tests/test_branch_coverage_validation.py`

- `HIGH-1` `/v1/jobs` prompt policy masking conversation/provider semantics
  - Fixed by commit `36d1036`
  - `create_job_route` now prevalidates web-ask thread/provider semantics before prompt policy
  - Regressions now pass:
    - `tests/test_conversation_url_kind_validation.py`
    - `tests/test_conversation_url_conflict.py`

- `MEDIUM-1` missing `PyYAML` dependency
  - Fixed by commit `78162ca`
  - `PyYAML>=6,<7` is now declared in `pyproject.toml`

- `MEDIUM-2` hard-coded `/vol1/...` paths in cited modules
  - Partially fixed by commit `78162ca`
  - Introduced `chatgptrest/core/path_resolver.py`
  - `dashboard/service.py`, `finbot.py`, and `observability/__init__.py` now resolve environment- and workspace-aware paths through a shared helper instead of embedding host-specific absolute paths inline

### Still Open After v2

- `MEDIUM-3` config access remains highly distributed (`os.environ.get` / `os.getenv` sprawl)
- `MEDIUM-4` several orchestration-heavy entrypoints remain monolithic
- `DOC-1` evidence plane is now indexed, but not physically reduced or moved out of the repo
- GitNexus freshness still needs ongoing maintenance outside this review snapshot

## 2. Current Judgment

`master` is no longer blocked by the two public-surface regressions that justified v1's P0 callout.

The repository still has medium-priority governance and maintainability debt, but the immediate northbound behavior regressions are no longer outstanding on the reviewed baseline.

## 3. Current Supporting Artifacts

- Original review: `docs/reviews/2026-03-29_chatgptrest_full_code_review_v5_v1.md`
- Evidence plane index: `docs/dev_log/artifacts/INDEX_v1.md`
- Evidence plane manifest: `docs/dev_log/artifacts/manifest_v1.json`

## 4. One-Line Conclusion

> v1 correctly identified real regressions; v2 records that the public clarify gate, `/v1/jobs` semantic error surface, and missing `PyYAML` declaration have now been repaired on `HEAD=78162ca`, while config consolidation and monolith reduction remain follow-up work.
