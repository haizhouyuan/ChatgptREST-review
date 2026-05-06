# OpenMind Canary Rollout Contract v1

Date: 2026-04-09  
Status: canonical PR-8 rollout contract for the OpenMind production-readiness launch

## Purpose

Freeze the canary cohort, failure budget, watch-window posture, and rollout-decision inputs for the OpenMind production rollout.

## Canonical cohort

- cohort file: `ops/data/openmind_canary_cohort_v1.json`
- projects:
  - `shortmobility`
  - `prs`
- surfaces:
  - `/v3/agent/turn`
  - `openmind-advisor`

## Default launch rule

`launch_canary_watch` is allowed when:

- the latest production regression summary is green
- no domain is in `fail`
- any remaining `warn` domain is explicitly allowed by the cohort failure budget

Current allowed warning domains:

- `promotion`

This allowance exists only for the staged-without-active backlog posture. It does not allow packet, recall, or crystal failures.

## Watch window

- default length: `7 days`
- initial launch decision may be `launch_canary_watch`
- final expansion decision `go_live` requires:
  - watch window elapsed
  - regression still green
  - no disallowed warning or failing domains

## Canonical commands

```bash
cd /vol1/1000/projects/ChatgptREST

python3 ops/report_openmind_production_health.py \
  --output-root artifacts/monitor/openmind_production_health

python3 ops/report_openmind_canary_scorecard.py \
  --output-root artifacts/monitor/openmind_canary_scorecard
```

## Evidence

PR-8 evidence should archive:

- canary scorecard JSON / Markdown
- rollout decision log
- post-rollout watch checklist
- the health and regression artifacts that fed the scorecard
