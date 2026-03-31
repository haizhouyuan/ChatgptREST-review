# 2026-03-26 Low-Level Ask Auth And JSON Guard Fix Walkthrough v1

## Why this pass happened

The previous low-level ask rollout was directionally right, but review correctly pointed out that:

- maintenance/internal exceptions were still only as strong as `X-Client-Name`
- the JSON-only deterministic rule was stricter than the intended "gray-zone goes through Codex classify" policy

## Implementation notes

### 1. Sensitive maintenance/internal callers now require real request signing

I introduced `chatgptrest/core/client_request_auth.py` as a small shared helper that:

- resolves a registered client from `ops/policies/ask_client_registry.json`
- checks whether the profile is `auth_mode=hmac`
- builds `X-Client-Id`, `X-Client-Timestamp`, `X-Client-Nonce`, and `X-Client-Signature`

That helper is now used by:

- CLI `ApiClient.request()` so maintenance wrappers using `chatgptrestctl-maint` sign automatically
- admin MCP `chatgptrest_job_create()` so low-level `/v1/jobs` submissions from `chatgptrest-admin-mcp` also sign automatically

### 2. Gray-zone JSON-output asks can reach Codex classify

The earlier rule treated any `json_only` prompt as a deterministic extractor block for non-maintenance callers.

That was too broad for profiles like:

- `planning-wrapper`
- `openclaw-wrapper`

which are intentionally configured as `codex_guard_mode=classify`.

The deterministic layer now yields to Codex classify for `automation_registered + codex_guard_mode=classify` JSON-output asks, while extractor/sufficiency/structured-microtask rules still block immediately.

## Verification

- `./.venv/bin/python -m py_compile ...`
- `./.venv/bin/pytest -q tests/test_low_level_ask_guard.py tests/test_block_smoketest_prefix.py`
- `./.venv/bin/pytest -q tests/test_cli_chatgptrestctl.py tests/test_cli_improvements.py tests/test_mcp_trace_headers.py`
- `./.venv/bin/pytest -q tests/test_write_guards.py tests/test_jobs_write_guards.py tests/test_client_name_allowlist.py tests/test_direct_provider_execution_gate.py`
- `./.venv/bin/pytest -q tests/test_mcp_gemini_ask_submit.py tests/test_mcp_repair_submit.py tests/test_mcp_sre_submit.py tests/test_mcp_unified_ask_min_chars.py`

## Follow-up expectation

Runtime deployment still needs the corresponding secret envs populated for any maintenance/internal low-level ask caller that should remain usable online. This patch intentionally fails closed if a caller is HMAC-scoped but its secret is missing.
