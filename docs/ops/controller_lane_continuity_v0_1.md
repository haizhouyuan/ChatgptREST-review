# Controller Lane Continuity v0.1

Date: 2026-03-10

## Purpose

This is the narrow continuity layer for local development lanes.

It exists to solve one concrete problem:

- Codex / Claude / auxiliary CLI lanes finish a chunk of work and exit
- the human controller is away
- there is no shared heartbeat, no durable lane state, and no automatic restart path

This tool does **not** try to be a general multi-agent platform.
It only provides:

- lane registry
- heartbeat / progress reporting
- stale detection
- optional auto-restart via stored launch/resume commands
- a simple digest for the main controller

## Design rules

- One controller remains the source of truth.
- Specialist lanes remain subordinate.
- Lane continuity is operational infrastructure, not product-facing agent orchestration.
- Auto-restart is allowed only for lanes explicitly marked `desired_state=running`.
- `needs_gate` and `checkpoint_pending=true` stop auto-restart and surface for human review.

## State model

State is persisted in:

- `state/controller_lanes.sqlite3`

Artifacts and launch logs are written under:

- `artifacts/controller_lanes/<lane_id>/`

Each lane stores:

- identity: `lane_id`, `purpose`, `lane_kind`, `cwd`, optional `session_key`
- desired state: `running | paused`
- runtime state: `idle | working | needs_gate | completed | failed | paused`
- liveness: `heartbeat_at`, `pid`, `stale_after_seconds`
- restart policy: `launch_cmd`, `resume_cmd`, `restart_cooldown_seconds`
- audit fields: `last_summary`, `last_artifact_path`, `last_error`, `checkpoint_pending`

## Command surface

### Register or update a lane

```bash
PYTHONPATH=. ./.venv/bin/python ops/controller_lane_continuity.py upsert-lane \
  --lane-id scout \
  --purpose "read-only gitnexus scout" \
  --lane-kind codex \
  --cwd /vol1/1000/projects/ChatgptREST \
  --desired-state running \
  --run-state idle \
  --stale-after-seconds 900 \
  --restart-cooldown-seconds 300 \
  --launch-cmd 'codex exec --cd /vol1/1000/projects/ChatgptREST -' \
  --resume-cmd 'codex exec resume --last --cd /vol1/1000/projects/ChatgptREST -'
```

### Heartbeat from a running lane

```bash
PYTHONPATH=. ./.venv/bin/python ops/controller_lane_continuity.py heartbeat \
  --lane-id scout \
  --pid $$ \
  --run-state working \
  --summary "reading impact surface for memory stage()"
```

### Final report from a lane

```bash
PYTHONPATH=. ./.venv/bin/python ops/controller_lane_continuity.py report \
  --lane-id scout \
  --run-state completed \
  --summary "impact read complete" \
  --artifact-path /vol1/1000/projects/ChatgptREST/docs/dev_log/example.md
```

### Human-readable digest

```bash
PYTHONPATH=. ./.venv/bin/python ops/controller_lane_continuity.py digest
```

### Sweep stale lanes and optionally restart

```bash
PYTHONPATH=. ./.venv/bin/python ops/controller_lane_continuity.py sweep --restart
```

Restart selection rule:

- first restart uses `launch_cmd`
- subsequent restarts use `resume_cmd` when present
- lanes in `completed`, `failed`, or `needs_gate` are not restarted

## Recommended local team shape

Keep the team small and controller-centric:

- `main`: the only controller
- `scout`: read-only Codex lane
- `worker-1`: bounded implementation lane
- `verifier`: test / smoke / artifact validation lane
- `cc-async`: ClaudeCode long async lane when needed

Do not create standing `planning`, `research-orch`, or `coordinator` personas here.

## Systemd integration

Two optional user units are provided:

- `ops/systemd/chatgptrest-controller-lanes.service`
- `ops/systemd/chatgptrest-controller-lanes.timer`

They run a periodic `sweep --restart` so stale lanes can be resumed without a human keeping a shell open.

Enable when ready:

```bash
systemctl --user daemon-reload
systemctl --user enable --now chatgptrest-controller-lanes.timer
```

## Limits of v0.1

This does not yet provide:

- semantic cross-lane conflict detection
- automatic task decomposition
- role-aware routing
- product-level agent teams

It only closes the operational continuity gap for local development lanes.
