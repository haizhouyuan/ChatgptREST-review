# Finbot Opportunity Dossier Walkthrough v1

> Date: 2026-03-16
> Branch: `codex/finbot-runtime-deploy-20260316`
> Goal: push finbot from "scout + brief" to "investor-grade opportunity dossier"

## Why This Pass Was Needed

The prior quality pass made the investor dashboard readable, but the deepest opportunity surface was still a `deepening_brief`. That was enough for triage, not enough for a real investor workflow.

The remaining gap was simple:

- `theme-radar-scout` could surface a frontier candidate
- dashboard could show the candidate and a next step
- but there was still no stable object that answered:
  - what is the decision now
  - which existing theme should absorb the candidate
  - what is the best expression today
  - why is it still not investable
  - which forcing events or disconfirming signals matter next

This pass adds that missing middle layer: a **research package**.

## What Changed

### 1. Finbot can now auto-deepen an opportunity

Code:

- `chatgptrest/finbot.py`
- `ops/openclaw_finbot.py`

New workflow:

1. select a frontier or adjacent opportunity candidate
2. assemble context from:
   - investor snapshot
   - theme detail
   - source detail
   - planning document
3. run KOL suite from `finagent`
4. call `coding_plan.ask`
5. synthesize a stable research package with:
   - JSON contract
   - markdown dossier
   - persisted context bundle
6. write a stable `research_package` inbox item

New CLI:

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python \
  ops/openclaw_finbot.py opportunity-deepen \
  --candidate-id candidate_tsmc_cpo_cpo_d519030bd1 \
  --format json
```

### 2. Coding-plan lane now powers the dossier

The dossier path does not rely on the old web-only extraction lane. It uses the API-based `coding_plan` executor, which in live runs resolved to:

- `provider = coding_plan/MiniMax-M2.5`

This matters because the dossier pipeline is intended to be part of continuous unattended work, not just an interactive one-off.

### 3. Research packages are now first-class artifacts

New artifact structure:

```text
artifacts/finbot/opportunities/<candidate_slug>/
  latest.json
  latest.md
  latest_context.json
  history/<timestamp>/
    research_package.json
    research_package.md
    research_context.json
```

Stable package fields include:

- `headline`
- `current_decision`
- `thesis_status`
- `best_absorption_theme`
- `best_expression_today`
- `why_not_investable_yet`
- `next_proving_milestone`
- `forcing_events`
- `disconfirming_signals`
- `key_sources`
- `research_gaps`

### 4. Investor dashboard now treats the dossier as the primary detail object

Code:

- `chatgptrest/dashboard/service.py`
- `chatgptrest/dashboard/templates/investor.html`
- `chatgptrest/dashboard/templates/investor_opportunity_detail.html`

Changes:

- opportunity cards expose `Open Package`
- opportunity detail page now has a `Latest Research Package` section
- package links now point to:
  - dossier markdown
  - dossier json
  - dossier context
  - brief
  - planning doc

The dashboard is no longer just:

- candidate
- route
- residual class

It now exposes the investor-facing judgment layer on top of the candidate.

## Targeted Tests

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_finbot.py \
  tests/test_dashboard_routes.py \
  tests/test_executor_factory.py \
  tests/test_coding_plan_executor.py
```

Result:

- all targeted tests passed

## Key Live Proof

### A. Live dossier generation succeeded

Command:

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python \
  ops/openclaw_finbot.py opportunity-deepen \
  --format json \
  --candidate-id candidate_tsmc_cpo_cpo_d519030bd1 \
  --force
```

Observed result:

- `ok = true`
- `created = true`
- `provider = coding_plan/MiniMax-M2.5`
- `current_decision = deepen_now`
- `best_absorption_theme = 硅光 / CPO 表达分层`
- `best_expression_today = 中际旭创 / 800G / 1.6T 光模块`
- `kol_suite.ok = true`
- `kol_suite.total_claims = 77`

### B. Dashboard now shows the package live

Live page:

- `/v2/dashboard/investor/opportunities/candidate_tsmc_cpo_cpo_d519030bd1`

Observed on the live page:

- `Latest Research Package`
- `Best expression today`
- `Why not investable yet`
- `Next proving milestone`
- `Open Dossier`
- `Open Dossier JSON`

### C. Investor API now counts research packages

Live investor snapshot now includes a package count, so the dashboard can distinguish:

- surfaced opportunities
- opportunities that have already been deepened into a dossier

## Quality Judgment

This pass changes the system in a meaningful way:

- before: radar produced a candidate and a brief
- after: radar can produce a candidate, a brief, and a stable investor dossier

That is the point where the system starts becoming usable as an investor workbench rather than only a discovery surface.

## Remaining Limits

1. The current auto-deepen path selects one candidate at a time. It is stable, but not yet a portfolio-scale research scheduler.
2. Dossier quality still depends on source coverage and KOL coverage from `finagent`.
3. The system now has a good investor-facing object, but not yet a full automated "candidate -> full research package -> absorption into theme" state machine.

## Bottom Line

This pass makes `finbot` materially deeper:

- it still discovers
- it still briefs
- but it can now also produce a persistent, investor-readable research package that the dashboard treats as the primary detail layer

That is the necessary bridge from continuous scouting to real investment workflow.
