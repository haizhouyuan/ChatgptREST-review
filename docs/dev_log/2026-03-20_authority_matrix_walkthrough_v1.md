# 2026-03-20 Authority Matrix Walkthrough v1

## 1. 任务目标

基于：

- [2026-03-20_post_reconciliation_next_phase_plan_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_post_reconciliation_next_phase_plan_v1.md)
- [2026-03-20_system_state_reconciliation_master_audit_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_system_state_reconciliation_master_audit_v1.md)
- [2026-03-20_system_state_reconciliation_master_audit_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_system_state_reconciliation_master_audit_v2.md)

落地 `Phase 0` 的第一份交付物：

- [2026-03-20_authority_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v1.md)

目标不是提出理想架构，而是回答：

- 今天到底哪些 authority 已经足够清楚，可以先冻结
- 哪些 authority 还在 split-brain，不能继续带糊涂账往后开发

## 2. 本次核对范围

这次没有继续无边界扩散，只围绕 authority 直接相关的 5 组证据做核对：

1. `Phase 0` 计划文档与前两轮 master audit
2. systemd 单元与 drop-in
3. 路径解析与 runtime composition root
4. API 实际挂载与入口默认值
5. durable 数据库当前厚度

## 3. 重点读取对象

### 3.1 文档

- [2026-03-20_post_reconciliation_next_phase_plan_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_post_reconciliation_next_phase_plan_v1.md)
- [2026-03-20_system_state_reconciliation_master_audit_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_system_state_reconciliation_master_audit_v2.md)
- [2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md)
- [2026-03-16_model_routing_and_key_governance_blueprint_v1.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-16_model_routing_and_key_governance_blueprint_v1.md)
- [2026-03-18_coding_agent_mcp_surface_policy_v1.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-18_coding_agent_mcp_surface_policy_v1.md)

### 3.2 代码与配置

- [openmind_paths.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/openmind_paths.py)
- [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py)
- [fabric.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/routing/fabric.py)
- [llm_connector.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/llm_connector.py)
- [app.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/app.py)
- [routes_cognitive.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py)
- [feishu_ws_gateway.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/feishu_ws_gateway.py)
- [openmind-advisor plugin](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
- `/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env`

### 3.3 运行时

- `systemctl --user cat openclaw-gateway.service`
- `systemctl --user cat chatgptrest-api.service`
- `systemctl --user cat chatgptrest-mcp.service`
- `systemctl --user cat chatgptrest-feishu-ws.service`
- `journalctl --user -u openclaw-gateway.service`

## 4. 关键核对动作

### 4.1 服务态核对

结果：

- `openclaw-gateway.service = active`
- `chatgptrest-api.service = inactive`
- `chatgptrest-mcp.service = inactive`
- `chatgptrest-feishu-ws.service = inactive`

这一步的作用是先把“现在谁在线”说清楚。  
否则 authority 容易被误写成“设计上谁更重要”，而不是“当前谁在承载 live runtime”。

### 4.2 systemd unit 核对

结论：

- `openclaw-gateway.service` 明确把 `HOME` 锁到 `/home/yuanhaizhou/.home-codex-official`
- 它还显式加载：
  - `~/.openclaw/secrets/memory-embedding.env`
  - `~/.config/chatgptrest/chatgptrest.env`
  - `/vol1/maint/MAIN/secrets/credentials.env`
- `chatgptrest-api.service` 基础 unit 还残留旧 worktree 路径，但 `20-runtime-worktree.conf` 已把 `WorkingDirectory`、`PYTHONPATH`、`CHATGPTREST_DB_PATH`、`CHATGPTREST_ARTIFACTS_DIR` 覆盖到当前 repo
- `chatgptrest-feishu-ws.service` 当前仍把 `ADVISOR_API_URL` 指向 `http://127.0.0.1:18711/v2/advisor/advise`
- `chatgptrest-mcp.service` 当前也明确把 `CHATGPTREST_BASE_URL` 指向 `http://127.0.0.1:18711`
- `/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env` 当前只显式提供 `OPENMIND_API_KEY`、`OPENMIND_AUTH_MODE`、`OPENMIND_RATE_LIMIT`，没有显式固定 `OPENMIND_* DB path`

这一步把一个很关键的事实钉死了：

- **当前 authority 不在 unit 基础文件，而在 drop-in 和 live gateway env**
- 但 `memory / KB / event bus` 这组 DB path 也并没有被 env 明确固定，而是继续由 `HOME` 间接决定

### 4.3 路径 authority 核对

结论：

- `openmind_paths.py` 已经把 `EvoMap runtime DB` 收敛到 repo-local `data/evomap_knowledge.db`
- 但 `memory / kb_search / kb_vectors / events` 仍然默认是 `~/.openmind/*`

这意味着今天的 authority 并不是“全部 repo-local”或者“全部 HOME-relative”，而是一个 **非对称状态**：

- `EvoMap = repo-local canonical`
- `memory / KB / event bus = HOME-relative live store`

这正是后续 `knowledge_authority_decision_v1` 必须继续处理的主问题。

### 4.4 API 入口核对

结论：

- `app.py` 当前同时挂载：
  - `v1` jobs/advisor/consult/issues/metrics/ops/evomap
  - `v2` cognitive/dashboard
  - `cc-sessiond`
  - `v3 advisor`
  - `v3 public agent facade`
- `routes_agent_v3.py` 前缀明确是 `/v3/agent`
- `routes_advisor_v3.py` 前缀明确是 `/v2/advisor`
- `routes_cognitive.py` 前缀是 `/v2`，因此 telemetry endpoint 真实路径是 `/v2/telemetry/ingest`
- `openmind-advisor` OpenClaw 插件当前直接打 `baseUrl + /v3/agent/turn`
- 但 `feishu_ws_gateway.py` 默认仍打 `/v2/advisor/advise`

这一步说明：

- `public live ask` 和 `advisor graph ingress` 目前仍然是双入口
- 当前真正与 OpenClaw 主桥对接的是 `/v3/agent/turn`
- Feishu 入口还没有完成同样的收敛

### 4.5 模型路由 authority 核对

结论：

- `RoutingFabric` 的设计目标已经很明确，就是统一选路入口
- `advisor/runtime.py` 也确实把它注入 runtime
- 但实际 API-only 模型选择仍然落在 `LLMConnector._select_model()`
- `_select_model()` 当前顺序是：
  - `RoutingFabric`
  - `ModelRouter`
  - static route map
  - Gemini/MiniMax fallback

所以当前状态不能写成“模型路由已经统一”，只能写成：

- `RoutingFabric` 是 **设计上的 authority 候选**
- `LLMConnector._select_model()` 是 **当前真实运行链**

### 4.6 durable 厚度核对

结论：

- `jobdb` 和 `repo-local EvoMap` 继续保持厚 authority
- `HOME-relative OpenMind memory/KB` 仍然很薄
- `/tmp/cc-sessions.db` 只有 `2` 条 session，已经明显降成 residue

这一步的作用是避免 authority matrix 继续沿用旧印象，而不看当前实库大小。

### 4.7 telemetry 核对

结果：

- `routes_cognitive.py` 的 telemetry endpoint 挂载路径本身没有歧义：`/v2/telemetry/ingest`
- 但 `openclaw-gateway.service` 最近日志持续出现：
  - `openmind-telemetry: flush failed: TypeError: fetch failed`

所以 telemetry 当前的真实状态是：

- **路径合同基本明确**
- **live 可用性仍然坏着**

## 5. 为什么文档里要区分 A1 / A2 / R / U

这不是形式主义，而是为了阻止后续计划继续犯两种错：

1. 把 `正在 live 使用但很薄` 的 store 误写成长期 canonical
2. 把 `仍在并行存在` 的入口或路由误写成已经统一完成

所以这次 authority matrix 刻意把：

- `OpenClaw runtime`
- `jobdb`
- `repo-local EvoMap`
- `/v3/agent/turn`

升到 `A1`

同时把：

- `HOME-relative memory / KB / event bus`
- `LLMConnector actual invocation chain`
- `/v2/telemetry/ingest`

放在 `A2`

并把：

- `Feishu ingress`
- `model routing contract`
- `facade session truth`

保留为 `U`

## 6. 这版文档解决了什么

它先收住了 3 个最容易继续误判的问题：

1. **OpenClaw 被继续低估**
   - 现在可以正式冻结为当前 live runtime substrate
2. **repo-local EvoMap 和 HOME-relative memory/KB 被继续混写**
   - 现在已经明确分层
3. **`/v3/agent/turn` 与 `/v2/advisor/advise` 继续被混成一个前门**
   - 现在已经明确它们不是同一个 authority

## 7. 没有在这次顺手做的事

这次刻意没有顺手写：

- `knowledge_authority_decision_v1`
- `routing_authority_decision_v1`
- `telemetry_contract_fix_v1`
- `front_door_contract_v1`

原因很简单：

- 这几份都是 authority matrix 之后的下游决策
- 如果这一版先不把事实源矩阵收稳，后面会继续在错前提上做设计

## 8. 产物

本次新增：

- [2026-03-20_authority_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v1.md)
- [2026-03-20_authority_matrix_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_walkthrough_v1.md)

## 9. 测试与残留

这次是文档与状态核对任务，没有代码改动，也没有跑测试。

已知残留：

- OpenClaw gateway telemetry 仍持续报 `fetch failed`
- `chatgptrest-api.service` 基础 unit 里仍有旧 worktree 路径
- Feishu ingress 仍指向 `/v2/advisor/advise`

这些都已经被 authority matrix 明确标出，下一步不再会被当作“已经统一完成”的部分。
