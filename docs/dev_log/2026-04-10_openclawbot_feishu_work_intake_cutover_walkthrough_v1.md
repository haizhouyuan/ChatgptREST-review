# OpenClawBot Feishu Work Intake Cutover Walkthrough v1

## Goal

Cut the live Feishu `OpenClawBot` path away from `main` and onto a dedicated work-only intake lane that hands off into `openmind_advisor_ask`.

## Why

The observed live issue was not transport loss. Feishu rich context already reached OpenClaw.

The real failure mode was:

- `feishu/default -> main`
- `main` answered image-heavy work asks directly
- `openmind_advisor_ask` was available but not used

This produced plausible but unstructured “product-commentary” answers instead of work-lane closure.

## Changes

### Repo code

1. Added `feishu-intake` to `scripts/rebuild_openclaw_openmind_stack.py`
2. Switched Feishu default binding from `main` to `feishu-intake`
3. Generated managed workspace guidance for the new intake lane
4. Updated meeting-intake smoke expectations from `agent:main:feishu:...` to `agent:feishu-intake:feishu:...`
5. Updated rebuild/smoke tests accordingly

## Live runtime prep

1. Backed up live config and old workspace text to:
   - `/home/yuanhaizhou/.home-codex-official/.openclaw/backups/feishu-intake-cutover-20260410T151629`
2. Patched:
   - `/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json`
3. Rewrote:
   - `/vol1/1000/openclaw-workspaces/feishu-intake/*.md`
4. Created clean live agent namespace:
   - `/home/yuanhaizhou/.home-codex-official/.openclaw/agents/feishu-intake`
   - with fresh `sessions/sessions.json = {}`
5. Restarted:
   - `systemctl --user restart openclaw-gateway.service`

## Validation

### Code/test validation

- `tests/test_rebuild_openclaw_openmind_stack.py`
- `tests/test_openclawbot_meeting_intake_smoke.py`

Both passed after the cutover changes.

### Runtime validation

1. Meeting-intake smoke:
   - `4/4 pass`
   - artifact:
     - `/vol1/1000/projects/ChatgptREST/artifacts/monitor/openclawbot_meeting_intake_smoke/20260410T1517Z/report_v2.json`
2. Advisor main-path gate:
   - `5/5 pass`
   - artifact:
     - `/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_main_path_gate_20260403_v2/report_v1.json`
3. Real intake-agent validation run:
   - session file:
     - `/home/yuanhaizhou/.home-codex-official/.openclaw/agents/feishu-intake/sessions/8ba11bbf-e228-413f-9d0e-9a0271de4a35.jsonl`
   - confirmed first tool call:
     - `openmind_advisor_ask`

## Final State

- Feishu work traffic no longer shares the `main` agent namespace
- `feishu-intake` is now the formal Feishu work ingress
- the advisor substrate remains the same verified ChatgptREST `/v3/agent/turn` lane
- real Feishu formal usage can start after this cutover

