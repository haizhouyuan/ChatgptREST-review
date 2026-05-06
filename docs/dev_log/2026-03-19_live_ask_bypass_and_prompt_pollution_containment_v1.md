# 2026-03-19 Live Ask Bypass And Prompt Pollution Containment v1

## Context

Two live-risk problems were still open:

1. Low-level direct `/v1/jobs` submissions could still create real `chatgpt_web.ask`
   threads from bypass clients such as `curl` / `chatgptrestctl`, even after smoke
   prompts were blocked.
2. Public advisor / agent flows were still pasting raw `--- 相关知识库参考 ---` and
   `--- 附加上下文 ---` blocks into the final question body, producing noisy live
   ChatGPT threads like:
   - `hello`
   - `hello\n\n--- 附加上下文 ---\n- depth: standard`
   - long business asks with KB snippets directly embedded into the visible prompt

## Changes

### 1. Block direct low-level live ChatGPT asks by default

Added `enforce_direct_live_chatgpt_submission()` in
`chatgptrest/api/write_guards.py`.

Behavior:
- applies only to `kind=chatgpt_web.ask`
- blocks direct `/v1/jobs` submissions by default
- allows only:
  - explicit override: `params.allow_direct_live_chatgpt_ask=true`
  - allowlisted clients from `CHATGPTREST_DIRECT_LIVE_CHATGPT_CLIENT_ALLOWLIST`
  - in-process `TestClient` traffic with no explicit client name

Default allowlist:
- `chatgptrest-admin-mcp`

Error:
- `direct_live_chatgpt_ask_blocked`

Intent:
- force live asks back onto `/v3/agent/turn` / `advisor_agent_turn`
- stop ad-hoc `curl` / `chatgptrestctl` low-level asks from opening front-end threads

### 2. Keep public agent prompts clean

Changed `chatgptrest/api/routes_agent_v3.py:_enrich_message()`:
- no longer appends raw `--- 附加上下文 ---`
- no longer pastes arbitrary context fields into the final prompt

Changed `chatgptrest/controller/engine.py:_build_enriched_question()`:
- no longer appends `--- 相关知识库参考 ---`
- no longer appends `--- 附加上下文 ---`
- returns the clean user question only

Intent:
- stop visible prompt pollution in real ChatGPT threads
- preserve context in controller/runtime state instead of leaking it into the
  user-facing question body

### 3. Keep `/v3/agent/turn` write provenance enforcement

The existing uncommitted guard on `/v3/agent/turn` was kept:
- `X-Client-Name` allowlist enforcement
- trace header enforcement when enabled

## Tests

Passed:

```bash
./.venv/bin/pytest -q tests/test_block_smoketest_prefix.py tests/test_routes_agent_v3.py tests/test_agent_v3_routes.py
./.venv/bin/pytest -q tests/test_advisor_v3_end_to_end.py -k 'files_only or auto_context'
```

Coverage added/updated:
- direct low-level live ask block for `chatgptrestctl`
- allowlist and explicit override behavior
- `/v3/agent/turn` client-name / trace-header enforcement tests
- prompt cleanliness checks for public agent enrichment
- advisor end-to-end expectation updated to assert KB/context is not pasted into
  `input.question`

## Notes

- This change does **not** restart services by itself.
- The runtime is intentionally still stopped at this point for containment.
- GitNexus marked controller-related scope as high/critical because
  `_build_enriched_question()` sits on the controller hot path. The change was
  deliberately limited to removing prompt-body pollution only, without altering
  route selection or controller state transitions.
