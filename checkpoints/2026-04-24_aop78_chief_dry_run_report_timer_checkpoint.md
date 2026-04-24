# AOP-78 Chief Dry-Run Report Timer Checkpoint

Date: 2026-04-24
Scope: local read-only replacement for the paused Multica create-issue governance autopilot.

## Decision

AOP-78 installs a local user-systemd timer that runs a read-only dry-run reporter for the Hermes chief control plane.

This is not Multica autopilot and not autonomous advancement. The reporter collects a sanitized live snapshot, runs the existing `chief_advance_one_dry_run.py` checker, and writes local report artifacts under `/vol1/maint/state/control_plane/sweeps/`.

## Target

- Workspace: Assistant Ops `bbc33e1b-a6d8-4724-b29f-b35ac8372572`
- Issue: AOP-78 `b712535d-ecb2-4c3d-b4c4-6c6d1ce7591a`
- Script: `ops/scripts/chief_scheduled_dry_run_report.py`
- User service: `services/systemd-user/chief-dry-run-report.service`
- User timer: `services/systemd-user/chief-dry-run-report.timer`
- Installed unit path: `/home/yuanhaizhou/.config/systemd/user/chief-dry-run-report.timer`

## Implementation

The reporter performs these steps:

1. Runs `chief_collect_live_snapshot.py` into a local snapshot JSON.
2. Runs `chief_advance_one_dry_run.py` against that snapshot.
3. Scans generated snapshot and decision artifacts for secret-like patterns.
4. Writes a local report JSON with hashes, drift summary, eligibility count, and explicit control-boundary flags.

It does not call Multica mutating commands and does not read auth JSON, environment secrets, browser profiles, session state, or secret stores.

## Manual Test

Command:

```bash
python3 ops/scripts/chief_scheduled_dry_run_report.py \
  --output-dir /vol1/maint/state/control_plane/sweeps \
  --stamp sidecar-test-20260424T1317Z \
  --run-id sidecar-test-after-aop77
```

Result:

```json
{
  "allowed_action": "no_op",
  "dry_run_only": true,
  "drift_count": 2,
  "eligible_count": 0,
  "proposed_issue_id": null
}
```

Generated artifacts:

- `/vol1/maint/state/control_plane/sweeps/sidecar-test-20260424T1317Z.snapshot.json`
- `/vol1/maint/state/control_plane/sweeps/sidecar-test-20260424T1317Z.decision.json`
- `/vol1/maint/state/control_plane/sweeps/sidecar-test-20260424T1317Z.report.json`

The report still shows two high drift blockers:

- `mcp.lanes.chatgptrest.multica_visible`: `block_transition`
- `skills.multica_visible_agent_skills`: `block_transition`

## Installed Timer

Commands:

```bash
install -m 0644 services/systemd-user/chief-dry-run-report.service ~/.config/systemd/user/chief-dry-run-report.service
install -m 0644 services/systemd-user/chief-dry-run-report.timer ~/.config/systemd/user/chief-dry-run-report.timer
systemctl --user daemon-reload
systemctl --user enable --now chief-dry-run-report.timer
systemctl --user status chief-dry-run-report.timer --no-pager
```

Readback:

- Timer status: `active (waiting)`
- Timer enabled: yes
- Next trigger: `2026-04-25 09:30:59 CST`
- Triggered service: `chief-dry-run-report.service`

## Validation

Commands run:

```bash
python3 - <<'PY'
import py_compile
from pathlib import Path
for path in [
    'ops/scripts/chief_scheduled_dry_run_report.py',
    'ops/scripts/chief_collect_live_snapshot.py',
    'ops/scripts/chief_advance_one_dry_run.py',
]:
    py_compile.compile(path, cfile=str(Path('/tmp') / (Path(path).name + '.pyc')), doraise=True)
print('py-compile-ok')
PY
python3 -m json.tool state/control_plane/sweeps/sidecar-test-20260424T1317Z.report.json >/dev/null
rg -n "sk-[A-Za-z0-9_-]{16,}|api[_-]?key\\s*[:=]|access[_-]?token\\s*[:=]|refresh[_-]?token\\s*[:=]|Authorization\\s*:|Bearer\\s+[A-Za-z0-9._~+/-]{10,}|password\\s*[:=]" state/control_plane/sweeps/sidecar-test-20260424T1317Z.report.json state/control_plane/sweeps/sidecar-test-20260424T1317Z.snapshot.json state/control_plane/sweeps/sidecar-test-20260424T1317Z.decision.json
rg -n "issue status|issue comment add|autopilot (create|update|delete|run)|agent (create|update|delete)|runtime (create|update|delete)|workspace (create|update|delete)" ops/scripts/chief_scheduled_dry_run_report.py
systemctl --user status chief-dry-run-report.timer --no-pager
```

Results:

- Python compile: passed.
- Report JSON parse: passed.
- Secret-pattern scan: no matches.
- Mutating-command scan over reporter: no matches.
- User timer: enabled and active.

## Safety Boundary

This checkpoint only enables a local read-only report schedule. It does not:

- create Multica issues,
- change issue status,
- trigger Multica autopilot,
- mutate agents, runtimes, projects, workspaces, MCP, skills, auth, or permissions,
- clear high-risk review gates,
- fix MCP or skills metadata drift,
- or authorize Hermes chief self-advance.

## Remaining Limits

- The old Multica create-issue autopilot remains paused.
- The report currently returns `no_op`, which is the correct result while high drift remains.
- High-risk changes still need independent GAC/Claude review when quota recovers; Codex GPT-5.5 xhigh fallback remains a degraded Grade-C gate for high-risk live control-plane changes.
- A separate MCP/skills metadata reconciliation task is still required before any broader automation or self-advance can be considered.
