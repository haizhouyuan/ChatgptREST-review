# Finbot Multi-Lane Review Packet v1

> Date: 2026-03-16
> Branch: `codex/finbot-runtime-deploy-20260316`
> Purpose: open-ended external review for evolving finbot from a continuous scout into a multi-lane investment analyst and data-mining expert

## Current Product Shape

The current architecture already has:

- single human ingress via `main`
- single investment execution agent via `finbot`
- continuous discovery via timers and deterministic `finagent` workflows
- investor dashboard views for themes, opportunities, sources, and reader links
- automatic opportunity deepening into a persisted research package

Recent key files:

- `chatgptrest/finbot.py`
- `ops/openclaw_finbot.py`
- `chatgptrest/dashboard/service.py`
- `chatgptrest/dashboard/templates/investor.html`
- `chatgptrest/dashboard/templates/investor_opportunity_detail.html`

Recent docs:

- `docs/2026-03-16_finbot_continuous_runtime_rollout_v2.md`
- `docs/2026-03-16_investor_dashboard_and_finbot_quality_walkthrough_v1.md`
- `docs/2026-03-16_finbot_opportunity_dossier_walkthrough_v1.md`
- `docs/2026-03-16_finbot_opportunity_dossier_live_rollout_v1.md`

## Current Live Proof

The current live system has already proven:

1. `finbot` runs unattended through systemd timers.
2. `theme-radar-scout` surfaces a frontier candidate.
3. `opportunity-deepen` can generate a persistent research package using `coding_plan/MiniMax-M2.5`.
4. The investor dashboard can display:
   - latest research package
   - best expression today
   - why not investable yet
   - next proving milestone
   - dossier / json / context links

Example live candidate:

- `candidate_tsmc_cpo_cpo_d519030bd1`

Example live artifact paths:

- `artifacts/finbot/opportunities/tsmc-cpo-cpo-d519030bd1/latest.json`
- `artifacts/finbot/opportunities/tsmc-cpo-cpo-d519030bd1/latest.md`
- `artifacts/finbot/opportunities/tsmc-cpo-cpo-d519030bd1/latest_context.json`

## Current Limitation

The system is now investor-readable, but still not yet behaving like a strong internal analyst.

The biggest remaining gap is that `finbot` is still mostly doing a linear deepen step:

- discover
- brief
- dossier

It is not yet explicitly running an internal multi-lane collaboration model such as:

- scout lane
- claim / evidence lane
- skeptic / anti-thesis lane
- expression comparison lane
- decision synthesis lane

## Open-Ended Review Questions

Please review the current shape as an evolving investment research operating system, not as a general chatbot.

Open questions:

1. What is the best internal multi-lane design for a single-ingress, single-finbot system that must continuously discover, challenge, compare, and synthesize investment opportunities?
2. Which internal lanes should exist first, and which should remain implicit or merged until scale justifies more separation?
3. How should claims, counter-claims, expression ranking, and forcing events be represented so that the system becomes a better analyst instead of simply producing longer reports?
4. What data-mining and weak-signal methods are worth adding next without turning the system into a noisy over-automation machine?
5. How should the investor dashboard evolve so that a human investor sees:
   - what changed
   - why it matters
   - what is investable now
   - what still blocks action
   without seeing internal noise or raw system exhaust?
6. What are the most important product and architecture mistakes still present in the current design?
7. If the target is “smarter investment analyst + stronger data-mining expert,” what should the next implementation slice be?

## Required Review Style

Please keep the review open-ended and constructive:

- focus on architecture, workflows, reasoning structure, and product quality
- critique where the current shape is still shallow or mis-specified
- propose a better internal operating model if the current one is wrong
- do not reduce the answer to a closed checklist or trivial bug review

## What The Next Prototype Will Attempt

The next local prototype will try to evolve `opportunity-deepen` into an explicit internal multi-lane workflow:

- scout context assembly
- claim lane
- skeptic lane
- expression lane
- decision lane

The goal is to compare the result against the current linear dossier workflow and see whether the upgraded shape is meaningfully closer to a real investment analyst.
