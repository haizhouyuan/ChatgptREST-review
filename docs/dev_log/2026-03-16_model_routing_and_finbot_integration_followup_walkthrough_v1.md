# 2026-03-16 Model Routing And Finbot Integration Follow-up Walkthrough v1

## Scope

This follow-up covered two tracks:

1. verify the antigravity-delivered model routing governance document was actually merged to `master`
2. tighten ChatgptREST-local finbot integration coverage so the repo has a real service-level bridge from finbot artifacts into `DashboardService`

## What I Verified

### Model routing blueprint merge state

- antigravity recorded commit `658da00` (`Add routing and key governance blueprint`)
- that commit existed locally on `feature/finbot-phase6-8`
- it was **not** present on current `master` when this follow-up started
- the document file `docs/2026-03-16_model_routing_and_key_governance_blueprint_v1.md` was therefore missing from the working tree on `master`

### Current worktree reality

The walkthrough claim that only `.codex_tmp/` and `.worktrees/` remained untracked did not match current repo state at review time. Additional untracked knowledge artifacts and `tests/test_openclaw_maintagent_integration.py` were already present before my edits, so I left them untouched.

### Gemini CLI availability

I attempted to use Gemini CLI in two ways:

- via the `gemini_cli` MCP wrapper
- via local shell command with `HOME=/home/yuanhaizhou`

Both paths stopped at Google OAuth authorization instead of producing output. Result: Gemini CLI was **not usable** for this task in the current environment, and I did not treat it as a successful generator run.

## Changes Made

### 1. Merged the missing routing blueprint

- cherry-picked `658da00` onto `master`
- resulting commit on `master`: `07a3bcb` (`Add routing and key governance blueprint`)

### 2. Fixed stale finbot tests

`chatgptrest.finbot.daily_work()` now defaults `include_market_discovery=True`. Two existing tests in `tests/test_finbot.py` had not been updated for that behavior, so they could hang on external discovery execution.

I updated those tests to pass `include_market_discovery=False`, keeping the test scope limited to refresh/watchlist/radar composition without changing production defaults.

### 3. Added real finbot -> dashboard service integration coverage

Added `tests/test_finbot_dashboard_service_integration.py` with one high-signal service-level test that:

- generates a real finbot research package artifact through `finbot.opportunity_deepen(...)` with stubbed lanes
- points `DashboardService` at the generated local artifact root
- verifies `investor_snapshot()`, `investor_theme_detail()`, `investor_opportunity_detail()`, and `investor_source_detail()` consume the generated package, citation register, claim support map, and score history correctly

This closes the gap where the repo previously had:

- finbot artifact writer tests
- dashboard route/template tests

but no test that exercised the actual service-layer handoff between them.

## Validation

Passed:

- `./.venv/bin/pytest -q tests/test_rebuild_openclaw_openmind_stack.py tests/test_llm_connector.py`
- `./.venv/bin/pytest -q tests/test_finbot.py tests/test_finbot_dashboard_service_integration.py`
- `./.venv/bin/pytest -q tests/test_dashboard_routes.py`

## Outcome

- the model routing governance blueprint is now actually present on `master`
- the stale `daily_work` tests no longer hang on market discovery
- ChatgptREST now has a repo-local finbot service integration test that validates the artifact-to-dashboard path instead of only testing each side in isolation
