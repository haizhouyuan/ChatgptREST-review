# OpenMind Phase Execution Independent Review v1

Date: 2026-04-09
Reviewer: Claude (GAC independent red-team)
Scope: Codex 的 Phase 0–6 全量执行（commits cec0d69f, 2d34b92e, 869e2bf7, 3967b3f2）

## 1. 总体判断

这轮执行是真实的。不是"只写了 ADR 和文档"，而是把 wake-up packet compiler 和 crystallized learning 真正接进了 `/v3/agent/turn` 的 runtime hot path，并且用真实 harness 产出了可验证的 artifact。

验收结论：**通过，有保留意见。**

## 2. 逐项验证

### 2.1 Wake-up packet compiler（Phase 2 核心）

验证方式：直接读代码 + 跑测试 + 检查 artifact。

代码验证：

- `chatgptrest/cognitive/wakeup_packet.py`：实现了 `WakeUpPacket` dataclass 和 `build_wakeup_packet()` 函数。4 层结构（L0 authority anchor, L1 active memory, L2 knowledge, L3 runtime handoff）与 contract 一致。
- `chatgptrest/api/routes_agent_v3.py:5573`：`_maybe_compile_wakeup_packet()` 在 `/v3/agent/turn` 主路径中被调用，编译结果写入 `task_intake.available_inputs.wake_up_packet`。
- 失败安全：`routes_agent_v3.py:1388` 的 `except Exception` 捕获所有编译失败，返回 `applied: False` receipt，不阻断主路径。这是正确的 fail-open 设计。
- source precedence 硬编码为 `authority anchor > project memory > EvoMap knowledge > runtime heuristics`，与 ADR-005 一致。

Artifact 验证：

- `artifacts/monitor/wakeup_packet_harness/20260409T022911Z/wakeup_packet.json` 是一个真实的 project-scoped packet（project_id=prs），包含：
  - L0：行星滚柱丝杠的 authority anchor，frozen facts 4 条，style rules 3 条，pinned authority docs 4 份
  - L1：active project map + decision ledger，planning task type = research_decision
  - L2：KB retrieval projection
  - L3：runtime handoff
- `degraded: true` + `degraded_sources: ["personal_graph_empty", "authority_schema_partial"]`：诚实标记了当前不完整的部分（graph 为空，owner 未设置）

测试验证：

- 125/125 focused tests pass（test_wakeup_packet, test_crystallized_learning, test_task_intake, test_prompt_builder, test_routes_agent_v3, test_run_wakeup_packet_harness）

**判断：Phase 2 实质完成。packet 已经在 runtime 中生效，不是纸面设计。**

### 2.2 Crystallized learning（Phase 5 核心）

验证方式：直接读代码。

代码验证：

- `chatgptrest/advisor/crystallized_learning.py`：`build_interaction_learning_crystal()` 从 interaction_learning payload 中提取稳定偏好。
- 治理约束：
  - `INTERACTION_LEARNING_MIN_SUPPORT = 2`：偏好必须有至少 2 次 support 才能结晶
  - 只提取 8 个预定义维度（raw_ingress_mode, quality_bar, preferred_executor_family, closure_style, brevity_preference, depth_preference, focus_preference, reply_first_preference）
  - `precedence_note: "Advisory only. Never override the authority anchor with crystallized learning."`：明确不能覆盖 authority anchor
  - 带 invalidation 机制：newer interaction-learning record 可以 supersede 旧 crystal

**判断：Phase 5 设计合理。crystal 是 advisory 而非 authoritative，有 support 门槛和 invalidation 机制，不会制造不可控的偏好漂移。**

### 2.3 文档收口（Phase 6）

验证方式：读文档内容。

- `docs/contracts/2026-04-09_wakeup_packet_contract_v1.md`：冻结了 packet schema、layer contract、source precedence。内容与代码实现一致。
- `docs/contracts/2026-04-09_openmind_scope_surface_inventory_v1.md`：把所有 openmind-* surface 分类为 bridge only / implemented runtime / audit only / reserved。关键结论：
  - openmind-advisor = bridge only（不是独立 advisor brain）
  - openmind-memory = bridge only（不拥有 durable memory）
  - standalone OpenMind advisor/memory runtime = reserved / not implemented
- `docs/integrations/2026-04-09_openclaw_cognitive_substrate_runtime_contract_v3.md`：更新了 topology 和 plugin contract summary，加入了 wake-up packet 路径。

**判断：文档与代码一致，scope inventory 的分类准确反映了当前代码现实。**

### 2.4 Phase 3（semantic recall）和 Phase 4（promotion baseline）

这两个 phase 的核心工作在前几轮已经完成（commits 923d3f0e, d3af9f66, 3f2a0ca0, a6ceb242, e091e077），本轮只是在 closeout 台账中确认关闭。

前几轮的独立验证结论：

- semantic recall 从 3/3 全零提升到 3/3 非零，绿源 recall 质量从泛化"准备"提升到实体相关内容
- vector lane 从 740 → 4547 → 6356
- promotion pipeline live：active 816, candidate 4312, chain_id 103,259

**判断：Phase 3 和 Phase 4 的关闭是合理的。**

## 3. 架构判断

### 3.1 依赖方向已经清晰

本轮验证中最重要的架构发现是 `openclaw_extensions/` 目录的存在和内容：

| Extension | 行数 | 调用方向 |
|---|---|---|
| `openmind-advisor` | 2289 | OpenClaw → ChatgptREST `/v3/agent/*` |
| `openmind-memory` | 535 | OpenClaw → ChatgptREST `/v2/context/*`, `/v2/memory/*` |
| `openmind-telemetry` | 465 | OpenClaw → ChatgptREST `/v2/telemetry/*` |
| `openmind-graph` | 131 | OpenClaw → ChatgptREST `/v2/graph/*` |

反向只有一个薄 adapter：`chatgptrest/integrations/openclaw_adapter.py`（140 行）。

这证实了用户的判断：**ChatgptREST 是事实生产 authority，OpenClaw 是事实消费 authority。** 插件包由 ChatgptREST 仓库提供，OpenClaw 只是加载和消费。

### 3.2 三方主权划分

本轮执行后，代码现实支持的主权划分是：

- **ChatgptREST = 事实生产 authority**
  - atom/evidence production（EvoMap）
  - promotion / groundedness / chain
  - structured memory（MemoryManager）
  - advisor task runtime
  - wake-up packet compiler
  - crystallized learning
- **OpenClaw = 事实消费 authority**
  - session lifecycle
  - executor orchestration
  - local memory assist（QMD/search）
  - document-layer routing
  - 通过 openmind-* 插件消费 ChatgptREST 的 packetized truth
- **OpenMind = 宪法与审计 authority**
  - event schema（event_bus.py）
  - artifact ledger（artifact_store.py）
  - policy receipts（policy_engine.py）
  - trace contract
  - 不拥有 advisor/kb/evomap runtime（这些包仍然是空的）

### 3.3 wake-up packet 的架构意义

wake-up packet 不只是一个技术改进，它改变了 OpenClaw 和 ChatgptREST 之间的信息流模型：

- **之前**：OpenClaw 通过多个 API 调用分别获取 memory、KB、planning 信息，自己组装 context
- **之后**：ChatgptREST 编译一个完整的 packetized truth，OpenClaw 消费 projection

这意味着 context assembly 的权威从 OpenClaw 侧转移到了 ChatgptREST 侧。这是正确的方向，因为 ChatgptREST 拥有所有 substrate truth（memory, KB, EvoMap, planning），它比 OpenClaw 更有资格决定如何组装 context。

## 4. 保留意见

### 4.1 packet 质量依赖 `_project_context.md` 人工维护

L0 authority anchor 的质量完全取决于 `_project_context.md` 的人工维护质量。harness artifact 已经暴露了 `authority_schema_partial`（owner 未设置）。如果 `_project_context.md` 过时或不完整，packet 的 L0 层就会退化。

这不是代码问题，而是运营问题。但需要意识到 packet 的天花板由人工维护的 anchor 决定。

### 4.2 crystallized learning 的 support 门槛可能太低

`INTERACTION_LEARNING_MIN_SUPPORT = 2` 意味着只需要 2 次相同偏好就能结晶。在高频交互场景下，这可能导致偶然偏好被过早固化。

当前的 invalidation 机制（newer record supersedes）可以缓解这个问题，但如果 crystal 被消费端缓存，supersede 的传播可能有延迟。

建议：观察一段时间后考虑是否需要提高到 3。

### 4.3 graph 和 policy 层仍然为空

harness artifact 显示 `graph` 和 `policy` 两个 retrieval plan 都是 `resolved: false, block_count: 0`。这意味着 packet 的 4 层结构中，L0 和 L1 有实质内容，L2 有部分内容（KB retrieval），但 graph recall 和 runtime policy hints 还没有真正接入。

这不影响当前 packet 的可用性，但说明 packet 的完整度还有提升空间。

### 4.4 全量测试套件仍有少量失败

focused tests 125/125 pass，但全量测试套件中仍有 3-5 个失败（test_skill_chatgptrest_call_coding_agent_v1, test_system_optimization 等）。这些失败在前几轮就存在，不是本轮引入的，但说明 broader regression 仍然存在。

## 5. 结论

这轮执行的质量是高的。Codex 没有停在"只写计划"，而是把 Phase 0–6 全部落地到了代码和 artifact。核心改造（wake-up packet compiler + crystallized learning）的设计是合理的，fail-open 保护到位，治理约束明确。

最重要的架构成果不是某个具体功能，而是通过 wake-up packet 把 context assembly 的权威从 OpenClaw 侧转移到了 ChatgptREST 侧，并通过 scope inventory 冻结了"openmind-* 插件是 bridge 而非独立 runtime"这个事实。

下一步的优先级应该是：

1. 继续 entity recall 改善（钛虎实体原料、绿源 ranking）
2. 接入 graph recall 和 policy hints 到 packet
3. 观察 crystallized learning 在真实交互中的表现
4. 清理全量测试套件中的 broader regression
