# OpenClaw + OpenMind Rebuild Round 9

Date: 2026-03-09

## What changed

- Identified the actual source of agent-topology drift:
  - `chatgptrest-orch-doctor.timer` was invoking `ops/openclaw_orch_agent.py --reconcile`
  - every run re-added legacy `chatgptrest-*` agents into OpenClaw state
- Fixed guardian defaults so the integrated stack uses `maintagent` instead of the retired `chatgptrest-guardian` lane.
- Hardened `openclaw` command resolution in both `ops/openclaw_guardian_run.py` and `ops/openclaw_orch_agent.py` so they work under both:
  - `HOME=/home/yuanhaizhou`
  - `HOME=/home/yuanhaizhou/.home-codex-official`
- Updated systemd unit templates:
  - `chatgptrest-orch-doctor.service` now runs read-only doctor mode and pins the official OpenClaw state dir
  - `chatgptrest-guardian.service` now pins the official OpenClaw state dir as well
- Updated `ops/openclaw_guardian_wake.sh` to target `maintagent` and the official state dir.
- Synced `docs/runbook.md` to the new baseline semantics.

## Why

The rebuilt OpenClaw + OpenMind baseline intentionally uses:

- `main`
- `planning`
- `research-orch`
- `openclaw-orch`
- `maintagent`

But the legacy ChatgptREST orch doctor was still maintaining a different five-agent set:

- `chatgptrest-orch`
- `chatgptrest-codex-w1`
- `chatgptrest-codex-w2`
- `chatgptrest-codex-w3`
- `chatgptrest-guardian`

That conflict was enough to re-pollute `openclaw.json`, trigger repeated gateway config reloads, and drag old Codex lanes back into token refresh contention.

## Validation

- `./.venv/bin/pytest -q tests/test_openclaw_guardian_issue_sweep.py tests/test_openclaw_orch_agent.py`
- `./.venv/bin/python -m py_compile ops/openclaw_guardian_run.py ops/openclaw_orch_agent.py tests/test_openclaw_guardian_issue_sweep.py tests/test_openclaw_orch_agent.py`

## Next

- Install the updated systemd unit templates into `~/.config/systemd/user/`
- reload systemd
- rebuild the OpenClaw state so only the intended five-agent topology remains
- verify that a manual orch doctor run no longer reintroduces legacy agents
- re-run live OpenMind tool-call probes from `main`
