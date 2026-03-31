# Google Workspace Surface Revival Walkthrough v1

日期：2026-03-23

## 为什么这样收

这轮没有重做 Google Workspace 集成，也没有替换 `rclone`。

判断依据是：

- `GoogleWorkspace` adapter 已经覆盖 Drive / Calendar / Sheets / Docs / Gmail / Tasks
- setup / env / handoff 路径都已存在
- 真正缺的是 northbound product surface，而不是底层能力本体

所以这轮的策略是：

- 保留现有 adapter
- 在其上加 `workspace/contracts.py + workspace/service.py`
- 用 `workspace_action` effect 收口 report delivery
- 再把 `public agent / MCP / CLI / skill wrapper` 接到同一 northbound contract

## 关键取舍

### 1. 没改 `GoogleWorkspace`

`GoogleWorkspace` 的 blast radius 太大，这轮刻意不动本体，只做包裹层。

### 2. 没改 `EffectsOutbox`

outbox 基座也不动，只在上层加：

- `workspace_action`
- legacy `google_workspace_delivery` 兼容消费

### 3. northbound 不暴露底层 SDK 方法

北向暴露的是任务动作，不是 Drive/Docs SDK 函数：

- `search_drive_files`
- `fetch_drive_file`
- `deliver_report_to_docs`
- `append_sheet_rows`
- `send_gmail_notice`

### 4. wrapper 也一起收口

如果只改 MCP 签名，不改 CLI / skill wrapper，这条 surface 还是会分叉。

所以这轮顺手把：

- `chatgptrest agent turn`
- `chatgptrest_call.py`

一起补成支持 `workspace_request`

## 验证里看到的真实状态

validation pack 证明了：

- northbound contract 已经收口
- report_graph / public agent / wrapper 都接上了
- 当前唯一 live 红点是 Google OAuth token 失效

这条 residual 不是代码结构问题，而是运行面问题。

## 当前推荐口径

对外描述时要说准确：

- `Workspace surface revival`: 完成
- `Workspace live OAuth readiness`: 未完成

不要说成：

- “Google Workspace 已全部 live ready”

因为当前 `workspace_auth_state` 仍是红的。
