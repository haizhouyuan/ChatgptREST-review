# OpenClawBot Workspace Material Ops Cutover Walkthrough v1

## Goal

Close the missing execution lane inside the existing Feishu `OpenClawBot` work ingress so the bot can inspect local planning materials instead of failing on `exec`.

## Trigger

The live Feishu bot already handled planning-style asks, but it failed on a real follow-up that asked it to:

- verify local planning file paths
- read xlsx sheet names
- list sibling materials

The failure mode was:

1. `feishu-intake` received the work ask correctly
2. the model tried `exec`
3. runtime returned `Tool exec not found`
4. the answer degraded into “please send screenshots”

This established that the gap was not work-intent routing. The gap was the lack of a dedicated workspace-material operations lane.

## Implementation

### Code

1. Added host-side plugin tool `openmind_work_material_ops` in:
   - `/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts`
2. Supported actions:
   - `inspect`
   - `move`
3. Supported inspect posture:
   - allowlisted local roots
   - workbook sheet-name extraction using stdlib zip/xml parsing
   - sibling-material listing
   - simple preview / directory entry listing
4. Supported move posture:
   - allowlisted write roots only
   - safe `dryRun` default
5. Updated stack rebuild script:
   - `/vol1/1000/projects/ChatgptREST/scripts/rebuild_openclaw_openmind_stack.py`
   - `feishu-intake` now gets `openmind_work_material_ops`
   - workspace guidance now explicitly tells the agent not to fall back to `exec`

### Validation

1. Python tests passed:
   - `tests/test_rebuild_openclaw_openmind_stack.py`
   - `tests/test_openclaw_cognitive_plugins.py`
   - `tests/test_openclawbot_meeting_intake_smoke.py`
2. Rebuilt live OpenClaw stack and restarted gateway
3. Replayed the real workbook-inspection ask through `feishu-intake`
4. Confirmed transcript now shows:
   - `openmind_work_material_ops`
   - real workbook sheet names in tool output
5. Confirmed gateway final text no longer asks for screenshots and no longer routes through missing `exec`

## Live Evidence

- archived validation transcript:
  - `/home/yuanhaizhou/.home-codex-official/.openclaw/backups/feishu-intake-wmops-clean-20260410T1845/validation_session_8ba11bbf-e228-413f-9d0e-9a0271de4a35.jsonl`
- gateway log checkpoint:
  - `journalctl --user -u openclaw-gateway.service -n 120 --no-pager`
- live session store after cleanup:
  - `/home/yuanhaizhou/.home-codex-official/.openclaw/agents/feishu-intake/sessions/sessions.json`

## Session Hygiene

After validation:

1. backed up the validation transcript and session map
2. cleared `feishu-intake` validation sessions
3. restarted `openclaw-gateway.service`

This leaves the live Feishu bot ready to start the next real work thread from a clean intake session state.

## Final State

The current Feishu `OpenClawBot` work ingress now has two working lanes behind the same bot:

1. `openmind_advisor_ask`
   - planning / report / research-style work closure
2. `openmind_work_material_ops`
   - local planning-material inspection and controlled organization

This closes the concrete failure you observed in live use without introducing a third bot or a generic shell lane.
