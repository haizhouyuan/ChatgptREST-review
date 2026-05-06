# 2026-03-20 Knowledge Authority Decision Walkthrough v1

## 1. 任务目标

基于 [2026-03-20_authority_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v1.md) 的 unresolved 项，继续完成 `Phase 0` 第二份交付物：

- [2026-03-20_knowledge_authority_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_knowledge_authority_decision_v1.md)

这次要回答的问题只有一个：

- `memory / KB / event bus / EvoMap` 到底谁是 canonical，谁只是 runtime working plane

## 2. 这次怎么收判断

这次没有再做大范围泛读，只围绕 4 个判断锚点收证据：

1. runtime 初始化到底怎么绑定这些 DB
2. 当前 live 数据厚度差异到底有多大
3. hot path 到底怎么消费这些对象
4. 正式写回时，知识是否已经真的进入 canonical graph

## 3. 重点读取对象

### 3.1 核心路径与初始化

- [openmind_paths.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/openmind_paths.py)
- [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py)

### 3.2 运行时消费面

- [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)
- [routes_consult.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_consult.py)
- [memory_capture_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/memory_capture_service.py)
- [ingest_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/ingest_service.py)

### 3.3 知识工作集组件

- [hub.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kb/hub.py)
- [registry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kb/registry.py)
- [writeback_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kb/writeback_service.py)
- [event_bus.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/event_bus.py)

### 3.4 正式写回主链

- [graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py)

## 4. 关键发现

### 4.1 代码已经默认是 split-plane

这是这次最关键的发现。

`openmind_paths.py` 和 `advisor/runtime.py` 组合起来的实际效果是：

- `EvoMap` 默认回 repo-local `data/evomap_knowledge.db`
- `memory / kb_search / kb_vectors / events` 默认回 `~/.openmind/*`

也就是说，系统早就不是“一个统一知识库”模型，只是之前没有把这件事正式说透。

### 4.2 live 数据厚度差异非常大

本次再核对到：

- `data/evomap_knowledge.db`
  - `documents=7863`
  - `atoms=99493`
  - `edges=90611`
- `home memory`
  - `records=5`
- `home KB`
  - `fts=4`
  - `registry=2`
  - `quality>0=0`
  - `non-draft=0`
- `home events`
  - `trace_events=6`

所以这里不存在“两个差不多厚的知识中心”。

现实是：

- `EvoMap` 厚
- 其他三套薄

### 4.3 hot path 也是组合式消费，不是单库消费

`ContextResolver` 同时装配：

- `memory`
- `kb_hub`
- `evomap_db`

`consult` 也同时看：

- KB
- EvoMap

这说明今天的运行态已经把这些对象分工使用，而不是等着哪一天再统一。

### 4.4 最大缺口在写回 contract

`KnowledgeIngestService` 已经能：

1. 写 KB
2. 再镜像到 EvoMap

但 `advisor graph` 正式的 `planning / research / report / funnel` 写回路径，当前还是：

1. 写文件
2. 注册 KB artifact
3. 发事件

没有统一走 graph projection。

这就是为什么这份决策文档最后没有说“现在已经完全统一好了”，而是明确写成：

- **canonical plane 已选定**
- **canonical projection contract 还要补**

## 5. 为什么最终没有选“全并库”

### 5.1 为什么不是全部 repo-local

如果把 `memory / event bus / KB working set` 都强行并到 repo：

- 会把 user/runtime-local 状态和项目知识混掉
- 会让 session/capture 相关数据失去清晰边界
- 会让 OpenClaw runtime substrate 和用户工作台的关联变弱

### 5.2 为什么不是全部 HOME-relative

如果把 canonical knowledge 也跟着 HOME 走：

- repo audit 会弱化
- knowledge authority 会跟 runtime/home 环境绑死
- planning/research 的正式知识资产会继续漂

### 5.3 为什么是 split-plane

因为它最符合今天真实代码：

- `memory/events/KB` 负责 runtime working plane
- `EvoMap` 负责 canonical knowledge plane

这不是抽象设计偏好，而是现实代码已经在这么跑。

## 6. 文档里的关键定稿

这次最终定了 4 个核心口径：

1. `memory.db` 是 runtime memory，不是主知识库。
2. `kb_registry/search/vector` 是 working-set artifact evidence layer，不是 canonical 知识层。
3. `events.db` 是 runtime event backbone，不是 durable system ledger。
4. `data/evomap_knowledge.db` 才是 canonical knowledge graph / retrieval substrate。

## 7. 和后续计划的关系

这份决策落完之后，后续 `Phase 0` 的顺序就更清楚了：

1. 先把这些 DB path 做显式 env pinning
2. 再做 `routing_authority_decision_v1`
3. 再做 `front_door_contract_v1`
4. 最后才补知识写回到 canonical graph 的正式接口

也就是说，知识 authority 已经足够清楚，可以进入实现阶段；还没清楚的是前门和模型路由。

## 8. 产物

本次新增：

- [2026-03-20_knowledge_authority_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_knowledge_authority_decision_v1.md)
- [2026-03-20_knowledge_authority_decision_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_knowledge_authority_decision_walkthrough_v1.md)

## 9. 测试与残留

这次仍然是文档决策任务，没有代码改动，也没有跑测试。

这次没有顺手处理的代码残留有两个：

- `advisor graph` 的正式写回主链还没有统一到 `KnowledgeIngestService`
- DB path 还没有做显式 env pinning

它们都已经被转成下一步清单，不再是隐性问题。
