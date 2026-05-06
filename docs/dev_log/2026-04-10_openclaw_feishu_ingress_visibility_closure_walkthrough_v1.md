# OpenClaw Feishu Ingress Visibility Closure Walkthrough v1

## 做了什么

这轮把“为什么看不到真实飞书/OpenClawBot 消息与图片”从猜测变成了实证，并补成了可执行工具。

我先做了两件调查：

1. 查 ChatgptREST live session store
   - 发现真正 live 路径是 `state/agent_sessions`
   - 不是 shell 默认误判出来的 `/tmp/chatgptrest-agent-sessions`

2. 查 OpenClaw transcript
   - 发现真实飞书图片消息、图片读取、assistant 回复主要在：
     - `~/.home-codex-official/.openclaw/agents/*/sessions/*.jsonl`
   - 也就是说，当前真实入口可见性不能只靠 ChatgptREST session artifact

## 为什么之前会误判

问题不是“数据没进来”，而是“找错了证据面”。

此前只看了：

- `ChatgptREST /v3/agent/*`
- `artifacts/jobs/*`
- `state/agent_sessions/*`

但真实飞书图片对话实际上还会经过 OpenClaw 本地 agent transcript，里面保留了：

- 用户 message metadata
- 图片文件名和 inbound 路径
- assistant 对图片的 read tool call
- assistant 的最终文本回复

## 这次落地的能力

### A. ingress receipt ledger

新增：

- `chatgptrest/api/agent_ingress_receipts.py`

接入：

- `chatgptrest/api/routes_agent_v3.py`

作用：

- 对真正经过 `v3/agent/turn` 的 openclaw / feishu ingress，落一个专用 receipt

### B. live 默认路径对齐

修复：

- `ops/find_openclaw_ingress_receipts.py`

作用：

- 本地直接跑脚本时，优先回到 repo live `state/jobdb.sqlite3 -> state/agent_sessions`
- 不再默认误落 `/tmp`

### C. transcript turn 检索

新增：

- `ops/find_openclaw_transcript_turns.py`

作用：

- 直接查最近真实 OpenClaw transcript turn
- 输出 `message_id / sender_id / 图片文件名 / 图片路径 / assistant reply`

## 怎么用

### 查 ChatgptREST ingress receipts

```bash
python3 ops/find_openclaw_ingress_receipts.py --backfill-session-store --since-hours 72 --limit 5
```

### 查 OpenClaw transcript turns

```bash
python3 ops/find_openclaw_transcript_turns.py --since-hours 24 --limit 10
```

按关键词过滤：

```bash
python3 ops/find_openclaw_transcript_turns.py --since-hours 24 --keyword "收到回复" --limit 10
```

JSON 输出：

```bash
python3 ops/find_openclaw_transcript_turns.py --since-hours 24 --limit 10 --json
```

## 这次验证到了什么

这轮已经能看到最近真实飞书图片对话：

- `微信图片_20260409173502_1865_961.jpg`
- `微信图片_20260410083735_1871_961.jpg`
- `微信图片_20260410084831_1873_961.jpg`

并能同时看到：

- `message_id`
- inbound media 物理路径
- OpenClawBot 的最终回复摘要

## 还没做的

还没有把 transcript turn 自动投影进单一 canonical ledger。

所以当前 operator 最准确的心智模型是：

- 查 `v3/agent` 产物：看 ingress receipts
- 查真实 OpenClawBot 对话：看 transcript turns

下一步如果要再做一层治理，应该是把 transcript turn 统一投影进 telemetry / receipt authority，而不是继续靠人脑记忆“两边去看”。 
