# OpenMind Production Graduation Contract v1

Date: 2026-04-09  
Status: canonical G0/G1 graduation contract for the OpenMind canary-to-go-live sequence

## Purpose

Freeze the exact vocabulary and evidence boundary between:

- `canary-ready`
- `watch-window active`
- `go-live ready`

This contract exists so launch, watch, and graduation are never described as the same thing.

## Canonical terminology

### `canary-ready`

Meaning:

- the current build is eligible to launch or continue the canary cohort
- latest regression is green
- there are no fail domains
- any remaining warn domain is explicitly allowed by the canary failure budget

This does **not** mean:

- full rollout is graduated
- the watch window is complete

### `watch-window active`

Meaning:

- the canary cohort is currently running under the declared watch window
- daily health / regression / scorecard evidence must be archived
- the system may remain in `hold` or `launch_canary_watch` posture even if engineering work is complete

This does **not** mean:

- go-live is approved

### `go-live ready`

Meaning:

- the watch window has elapsed
- the latest scorecard is `go_live`
- there are no current fail domains
- there are no current unapproved warn domains
- the graduation artifact cites current health / regression / ledger evidence

## Canonical decision states

| State | Meaning |
| --- | --- |
| `launch_canary_watch` | canary-ready and watch window may start or continue |
| `hold` | do not widen beyond the current cohort yet |
| `rollback` | current health/regression posture is unsafe for continued rollout |
| `go_live` | the watch window is complete and current evidence supports graduation |

## Required evidence

### For canary launch / continued watch

- latest production regression artifact
- latest production health artifact
- latest canary scorecard artifact

### For graduation

- latest production regression artifact
- latest production health artifact
- latest canary scorecard artifact
- watch-window ledger entries covering the current watch window
- final graduation gate artifact

## Hard rules

1. Do not describe `launch_canary_watch` as `go_live`.
2. Do not describe `canary-ready` as `production-grade`.
3. Do not emit `go_live` unless the watch window is complete.
4. Do not emit `go_live` when fail domains exist.
5. Do not emit `go_live` when unapproved warn domains exist.

## Canonical commands

```bash
cd /vol1/1000/projects/ChatgptREST

python3 ops/report_openmind_canary_scorecard.py \
  --output-root artifacts/monitor/openmind_canary_scorecard

python3 ops/report_openmind_watch_window_ledger.py \
  --output-root artifacts/monitor/openmind_watch_window_ledger

python3 ops/finalize_openmind_graduation_gate.py \
  --output-root artifacts/monitor/openmind_graduation_gate
```
