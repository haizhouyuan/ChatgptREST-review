---
name: chatgptrest-call
description: Use ChatgptREST from coding agents through the public MCP automation-kernel-v1 lane only, with legacy queued jobs kept only for controlled maintenance.
metadata:
  short-description: Agent-first ChatgptREST caller
---

# ChatgptREST Call (Codex)

Use this skill when the user asks to:
- send a shared automation task through the public MCP automation-kernel-v1 lane,
- run a long model call with durable artifacts,
- or retrieve full answer/conversation without truncation in controlled legacy mode.

## Why this skill

- Uses ChatgptREST server-side control plane, session continuity, and queue/retry/idempotency.
- Uses machine-readable JSON outputs by default.
- In agent mode, returns a submit receipt with push/background delivery semantics instead of foreground wait loops.
- Stores long answers/conversation exports into files for follow-up automation when legacy mode is explicitly needed.

## Read first

- `scripts/chatgptrest_call.py` (public-MCP-first wrapper)
- Optional direct CLI from repo root: `./.venv/bin/python -m chatgptrest.cli`

## First classify the request

Before choosing flags or tools, classify the user's ask. This prevents the two recurring failure modes: over-constraining a high-value research ask, and re-submitting around an already-running web job.

| User intent | Use | Do not do |
| --- | --- | --- |
| Ask a new long-running model question | wrapper / public MCP `automation_ask` with explicit provider, preset, idempotency key, preflight, provider-selection rationale, and background receipt | Do not foreground-wait or lower timeout just to finish the agent turn |
| Retrieve an existing web conversation by URL | `automation_conversation_find/fetch/get` when exposed; otherwise create `kind=chatgpt_web.conversation_export` with `manual_harvest=true`, `read_only_harvest=true`, `backend_mode=dom_only`, `answer_format=markdown` | Do not send a prompt, follow-up, or browser click just to export a human-created conversation |
| Check status or fetch a known job answer | `automation_result`, `automation_job_status`, `automation_job_events`, then `automation_job_answer` for chunks | Do not create a replacement job unless the old one is terminal and the failure reason is understood |
| Pro architecture/code review over local artifacts | Build a compact memo/zip/code snapshot first, then submit asynchronously with an explicit evidence boundary | Do not send a bare prompt that makes Pro rediscover local facts |
| Tool selection, benchmarks, current provider comparison, or time-sensitive facts | Allow or request current external research; use Deep Research only when the user asks for it or citations/current-source discovery are central | Do not add a default "no web search / no Deep Research" clause |
| Local closure/gate review | Attachment-first review; ask for Missing Evidence if attachments are insufficient | Do not let the model invent facts outside the packet |
| Gemini DeepThink / GeminiDT / web-only Gemini review | `provider=gemini`, `preset=deep_think`, through `gemini_web.ask` or the public automation surface | Do not switch to Gemini CLI or API-key flow |
| 429, concurrency, cooldown, send-stage failure, or no final answer | Use the failure taxonomy below and keep the same idempotency key / same job / same conversation where possible | Do not change keys and retry in a loop |

## Evidence boundary policy

Every high-value ask should state its evidence boundary explicitly, and `provider_selection` should mirror it:

- `attachment_first`: local code/artifacts are authoritative; external facts are not required. Use for closure, gate, local runtime, and code snapshot reviews.
- `current_research_allowed`: local artifacts are provided, but current external facts may change the answer. Use for tool selection, provider comparison, benchmarks, product choices, or anything time-sensitive.
- `deep_research_requested`: the user wants cited/current-source research or broad external discovery. Use `--deep-research` / `deep_research=true` deliberately.

Do not encode the boundary as a blanket ban by default. "No web search / no Deep Research" is a valid task-specific instruction only when the user or acceptance criteria explicitly want attachment-only judgment.

## Hard rules

- Prefer ChatgptREST; do not bypass with ad-hoc browser prompting when the task is a queued job.
- For coding agents, default to public MCP `automation_*`, not direct REST.
- For public GitHub repo review on ChatGPT web, pass the repo URL directly. A separate review repo is optional and only justified for private mirrors, curated subsets, or import-size control.
- For `Gemini DeepThink / GeminiDT / web-only Gemini review`, do not switch to Gemini CLI, plain MCP text calls, or API-key flows. These tasks must stay on `gemini_web.ask` or on a higher-level surface that compiles to `gemini_web.ask`.
- Wrapper remediation note:
  - ChatGPT Pro review now prefers reusing an existing healthy ChatGPT CDP tab instead of forcing a fresh tab in CDP mode, to avoid Cloudflare interstitial pages that hide the prompt box.
  - ChatGPT Pro review-style agent calls are serialized on the shared review/CDP lane by default, so two long review jobs do not concurrently re-trigger `verification_pending` on the same browser surface.
  - If a deferred ChatGPT Pro review returns `needs_followup + same_session_repair` because the lane entered `verification_pending`, the wrapper now waits through the published cooldown and automatically resumes the **same session** instead of requiring a manual browser fallback.
  - If `same_session_repair` is caused by `WebRetryBudgetExceeded`, the wrapper now first submits a guarded `repair.autofix` runtime recovery (`capture_ui/clear_blocked/refresh`), waits for that repair job to finish, and only then resumes the same session.
  - Gemini imported-code review now fail-opens only in the narrow review-safe case where the public repo URL is present **and** review packet attachments are already attached; it continues on `gemini_web.ask` with the review packet instead of silently switching channels.
- `gemini_cli` is a different local-login lane. It is not a substitute for `gemini_web.ask` repo review or imported-code review.
- Always use an explicit `idempotency_key` for reproducibility.
- `--file-path` values are resolved by the wrapper against the caller's current working directory before submission. Prefer absolute paths in scripts anyway; changing the same job from relative to absolute after creation can still create an idempotency collision on older clients.
- Save long output to files (`out_answer`, `out_conversation`) instead of pasting huge text in chat.
- If a failure looks infra-related, include `job_id`, `conversation_url`, and `reason/error` in your report.
- Do not run trivial prompts on ChatGPT Pro presets (e.g. "OK", "请回复OK").
- Smoke tests should prefer non-Pro paths and should not teach deprecated Qwen paths.
- For ChatGPT Pro sends, keep at least a 61-second interval (wrapper enforces by default).
- If the task is long-running and Codex should continue other work, do not teach or rely on foreground wait loops. Prefer the public MCP `automation_*` submit receipt plus background push semantics.
- Do not hard-code legacy bare MCP names such as `chatgptrest_ask`, `chatgptrest_consult`, `chatgptrest_ops_status`, or `chatgptrest_job_wait*` in prompts or task specs.
- `ChatGPT Pro` and `Deep Research` are different asks. If the user says “问 Pro”，use `provider=chatgpt` + `preset=pro_extended` without `--deep-research` unless they explicitly ask for Deep Research.
- Time expectation rule for `问 Pro`:
  - Do **not** imply that a ChatGPT Pro ask will produce an immediate final answer in the same foreground turn.
  - For substantial Pro judgment / review / long-answer tasks, set the expectation that end-to-end completion commonly takes **30-60 minutes** and can exceed **40 minutes** when the answer is genuinely thinking-heavy.
  - Default posture: submit asynchronously, keep working, and treat the first response as a receipt / background run handoff unless the task is explicitly scoped as a short quick judgment.
- ChatGPT Pro / Thinking finality discipline:
  - Visible “Pro thinking” in the browser is not the authority. Treat backend/export metadata (`model_observed_export`, `thinking_effort`, selected provider/preset) as model-selection evidence.
  - `status=completed` alone is not enough for external-review evidence. The answer must be usable, not a prompt echo, stale DOM text, truncated section, or generic shallow summary that fails the ask.
  - If a Pro answer is late, keep the same `job_id` / same conversation and wait on background push/status. Do not send corrective follow-ups on short intervals just because the first visible text looks incomplete.
  - Before sending a same-thread corrective follow-up, inspect `automation_job_events` / `automation_result` for finality signals. Red flags include `awaiting_assistant_answer`, `browser_retry_scheduled`, `completion_guard_downgraded`, `matched_assistant_still_in_progress`, `thinking_send_timeout_without_complete_export`, prompt echo, or current export SHA changing while answer text is not final.
  - A prompt echo is not progress. Repeated `wait_partial_answer_echo_observed`, or a constant short preview matching the latest user prompt, means the wait/export layer is on a no-answer plateau; keep the same job and let the server's wait guard terminalize it instead of sending more corrective prompts.
  - A quick but complete Pro answer can be a low-value answer, not necessarily a wrong-model answer. Record it as quality failure and ask one sharper same-thread follow-up only after the prior turn is final.
- For `ChatGPT Pro` internal technical judgment / architecture-review asks, do not send a bare question when local repo/runtime facts are already available. First write a compact local context memo and attach it with `--file-path`, then state the intended evidence boundary explicitly. Do **not** add a blanket "no web search / no Deep Research" restriction by default: use an attachment-only boundary only when the user or task explicitly wants local-evidence judgment, and allow current external research when the task is tool selection, market/current-source comparison, or asks for up-to-date facts.
- Gemini follow-up should prefer `parent_job_id`; do not pin the old `conversation_url` as the only truth source.
- For Gemini Deep Think / Deep Research follow-up, do not manually send a second “开始研究 / OK” rescue prompt. The server may auto-progress one research-plan stub; the client should keep following the same `job_id`.
- For `Gemini DeepThink` requests, explicitly set `preset=deep_think`. Do not submit `preset=pro` and rely on `provider_selection` prose to imply DeepThink; if the tool receipt shows `effective_preset=pro`, treat that as a wrong-lane submission and stop before using it as evidence.
- If `automation_job_cancel` returns `ExplicitCancelReasonRequired`, call it with an explicit business reason. If the active Codex tool schema does not expose a `reason` argument, the MCP service/client schema is stale: restart `chatgptrest-mcp.service` and start a fresh client session instead of issuing no-reason cancels or ad-hoc browser actions.
- If a heavy ask is rejected with `low_level_ask_client_concurrency_exceeded`, do not change idempotency keys and resubmit in a loop. Inspect the listed `active_job_ids`; wait for a real terminal state or cancel a confirmed stale/superseded job with an explicit reason.

## Recurring Client Failure Playbook

Use this taxonomy before retrying a Pro, Deep Research, or GeminiDT request:

- **No job created**: local preflight, attachment path, provider-selection JSON, or MCP transport failed before `job_id`. Fix the request construction and reuse the same business idempotency key; do not tell the user Pro failed.
- **Job created but no `prompt_sent_at`**: send-stage/runtime problem (`TargetClosedError`, browser restart, frontend cooldown, manual guard, SSE timeout). Do not count this as external review evidence. Check events and runtime health before retrying.
- **`prompt_sent_at` but no final answer**: wait/export/finality problem. Inspect `automation_job_events` for `deep_research_pending_from_export`, `completion_guard_downgraded`, `wait_partial_answer_echo_observed`, or `WebRetryBudgetExceeded`. Continue the same job or same conversation; do not open a new job unless the old one is terminal and the reason is understood.
- **Concurrency or 429 rejection**: this is admission control, not model failure. Preserve the existing idempotency key, inspect `active_job_ids`, and wait or explicitly cancel only stale/superseded jobs.
- **Short Pro answer / progress stub**: not usable evidence. Record it as `needs_followup` / repair on the same session after finality is established.
- **Architecture/local-runtime review**: prefer compact local memo + zip/code snapshot and state the evidence boundary. Do not default-ban web search or Deep Research; decide from the user request. Use attachment-only review for local closure/gate checks, and use external/current-source research for tool selection, benchmark comparison, or time-sensitive facts.

Fix location rule:

- Put it in **server code** when the condition is observable from job state, export metadata, browser status, rate-limit state, or attachment contracts.
- Put it in the **wrapper/skill** when the condition is caller construction discipline: file path normalization, idempotency reuse, Pro-vs-Deep-Research selection, status wording, and handoff records.
- Put it in **client project docs/templates** only after the server/wrapper cannot enforce it without task-specific judgment.

## Default mode

For coding agents, the default mode is public MCP `automation-kernel-v1`:

- canonical URL: `http://127.0.0.1:18712/mcp`
- canonical tools:
  - `automation_ask`
  - `automation_result`
  - `automation_job_create`
  - `automation_job_status`
  - `automation_job_answer`
  - `automation_job_events`
  - `automation_job_cancel`
  - `automation_conversation_fetch` / `automation_conversation_get` / `automation_conversation_find` when the active MCP schema exposes them
- canonical ask objects:
  - `idempotency_key`
  - `question`
  - `provider`
  - `preset`
  - `parent_job_id`
  - `conversation_url`
  - `file_paths`
  - `deep_research`

Behavior notes:
- The repo wrapper now follows the same streamable-HTTP MCP handshake as the validation harness: `initialize` first, then `tools/call` with the negotiated MCP session headers. Public MCP is sessionful by default, so a healthy `initialize` should return `mcp-session-id`; do not reintroduce bare `tools/call` shortcuts or stateless assumptions.
- For automation-kernel asks, the wrapper now submits `automation_ask`, writes an early summary snapshot with the generated `job_id`, and returns the submit receipt immediately. Front clients should continue other work and rely on push/background completion instead of foreground wait or client polling.
- For `provider=chatgpt` + `preset=pro_extended`, agents should assume an **async human-scale wait** by default: long Pro asks frequently need about **30 minutes** before a stable final answer is available. Plan user messaging and orchestration around receipt-now / answer-later semantics, not immediate foreground completion.
- The wrapper default budget is intentionally long for ChatGPT Pro: `pro_extended` defaults to 3600 seconds, and `pro_extended + --deep-research` defaults to 7200 seconds unless `--job-timeout-seconds` is explicitly set. Do not lower this for high-value Pro review just to make a foreground turn finish faster.
- Client agents should submit a preflight checklist and provider-selection rationale together with the prompt and attachments. The server does lightweight hard validation only; task understanding stays client-side.
- For ChatGPT Pro review-style runs, keep the default `--serialize-chatgpt-review-lane`; disabling it is an expert-only override and reopens the shared-lane verification risk.
- Sync agent turns now advance the early summary past MCP bootstrap and stop at submit receipt; clients should see `submission_started=true` / `status=submitted` plus the returned push receipt instead of an `initialized`-only snapshot.
- In agent mode, `--job-timeout-seconds/--timeout-seconds` is the total run budget. `--request-timeout-seconds` is only the transport timeout and now auto-derives from that budget unless you override it explicitly.
- Agent mode rejects legacy jobs wait/export flags such as `--run-wait-timeout-seconds`, `--out-conversation`, and related conversation retry flags. Those belong to `--no-agent --maintenance-legacy-jobs`.
- Public MCP preserves the upstream MCP caller identity via `client.mcp_client_name` / `client.mcp_client_version`; the backend no longer owns task-intake or advisor routing.
- If the same MCP caller re-submits an equivalent heavy automation ask while an earlier one is still running, the service returns the existing `job_id` handoff semantics instead of inviting a second foreground wait loop.
- Agent responses and summary files now expose `provenance.provider_selection` when a provider was requested, so clients can see requested provider, final provider family, and whether fallback occurred.
- Local preflight failures now emit `submission_started=false` plus a concrete `failure_stage` (`preflight`, `initialize_mcp`, `submit_turn`) so clients do not wait on requests that never left the wrapper.

Use legacy provider queue mode only when the task explicitly needs low-level maintenance, provider debugging, or artifact-oriented `/v1/jobs` behavior. Coding agents must not treat it as a normal execution path.

### Conversation URL recovery

If the user gives a ChatGPT conversation URL and asks to retrieve the answer or full thread, this is not a model ask. Use the read-only export lane:

1. Try `automation_conversation_find(conversation_url=...)` to locate existing exports.
2. Prefer an existing job only when it is a dedicated `chatgpt_web.conversation_export` job with full rendered turn markers (`## user` and `## assistant`) or an equivalent full-conversation artifact. A historical `chatgpt_web.ask` job can have a valid raw `conversation.json`, but its `answer.md` may be only the final ask answer, not the full conversation.
3. If missing, stale, or only ask jobs are found, use `automation_conversation_fetch(conversation_url=..., backend_mode="dom_only")`.
4. If the active MCP client schema has not refreshed and those tools are unavailable, use `automation_job_create` with:
   - `kind="chatgpt_web.conversation_export"`
   - `input.conversation_url=<url>`
   - `params.manual_harvest=true`
   - `params.read_only_harvest=true`
   - `params.allow_dom_fallback=true`
   - `params.backend_mode="dom_only"`
   - `params.answer_format="markdown"`
5. Fetch final markdown with `automation_result(job_id, include_answer=true)` and raw chunks with `automation_conversation_get` when available.

This lane must never send a prompt. It exists for human-created conversations and multi-turn recovery by URL.

### Response contract for agents

When reporting to the user or another agent, include:

- `job_id`
- `conversation_url` when available
- `status`, `phase`, `phase_detail`
- `canonical_answer.ready` / `answer_state` / `authoritative_answer_path`
- output file paths for long answers or conversation exports
- whether the result is final, provisional, needs follow-up, cooldown, blocked, or failed before prompt send

Do not imply a Pro/Deep Research answer is usable until the canonical answer is ready and the content satisfies the user's minimum quality/length/structure expectations.

### Gemini DeepThink / GeminiDT rule

If the user explicitly wants:

- `GeminiDT`
- `Gemini DeepThink`
- web-only Gemini review
- a Gemini review that depends on the consumer web capability

then the valid channel is:

- `kind=gemini_web.ask`
- or the public MCP automation surface that resolves to `gemini_web.ask`

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
  - default: agent/public MCP (`automation-kernel-v1`)
  - explicit provider/preset
  - prompt + attachments
  - client-side preflight checklist
  - provider-selection rationale
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
- The wrapper now auto-loads missing runtime env from `~/.config/chatgptrest/chatgptrest.env` and `/vol1/maint/MAIN/secrets/credentials.env` before legacy maintenance calls. That is the supported source for `CHATGPTREST_ASK_HMAC_SECRET_CTL_MAINT`, API/OPS tokens, and related maintenance secrets.
- Legacy mode success/error payloads now print `resolved_runtime` so the client can see the effective ChatgptREST root, Python interpreter, transport timeout, and concrete command.
- Agent-mode timeout/transport failures now keep the generated `session_id` in the error payload so clients can recover with the selected surface's wait/status tools instead of blindly resubmitting.
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

ChatGPT Pro (not Deep Research) in legacy maintenance mode:

```bash
/usr/bin/python3 skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --no-agent \
  --maintenance-legacy-jobs \
  --provider chatgpt \
  --preset pro_extended \
  --idempotency-key pro-20260413-01 \
  --question "请直接给我 Pro 长答，重点给结论、证据边界和可执行建议。" \
  --out-answer /tmp/pro-answer.md
```

ChatGPT Pro local technical judgment (use when the task wants attachment-first repo/runtime architecture judgment):

```bash
/usr/bin/python3 skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --no-agent \
  --maintenance-legacy-jobs \
  --provider chatgpt \
  --preset pro_extended \
  --idempotency-key pro-local-judgment-001 \
  --file-path /tmp/local_context.md \
  --question "你是 ChatGPT Pro。请以附件中的本地事实为主，结合一般工程判断做技术评审：先给 yes/no，再给可执行路径；如果需要外部资料才能判断，请明确列为 Missing Evidence。" \
  --out-answer /tmp/pro-local-judgment-answer.md \
  --out-summary /tmp/pro-local-judgment-summary.json
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
