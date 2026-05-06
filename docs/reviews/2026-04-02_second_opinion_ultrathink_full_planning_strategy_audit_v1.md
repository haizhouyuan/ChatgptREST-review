# 2026-04-02 Second Opinion: Ultrathink Full Planning Strategy Audit v1

> **审查说明**：基于 Ultrathink 深度批判性模式，本次审核没有停留在阅读 `_packet_v1` 等汇总文档的表面，而是下钻到了 `routes_agent_v3.py`、`mcp/server.py`、`feishu_handler.py`、`task_store.py` 及 `work_memory_manager.py` 的原子代码层。

针对你提出的 6 个战略判断（A-F），以下是我的独立审查结论。

## 1. 核验通过 (Validations)

以下战略判断在代码现实与逻辑推演中均完全成立，建议**坚决冻结，不再动摇**：

- **[A] 第一阶段主线判断**：完全正确。聚焦 `planning` 的长任务，而不是做大而全的泛平台。当前 `context_service.py` 和 packs 的硬编码逻辑就是为 `planning` 特化的，继续扩张会导致知识维度崩塌。
- **[B] Surface 分层判断**：高度精准。`Codex / Claude Code` 是真正的主工作台。原子代码证明，`feishu_handler.py` 的架构是纯粹的异步回调（`event -> background thread -> result card`），它是天生的“事件触发与状态分发”探针（dispatch/capture），**不是且永远不该是**一个重状态的长任务执行盘。
- **[D] Planning 知识主线判断**：完全正确。之前的原子审计已证明 `planning_runtime_pack_search` 是一个高性能（<15ms）且完备的独立查询闭环。`KB/vector` 作为支撑层是现实且高效的。
- **[E] “补齐优先，不重构”判断**：战略正确。当前架构的主干（图谱、知识快照、路由分发）已经成型，不需要重构。真正的瓶颈在工程闭环（如 promotion 的自动化、物理状态的打通）。

---

## 2. 发现问题 (Atomic Level Issues Discovered)

> **警告：战略预期与代码物理现实存在严重脱节**

在深度审计 **[C] 统一逻辑任务层判断** 时，我发现目前的“冻结口径”过度乐观，把“Schema上的准备”当成了“物理隔离的完备”。

1. **`routes_agent_v3.py` 与 `task_id` 物理剥离**：
   - 虽然文档称 `task_id` / `checkpoint` / `new/continue/branch` 是已冻结的 load-bearing pieces，但在 `routes_agent_v3.py` 和 MCP (`mcp/server.py` 的 `advisor_agent_turn`) 中，真正控制上下文的依然是 `session_id`。
   - `logical_task_id` 仅仅作为一个无副作用的被动字符串字段（在 payload validation 中出现），**完全没有**触发任何 Task Harness 的控制流逻辑。
2. **`task_store.py` 是孤岛**：
   - 定义了 `logical_task_key` 和状态机的 `task_store.py`，并没有被北向网关 (`routes_agent_v3.py`) 引入和消费。这意味着“统一逻辑任务层”在网关入口处其实是“空气”。
3. **Feishu 的 `trace_id` = `task_id` 谬误**：
   - 深入 `feishu_handler.py` (Line 410)，每一个 Feishu 消息都会裸生成一个全新的 UUID：`trace_id = str(uuid.uuid4())`。
   - 而在 `work_memory_manager.py` (Line 197) 中，直接硬编码了 `task_id=trace_id`。
   - **后果**：Feishu 进来的每一个单句都会被当作一个平行的、全新的 Task。根本不具备把多次交互串联进同一个 `task_id` 做 `continue` 或 `branch` 的能力。

---

## 3. 我会收紧或改写的口径 (Tightened Rephrasing)

基于上述发现，我会对你的原始口径进行以下“收紧”与“改写”：

### 关于“统一逻辑任务层” (改写)
- **原口径**：现在优先统一 `task_id`、`checkpoint`、`new / continue / branch`，而不是先强行统一入口。
- **收紧后口径**：现在**必须从物理层面落地**统一的逻辑任务层。目前的 `task_id` 仅停留在存储 Schema（`task_store.py`）阶段；在入口层（`routes_agent_v3.py` / `Feishu`）依然在裸用 `session_id` 和随机 `trace_id`，存在“伪驻留”风险。我们的目标不是推翻概念，而是**把空转的概念接入物理网关**。

### 关于 Feishu 等轻交互面的角色 (收紧)
- **原口径**：`Feishu` 目前更适合做 capture / dispatch / 轻交互。
- **收紧后口径**：`Feishu` 必须被**严格限制**在 capture / dispatch 的角色。在其原生消息中加入任务上下文映射（将无状态的 `message_id/trace_id` 映射到一致的 `task_id`）之前，**绝对不能**让 Feishu 触发任何需要 `work memory` 更新的写一致性操作。

---

## 4. 下一阶段建议 (Next Phase Actions)

在坚守“补齐优先，不重构”的主轴下，下一阶段（P0/P1）的执行动作必须重新排序：

1. **P0 (物理挂载逻辑任务层)**：
   - 在 `routes_agent_v3.py` 的 `advisor_agent_turn` 中，物理引入 `task_store.py` 的调用。
   - 取代单纯的 `session_id` 续写逻辑，强制基于 `task_id` 判定 `new / continue / branch`。
   - 修复 `work_memory_manager.py` 中 `task_id=trace_id` 的粗暴等价，剥离“追踪 ID”与“业务逻辑任务 ID”。

2. **P1 (补齐 Runtime Pack 的闭环自动化)**：
   - 这是上一轮审计的遗留，`promotion_engine.py` 必须配置 systemd/cron 自动化调度，将停留在 `staged` 流转到 `active`。这是 knowledge 发挥作用的刚需。

3. **P2 (收口 Public MCP 污染)**：
   - 如你判断的 **[F] 清理节奏** 非常合理：按计划裁剪掉如 `repo_bootstrap` 和 `doc_obligations` 这类破坏 `planning` 边界的底层工具暴露。

### 回答你的三个问题

1. **方向问题**：正确。收口到 `planning` 长任务。
2. **架构问题**：正确且必须。分层架构是可持续的，但前提是**真正物理切断和重连**（比如把 `task_id` 真正在网关层挂载，而不是隔空喊话）。
3. **节奏问题**：**绝对不要推翻重来**，也不需要大规模全盘重构。当前的核心动作就是：**接线（Wire up）+ 闭环自动化（Automate loop）**。现有的砖块（`task_store`, `feishu_handler`, `promotion_engine`）都非常坚实，只需在它们之间焊上信道。
