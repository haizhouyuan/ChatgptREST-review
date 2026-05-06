# 2026-04-25 MCP Cancel Explicit Reason Guard v1

## 背景

Maint control-plane external review jobs exposed a cancellation attribution gap: public MCP `automation_job_cancel` could cancel a job while only recording the generated reason `mcp_cancel:<job_id>`. The event still identified the MCP client and request id, but it did not preserve the caller's business intent, so later audit could not distinguish intentional stale-job cleanup from accidental or wrong-target cancellation.

## 根因

The public MCP cancel path delegated to `chatgptrest_job_cancel`, which always populated `X-Cancel-Reason` through `_default_cancel_reason(job_id=...)`. Existing REST write guards could require `X-Cancel-Reason`, but MCP always supplied an auto-generated value, so that gate did not force explicit operator intent.

## 改动

- Added `CHATGPTREST_REQUIRE_EXPLICIT_MCP_CANCEL_REASON`.
- Added an optional `reason` argument to `chatgptrest_job_cancel` and public `automation_job_cancel`.
- When the new env var is enabled, MCP cancel tools return `ExplicitCancelReasonRequired` before sending HTTP `/cancel` if no explicit reason is provided.
- Preserved compatibility by keeping the legacy auto-generated reason when the new env var is disabled.
- Documented the public MCP cancel reason contract in `docs/contract_v1.md`, `docs/runbook.md`, `docs/client_projects_registry.md`, and `AGENTS.md`.

## 验证

```bash
PYTHONPATH=. ./.venv/bin/python -m pytest -q tests/test_mcp_trace_headers.py
```

Result: `12 passed`.

## 后续

Enable `CHATGPTREST_REQUIRE_EXPLICIT_MCP_CANCEL_REASON=1` on high-risk MCP runtimes after checking active clients. This is a behavior hardening gate, not a replacement for cancel allowlists or trace headers.
