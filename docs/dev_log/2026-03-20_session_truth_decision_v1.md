# 2026-03-20 Session Truth Decision v1

## 1. 决策目标

这份文档承接：

- [2026-03-20_authority_matrix_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v2.md)
- [2026-03-20_front_door_contract_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_contract_v2.md)

要解决的问题不是“系统里有几个带 session_id 的地方”，而是：

- 到底哪一层负责 **原生会话连续性**
- 哪一层负责 **public agent facade 的 session contract**
- 哪一层负责 **execution correlation / status truth**

如果这三件事不拆开，继续把 `~/.openclaw`、`state/agent_sessions`、`state/jobdb.sqlite3` 写成“三账本平权”，后面所有 session recovery、telemetry、front-door 收敛都会继续歪。

## 2. 先说结论

当前系统不是“有三套 session truth 并列竞争”，而是：

**一个分层 session truth 模型**

1. **Channel-native continuity truth**
   - `~/.openclaw`
   - 负责 OpenClaw / Feishu / DingTalk / agent runtime 的原生会话连续性
2. **Public agent facade session truth**
   - `state/agent_sessions`
   - 负责 `/v3/agent/session/*`、SSE stream、public session contract
3. **Execution correlation truth**
   - `state/jobdb.sqlite3`
   - 负责 job / controller run / work items / checkpoints / artifacts 的底层执行关联

所以我的正式判断不是：

- “三账本平权”

而是：

- **三层 truth，各自回答不同问题**

## 3. 代码现实

## 3.1 `~/.openclaw` 负责原生 channel/session continuity

`OpenClaw` 当前仍然是唯一持续在线的 runtime substrate，这一点前面已经冻结过。

更关键的是，它的 session identity 是原生生成和维护的，不是 ChatgptREST 代管的。

在 OpenClaw bridge 里：

- [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L194)
  - `runtimeIdentity()` 直接从 OpenClaw runtime context 取：
    - `sessionKey`
    - `agentAccountId`
    - `sessionId`
    - `agentId`
- [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L226)
  - bridge 的 `sessionId` 优先使用 `identity.session_id || identity.thread_id`
- [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L281)
  - 调 `/v3/agent/turn` 时把这个值作为 `session_id` 传给 ChatgptREST

同时 bridge 还把 OpenClaw 原生 identity 再塞进 context：

- `openclaw_session_key`
- `openclaw_account_id`
- `openclaw_thread_id`
- `openclaw_agent_id`

这说明一个关键事实：

- ChatgptREST 并不是 OpenClaw 原生会话的拥有者
- 它只是 **消费** OpenClaw 传进来的会话 identity

所以 `~/.openclaw` 应冻结为：

- **channel-native continuity truth**

它回答的是：

- “这个用户/频道/agent 当前会话是谁”
- “原生会话上下文和 channel continuity 是什么”

## 3.2 `state/agent_sessions` 负责 public facade session contract

`/v3/agent/*` 这套 public facade 确实有自己的一层 durable session store，而且这层不是摆设。

[agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py#L20)
已经把路径规则写死：

- 如果有 `CHATGPTREST_AGENT_SESSION_DIR`，优先用它
- 否则如果有 `CHATGPTREST_DB_PATH`，就落到 `dirname(DB)/agent_sessions`
- 当前环境下就是：
  - `state/agent_sessions`

[routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L968)
明确实例化：

- `_session_store = AgentSessionStore.from_env()`

而且这套 public facade 路由真的把它当主 session contract 在用：

- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L992)
  - `_upsert_session(...)`
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1613)
  - `GET /v3/agent/session/{session_id}`
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1624)
  - `GET /v3/agent/session/{session_id}/stream`
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1667)
  - `POST /v3/agent/cancel`

当前本地状态也证明它不是空壳：

- `state/agent_sessions` 里现在有 `3` 套 `.json + .events.jsonl`

所以这层的准确定位是：

- **public agent facade session truth**

它回答的是：

- “`/v3/agent/session/{id}` 应该返回什么”
- “当前 public session 的 user-facing status / answer / SSE stream 是什么”

## 3.3 `jobdb` 负责 execution correlation，不是原生 continuity store

`state/jobdb.sqlite3` 当然也带 `session_id`，但它的角色不能写错。

[controller/store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/store.py#L97)
在 `controller_runs` 里保存：

- `session_id`
- `account_id`
- `thread_id`
- `agent_id`
- `role_id`
- `user_id`

[controller/engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L299)
到 [controller/engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L319)
也明确把这些 identity 写进 run。

但这并不等于 `jobdb` 是 canonical session continuity store。

理由很硬：

1. 它的主主键不是 `session_id`
   - 是 `run_id`
   - jobs 还有 `job_id`
2. 它存的是 execution ledger
   - route
   - provider
   - preset
   - work items
   - checkpoints
   - artifacts
3. 当前 live 数据也说明它不是 session-first
   - 我实测 `controller_runs` 里：
     - `130` 条有 `trace_id`
     - 只有 `55` 条有非空 `session_id`

这说明：

- `jobdb` 不是所有执行都以 session 为中心
- 它更像 execution correlation / durable run ledger

所以 `jobdb` 的准确定位应当是：

- **execution correlation truth**

它回答的是：

- “这个 public session 对应了哪个 job/run”
- “底层执行现在到底在哪个状态”
- “controller/work-item/checkpoint/artifact 的 durable truth 是什么”

## 3.4 `/v2` 路径不会自己生成一套新的 session truth

这一点也很关键。

`/v2/advisor/advise` 和 `/v2/advisor/ask` 都会接受 `session_id`，但它们不拥有独立 session ledger。

[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L500)
和 [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1622)
都只是：

- 接收 `session_id`
- 传给 `ControllerEngine.advise(...)` / `ControllerEngine.ask(...)`

它们没有像 `/v3/agent/*` 那样：

- 自己的 session JSON
- 自己的 SSE stream
- 自己的 facade session APIs

所以 `/v2` 路径不应被误写成第四套 session truth。

它们只是：

- **session-aware execution ingress**

不是独立 continuity ledger。

## 4. 正式决策

## 4.1 三层 truth 的 owner

### A. Channel-native continuity truth

当前 owner：

- `~/.openclaw`

职责：

- 原生 channel 会话连续性
- OpenClaw agent runtime session identity
- channel/account/thread continuity

结论：

- **A1 Canonical**

### B. Public facade session truth

当前 owner：

- `state/agent_sessions`

职责：

- `/v3/agent/session/*`
- public session status / stream
- public session cancel / follow-up continuity

结论：

- **A1 Canonical for `/v3/agent/*` surface**

注意：

- 这层是 facade-local canonical，不是全系统唯一 session source

### C. Execution correlation truth

当前 owner：

- `state/jobdb.sqlite3`

职责：

- job/controller run/status durable truth
- session to job/run correlation
- artifacts/checkpoints/work-items

结论：

- **A1 Canonical for execution state**

注意：

- 这层不是原生 continuity source

## 4.2 以后不能再写的话

从现在开始，后续文档不能再写：

- “session truth = 三账本平权”
- “jobdb 是会话连续性的唯一真相源”
- “`state/agent_sessions` 只是缓存，没有 canonical 意义”
- “OpenClaw session 只是外部入口壳，不算 truth”

这些说法都会再次把不同层次的问题压扁。

## 4.3 正式判断

当前系统的正确说法是：

- **OpenClaw 拥有原生会话连续性**
- **ChatgptREST public agent facade 拥有自己的 facade session truth**
- **jobdb 拥有底层执行关联 truth**

这是一个 **layered truth model**，不是 split-brain 平权模型。

## 5. 对后续工作的影响

基于这个判断，后面几件事的边界也会跟着定住：

1. `session recovery`
   - OpenClaw 恢复原生 continuity
   - `/v3/agent/session/*` 恢复 facade 投影
   - `jobdb` 恢复执行状态
2. `telemetry`
   - 要分 channel continuity signals
   - facade session signals
   - execution signals
3. `front-door 收敛`
   - 不该试图用 `jobdb` 替代 OpenClaw continuity
   - 也不该让 OpenClaw 直接替代 `/v3/agent/session/*`

## 6. 最小结论

当前系统不是“三套 session truth 打架”，而是：

- **`~/.openclaw` = channel-native continuity truth**
- **`state/agent_sessions` = public facade session truth**
- **`state/jobdb.sqlite3` = execution correlation truth**

这才是后续继续做 recovery、telemetry、ingress 收敛时应该使用的准确前提。
