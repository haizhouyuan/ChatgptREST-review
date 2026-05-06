# Google Workspace Surface Revival Completion v1

日期：2026-03-23

## 完成范围

按既定包顺序，这轮已经完成：

1. `GW-1 capability audit + alive-path verification`
2. `GW-2 workspace/contracts.py + workspace/service.py`
3. `GW-3 workspace/outbox_handlers.py`
4. `GW-4 report_graph + public agent integration`
5. `GW-5 validation pack`

## 已落地内容

### 统一 northbound contract

新增 Workspace northbound object：

- [contracts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/workspace/contracts.py)

统一入口动作：

- `search_drive_files`
- `fetch_drive_file`
- `deliver_report_to_docs`
- `append_sheet_rows`
- `send_gmail_notice`

### service / outbox 层

- [service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/workspace/service.py)
- [outbox_handlers.py](/vol1/1000/projects/ChatgptREST/chatgptrest/workspace/outbox_handlers.py)

这层把现有 `GoogleWorkspace` 和 `rclone` 相关现实收在受控层里，没有让北向直接碰底层 SDK 方法。

### report_graph / public agent / wrapper

已接通：

- [report_graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/report_graph.py)
- [graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py)
- [cli.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cli.py)
- [chatgptrest_call.py](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py)
- [check_public_mcp_client_configs.py](/vol1/1000/projects/ChatgptREST/ops/check_public_mcp_client_configs.py)

现在 northbound 使用方式已经统一成：

- public MCP / `advisor_agent_turn(..., workspace_request=...)`
- `chatgptrest agent turn --workspace-request-json ...`
- `chatgptrest_call.py --workspace-request-json ...`

### validation

Validation pack 已补齐：

- [google_workspace_surface_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/google_workspace_surface_validation.py)
- [run_google_workspace_surface_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_google_workspace_surface_validation.py)
- [test_google_workspace_surface_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_google_workspace_surface_validation.py)

当前结果：

- `11` checks
- `10` passed
- `1` failed

accepted report:

- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/google_workspace_surface_validation_20260323/report_v1.json)

## 当前正式结论

这轮可以正式收成：

- `Google Workspace northbound surface revival`: 完成
- `Workspace product surface`: 已收口
- `Workspace live OAuth readiness`: 当前未恢复

也就是说：

- 代码结构问题已经解决
- 统一 northbound surface 已经建立
- 当前唯一未收口项是 live token `invalid_grant`

## 当前 residual

live probe 的红点不是结构问题，而是运维现实：

- `/home/yuanhaizhou/.openmind/google_token.json`
- 当前 silent load 返回 `invalid_grant`

这意味着：

- `Drive/Docs/Sheets/Gmail` 的 northbound contract 已 ready
- 但真正触达 Google API 的 live 调用还需要重新授权

## 下一步

下一步不该再改 northbound contract，而应该做：

1. rerun [setup_google_workspace.sh](/vol1/1000/projects/ChatgptREST/scripts/setup_google_workspace.sh) 或等价 re-auth
2. 重新跑 [run_google_workspace_surface_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_google_workspace_surface_validation.py)
3. 产出 `v2` 文档和 `report_v2`
