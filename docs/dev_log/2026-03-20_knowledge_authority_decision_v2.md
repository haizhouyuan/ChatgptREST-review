# 2026-03-20 Knowledge Authority Decision v2

## 1. 为什么需要 v2

[2026-03-20_knowledge_authority_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_knowledge_authority_decision_v1.md) 已经把知识层定成了 `split-plane`，这个大方向不变。

但在 [2026-03-20_authority_matrix_verification_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_verification_v1.md) 之后，有一个必须补的修正：

- `EvoMap` 在 runtime 里不是单一 DB，而是至少分成：
  - `knowledge DB`
  - `signals DB`

所以 v2 的任务不是推翻 v1，而是把知识层正式改写成：

**`runtime working plane + EvoMap signals plane + EvoMap canonical knowledge plane`**

## 2. 继续成立的核心结论

下面这些结论继续成立：

1. `memory / KB / event bus` 不是 canonical knowledge authority。
2. `data/evomap_knowledge.db` 仍然是 canonical knowledge graph DB。
3. planning/research 正式知识不能只停在 KB artifact。
4. 现在最该收的是显式 env pinning 和 canonical graph projection contract。

## 3. v2 修正点

## 3.1 EvoMap 不是单 plane

v1 把 EvoMap 近似成“canonical knowledge plane”，这在知识主库层面没错，但对 runtime 来说不够完整。

当前代码明确分成两层：

- [openmind_paths.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/openmind_paths.py)
  - `resolve_evomap_knowledge_runtime_db_path()` -> repo-local `data/evomap_knowledge.db`
- [evomap/paths.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/paths.py)
  - `resolve_evomap_db_path()` -> HOME-relative `~/.openmind/evomap/signals.db`

而 [advisor/runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py) 运行时同时用这两条：

- `EvoMapObserver` / team scorecard / team policy / team control plane 用 `signals.db`
- `KnowledgeDB` / graph retrieval / graph ingest 用 `evomap_knowledge.db`

## 3.2 所以知识层应该重新分 3 个 plane

### Plane A: Runtime Working Plane

包含：

- `memory.db`
- `kb_registry.db`
- `kb_search.db`
- `kb_vectors.db`
- `events.db`

职责：

- 会话级记忆
- artifact working set
- text evidence retrieval
- event backbone

### Plane B: EvoMap Signals Plane

包含：

- `~/.openmind/evomap/signals.db`

职责：

- observer/runtime signals
- scorecard / team policy / secondary runtime scoring
- 运行期 feedback loop

### Plane C: EvoMap Canonical Knowledge Plane

包含：

- `/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db`

职责：

- canonical knowledge graph
- long-lived retrieval substrate
- recall telemetry substrate
- provenance / review / archive plane

## 4. 决策

## 4.1 Memory

不变：

- `memory.db` 继续是 runtime-local memory
- 不升格成 canonical knowledge

## 4.2 KB

不变：

- `KB` 继续是 working-set artifact/evidence layer
- 不升格成 canonical knowledge

## 4.3 EventBus

不变：

- `events.db` 继续是 runtime event backbone
- 不升格成 durable system ledger

## 4.4 EvoMap Signals DB

### 新增决策

`~/.openmind/evomap/signals.db` 明确定位为：

- **runtime observer / scoring / signals plane**

但明确 **不是 canonical knowledge DB**。

### 规则

- 以后提 “EvoMap runtime” 时，必须先说清是在指：
  - `signals plane`
  - 还是 `knowledge plane`
- `signals.db` 可以薄，但不能被误判成 dead code
- 它不是 planning/research 主知识库，也不是 execution 主 ledger

## 4.5 EvoMap Knowledge DB

不变但表述更精确：

- `data/evomap_knowledge.db` 是 **canonical knowledge plane**
- 不是整个 EvoMap runtime 的全部状态

## 5. 最终结构 v2

从 v2 开始，知识层必须按下面理解：

```text
OpenClaw / ChatgptREST runtime
    -> Memory DB
    -> KB Registry/Search/Vector
    -> EventBus DB
    -> EvoMap Signals DB
    -> EvoMap Knowledge DB
```

语义上：

- `memory / KB / events` = runtime working plane
- `signals.db` = runtime observer plane
- `evomap_knowledge.db` = canonical knowledge plane

## 6. 为什么这比 v1 更准确

因为它解决了 v1 容易误导的地方：

1. v1 容易让人以为 EvoMap 只有一个 DB
2. v1 没把 signals plane 的作用写出来
3. v1 容易把 observer/runtime scoring 混进 canonical knowledge 叙事

## 7. 必须跟着 v2 一起落地的规则

### 7.1 显式 env pinning

除了 v1 里列出的：

- `OPENMIND_MEMORY_DB`
- `OPENMIND_KB_DB`
- `OPENMIND_KB_SEARCH_DB`
- `OPENMIND_KB_VEC_DB`
- `OPENMIND_EVENTBUS_DB`
- `EVOMAP_KNOWLEDGE_DB`

还应该新增显式固定：

- `OPENMIND_EVOMAP_DB=/home/yuanhaizhou/.home-codex-official/.openmind/evomap/signals.db`

### 7.2 术语统一

从 v2 开始，禁止再写模糊措辞：

- “EvoMap DB”
- “OpenMind 知识库”

必须具体写：

- `EvoMap signals DB`
- `EvoMap knowledge DB`
- `KB working set`
- `runtime memory`

## 8. 残留未解决项

这次仍然没有顺手实现的，是：

1. `advisor graph` 正式写回主链还没有统一走 canonical graph projection
2. env pinning 还没真正落代码/配置

## 9. 最小结论

`knowledge_authority_decision_v1` 的核心判断没有错，但粒度不够。

从 v2 开始，知识层的正式口径应该是：

- `memory / KB / events` 是 runtime working plane
- `signals.db` 是 EvoMap runtime observer plane
- `data/evomap_knowledge.db` 是 canonical knowledge plane

这才是当前真实代码和真实运行态共同支持的结构。
