# 2026-03-20 Session Truth Decision Walkthrough v1

## 1. 任务目标

完成 `Phase 0` 的下一份正式决策文档：

- [2026-03-20_session_truth_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v1.md)

这次不再沿用“三账本平权”的说法，而是要把 session truth 的层次拆清楚。

## 2. 这次重点核对的问题

我围绕 4 个问题收证据：

1. OpenClaw 到底是不是原生 continuity owner
2. `/v3/agent/*` 是否真的有自己独立的 session store
3. `jobdb` 是否真的只是 execution correlation ledger
4. `/v2` 路径是否又长出第四套 session truth

## 3. 这次读取的关键对象

- [agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [controller/store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/store.py)
- [controller/engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py)
- [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py)

## 4. 这次最关键的判断

### 4.1 不是三账本平权，而是三层 truth

这次最重要的收束不是又多列几个文件路径，而是把三者职责拆开：

- `~/.openclaw`
  - 原生 channel/session continuity
- `state/agent_sessions`
  - `/v3/agent/*` facade session truth
- `state/jobdb.sqlite3`
  - execution correlation truth

这三层回答的不是同一个问题，所以不该继续被写成“平权账本冲突”。

### 4.2 OpenClaw 不是附属上下文，而是上游 continuity owner

OpenClaw bridge 不是随机塞几个 context 字段，它是把自己的原生 session identity 下传给 ChatgptREST：

- `sessionKey`
- `sessionId`
- `agentAccountId`
- `agentId`

然后才变成 `/v3/agent/turn` 的 `session_id` 和 `openclaw_*` context。

这说明 OpenClaw 是上游 continuity owner，不是 facade 的一个附属字段来源。

### 4.3 `/v3/agent/*` 确实有自己一层 canonical session truth

`state/agent_sessions` 不是缓存，也不是随手写的临时文件。

它直接支撑：

- `GET /v3/agent/session/{id}`
- `GET /v3/agent/session/{id}/stream`
- `POST /v3/agent/cancel`

所以对 public agent surface 来说，它就是 canonical truth。

### 4.4 `jobdb` 是执行 truth，不是 continuity truth

虽然 `controller_runs` 里有 `session_id`，但它的自然主键仍然是：

- `run_id`
- `job_id`

而且 live 数据上也能看出来，`trace_id` 比 `session_id` 更普遍。

所以把 `jobdb` 写成“唯一 session truth”会直接误导后面的 recovery 和收敛设计。

## 5. 最终收下来的口径

从 `v1` 开始，session truth 的正式口径是：

1. `~/.openclaw`
   - channel-native continuity truth
2. `state/agent_sessions`
   - public facade session truth
3. `state/jobdb.sqlite3`
   - execution correlation truth

## 6. 为什么这版判断重要

因为下一步不管做：

- telemetry contract
- runtime recovery
- front-door 收敛

都必须先接受一个事实：

**session 不是单层对象，而是 continuity / facade / execution 三层叠加。**

## 7. 产物

本轮新增：

- [2026-03-20_session_truth_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v1.md)
- [2026-03-20_session_truth_decision_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_walkthrough_v1.md)

## 8. 测试说明

这次仍然是文档和代码证据决策任务，没有改代码，也没有跑测试。
