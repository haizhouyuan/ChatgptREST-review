# Investor Dashboard And Finbot Quality Walkthrough v1

> Date: 2026-03-16
> Branch: `codex/finbot-runtime-deploy-20260316`
> Focus: make finbot output investor-consumable instead of scout-only

## What Was Wrong

Before this pass, the live system had four obvious quality problems:

1. `finbot` was writing duplicate radar/watchlist items because historical digest-suffixed item ids were still alive in pending inbox.
2. `theme-radar-scout` surfaced opportunity candidates, but did not generate an explicit deepening brief that tells a human what to do next.
3. Investor dashboard detail pages were misaligned with the real `finagent` run docs. Themes like `transformer` and `ai_energy_onsite_power` showed empty `recommended_posture` / `best_expression`.
4. Investor pages still read finbot inbox using an older schema, so the page showed empty `type/topic/thesis/next_action` fields even when the underlying inbox item had useful content in nested payloads.

## What Changed

### 1. Finbot inbox became stable and coalesced

Code:

- `chatgptrest/finbot.py`

Changes:

- switched radar/watchlist/theme items to stable logical ids
- added deepening brief items for radar candidates
- taught `write_inbox_item()` to update existing items instead of creating a new digest row every run
- added `_coalesce_pending_duplicates()` to archive old pending items with the same logical target

Result:

- pending inbox now keeps one stable item per logical radar/watchlist object
- historical duplicates move to `artifacts/finbot/inbox/archived/`

### 2. Opportunity discovery now produces a human next step

Code:

- `chatgptrest/finbot.py`
- `chatgptrest/dashboard/service.py`

Changes:

- `theme_radar_scout()` now also emits a `deepening_brief`
- dashboard opportunity cards now merge:
  - radar candidate
  - related themes
  - suggested sources
  - brief summary
  - next proving milestone

Result:

- the investor surface now answers:
  - why this candidate surfaced
  - which existing theme should absorb it
  - which first-hand sources should be checked next

### 3. Investor dashboard is now aligned with real run docs

Code:

- `chatgptrest/dashboard/service.py`

Changes:

- `_parse_run_report_summary()` now supports the current markdown patterns used by `finagent` run docs:
  - `- recommended posture: ...`
  - `- best expression: ...`

Result:

- live theme cards now resolve:
  - `transformer -> watch_with_prepare_candidate / sntl_xidian_alt`
  - `ai_energy_onsite_power -> watch_with_prepare_candidate / sntl_gev_ai_power`
  - `commercial_space -> watch_only / sntl_rklb_space_systems`

### 4. Investor dashboard now has an opportunity detail page

Code:

- `chatgptrest/api/routes_dashboard.py`
- `chatgptrest/dashboard/templates/investor.html`
- `chatgptrest/dashboard/templates/investor_theme_detail.html`
- `chatgptrest/dashboard/templates/investor_opportunity_detail.html`

Changes:

- added:
  - `/v2/dashboard/api/investor/opportunities/{candidate_id}`
  - `/v2/dashboard/investor/opportunities/{candidate_id}`
- opportunity cards are now clickable
- theme detail page links related opportunities to opportunity detail page
- finbot inbox section now renders summary/category/next action correctly

Result:

- investor dashboard is no longer a raw operator dump
- it now behaves like a research desk surface:
  - current themes
  - best expression
  - opportunities
  - deepening brief
  - source links
  - document reader links

## Tests Run

Targeted tests:

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_finbot.py \
  tests/test_dashboard_routes.py \
  tests/test_executor_factory.py \
  tests/test_coding_plan_executor.py
```

Result:

- `18 passed`

## Live Smoke

### Finbot runtime

Commands:

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python ops/openclaw_finbot.py theme-radar-scout --format json
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python ops/openclaw_finbot.py watchlist-scout --format json --scope today --limit 8
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python ops/openclaw_finbot.py inbox-list --format json --limit 12
```

Observed:

- `theme-radar-scout` returned `updated=true` for stable radar item
- `deepening_brief` also returned `updated=true`
- `watchlist-scout` wrote stable item id `finbot-watchlist-transformer-supercycle`
- pending inbox kept:
  - one stable radar item
  - one stable watchlist item
  - one stable brief item
- legacy digest items were moved into archived inbox

### Investor dashboard pages

Commands:

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python - <<'PY'
from fastapi.testclient import TestClient
from chatgptrest.api.app import create_app
client = TestClient(create_app())
for path in [
    '/v2/dashboard/investor',
    '/v2/dashboard/investor/themes/transformer',
    '/v2/dashboard/investor/opportunities/candidate_tsmc_cpo_cpo_d519030bd1',
    '/v2/dashboard/investor/sources/src_broadcom_ir',
]:
    r = client.get(path)
    print(path, r.status_code)
PY
```

Observed:

- all 4 pages returned `200`

Live snapshot check showed:

- `theme_count = 5`
- `opportunity_count = 2`
- `strong_source_count = 19`
- `kol_count = 28`
- `inbox_count = 8`

And the previously broken themes now resolve correctly:

- `transformer -> watch_with_prepare_candidate / sntl_xidian_alt`
- `ai_energy_onsite_power -> watch_with_prepare_candidate / sntl_gev_ai_power`
- `commercial_space -> watch_only / sntl_rklb_space_systems`

## Real Limitations Still Left

1. Opportunity detail still inherits source coverage from current investor snapshot. It is much better than before, but still limited by what `source-board` currently surfaces.
2. Radar candidates still come from `finagent` event mining quality. This pass improved presentation and deepening workflow, not the underlying thesis scoring model.
3. GitNexus `impact` and `detect_changes` both failed again with `Transport closed`, so validation relied on:
   - local symbol inspection
   - targeted tests
   - live smoke

## Judgment

This pass moved the system from:

- "finbot is running, but outputs are still scout-grade"

to:

- "finbot and dashboard now produce an investor-readable working surface with stable inbox semantics, clickable opportunity/theme/source views, and a visible deepening path."

It is now reasonable to keep iterating on research quality on top of this surface instead of first fighting dashboard shape and inbox duplication.
