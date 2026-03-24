# Google Workspace Surface Revival Audit v1

日期：2026-03-23

## 目标

把仓库里已经存在但分裂的 Google Workspace 能力，收成统一、受控、幂等、可审计的 northbound task surface，而不是继续让上层直接碰 `GoogleWorkspace` SDK 方法。

## 现有能力核对

底层能力并不是从零开始：

- 统一适配器已经存在：[google_workspace.py](/vol1/1000/projects/ChatgptREST/chatgptrest/integrations/google_workspace.py)
- 已覆盖：
  - Drive：`drive_list_files` / `drive_upload_file` / `drive_create_folder` / `drive_download_file`
  - Calendar：`calendar_list_events` / `calendar_create_event`
  - Sheets：`sheets_read` / `sheets_write` / `sheets_create`
  - Docs：`docs_create` / `docs_read`
  - Gmail：`gmail_send`
  - Tasks：`tasks_list` / `tasks_create`
- 正式 setup 路径已经存在：[setup_google_workspace.sh](/vol1/1000/projects/ChatgptREST/scripts/setup_google_workspace.sh)
- Drive 生产传输侧 handoff 已存在：[handoff_gemini_drive_attachments_20251230.md](/vol1/1000/projects/ChatgptREST/docs/handoff_gemini_drive_attachments_20251230.md)
- 环境变量已进入正式清单：[env.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/env.py)

## 本轮收口

### L1 northbound contracts/service

新增了统一 Workspace northbound object：

- [contracts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/workspace/contracts.py)
- [service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/workspace/service.py)

第一批动作固定为：

- `search_drive_files`
- `fetch_drive_file`
- `deliver_report_to_docs`
- `append_sheet_rows`
- `send_gmail_notice`

### L1.5 outbox 执行层

新增：

- [outbox_handlers.py](/vol1/1000/projects/ChatgptREST/chatgptrest/workspace/outbox_handlers.py)

作用：

- 把标准 `workspace_action` effect 和 legacy `google_workspace_delivery` 统一消费
- 不修改 `EffectsOutbox` 本体
- 允许 `report_graph` 统一 enqueue 标准 Workspace effect

### L2 上层接入

已接通：

- `report_graph -> workspace_action`
  - [report_graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/report_graph.py)
  - [graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py)
- `public /v3/agent/turn -> workspace_request`
  - [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- `public MCP advisor_agent_turn -> workspace_request`
  - [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py)
- repo 自带 northbound wrapper
  - [cli.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cli.py)
  - [chatgptrest_call.py](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py)

## Alive-path 现实状态

read-only probe 结果：

- `rclone listremotes`：存在 `gdrive:`
- `OPENMIND_GOOGLE_*` 默认路径：存在
  - credentials: `/home/yuanhaizhou/.openmind/google_credentials.json`
  - token: `/home/yuanhaizhou/.openmind/google_token.json`
- `WorkspaceService().auth_state()`：当前为 `ok=false`
- 直接原因：token silent load 返回 `invalid_grant`

所以当前状态必须说准确：

- 产品化收口：已完成
- L0 传输侧 `rclone gdrive:`：活着
- Google OAuth token：当前失效，导致 live Docs/Sheets/Gmail/Drive API 调用还不能按 `GO` 使用

## 结论

这件事现在不该再定义成“Google Workspace 能不能用”的研究问题。

更准确的结论是：

- Workspace 能力本体已经存在
- northbound surface 这轮已经收成统一 contract / service / outbox / public agent / wrapper
- 当前唯一 live residual 是 OAuth token 失效，不是产品结构缺失
