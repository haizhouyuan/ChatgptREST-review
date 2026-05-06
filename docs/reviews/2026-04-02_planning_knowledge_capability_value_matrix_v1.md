# 2026-04-02 Planning Knowledge Capability Value Matrix v1

## 1. 结论先说

如果只站在 `planning` 角度看，你这条线里最值钱的不是“通用向量检索”或“泛知识图谱平台”，而是这条窄而实用的链路：

`planning review plane -> planning reviewed runtime pack -> planning-priority context resolution -> active_project / decision_ledger work memory`

更直白一点：

1. 你已经做出了对 `planning` 真有帮助的知识能力。
2. 这些能力的核心不是“检索越多越好”，而是“把杂乱材料变成受控、可直接供运行时消费的 planning 上下文”。
3. 真正应该继续投入的，是 `planning` 专线和 `work memory`，不是继续把通用 `KB / 向量 / 图谱` 平台越做越大。

## 2. 这几层东西到底是什么

### 2.1 Working evidence layer

这是通用召回层，负责“找得到”。

- `KBHub`：`FTS5 + vector + RRF + evidence_pack`
- `ArtifactRegistry`：artifact 元数据治理
- `KBWritebackService`：研究/报告产物写回 KB

代码：

- [hub.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kb/hub.py#L1)
- [retrieval.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kb/retrieval.py#L55)
- [vector_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kb/vector_store.py#L1)
- [registry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kb/registry.py#L149)
- [writeback_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kb/writeback_service.py#L87)

### 2.2 Planning runtime product

这是 `planning` 真正的热路径产品，负责“拿到可直接用的 planning 上下文”。

- `planning_review_plane`
- `planning_runtime_pack_search`
- `ContextResolver` 里的 `planning_pack` 优先注入

代码：

- [planning_review_plane.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_review_plane.py#L24)
- [planning_runtime_pack_search.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_runtime_pack_search.py#L39)
- [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py#L862)

### 2.3 Canonical knowledge plane

这是长期正式知识面，负责“受控、可追溯、可 promotion 的知识底盘”。

- `documents / episodes / atoms / evidence / entities / edges`
- retrieval 走 `atoms_fts + quality gate + time decay + promotion gate`

代码：

- [db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/db.py#L55)
- [schema.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/schema.py#L27)
- [retrieval.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/retrieval.py#L61)

边界决策：

- [2026-03-20_knowledge_authority_decision_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_knowledge_authority_decision_v2.md#L21)

### 2.4 Planning durable work memory

这是任务线程和项目线程的记忆层，负责“当前项目到底在干什么、已经定了什么、下次从哪继续”。

- `active_project`
- `decision_ledger`
- `post_call_triage`
- `handoff`

代码：

- [work_memory_manager.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_manager.py#L58)
- [work_memory_importer.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_importer.py#L16)

runbook：

- [work_memory_backfill_importer_runbook_v1.md](/vol1/1000/projects/ChatgptREST/docs/ops/work_memory_backfill_importer_runbook_v1.md#L5)

### 2.5 Signals / observer

这是观测和进化信号层，不是 planning 真相层。

- `signals.db`
- observer / scorecard / policy / telemetry

代码：

- [observer.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/observer.py#L33)

## 3. 能力价值矩阵

| 能力 | 代码现实 | 对 planning 的直接价值 | 现在该怎么放 |
| --- | --- | --- | --- |
| `planning_review_plane` | 已落地，直接从 `planning` 源抓文档、分桶、筛噪、生成 review 面 | 很高 | `主线保留，继续投` |
| `planning reviewed runtime pack` | 已落地，显式读取 ready bundle，并叠加 quality / promotion / groundedness gate | 很高 | `主线保留，继续投` |
| `planning-priority context resolution` | 已接进 `ContextResolver`，`role_id=planning` 时优先 planning pack | 很高 | `主线保留，继续投` |
| `active_project / decision_ledger` work memory | 已落地，支持 durable 写入、导入、active context 构建 | 很高 | `主线保留，继续投` |
| `post_call_triage / handoff` work memory | 已有对象模型和 active context 入口 | 高 | `第二优先级，继续补强` |
| `KB FTS + ArtifactRegistry + scanner + writeback` | 已落地，是完整 working evidence 层 | 中高 | `保留，但明确只是支撑层` |
| `vector recall` | 已实现，但仍是 SQLite + numpy，本地小规模方案；向量覆盖相对稀疏 | 中 | `保留，但不要当主卖点` |
| `canonical knowledge graph` | 已是活库，不是空壳；planning 已是主语料之一 | 中高 | `保留，作为长期底盘` |
| `graph edge builder / edge-rich graph` | 有实现，但当前 hot path 价值低于 atom/promotion/gating | 中低 | `后置，不要继续放大` |
| `multi-graph query platform` | `business / repo_code / issue_execution` 已混到一起 | 低 | `对 planning 降级看待` |
| `signals / observer` | 已有，但偏观测、审计、进化 | 低 | `保留为运营层，不当 planning 主线` |
| `task_runtime planning distillation scaffold` | 仍是 scaffold，未接成 planning 主热路径 | 低 | `后置` |

## 4. 我建议你现在怎么理解这些能力

### 4.1 真正该围绕它来做 planning agent 的

1. `planning_review_plane`
2. `planning reviewed runtime pack`
3. `ContextResolver` 的 planning 优先逻辑
4. `active_project / decision_ledger / handoff / post_call_triage`

这四块合起来，才最接近你要的：

> 能理解 planning 历史、知道项目现状、继续旧任务、少理解偏、少漏项、并能跨端延续。

### 4.2 值得留，但要降级定位的

1. 通用 `KB FTS`
2. `ArtifactRegistry`
3. `KB writeback`
4. `vector recall`

这些是底座，不是主角。它们更像：

> 证据层 / working set / 召回层

而不是：

> planning 真相层

### 4.3 不该继续当第一优先级放大的

1. 泛化“图谱平台化”冲动
2. 图边推理优先于 reviewed pack / promotion gate
3. multi-graph query 持续扩张

原因很简单：你现在最需要的是能把 `planning` 做稳，不是再开更大的知识平台面。

## 5. 最关键的几个证据

### 5.1 `planning` 已经是图谱主语料，不是边缘材料

`2026-03-19` 审计时：

- `documents = 7863`
- `atoms = 99493`
- top source 第一名是 `planning = 3350`
- 还有 `planning_review_plane = 542`

而同一份审计也明确写了：

- vector 覆盖相对 FTS 仍稀疏

证据：

- [2026-03-19_memory_kb_graph_inventory_audit_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_memory_kb_graph_inventory_audit_v1.md#L103)
- [2026-03-19_memory_kb_graph_inventory_audit_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_memory_kb_graph_inventory_audit_v1.md#L124)

这说明：`planning` 的价值不在“有没有做向量库”，而在“有没有把 planning 语料变成受控热路径”。

### 5.2 早期偏航，后来才收回主线

你自己那套系统在 `2026-03-10` 的深审里就承认过：

1. `three-store disconnection`
2. `vector search is dead`
3. `knowledge graph is hollow`

证据：

- [2026-03-10_kb_architecture_deep_audit.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-10_kb_architecture_deep_audit.md#L5)

后来真正收住主线的，不是继续做大通用检索，而是：

1. `planning_review_plane`
2. `planning reviewed runtime pack`
3. `planning` 角色优先注入
4. `work memory` backfill

## 6. 现在最该拍板的口径

我建议你后面就用这句当判断基线：

> `planning` 方向最该保留和继续投入的是 reviewed planning context 与 durable work memory；KB、向量检索、知识图谱要服务这条主线，而不是反过来把主线拖成一个更大的通用平台。

## 7. 最终建议

### 7.1 继续投

1. `planning_review_plane`
2. `planning reviewed runtime pack`
3. `ContextResolver` 的 planning 优先逻辑
4. `active_project / decision_ledger / handoff / post_call_triage`

### 7.2 保留，但压成支撑层

1. `KB FTS`
2. `ArtifactRegistry`
3. `KB writeback`
4. `vector recall`

### 7.3 后置或降级

1. 图边推理优先化
2. multi-graph query 扩张
3. signals/observer 当 planning 主能力
4. task_runtime 里的 planning scaffold 提前升格

