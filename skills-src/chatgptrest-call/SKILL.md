---
name: chatgptrest-call
description: Use ChatgptREST from coding agents through the public advisor-agent MCP by default, with a legacy queued-job fallback only for controlled maintenance or expert overrides.
metadata:
  short-description: Agent-first ChatgptREST caller
---

# ChatgptREST Call (Codex)

Use this skill when the user asks to:
- send a coding-agent task through the public advisor-agent MCP,
- use `task_intake` / `contract_patch` / `workspace_request`,
- request `thinking_heavy` / `deep_research` / `report_grade`,
- run a long model call with durable artifacts,
- or retrieve full answer/conversation without truncation in controlled legacy mode.

## Why this skill

- Uses ChatgptREST server-side control plane, session continuity, and queue/retry/idempotency.
- Uses machine-readable JSON outputs by default.
- In agent mode, projects `task_intake`, `control_plane`, `clarify_diagnostics`, `lifecycle`, `delivery`, and `effects`.
- Stores long answers/conversation exports into files for follow-up automation when legacy mode is explicitly needed.

## Read first

- `scripts/chatgptrest_call.py` (public-MCP-first wrapper)
- Optional direct CLI from repo root: `./.venv/bin/python -m chatgptrest.cli`

## Hard rules

- Prefer ChatgptREST; do not bypass with ad-hoc browser prompting when the task is a queued job.
- For coding agents, default to public advisor-agent MCP, not direct REST.
- For public GitHub repo review on ChatGPT web, pass the repo URL directly. A separate review repo is optional and only justified for private mirrors, curated subsets, or import-size control.
- For `Gemini DeepThink / GeminiDT / web-only Gemini review`, do not switch to Gemini CLI, plain MCP text calls, or API-key flows. These tasks must stay on `gemini_web.ask` or on a higher-level surface that compiles to `gemini_web.ask`.
- `gemini_cli` is a different local-login lane. It is not a substitute for `gemini_web.ask` repo review or imported-code review.
- Always use an explicit `idempotency_key` for reproducibility.
- Save long output to files (`out_answer`, `out_conversation`) instead of pasting huge text in chat.
- If a failure looks infra-related, include `job_id`, `conversation_url`, and `reason/error` in your report.
- Do not run trivial prompts on ChatGPT Pro presets (e.g. "OK", "请回复OK").
- Smoke tests should prefer non-Pro paths and should not teach deprecated Qwen paths.
- For ChatGPT Pro sends, keep at least a 61-second interval (wrapper enforces by default).
- If the task is long-running and Codex should continue other work, do not teach or rely on legacy MCP bare wait tools by name. Prefer the public advisor-agent MCP surface for coding agents; reserve direct REST `/v3/agent/*` session APIs for internal runtime/integration cases.
- Do not hard-code legacy bare MCP names such as `chatgptrest_ask`, `chatgptrest_consult`, `chatgptrest_ops_status`, or `chatgptrest_job_wait*` in prompts or task specs.
- Gemini follow-up should prefer `parent_job_id`; do not pin the old `conversation_url` as the only truth source.
- For Gemini Deep Think / Deep Research follow-up, do not manually send a second “开始研究 / OK” rescue prompt. The server may auto-progress one research-plan stub; the client should keep following the same `job_id`.

## Default mode

For coding agents, the default mode is agent/public MCP mode:

- canonical URL: `http://127.0.0.1:18712/mcp`
- canonical tools:
  - `advisor_agent_turn`
  - `advisor_agent_status`
  - `advisor_agent_cancel`
  - `advisor_agent_wait`
- canonical high-level objects:
  - `task_intake`
  - `contract_patch`
  - `workspace_request`

Behavior notes:
- `advisor_agent_turn.attachments` may be a single path string or `list[string]`; the public MCP normalizes it server-side.
- If a long-running turn returns `accepted_for_background=true`, use `advisor_agent_wait(session_id, timeout_seconds)` or `advisor_agent_status(session_id)` instead of inventing custom polling semantics.
- The repo wrapper now follows the same streamable-HTTP MCP handshake as the validation harness: `initialize` first, then `tools/call` with the negotiated MCP session headers. Public MCP is sessionful by default, so a healthy `initialize` should return `mcp-session-id`; do not reintroduce bare `tools/call` shortcuts or stateless assumptions.
- For review/research/report/image style agent tasks, or whenever attachments / `github_repo` / `enable_import_code` are present, the wrapper now requests `delivery_mode=deferred`, writes an early summary snapshot with the generated `session_id`, and then waits through `advisor_agent_wait` instead of holding a long opaque sync `advisor_agent_turn` call open.
- Sync agent turns also advance the early summary past MCP bootstrap before blocking on `advisor_agent_turn`; clients should now see `submission_started=true` / `status=submitted` instead of an `initialized`-only snapshot.
- In agent mode, `--job-timeout-seconds/--timeout-seconds` is the total run budget. `--request-timeout-seconds` is only the transport timeout and now auto-derives from that budget unless you override it explicitly.
- Agent mode rejects legacy jobs wait/export flags such as `--run-wait-timeout-seconds`, `--out-conversation`, and related conversation retry flags. Those belong to `--no-agent --maintenance-legacy-jobs`.
- Public MCP now preserves the upstream MCP caller identity in `task_intake.context.client` (`mcp_client_name`, `mcp_client_version`, `mcp_client_id`) instead of collapsing every caller into a generic `mcp-agent`.
- Public advisor-agent is for user-facing end-to-end turns only. Structured extractor / JSON-only microtasks and sufficiency gates now fail fast with `public_agent_microtask_blocked`.
- If the same MCP caller re-submits an equivalent heavy `research/report/code_review` turn while an earlier one is still running, the service now returns `duplicate_public_agent_session_in_progress` plus the existing `session_id` and `wait_tool=advisor_agent_wait`. This still applies when the caller generated a new `session_id`; only true resume/patch calls against the same existing session bypass dedupe. Reuse the returned session instead of resubmitting.
- Agent responses and summary files now expose `provenance.provider_selection` when a provider was requested, so clients can see requested provider, final provider family, and whether fallback occurred.
- Local preflight failures now emit `submission_started=false` plus a concrete `failure_stage` (`preflight`, `initialize_mcp`, `submit_turn`, `wait`) so clients do not poll `advisor_agent_status` for requests that never left the wrapper.

Use legacy provider queue mode only when the task explicitly needs low-level maintenance, provider debugging, or artifact-oriented `/v1/jobs` behavior. Coding agents must not treat it as a normal execution path.

### Gemini DeepThink / GeminiDT rule

If the user explicitly wants:

- `GeminiDT`
- `Gemini DeepThink`
- web-only Gemini review
- a Gemini review that depends on the consumer web capability

then the valid channel is:

- `kind=gemini_web.ask`
- or a public advisor-agent surface that resolves to `gemini_web.ask`

Do **not**:

- fall back to Gemini CLI
- reinterpret the task as a generic text-model call
- blame OAuth/API key setup for a DeepThink failure path

If the current execution path cannot reach `gemini_web.ask`, fail fast and report the channel mismatch.

## Legacy provider mapping

- `provider=chatgpt` -> `kind=chatgpt_web.ask`, default `preset=pro_extended`
- `provider=gemini` -> `kind=gemini_web.ask`, default `preset=pro`

## Workflow

1. Build a compact call plan:
   - default: agent/public MCP
   - optional `goal_hint`
   - optional `execution_profile`
   - optional `task_intake` / `contract_patch` / `workspace_request`
   - only if explicitly needed: provider/preset and legacy job outputs
2. Run wrapper script.
3. Return:
   - `job_id`
   - `status`
   - output file paths
   - short result summary and next action

## Preferred command

```bash
/usr/bin/python3 skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --question "请总结面试纪要" \
  --goal-hint planning \
  --out-summary /tmp/chatgptrest-summary.json
```

The script prints one JSON object (stdout), suitable for agent parsing.
In agent mode the summary file contains:

- `mode=agent_public_mcp`
- `session_id`
- `route`
- `provider_selection` (when provider was requested)
- `lifecycle`
- `delivery`
- `effects`
- `result`

### Thinking-heavy example

```bash
/usr/bin/python3 skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --question "先给我一个快速但有深度的研究判断，不要走 deep research" \
  --goal-hint research \
  --execution-profile thinking_heavy \
  --out-summary /tmp/chatgptrest-thinking-heavy-summary.json
```

### Same-session contract patch example

```bash
/usr/bin/python3 skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --question "继续同一个 session，补齐 audience 和 decision" \
  --session-id agent_sess_xxx \
  --contract-patch-json '{"decision_to_support":"是否进入下一轮","audience":"招聘经理"}' \
  --goal-hint planning \
  --out-summary /tmp/chatgptrest-patch-summary.json
```

### Workspace request example

```bash
/usr/bin/python3 skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --workspace-request-json '{"spec_version":"workspace-request-v1","action":"deliver_report_to_docs","payload":{"title":"日报","body_markdown":"# 日报"}}' \
  --out-summary /tmp/chatgptrest-workspace-summary.json
```

## Legacy queued-job example

```bash
/usr/bin/python3 skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --no-agent \
  --maintenance-legacy-jobs \
  --provider gemini \
  --preset pro \
  --idempotency-key my-task-001 \
  --question "..." \
  --out-answer /tmp/my-task-answer.md \
  --out-conversation /tmp/my-task-conversation.json
```

By default it auto-discovers the ChatgptREST repo root from the script location. If the skill is copied outside this repository, set `CHATGPTREST_ROOT=/path/to/ChatgptREST`.

Policy defaults in wrapper:

- Blocks trivial prompts on ChatGPT Pro presets unless `--allow-trivial-pro`.
- Blocks `--purpose smoke` with any `pro*` preset unless `--allow-pro-smoke`.
- Treat live ChatGPT smoke as exceptional; prefer Gemini or the public agent facade for low-value probes instead of creating real `chatgpt_web.ask` threads.
- Enforces minimal interval for ChatGPT Pro sends (`--min-send-interval-seconds`, default `61`).
- Always sends `--purpose` to ChatgptREST (`params.purpose`) for server-side policy/audit.
- If `--out-conversation` is requested, the wrapper now does bounded retries when the server returns `409 conversation export not ready` (because conversation export may lag behind job completion).
- Legacy mode now requires `--maintenance-legacy-jobs` and stamps `CHATGPTREST_CLIENT_NAME=chatgptrestctl-maint`, so the fallback path stays auditable and is not silently reused by coding agents. If it falls through to low-level web ask, you also need the matching `CHATGPTREST_ASK_HMAC_SECRET_*` env so the wrapper can sign the request.
- Legacy mode success/error payloads now print `resolved_runtime` so the client can see the effective ChatgptREST root, Python interpreter, transport timeout, and concrete command.
- Agent-mode timeout/transport failures now keep the generated `session_id` in the error payload so clients can recover with `advisor_agent_status` / `advisor_agent_wait` instead of blindly resubmitting.
- Agent-mode local validation failures do not claim `still_running_possible=true`; only post-submit transport failures are treated as recoverable remote runs.
- If a sandboxed Codex shell cannot open loopback HTTP to `127.0.0.1:18711`, do not invent ad-hoc curl variants. Treat that as a transport constraint and use the repository-documented ChatgptREST MCP path instead, while recording the gap.

Install notes:
- Keep the source of truth in `skills-src/chatgptrest-call`
- Install or symlink it into the active Codex home under `skills/chatgptrest-call`

## Legacy advanced examples

ChatGPT Deep Research (legacy low-level path):

```bash
/usr/bin/python3 skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --no-agent \
  --maintenance-legacy-jobs \
  --provider chatgpt \
  --preset pro_extended \
  --deep-research \
  --idempotency-key dr-20260221-01 \
  --question "..." \
  --out-answer /tmp/dr-answer.md
```

Gemini Pro + import code (legacy low-level path):

```bash
/usr/bin/python3 skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --no-agent \
  --maintenance-legacy-jobs \
  --provider gemini \
  --preset pro \
  --enable-import-code \
  --github-repo https://github.com/haizhouyuan/homeagent/tree/master \
  --idempotency-key gem-pro-20260221-01 \
  --question "..." \
  --out-answer /tmp/gem-answer.md
```
