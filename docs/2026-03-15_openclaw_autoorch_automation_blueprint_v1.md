# OpenClaw AutoOrch Automation Blueprint v1

日期：2026-03-15  
仓库：ChatgptREST

## 目标

在不污染 `main` 主交互上下文的前提下，让 OpenClaw + OpenMind 自动跑起来：

- `main` 继续做人机主会话。
- `maintagent` 保持健康 watchdog，不承接业务自动化。
- 新增 `autoorch` 作为后台自动化 scout。

## 运行面

### Agent 拓扑

- `lean`: `main`
- `ops`: `main + maintagent + autoorch`

### AutoOrch 职责

- 刷新 dashboard control-plane projection。
- 运行 finagent watchlist scout。
- 将可执行摘要写入 `artifacts/autoorch/inbox/pending/`。
- 仅对 net-new actionable delta 向 `main` 发送简短信号。

### 第一批自动任务

1. `dashboard-refresh`
   - 触发方式：`autoorch` heartbeat
   - 频率：每 6 小时
   - 命令：`python3 ops/openclaw_autoorch.py dashboard-refresh --format json`

2. `watchlist-scout`
   - 触发方式：OpenClaw cron job
   - 频率：每天 `07:00`（Asia/Shanghai）
   - 命令：`python3 ops/openclaw_autoorch.py watchlist-scout --format json`

## Inbox 协议

路径：

- pending: `artifacts/autoorch/inbox/pending/*.json|*.md`
- archived: `artifacts/autoorch/inbox/archived/*.json|*.md`

字段：

- `item_id`
- `created_at`
- `title`
- `summary`
- `category`
- `severity`
- `source`
- `action_hint`
- `payload`

语义：

- 文件是 handoff truth。
- `main` heartbeat 或人工审阅后可调用 `inbox-ack` 归档。
- 默认不直接打断 `main`，只在 net-new actionable delta 时用 `sessions_send` 补一句提示。

## 约束

- 不复活 legacy `chatgptrest-* orch/worker` 拓扑。
- 不把业务自动化并入 `maintagent`。
- 不让 `main` 自己跑 routine scout。
- 先只上 2 个自动任务，不同步扩到 opportunity radar。
