# 2026-03-15 Finbot Feishu Ingress Rollout v1

## Goal

Bring `finbot` online as a dedicated Feishu-facing research assistant without replacing the existing `main` entry.

Target routing after rollout:

- `feishu/default` -> `main`
- `feishu/research` -> `finbot`

## Why This Rollout

The live OpenClaw state already had:

- `main`
- `maintagent`
- `finbot`

But Feishu ingress still only routed the default account to `main`, while the historical `research` account stayed disabled. That meant users could not directly reach `finbot` through Feishu even though the agent was live.

## Implementation

Updated:

- `scripts/rebuild_openclaw_openmind_stack.py`
- `tests/test_rebuild_openclaw_openmind_stack.py`

### Behavior change

When topology is `ops`:

- `channels.feishu.accounts.research.enabled = true`
- `channels.feishu.accounts.research.botName = "Finbot"`
- `channels.feishu.accounts.research.dmPolicy = "pairing"`
- `channels.feishu.accounts.research.groupPolicy = "disabled"`
- route binding added:
  - `{"type":"route","agentId":"finbot","match":{"channel":"feishu","accountId":"research"}}`

When topology is not `ops`:

- the old safe behavior remains
- `research` stays disabled and non-human-facing

## GitNexus note

Impact analysis was attempted on the edited rebuild symbols before changing code, but GitNexus MCP again failed with:

- `Transport closed`

Because of that, this rollout relied on:

- local code-path inspection
- targeted regression tests
- live rebuild inspection

## Validation

### Tests

Executed:

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_verify_openclaw_openmind_stack.py \
  tests/test_finbot.py
```

Result:

- all selected tests passed

### Live rebuild

Executed:

```bash
python3 scripts/rebuild_openclaw_openmind_stack.py --topology ops
```

### Live state inspection

Observed in `~/.openclaw/openclaw.json`:

- `bindings` now contains:
  - `feishu/default -> main`
  - `feishu/research -> finbot`
- `channels.feishu.accounts.research` now shows:
  - `enabled: true`
  - `botName: Finbot`
  - `dmPolicy: pairing`
  - `groupPolicy: disabled`

## Operator usage after rollout

Use the two Feishu accounts with clear separation:

- `OpenClaw`
  - general human-facing assistant
  - routes to `main`
- `Finbot`
  - dedicated research / market / theme / watchlist / radar requests
  - routes to `finbot`

Recommended posture:

- keep `main` for orchestration, judgment, and mixed requests
- use `Finbot` for direct research tasks when you explicitly want the research lane

## Outcome

This rollout makes `finbot` directly reachable from Feishu while preserving the existing `main` entry and keeping `maintagent` out of the human-facing ingress path.
