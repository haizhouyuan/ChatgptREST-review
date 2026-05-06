# 2026-03-15 Main Single-Ingress Finbot Dispatch Decision v1

## Decision

Keep Feishu as a **single human-facing ingress**:

- `feishu/default` -> `main`

Do **not** enable the historical `research` Feishu account as a direct `finbot` ingress.

## Why

The alternative that was briefly rolled out was:

- `feishu/default` -> `main`
- `feishu/research` -> `finbot`

That path works technically, but it creates the wrong product shape for the current stage:

- two human-facing entry points
- split task history
- split memory traces
- ambiguity about whether a request belongs to `main` or `finbot`

The intended operating model is different:

- user talks to `main`
- `main` decides whether to keep the request or delegate to `finbot`
- `finbot` runs research work and returns structured outputs

## Current Product Boundary

### main

- only stable Feishu-facing human entry
- orchestration, judgment, escalation, and task routing

### finbot

- background research lane
- uses `finagent` runtime / CLI / dashboards / radar
- should be invoked by delegation, not by a second public ingress

### maintagent

- watchdog / health / recovery lane
- not human-facing

## Implementation Choice

This rollback restores the rebuild behavior so that:

- `research` remains disabled
- `default` remains the only Feishu account routed by bindings

That means live Feishu/OpenClaw state returns to:

- `feishu/default` -> `main`

## Follow-on Work

The next step is not another ingress account. The next step is:

- define and implement a `main -> finbot` delegation protocol

That protocol should cover:

- what messages should be delegated
- how `main` records the handoff
- how `finbot` reports back
- how inbox / dashboard / session history stay coherent

## Outcome

This decision prioritizes:

- one clear user entry
- less confusion
- cleaner memory/task lineage
- safer staged rollout
