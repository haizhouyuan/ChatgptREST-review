# OpenClaw Feishu Ingress Visibility Closure v1

## 结论

这轮已经把“能看到真实飞书/OpenClawBot 消息、图片和回复”收口成可操作能力，不再依赖手工翻散落文件。

当前需要明确区分两条证据面：

1. **ChatgptREST agent ingress receipts**
   - 适用于真正经过 `POST /v3/agent/turn` 持久化的 OpenClaw/OpenMind advisor 请求
   - 当前持久化目录：
     - `artifacts/monitor/openclaw_ingress_receipts/live`
   - 检索脚本：
     - `python3 ops/find_openclaw_ingress_receipts.py --backfill-session-store --since-hours 72 --limit 5`

2. **OpenClaw transcript turns**
   - 适用于当前真实 OpenClawBot/飞书入口对话，尤其是图片消息、图片读取和 bot 最终回复
   - 当前 transcript 根目录默认解析到：
     - `/home/yuanhaizhou/.home-codex-official/.openclaw`
   - 检索脚本：
     - `python3 ops/find_openclaw_transcript_turns.py --since-hours 24 --limit 10`

这两条面都需要保留。原因是当前真实飞书入口并不保证把所有原始 `OriginatingChannel / MessageSid / MediaPaths` 完整投影进 ChatgptREST `state/agent_sessions/*.json`；而 OpenClaw transcript 会完整保留用户图片消息、读取图片的 tool call，以及 bot 的最终文本回复。

## 根因

之前“我看不到你刚发的真实飞书消息和图片”，不是因为数据根本不存在，而是因为我只在 ChatgptREST session artifact 这一层找。

实际代码和 live 数据显示：

- OpenClaw 飞书 transport 会把图片先落盘到：
  - `/home/yuanhaizhou/.home-codex-official/.openclaw/media/inbound/...`
- OpenClaw agent transcript 会记录：
  - 用户消息
  - `message_id`
  - 图片文件名和 inbound 路径
  - assistant 对图片的读取和回复
- ChatgptREST 这边此前缺一个 first-class 的 ingress receipt ledger，也缺一个直接查 transcript turn 的 operator 工具

## 本轮改动

### 1. 新增 ChatgptREST ingress receipt ledger

- 新文件：
  - `chatgptrest/api/agent_ingress_receipts.py`
- 在 `routes_agent_v3` session upsert 时自动尝试写入 receipt：
  - `chatgptrest/api/routes_agent_v3.py`

receipt 会提取：

- source / surface / originating_channel / provider
- identity：`account_id / thread_id / agent_id / user_id / role_id / session_key`
- transport：`message_sid / chat_id / sender / reply_to_body / timestamp`
- request：`message / body / body_for_agent / raw_body / command_body / attachments / media_paths / media_types`
- response：`status / route / answer / next_action / artifacts / provenance`
- task：`goal_hint / scenario / output_shape / task_id / project_id`

### 2. 修复 receipt backfill 的 live 默认路径

- 文件：
  - `ops/find_openclaw_ingress_receipts.py`

修复前：

- shell 下未显式设置 `CHATGPTREST_DB_PATH` 时，会退回 `/tmp/chatgptrest-agent-sessions`
- 这和 systemd live 服务实际使用的 `state/jobdb.sqlite3 -> state/agent_sessions` 不一致

修复后：

- 优先使用 `CHATGPTREST_AGENT_SESSION_DIR`
- 其次使用 `CHATGPTREST_DB_PATH`
- 再其次自动对齐 repo live 默认：
  - `state/jobdb.sqlite3 -> state/agent_sessions`

### 3. 新增 OpenClaw transcript turn 检索脚本

- 新文件：
  - `ops/find_openclaw_transcript_turns.py`

能力：

- 直接搜索 `~/.openclaw/agents/*/sessions/*.jsonl`
- 解析 turn 级结构：`user -> assistant/toolCall -> assistant final`
- 提取：
  - `message_id`
  - `sender_id`
  - 图片文件名
  - inbound media 路径
  - assistant 最终回复摘要

## live 验证

### focused tests

以下测试通过：

- `tests/test_agent_ingress_receipts.py`
- `tests/test_routes_agent_v3.py`
- `tests/test_run_feishu_ingress_canary.py`

### live operator queries

#### ingress receipt

命令：

```bash
python3 ops/find_openclaw_ingress_receipts.py --backfill-session-store --since-hours 72 --limit 3
```

结果：

- 能直接查到近期 seeded canary / openclaw 侧的 message + answer
- 已不再误落到 `/tmp/chatgptrest-agent-sessions`

#### transcript turns

命令：

```bash
python3 ops/find_openclaw_transcript_turns.py --since-hours 24 --limit 5
```

结果：可以直接看到最近真实飞书图片对话，例如：

- `om_x100b52b0e94f9c70c3c91ce5162a57b`
  - user: `[image] 微信图片_20260409173502_1865_961.jpg`
  - reply: 关于“收到回复”功能是否需要引用样式的分析
  - media: `/home/yuanhaizhou/.home-codex-official/.openclaw/media/inbound/微信图片_20260409173502_1865_961---af7c24fb-b6a7-478e-816b-0995848710c2.jpg`

- `om_x100b52b0e94f78bcc3f7fe88a4d853f`
  - user: `[image] 微信图片_20260410083735_1871_961.jpg`
  - reply: 关于“收到回复”需求文档、引用样式和 MVP 建议的分析

- `om_x100b52b0e94e7488c14014a298387d1`
  - user: `[image] 微信图片_20260410084831_1873_961.jpg`
  - reply: 关于 `parent_id`、引用展示和删除 fallback 的分析

## 当前边界

这轮解决的是“看得到”，不是“所有真实飞书交互都自动统一进同一个 canonical ledger”。

当前最准确的口径是：

- **ChatgptREST receipts**：覆盖 `v3/agent/turn` 持久化面
- **OpenClaw transcripts**：覆盖真实 OpenClawBot 对话面

如果后续要把两者收成单一 authority surface，下一步应做的是 transcript -> canonical telemetry / receipt projection，而不是继续让 operator 手工对照两边。
