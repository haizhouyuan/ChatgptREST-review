# PR #199 Review: Finbot Investor Dashboard

**Branch**: `codex/finbot-runtime-deploy-20260316` (head `83562ae`)  
**Reviewer**: Antigravity  
**Verdict**: ✅ **Conditional Merge** — restore 7 deleted test files first

## PR Scope

| Category | Stats |
|----------|-------|
| Files changed | 492 |
| Lines added | +19,802 |
| Lines deleted | −43,253 |
| New files | 241+ |
| Deleted files | 241 |
| Commits | 30 |

> [!WARNING]
> This is not a focused finbot PR. It bundles finbot features with massive codebase cleanup (variant removal, test consolidation, dead code removal). The finbot changes alone are ~5000 lines.

## What's Good ✅

### Finbot Runtime (`finbot.py` — 2668 lines, 97 functions)
- Clean orchestrator: manages finagent scripts, inbox items, themes, opportunities, dossiers
- Schema versioning (DOSSIER 3.0, SOURCE_SCORE 2.0, THEME_STATE 2.0) is solid
- Claim/citation objects, source scoring, thesis-opportunity evolution — real data model
- `daily_work()` composes watchlist + radar + themes + source refresh cleanly

### Dashboard Service (`service.py` — 2178 lines, 92 functions)
- Investor-grade data layer: `investor_snapshot()`, `investor_opportunity_detail()`, `investor_theme_detail()`, `investor_source_detail()`
- Expression tradability labels, conviction bottleneck detection, semantic delta
- Source role classification (originator/corroborator/amplifier)

### Investor Templates
- `investor.html` (332 lines): Hero metrics, One Sheet, Research Coverage Table, Latest Updates
- `investor_opportunity_detail.html` (511 lines): Epistemic Tear-Sheet with claim ledger, citation register
- `investor_theme_detail.html` (289 lines): Research Progress, Theme Source Map, Timeline
- `investor_source_detail.html` (156 lines): Source role, score timeline, keep/downgrade decision

### Tests
- `test_finbot.py` (570 lines): Covers inbox, watchlist, themes, dossiers, source scoring, claim/citation objects
- `test_dashboard_routes.py` rewritten (1247 lines → focused investor routes)
- `test_coding_plan_executor.py` (56 lines, new): Covers MiniMax API lane
- **151/151 targeted tests pass**

## Critical Issue ❌

### 7 Test Files Deleted — Covering Our Recent Fixes

| Deleted Test | What It Covered |
|-------------|----------------|
| `test_browser_runtime_executor_retry.py` | **F-04** (idempotent send guard) |
| `test_base_wait_daemon_thread.py` | **F-11** (daemon thread semaphore) |
| `test_memory_governance_api.py` | **F-06** (BEGIN IMMEDIATE), **F-08** (category dedupe), **F-15** (TTL filter) |
| `test_memory_governance_service.py` | Memory lifecycle tests |
| `test_feishu_api_client.py` | **F-09** (Feishu auth alignment) |
| `test_queue_health.py` | Queue health monitoring |
| `test_ui_canary_sidecar.py` | UI canary monitoring |

Also reduced: `test_advisor_graph.py` (29→24 test functions)

> [!CAUTION]
> Merging this PR as-is eliminates regression coverage for all dual-model review fixes (F-04/F-06/F-08/F-09/F-11/F-15). These are security-adjacent fixes (race conditions, duplicate prompts, information leakage) that MUST retain test coverage.

## Merge Conditions

1. **Restore 7 deleted test files** or prove equivalent coverage exists elsewhere in the PR branch
2. Verify `test_advisor_graph.py` still covers F-01/F-21 with the 5 dropped tests

## My Independent Assessment

Codex's claim that this "crosses the line from analyst notebook to investor operating system" is **substantiated**:
- Epistemic Tear-Sheet is a real investor artifact (semantic delta, kill box, conviction bottleneck)
- Source role distinction (originator vs amplifier) is genuinely novel for automated research
- Theme evolution timeline provides actionable signal

The finbot code quality is high — clean data models, proper schema versioning, error handling. The dashboard templates are well-structured with clear investor semantics.

**But**: the test coverage regression is a blocking issue. We just spent an entire session building F-04/F-06/F-08/F-11/F-15/F-21 and their tests. Deleting those tests without migration is unacceptable.
