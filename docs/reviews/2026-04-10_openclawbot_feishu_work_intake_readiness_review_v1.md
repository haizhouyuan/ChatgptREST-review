# OpenClawBot Feishu Work Intake Readiness Review v1

## Verdict

`OpenClawBot` is ready for **formal work-only Feishu usage**.

This is not a generic multimodal bot release. It is a scoped cutover:

- Feishu default route no longer falls into `main`
- work asks now enter the dedicated `feishu-intake` lane
- the intake lane hands off into `openmind_advisor_ask`
- the advisor substrate remains ChatgptREST `/v3/agent/turn`

## What Changed

### Repo

- `scripts/rebuild_openclaw_openmind_stack.py`
  - added `feishu-intake` agent spec
  - switched Feishu default binding to `feishu-intake`
  - generated managed workspace content for the new work-only intake lane
- `chatgptrest/eval/openclawbot_meeting_intake_smoke.py`
  - updated Feishu route/session-key expectations from `main` to `feishu-intake`
- `tests/test_rebuild_openclaw_openmind_stack.py`
  - updated topology/config expectations for `feishu-intake`
- `tests/test_openclawbot_meeting_intake_smoke.py`
  - updated route/session-key expectations

### Live Runtime

- patched live config:
  - `/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json`
- rewrote managed workspace files:
  - `/vol1/1000/openclaw-workspaces/feishu-intake`
- created dedicated live agent dir:
  - `/home/yuanhaizhou/.home-codex-official/.openclaw/agents/feishu-intake`
- restarted:
  - `openclaw-gateway.service`

## Evidence

### Binding + agent presence

- live config now contains:
  - `{"channel":"feishu","accountId":"default"} -> "feishu-intake"`
- live config also contains:
  - `agent id = feishu-intake`
  - `tool profile = minimal`
  - `alsoAllow = ["openmind_advisor_ask"]`

### Meeting-intake smoke

- artifact:
  - [report_v2.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/openclawbot_meeting_intake_smoke/20260410T1517Z/report_v2.json)
- result:
  - `4/4 pass`
- key proof:
  - `route_session_key = agent:feishu-intake:feishu:chat:oc_chat_1`
  - `openmind_advisor_ask` appears in the bridge tool set
  - attachments/media still project into `/v3/agent/turn`

### Advisor substrate still healthy

- artifact:
  - [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_main_path_gate_20260403_v2/report_v1.json)
- result:
  - `5/5 pass`
- key proof:
  - `openmind_advisor_ask -> task_list -> task_get -> session_get -> cancel` remains live on `18711`

### Real intake-agent transcript

- transcript:
  - `/home/yuanhaizhou/.home-codex-official/.openclaw/agents/feishu-intake/sessions/8ba11bbf-e228-413f-9d0e-9a0271de4a35.jsonl`
- key proof:
  - first assistant tool call is `openmind_advisor_ask`
  - no `read`-first image commentary behavior on this validation run

## Scope Boundary

Ready now:

- work-related Feishu asks
- screenshots/files as work materials
- planning/research/report style work intake through the advisor lane

Not claimed by this cutover:

- education / parenting
- finbot / investment
- generic life chat
- full non-work multimodal support
- old `feishu_handler.py` path parity

## Operator Note

Formal usage should start from the Feishu `OpenClawBot` entry now.

Use it as:

- project planning
- visit / cooperation preparation
- stakeholder reply drafting
- work research / report organization
- work material capture from screenshots and files

Do not use this entry as the general personal bot.

