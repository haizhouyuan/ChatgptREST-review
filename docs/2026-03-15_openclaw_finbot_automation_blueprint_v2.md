# OpenClaw Finbot Automation Blueprint v2

## Goal

Freeze the OpenClaw runtime shape for investment-research automation as:

- `main`: human-facing primary lane
- `maintagent`: watchdog / health lane
- `finbot`: background investment-research scout backed by `/vol1/1000/projects/finagent`

`autoorch` remains a compatibility alias only. New topology, docs, cron, and inbox paths should all treat `finbot` as canonical.

## Why the rename

- The user wants a clear distinction between:
  - `finbot`: the OpenClaw agent identity
  - `finagent`: the underlying investment-research codebase
- This keeps OpenClaw runtime semantics separate from the standalone finagent repository and its own CLI/runtime.

## Runtime split

### `main`

- Handles direct user interaction
- Reads high-value inbox items
- Does not run noisy scheduled background sweeps

### `maintagent`

- Handles watchdog and health checks
- Stays read-mostly
- Does not absorb finbot business automation responsibilities

### `finbot`

- Runs dashboard refresh
- Runs finagent-driven watchlist scouting
- Writes inbox items under `artifacts/finbot/inbox/pending/`
- Escalates only net-new actionable deltas back to `main`

## Task surface

### Heartbeat

- `python3 ops/openclaw_finbot.py dashboard-refresh --format json`
- `python3 ops/openclaw_finbot.py inbox-list --format json --limit 10`

### Cron

- daily watchlist scout:
  - `python3 ops/openclaw_finbot.py watchlist-scout --format json`

## Compatibility rules

- `chatgptrest.finbot` is canonical runtime module
- `chatgptrest.autoorch` is a compatibility wrapper
- `ops/openclaw_finbot.py` is canonical CLI entrypoint
- `ops/openclaw_autoorch.py` is a compatibility wrapper
- verifier accepts both:
  - `{main, maintagent, finbot}`
  - `{main, maintagent, autoorch}`

## Inbox protocol

- pending:
  - `artifacts/finbot/inbox/pending/*.json`
  - `artifacts/finbot/inbox/pending/*.md`
- archived:
  - `artifacts/finbot/inbox/archived/*.json`
  - `artifacts/finbot/inbox/archived/*.md`

Inbox remains file-based by design:

- low coupling
- no hard dependency on immediate notifications
- natural audit trail
- easy dashboard ingestion later

## Phase result

This v2 slice does not add new discovery logic. It standardizes naming and operating boundaries so later automation and graph work can build on a stable agent identity.
