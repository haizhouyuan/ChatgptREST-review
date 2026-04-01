# Phase 25 Admin MCP Provider Compatibility Gate v1

## Goal

证明 legacy 低层 MCP tool surface 仍能动态 replay：

- `initialize`
- `tools/list`
- `chatgptrest_gemini_ask_submit`
- `chatgptrest_job_wait`
- `chatgptrest_answer_get`

## Final Evidence

- accepted artifact: [report_v3.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase25_admin_mcp_provider_compatibility_gate_20260323/report_v3.json)

## Notes

- `report_v2` 不是当前真值。它失败不是 transport 坏了，而是 launched subprocess 默认用了 `chatgptrest-admin-mcp` client name，被当前 allowlist 故意挡下。
- `report_v3` 的 replay 改成在 allowlisted MCP identity 下执行，证明的是 legacy low-level MCP tool surface 兼容性，而不是证明 dedicated admin client name 当前也被 allowlisted。

## Scope Boundary

- dynamic MCP replay against live `18711` API
- legacy low-level gemini submit + wait + answer compatibility
- not a proof that admin MCP must be always-on as a systemd service
- not a proof that `chatgptrest-admin-mcp` client name is separately allowlisted
- not a public agent MCP proof
