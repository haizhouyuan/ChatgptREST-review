# Phase 25 Admin MCP Provider Compatibility Gate Completion Walkthrough v1

## What Changed

- 新增 [admin_mcp_provider_compatibility_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/admin_mcp_provider_compatibility_gate.py)
- 新增 [run_admin_mcp_provider_compatibility_gate.py](/vol1/1000/projects/ChatgptREST/ops/run_admin_mcp_provider_compatibility_gate.py)
- 新增 [test_admin_mcp_provider_compatibility_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_admin_mcp_provider_compatibility_gate.py)

## Why v2 Was Rejected

- live transport 已通，但 submit 结果为空
- 根因不是 tool surface 坏了，而是 launched MCP subprocess 使用 `chatgptrest-admin-mcp`，被当前 allowlist 直接挡下

## Why v3 Is Accepted

- gate 维持 admin-style tool surface，但 replay 时切到 allowlisted MCP identity
- 同时将 Gemini submit 改成 `preset=auto + 实质性问题`
- live runner 重新生成 `report_v3` 后，5/5 通过
