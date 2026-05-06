# 2026-03-26 Low-Level Ask Auth And JSON Guard Fix v1

## Context

Follow-up review on the low-level ask identity guard found two service-side gaps:

1. maintenance/internal low-level ask identities were still effectively name-based because several sensitive registry profiles used `auth_mode=registry`
2. the deterministic `json_only` rule was too broad and blocked substantive gray-zone automation asks before Codex classify could review them

## What changed

- promoted sensitive maintenance/internal low-level ask profiles to HMAC-scoped identities in `ops/policies/ask_client_registry.json`
  - `chatgptrest-admin-mcp`
  - `chatgptrestctl-maint`
  - `internal-submit-wrappers`
  - `finagent-event-extractor`
- added shared client-side HMAC signing helper in `chatgptrest/core/client_request_auth.py`
- wired automatic signing into:
  - `chatgptrest/cli.py` `ApiClient.request()`
  - `chatgptrest/mcp/server.py` `chatgptrest_job_create()`
- narrowed `chatgptrest/core/ask_guard.py` so `json_only` no longer hard-blocks classify-mode registered automation before Codex intent review
- kept extractor-style / sufficiency / structured microtask deterministic blocks intact

## Regression coverage

- `tests/test_low_level_ask_guard.py`
  - added substantive JSON-output classify regression
  - added maintenance HMAC requirement regression
- `tests/test_block_smoketest_prefix.py`
  - updated maintenance/admin allow cases to use valid HMAC signatures
- `tests/test_cli_chatgptrestctl.py`
  - added `ApiClient` HMAC signing regression for maintenance identity
- `tests/test_mcp_trace_headers.py`
  - added admin MCP `chatgptrest_job_create()` HMAC signing regression

## Result

- spoofing a maintenance/internal low-level ask caller by client name alone no longer passes the low-level ask gate
- classify-mode automation can still request structured JSON output for substantive review/report asks without getting deterministically blocked just for preferring JSON formatting
