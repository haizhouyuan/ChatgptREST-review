# 2026-03-20 Knowledge Authority Decision v1

## 1. 决策目标

这份文档承接 [2026-03-20_authority_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v1.md) 里仍未冻结的这一组 authority：

- `memory`
- `KB registry / search / vectors`
- `event bus`
- `EvoMap`

这次不再只是盘点，而是做出明确决策：

**知识层采用 `split-plane`，不是全量并库。**

也就是说：

- `EvoMap` 负责 canonical knowledge plane
- `memory / KB / event bus` 负责 runtime working plane

二者以后必须通过显式写回和镜像契约联通，不能再靠“反正都叫 OpenMind 数据”混写。

## 2. 先说结论

### 2.1 采用的方案

采用 `Split-Plane with Explicit Pinning`：

1. `data/evomap_knowledge.db`
   - 继续作为 **唯一 canonical knowledge graph / retrieval substrate**
2. `~/.openmind/memory.db`
   - 继续作为 **个人/会话级 runtime memory**
   - 不升格为 canonical corpus
3. `~/.openmind/kb_registry.db` + `kb_search.db` + `kb_vectors.db`
   - 继续作为 **front-door working set / artifact index**
   - 不再宣称是长期 authoritative knowledge base
4. `~/.openmind/events.db`
   - 继续作为 **runtime event backbone**
   - 不再宣称是 durable system ledger
5. 所有这些路径都必须改成 **显式 env pinning**
   - 不再继续依赖 `HOME` 间接决定 authority

### 2.2 不采用的方案

不采用 `All Repo-Local`：

- 因为 `memory / event bus / session-adjacent hot state` 天然是 user/runtime-local
- 强行 repo-local 会把个人运行态和项目知识层混成一坨

不采用 `All HOME-Relative`：

- 因为 canonical knowledge 如果跟着 runtime HOME 走，会让 planning/research 的主知识资产脱离 repo audit 和受控路径
- 今天已经证明 `repo-local EvoMap` 才是最厚、最稳定的知识资产

## 3. 代码现实

### 3.1 当前 runtime 初始化已经是非对称结构

[advisor/runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py) 当前实际初始化方式是：

- `ArtifactRegistry` 默认 `OPENMIND_KB_DB` 或 `~/.openmind/kb_registry.db`
- `KBHub` 默认 `resolve_openmind_kb_search_db_path()` 和 `resolve_openmind_kb_vector_db_path()`
- `MemoryManager` 默认 `OPENMIND_MEMORY_DB` 或 `~/.openmind/memory.db`
- `EventBus` 默认 `resolve_openmind_event_bus_db_path()`
- `EvoMap KnowledgeDB` 走 `resolve_evomap_knowledge_runtime_db_path()`

其中 [openmind_paths.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/openmind_paths.py) 已经明确做了一个不对称决定：

- `EvoMap runtime DB` 默认强制回 repo-local `data/evomap_knowledge.db`
- `memory / kb_search / kb_vectors / events` 仍然默认回 `~/.openmind/*`

也就是说，系统代码本身已经隐含选择了 split-plane，只是之前没有正式承认。

### 3.2 当前 live 数据也支持 split-plane 结论

截至本次核对：

- `data/evomap_knowledge.db`
  - `documents = 7863`
  - `atoms = 99493`
  - `edges = 90611`
- `/home/yuanhaizhou/.home-codex-official/.openmind/memory.db`
  - `memory_records = 5`
- `/home/yuanhaizhou/.home-codex-official/.openmind/kb_search.db`
  - `kb_fts_meta = 4`
- `/home/yuanhaizhou/.home-codex-official/.openmind/kb_registry.db`
  - `artifacts = 2`
  - `quality_score > 0 = 0`
  - `non-draft stability = 0`
- `/home/yuanhaizhou/.home-codex-official/.openmind/events.db`
  - `trace_events = 6`

这说明：

- `EvoMap` 是厚 canonical store
- 当前 `memory / KB / events` 是薄 runtime store

如果在这种现实下硬说“memory/KB 才是主知识库”，那是错口径。

### 3.3 当前消费面也是 split-plane

`ContextResolver` 在 [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py) 里同时装配：

- `memory`
- `kb_hub`
- `evomap_db`

这意味着当前 hot path 已经是三路上下文组装，不是单库。

`consult` 在 [routes_consult.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_consult.py) 里也体现了相同模式：

- KB 走 `resolve_consult_kb_db_path()`
- EvoMap 走 `resolve_evomap_knowledge_read_db_path()`
- recall telemetry 直接写回 EvoMap telemetry tables

因此从消费面看：

- `KB` 更像轻量文档 evidence layer
- `EvoMap` 更像真正的 knowledge graph / recall substrate

### 3.4 当前写回面还没有完全收口

这里是现在最大的知识 authority 缺口。

`KnowledgeIngestService` 在 [ingest_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/ingest_service.py) 里已经支持：

- 先写 `KB`
- 再按 `OPENMIND_COGNITIVE_GRAPH_MIRROR_MODE` 做 EvoMap graph mirror

但 `advisor graph` 里的 `planning / research / report / funnel` 正式写回路径，在 [graph.py::_kb_writeback_and_record](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py#L681) 里目前还是：

- 写文件
- 注册 KB artifact
- 发 `kb.writeback` event

**没有** 统一通过 `KnowledgeIngestService` 完成 canonical graph projection。

这意味着今天的知识层 authority 决策不能只停在“路径选哪边”，还必须承认：

- canonical graph projection contract 还没完全打通

## 4. 决策

## 4.1 EvoMap

### 决策

`data/evomap_knowledge.db` 继续作为：

- `planning / research` 的 canonical knowledge graph
- 主 retrieval substrate
- recall telemetry substrate
- review/archive/provenance plane

### 理由

1. 当前最厚。
2. 当前路径口径最清楚。
3. `consult` 和 graph retrieval 已经偏向它。
4. `03-10` 开始的 authority 文档就已经把它钉成 canonical。

### 规则

- 以后任何“主知识库”措辞，默认指 EvoMap，不指 KB registry/search。
- 任何 planning/research 正式产物，只要被判定为可保留知识，就必须能进入 EvoMap，不能只停在 KB artifact。

## 4.2 Memory

### 决策

`~/.openmind/memory.db` 保留为：

- user/runtime-local working memory
- episodic memory
- captured guidance store

但明确 **不是** canonical knowledge corpus。

### 理由

1. `MemoryCaptureService` 的语义就是 session/account/agent/thread 相关的运行时记忆。
2. 当前 memory 热路径围绕 `captured guidance`，天然偏 personal/runtime。
3. 这类数据跟 `OpenClaw session continuity` 绑定，比跟 repo 更绑定。

### 规则

- `memory.db` 的 authority 是“运行时个体记忆”，不是“项目知识总库”。
- semantic consolidation 可以继续做，但即便做厚，也不改变它属于 runtime plane 的性质。
- 以后如果要做迁移，也只能是把 **合格知识** 投影到 EvoMap，不是把 MemoryManager 本身升成总知识库。

## 4.3 KB Registry / Search / Vectors

### 决策

`kb_registry.db`、`kb_search.db`、`kb_vectors.db` 保留为：

- front-door working set
- artifact registry
- text-centric evidence retrieval layer

但明确 **不再视为 canonical knowledge authority**。

### 理由

1. 当前 live 数据很薄。
2. registry 治理生命周期在当前 live runtime 下几乎没跑起来。
3. `KBHub` 的定位本来就是 retrieval facade，不是主知识图。
4. 正式 graph authority 已经在 EvoMap。

### 规则

- KB 的角色是“让 runtime 快速找文档证据、管理 artifact 元数据、做写回落点”。
- planning/research 正式知识不能只停在 KB；KB 只是工作集，不是终局库。
- `KB writeback success != canonical knowledge accepted`。

## 4.4 Event Bus

### 决策

`events.db` 保留为：

- runtime event backbone 的本地 durability 层
- subscriber fanout / side effect backbone

但明确 **不作为 durable system ledger**。

### 理由

1. 现在真正厚的系统 ledger 是 `jobdb`。
2. `EventBus` 的价值是 pub/sub 与低延迟 cross-layer coordination，不是长期系统审计总账。
3. 当前 live `events.db` 很薄，不能把它误判成另一个 `jobdb`。

### 规则

- system-level audit / incidents / controller trace 继续看 `jobdb`
- knowledge-level canonical provenance 继续看 `EvoMap`
- runtime event flow 和 subscriber side effects 看 `events.db`

## 5. 最终结构

冻结后的知识层结构应该按下面理解：

```text
OpenClaw session/runtime
    -> Memory DB (personal/runtime memory)
    -> EventBus DB (runtime event backbone)
    -> KB Registry/Search/Vector (working-set + artifact evidence)
    -> EvoMap Knowledge DB (canonical knowledge graph)
```

换句话说：

- `memory / events / KB` 是 runtime working plane
- `EvoMap` 是 canonical knowledge plane

## 6. 必须跟着决策一起落地的规则

### 6.1 显式 env pinning

当前最不应该继续保留的是“靠 HOME 间接决定 DB 路径”。

下一步应该显式固定：

- `OPENMIND_MEMORY_DB`
- `OPENMIND_KB_DB`
- `OPENMIND_KB_SEARCH_DB`
- `OPENMIND_KB_VEC_DB`
- `OPENMIND_EVENTBUS_DB`
- `EVOMAP_KNOWLEDGE_DB`

建议固定为：

- `OPENMIND_MEMORY_DB=/home/yuanhaizhou/.home-codex-official/.openmind/memory.db`
- `OPENMIND_KB_DB=/home/yuanhaizhou/.home-codex-official/.openmind/kb_registry.db`
- `OPENMIND_KB_SEARCH_DB=/home/yuanhaizhou/.home-codex-official/.openmind/kb_search.db`
- `OPENMIND_KB_VEC_DB=/home/yuanhaizhou/.home-codex-official/.openmind/kb_vectors.db`
- `OPENMIND_EVENTBUS_DB=/home/yuanhaizhou/.home-codex-official/.openmind/events.db`
- `EVOMAP_KNOWLEDGE_DB=/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db`

注意：

- 这一步不是为了改结构，而是为了把已经存在的结构写死，避免隐式漂移。

### 6.2 写回 contract 必须补齐

以后 planning/research 的正式知识写回必须满足：

1. artifact 先写入 KB working set
2. canonical knowledge 再投影到 EvoMap
3. 如果 graph projection 没成功，不能把这次写回当作“知识层已完整收口”

这意味着下一步要么：

- 把 `advisor graph` 的 `_kb_writeback_and_record()` 收敛到 `KnowledgeIngestService`

要么：

- 给它补一条正式的 graph mirror contract

### 6.3 术语统一

从这份文档起，后续所有计划和蓝图里：

- `OpenMind memory` 指 runtime memory
- `KB` 指 working-set artifact evidence layer
- `EvoMap` 指 canonical knowledge graph

禁止再用“知识库”这个总称同时指这三套东西。

## 7. Rejected Alternatives

### 7.1 全部切 repo-local

不采用。

因为这会把：

- 会话相关记忆
- user/runtime-local event bus
- assistant working set

全都并进项目库，混掉 runtime/user 边界。

### 7.2 全部切 HOME-relative

不采用。

因为 canonical knowledge 需要：

- 可审计
- 可回溯
- 可跟 repo/runtime 一起治理

如果跟着 HOME 漂，会继续制造 authority 歧义。

### 7.3 让 KB 继续当主知识库，EvoMap 只是 graph projection

不采用。

因为当前现实刚好相反：

- 厚的是 EvoMap
- 薄的是当前 live KB

## 8. 下一步

这份决策落完后，`Phase 0` 知识层下一步动作应该是：

1. 把 DB path 做显式 env pinning
2. 写 `routing_authority_decision_v1`
3. 写 `front_door_contract_v1`
4. 补 `advisor graph -> canonical graph projection` 的正式接口方案
5. 把 `event bus` 的定位写进后续 telemetry 决策，避免再和 `jobdb` 冲突

## 9. 最小结论

知识层以后不再按“一个 OpenMind 知识库”理解。

正确理解是：

- `memory / events / KB` 负责运行时工作集
- `EvoMap` 负责 canonical knowledge

这不是退让，而是承认当前最有效、最稳的真实结构，然后把它正式化。
