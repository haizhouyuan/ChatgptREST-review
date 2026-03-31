# 2026-03-20 Post-Reconciliation Next Phase Plan v2

## 1. 为什么要出 v2

[2026-03-20_post_reconciliation_next_phase_plan_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_post_reconciliation_next_phase_plan_v1.md)
是在 authority freeze 之前写的，所以它的顺序是对的，但状态已经过期了。

截至现在，下面这些前置工作已经完成：

- authority freeze 主链完成
  - [authority_matrix_v2](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v2.md)
  - [knowledge_authority_decision_v2](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_knowledge_authority_decision_v2.md)
  - [routing_authority_decision_v2](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_v2.md)
  - [front_door_contract_v2](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_contract_v2.md)
  - [session_truth_decision_v3](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v3.md)
  - [telemetry_contract_fix_v1](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_telemetry_contract_fix_v1.md)
- implementation 收口已做两件
  - `/v3/agent/*` facade session 已桥进 canonical telemetry plane
  - `chatgptrest-api.service` 已恢复，`18711 /healthz` 与 `/v2/telemetry/ingest` 已重新可用

所以现在不该再从 “Phase 0: Authority Freeze” 开始，而该进入真正的实施阶段。

## 2. 当前基线

### 2.1 已经确定的系统关系

- `OpenClaw`
  - live runtime substrate
  - continuity owner
- `ChatgptREST`
  - current runtime host
  - front-door / execution / artifacts / telemetry host
- `OpenMind`
  - 系统身份、方法论、任务语义、知识与演化逻辑
  - 当前主要以 ChatgptREST 内的 runtime + docs/contract 形式存在
- `Finagent`
  - 独立垂直系统

### 2.2 已经冻结的关键 truth

- public live ask 正门：
  - `/v3/agent/turn`
- internal smart-execution 入口：
  - `/v2/advisor/ask`
- internal graph/controller + Feishu WS 入口：
  - `/v2/advisor/advise`
- legacy compatibility ask 入口：
  - `/v1/advisor/advise`
- session truth：
  - `OPENCLAW_STATE_DIR`
  - `state/agent_sessions`
  - `state/jobdb.sqlite3`
- payload truth：
  - `artifacts/jobs/*`
  - `artifacts/advisor_runs/*`
- telemetry canonical HTTP seam：
  - `POST http://127.0.0.1:18711/v2/telemetry/ingest`

### 2.3 现在还没做完的事

虽然 freeze 做完了，但下面这些还没有真正落成系统能力：

1. `IntentEnvelope / Task Intake Spec / Acceptance Spec` 还没有成为所有入口的统一对象。
2. `OpenClaw / Feishu / public facade / MCP` 还没有全部对齐到同一 front-door object contract。
3. `planning / research` 还没有成为真正稳定的场景包，只是散落在 `task_spec.py / standard_entry.py / funnel_graph.py / ask_contract / strategist`。
4. `knowledge split-plane` 只在决策文档里成立，还没有完全收成代码写路和回写路。
5. `heavy execution / Work Orchestrator` 还不具备上桌条件，不能现在就扶正。

## 3. 本阶段总目标

从现在开始，下一阶段只追 3 个结果：

1. **把 front door object contract 做实**
2. **把 planning / research 两个主场景做成稳定场景包**
3. **把 knowledge runtime 与 runtime host 收成可持续运行的主链**

不再以“通用 agent 平台”作为近期目标。

## 4. 实施顺序

## Phase 1: Front Door Object Freeze

### 目标

把当前已经存在但分散的这些东西收成一套统一对象链：

- `IntentEnvelope`
- `Task Intake Spec`
- `Ask Contract`
- `Acceptance Spec`

### 为什么先做

现在最大的系统性缺口已经不是 authority，而是：

- 同一种请求从不同入口进来，还会被不同对象模型处理
- `task_spec.py`、`standard_entry.py`、`funnel_graph.py`、`routes_agent_v3.py` 的 contract 没收敛

不先统一对象，后面的场景包和知识回写都会继续漂。

### 代码落点

- [task_spec.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py)
- [standard_entry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py)

### 要做的事

1. 收敛字段，统一出一版 canonical object：
   - `source`
   - `session_id`
   - `trace_id`
   - `objective`
   - `decision_to_support`
   - `output_shape`
   - `available_inputs`
   - `missing_inputs`
   - `constraints`
   - `evidence_required`
   - `acceptance`
   - `scenario`
2. 决定 `task_spec.py` 和 `standard_entry.py` 的主从关系。
   - `task_spec.py` 留作 canonical schema
   - `standard_entry.py` 退成 adapter / normalizer
3. 明确 `ask_contract` 与 `Task Intake Spec` 的边界。
   - `ask_contract` 不是另一个平行系统
   - 它应该成为 front-door object 的 reasoning view

### 交付物

- `front_door_object_contract_v1.md`
- `task_intake_spec_v1.json`
- `entry_adapter_matrix_v1.md`

### 验收

- `routes_agent_v3` 与 `routes_advisor_v3` 都能消费同一套结构化对象
- 不再存在平行 schema

## Phase 2: Ingress Alignment

### 目标

把入口对齐到前门 contract，而不是继续让每个入口长自己的语义。

### 代码落点

- [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
- [feishu_ws_gateway.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/feishu_ws_gateway.py)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py)

### 要做的事

1. 明确 OpenClaw main bridge 的 canonical payload shape。
2. 明确 Feishu WS 为什么暂时仍走 `/v2/advisor/advise`，以及迁移条件。
3. 给 `/v3/agent/turn` 和 `/v2/advisor/ask` 做统一 request envelope。
4. 清点 legacy `/v1/advisor/advise` caller，限制新流量继续进入。

### 交付物

- `ingress_alignment_matrix_v1.md`
- `public_vs_internal_ingress_payload_diff_v1.md`

### 验收

- OpenClaw / public MCP / CLI / Feishu WS 的 request shape 能对应同一套 front-door contract
- legacy lane 不再继续扩张

## Phase 3: Planning Scenario Pack

### 目标

把 `planning` 从抽象概念变成一条稳定工作流。

### 为什么优先于 research

`planning` 对 contract、clarify、acceptance、knowledge 回指的要求最高。  
这条线打透后，系统边界才真正稳。

### 代码落点

- [funnel_graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/funnel_graph.py)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [prompt_builder.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/prompt_builder.py)
- [ask_strategist.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py)

### 要做的事

1. 定义 `planning` 的 scenario pack：
   - intake
   - clarify
   - synthesis
   - acceptance
2. 决定 `funnel_graph` 的地位：
   - 只做 `planning` 重型入口增强
   - 不再作为所有请求默认前门
3. 固定 `planning` deliverable profiles：
   - 会议总结
   - 业务规划
   - 人力规划
   - 面试记录/调查纪要

### 交付物

- `planning_scenario_pack_v1.md`
- `planning_acceptance_profiles_v1.json`

### 验收

- 至少 2 条真实 `planning` 请求能从 intake 跑到结构化产物
- clarify 与 acceptance 不再靠人工约定

## Phase 4: Research Scenario Pack

### 目标

把 `research` 从“调 Gemini / ChatGPT 深研”提升成受 contract 约束的场景包。

### 代码落点

- [preset_recommender.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/preset_recommender.py)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [routes_consult.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_consult.py)
- [report_graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/report_graph.py)

### 要做的事

1. 定义 `research` 的必要字段：
   - research question
   - scope in/out
   - evidence threshold
   - expected output
2. 把 `preset recommendation` 与 `research scenario` 对齐，不再只靠长度/关键词。
3. 把 `report_graph` 收成 `research` 的下游 deliverable path，而不是平行子系统。

### 交付物

- `research_scenario_pack_v1.md`
- `research_evidence_policy_v1.md`

### 验收

- 至少 2 条真实 `research` 请求能稳定产出 memo / report
- provider/preset 选择与 evidence threshold 一致

## Phase 5: Knowledge Runtime Rebalance

### 目标

把已经冻结的 split-plane 真正落成可执行的写入/读取边界。

### 代码落点

- [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py)
- [writeback_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kb/writeback_service.py)
- [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)
- `chatgptrest/cognitive/ingest_service.py`

### 要做的事

1. 明确哪些写入必须走 canonical knowledge plane。
2. 明确哪些只是 runtime working plane。
3. 把 `advisor graph` / `report` / `post-review` / telemetry activity 的写回路径对齐。

### 交付物

- `knowledge_runtime_write_path_v1.md`
- `knowledge_runtime_read_path_v1.md`

### 验收

- 不再存在 “写到 KB 但没进 canonical graph” 的模糊状态
- retrieval plan 能解释为什么命中了哪一层

## Phase 6: Heavy Execution Decision Gate

### 目标

不是立即做 `Work Orchestrator`，而是给它一个真正的准入门槛。

### 为什么放最后

如果 `planning / research` 两条主场景还没稳定，先做 heavy execution 层只会再次重演：

- 想要全
- 想要专
- 最后没有一块真正做实

### 现在允许做的只有两件事

1. 为 `heavy execution` 写准入标准
2. 定义什么时候需要引入它，而不是先把服务搭起来

### 交付物

- `heavy_execution_decision_gate_v1.md`

### 验收

- 能用明确标准回答“现在该不该做 Work Orchestrator”

## 5. 近期不做

- 不扶正 `cc-sessiond`
- 不重启通用 team runtime 大工程
- 不先做图库
- 不让 `Finagent` 反向定义主系统
- 不先做任意 team topology

## 6. 立即执行顺序

下一轮应直接按下面顺序做，不再回到抽象争论：

1. `front_door_object_contract_v1`
2. `task_intake_spec_v1.json`
3. `entry_adapter_matrix_v1`
4. `ingress_alignment_matrix_v1`
5. `planning_scenario_pack_v1`
6. `research_scenario_pack_v1`
7. `knowledge_runtime_write_path_v1`

## 7. 最小结论

从现在开始，下一阶段的重心不是：

- authority 讨论
- telemetry 讨论
- service 是否活着

而是：

- **把 front-door object contract 做实**
- **把 planning / research 做成稳定场景包**
- **最后再决定 heavy execution 要不要扶正**
