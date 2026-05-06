# OpenClaw / OpenMind Unified Agent Business Integration Test Plan v1

Date: 2026-03-17

## Goal

Verify that the public advisor-agent surface behaves like a real agent for actual client workflows, not just for isolated unit calls.

The plan covers:

- public HTTP agent facade: `/v3/agent/turn`, `/v3/agent/session/{session_id}`, `/v3/agent/cancel`
- public MCP facade: `advisor_agent_turn`, `advisor_agent_status`, `advisor_agent_cancel`
- OpenClaw `openmind-advisor` plugin
- agent-first CLI surfaces: `chatgptrest cli agent ...` and `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
- rebuild/config convergence for OpenClaw plugin provisioning
- actual execution lanes behind the facade: ChatGPT Pro, Gemini Deep Think, Gemini Deep Research, dual-model consult, Gemini image generation

## Out Of Scope

- legacy low-level MCP tools as standalone UX surface
- dashboard UX flows
- external OpenClaw repo code changes beyond the plugin shipped in this repo
- long-running production soak beyond one targeted business pass per lane

## Preconditions

- ChatgptREST API running on `127.0.0.1:18711`
- worker send/wait processes running
- ChatGPT Web and Gemini Web already authenticated in the browser automation environment
- `OPENMIND_API_KEY` or `CHATGPTREST_API_TOKEN` configured
- OpenClaw plugin bundle rebuilt from current repo state before plugin-level business tests
- test artifacts directory writable
- at least one realistic attachment bundle prepared:
  - a small repo zip for code review
  - one reference image for Gemini image generation

## Automated Gate

These automated suites must pass before manual business validation starts:

- `tests/test_agent_v3_routes.py`
- `tests/test_agent_mcp.py`
- `tests/test_skill_chatgptrest_call.py`
- `tests/test_openclaw_cognitive_plugins.py`
- `tests/test_rebuild_openclaw_openmind_stack.py`
- `tests/test_mcp_advisor_tool.py`
- `tests/test_advisor_v3_end_to_end.py`
- `tests/test_cli_improvements.py`
- `tests/test_routes_advisor_v3_security.py`

## Environment Matrix

| Lane | Entry Surface | Underlying Lane | Core Risk |
|---|---|---|---|
| A | HTTP `/v3/agent/turn` | ChatGPT Pro ask | facade returns only submitted state |
| B | HTTP `/v3/agent/turn` | Gemini Deep Think | wrong preset or provider drift |
| C | HTTP `/v3/agent/turn` | Gemini Deep Research | deep research flags / long wait / followup state |
| D | HTTP `/v3/agent/turn` | Consult (ChatGPT Pro + Gemini DT) | facade fails to combine multi-job result |
| E | HTTP `/v3/agent/turn` | Gemini image generation | wrong prompt field / attachment forwarding |
| F | Public MCP | same as A-E | MCP payload drops attachments or identity |
| G | `chatgptrest_call.py` | same as A-E | legacy flags silently discarded |
| H | OpenClaw plugin | same as A-E through `/v3/agent/turn` | plugin still calling old `/v2` or polling `/v1/jobs/*` directly |
| I | Rebuild stack | plugin config generation | generated config drifts back to old fields |

## Test Scenarios

### BI-01 ChatGPT Pro repo review through HTTP agent facade

Request:

- `goal_hint=code_review`
- attachment: repo zip
- depth: `deep`

Steps:

1. `POST /v3/agent/turn` with repo zip attachment.
2. Record `session_id`, `run_id`, `job_id`, `route`, `final_provider`.
3. If the response is already final, validate answer quality.
4. If the response is still running, poll `GET /v3/agent/session/{session_id}` until terminal.

Expected:

- answer is delivered through the agent response, not by manual `/answer` paging
- provenance contains `job_id`
- attachment is forwarded into the underlying job input
- session status eventually reaches `completed` or a meaningful non-success terminal state

Evidence:

- request/response payloads
- `artifacts/jobs/<job_id>/request.json`
- answer artifact preview
- session status snapshots

### BI-02 Gemini Deep Think repo review through HTTP agent facade

Request:

- `goal_hint=gemini_research`
- attachment: repo zip

Expected:

- created job uses `kind=gemini_web.ask`
- preset normalizes to Deep Think path
- response provenance shows Gemini as final provider
- no fallback to ChatGPT-only route mapping

Evidence:

- job request artifact
- events showing Gemini execution
- final answer or actionable `needs_followup`

### BI-03 Gemini Deep Research through HTTP agent facade

Request:

- `goal_hint=gemini_deep_research`
- attachment: repo zip or markdown research packet

Expected:

- created job uses `kind=gemini_web.ask`
- params include `deep_research=true`
- long wait returns final answer when available, otherwise running/needs_followup with same session continuity

Evidence:

- request artifact params
- conversation URL if present
- terminal answer or explicit blocker state

### BI-04 Dual-model review through HTTP agent facade

Request:

- `goal_hint=dual_review`
- prompt asks for explicit disagreement / second opinion

Expected:

- facade creates a consultation, not a single ChatGPT-only job
- provenance contains `consultation_id`
- answer contains both model lanes or an explicit partial state
- `cancel` can target all underlying child jobs

Evidence:

- consultation job list
- combined answer text
- cancel response listing cancelled child job ids

### BI-05 Gemini image generation through HTTP agent facade

Request:

- `goal_hint=image`
- message contains image prompt
- optional reference image attachment

Expected:

- underlying kind is `gemini_web.generate_image`
- prompt is forwarded via `input.prompt`, not `input.question`
- file attachments land in `input.file_paths`
- returned answer contains generated image markdown or clear failure state

Evidence:

- request artifact
- output markdown
- generated files under `artifacts/jobs/<job_id>/images/`

### BI-06 Same-session follow-up continuity

Steps:

1. Complete any successful agent turn.
2. Send a second turn with the same `session_id`.
3. Verify stored session state updates rather than creating a broken detached flow.

Expected:

- second turn reuses the same logical session
- follow-up context survives into route selection and underlying job input
- status endpoint reflects the latest message and latest answer

### BI-07 Running / cooldown / needs_followup session refresh

Steps:

1. Trigger a lane that is likely to remain pending briefly, or simulate by shortening timeout.
2. Call `/v3/agent/session/{session_id}` while the task is not terminal.

Expected:

- session endpoint refreshes live state from the underlying job or consultation
- `status` is one of `running`, `needs_followup`, `failed`, `completed`, `cancelled`
- `next_action` is actionable and consistent with the underlying state

### BI-08 Session cancel propagation

Run this for:

- a single-job session
- a consultation session with multiple child jobs

Expected:

- `POST /v3/agent/cancel` updates session status to `cancelled`
- single-job session attempts underlying job cancel
- consult session attempts cancel for every child job id
- returned payload lists cancelled job ids

### BI-09 Public MCP business pass

Run the same scenario set as BI-01 to BI-05, but from the public MCP surface:

- `advisor_agent_turn`
- `advisor_agent_status`
- `advisor_agent_cancel`

Expected:

- attachments survive MCP transport
- `role_id`, `user_id`, `trace_id` survive MCP transport
- MCP users do not need to see low-level `/v1/jobs/*` details

### BI-10 Agent-first skill wrapper business pass

Surface:

- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`

Use a realistic repo review command including:

- `--file-path`
- `--github-repo`
- `--conversation-url`
- `--parent-job-id`
- `--role-id`
- `--user-id`
- `--trace-id`

Expected:

- wrapper emits `chatgptrest cli agent turn`
- repo/file/trace context is preserved through `--context-json`
- no legacy context is silently dropped in agent mode

### BI-11 OpenClaw plugin business pass

Surface:

- `openmind-advisor` plugin inside a rebuilt OpenClaw environment

Checks:

- plugin source calls `/v3/agent/turn`
- plugin no longer depends on direct `/v2/advisor/*` or `/v1/jobs/*/wait` choreography
- runtime `session_id`, `account_id`, `thread_id`, `agent_id`, `user_id` reach the agent facade

Business execution:

1. Trigger `openmind_advisor_ask` from OpenClaw with a slow-path task.
2. Validate final answer formatting and provenance text.
3. Confirm there is no separate client-managed wait loop.

### BI-12 Rebuild / deployment convergence

Surface:

- `scripts/rebuild_openclaw_openmind_stack.py`
- shipped plugin manifest

Expected:

- generated plugin config uses `defaultGoalHint`, not legacy `defaultMode`
- generated OpenClaw config still points to `127.0.0.1:18711`
- rebuilt plugin bundle matches the shipped README/manifests/source

### BI-13 Auth matrix

Cover:

- no auth configured -> `503`
- wrong `X-Api-Key` -> `401`
- wrong Bearer token -> `401`
- correct `X-Api-Key` -> success
- correct Bearer token -> success

Expected:

- clients can distinguish misconfiguration from bad credentials

### BI-14 Fault and blocker handling

Inject or simulate:

- blocked
- cooldown
- needs_followup
- error

Expected:

- facade does not lose underlying identifiers
- session status remains queryable
- `next_action` makes sense for retry vs human intervention
- cancel still behaves safely

## Manual Evidence Checklist

- save raw request/response JSON for every BI case
- save `session_id`, `run_id`, `job_id`, `consultation_id`
- capture `events.jsonl`, `request.json`, `result.json`, `answer.*`, `conversation.json` when available
- for OpenClaw, save plugin transcript and generated OpenClaw config snippet
- for image generation, save resulting image paths and markdown output

## Exit Criteria

The rollout is acceptable only if all of the following are true:

- all automated gate suites pass
- BI-01 to BI-05 pass on at least one real business prompt each
- BI-08 cancel propagation is verified for both single-job and consult sessions
- BI-11 proves OpenClaw now depends on the public agent surface
- BI-12 proves rebuild output does not regress the converged config
- no case requires the client to manually use `/v1/jobs/{job_id}/wait` or `/answer`

## Known Residual Risks

- the controller-backed path is still quality-gated mainly by controller/runtime behavior, not by a dedicated agent judge loop
- consultation output is currently a combined multi-answer delivery, not a synthesized meta-answer
- long-running Gemini Deep Research still depends on the existing worker/runtime reliability envelope
