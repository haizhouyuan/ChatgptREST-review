# Issue #161 OpenClaw Hot-Path Visibility Execution Plan v1

**日期**: 2026-03-13  
**分支**: `codex/issue-161-implementation-20260313`  
**Issue**: `#161` `OpenClaw default recall excludes knowledge and graph, making canonical objects invisible on the main hot path`

---

## 目标

把 OpenClaw `openmind-memory` 插件的默认 recall 契约从 `memory + policy` 修到 `memory + knowledge + graph + policy`，并补上最小但有效的回归测试和开发记录。

本轮只解决默认热路径可见性，不在一个 PR 里顺手处理 authority unification、retrieval quality gate、promotion automation。

---

## 历史 issue 复核

### `#121` memory identity / dedup / capture hardening

当前判断：**大部分已落地，仍有后续可做项，但不是本轮阻塞**

- `MemoryManager` 的 dedup 已包含 identity-scoped 字段，不再是早期单纯 `fingerprint + category`。
- `context_service.py` 已把缺失 identity、captured memory scope、repo graph 缺失标成 degraded。
- `memory_capture_service.py` 已有服务端 quality gate 和 blocked event。
- `openmind-advisor` 慢路径身份透传现在也在。

结论：

- `#121` 不该再作为 `#161` 的前置 blocker。
- 本轮只复用其“degraded semantics 已存在”的成果，不重开 memory hardening。

### `#128` feedback loop dead code

当前判断：**仍成立**

- `telemetry.py` 里 `record_feedback()`、`mark_atoms_used()`、`get_frustration_index()`、`get_gap_metrics()` 还在。
- repo 内当前没有找到稳定生产路径把这些函数真正接上 recall/advisor 返回路径。
- `answer_feedback` 当前库内计数仍是 `0`。

结论：

- 这是独立的 P0/P1 学习闭环问题。
- 不纳入本 PR，但需要保留在 follow-up queue。

### `#129` retrieval serves staged atoms by default

当前判断：**仍成立**

- `chatgptrest/evomap/knowledge/retrieval.py` 仍默认 `allowed_promotion_status = (ACTIVE, STAGED)`。
- 当前库状态仍是 `active=201`、`candidate=25`、`staged=96334`，默认检索噪音比极高。

结论：

- `#161` 修完以后，主热路径会更容易读到 knowledge/graph，但也会把 `#129` 的噪音问题暴露得更明显。
- 因此 `#129` 必须被明确挂到本 issue 的后续计划里。

### `#132` activity ingest auto-promotion gap

当前判断：**部分变化，但问题仍成立**

- `cognitive/ingest_service.py` 新写入对象已是 `status=CANDIDATE`。
- 但 `evomap/activity_ingest.py` 里的 commit/closeout ingest 仍写 `promotion_status=STAGED`。
- 也没有看到统一的自动 promote batch/job 正在默认跑。

结论：

- `#132` 不是完全没动，但主问题没有消失。
- 本轮不改 promotion pipeline，只把它列为 `#161` 的后续约束。

### `#134` authority resolution / legacy-store growth

当前判断：**部分缓解，未彻底完成**

- `core/openmind_paths.py` 已把一部分路径收敛到 canonical `data/evomap_knowledge.db`。
- `advisor/runtime.py` 和 `routes_consult.py` 已使用统一 helper。
- 但 `~/.openmind/*` 仍然是 memory/kb/event 等 runtime store 的实际来源之一，authority classification 还没有完全显式化。

结论：

- `#134` 不再是“完全无进展”。
- 但它依旧独立存在，不能因为 `#161` 修复了默认 recall source 就被误判为已解决。

### `#161` default recall excludes knowledge/graph

当前判断：**仍完全成立，且应当立即修**

- `openclaw_extensions/openmind-memory/index.ts` 当前仍写死 `["memory", "policy"]`。
- 插件仍然无条件发送 `graph_scopes`，即使 `sources` 不包含 `graph`。
- 服务端 `/v2/context/resolve` 已经支持 `memory + knowledge + graph + policy`，所以瓶颈明确在插件默认契约。

---

## 当前状态快照

2026-03-13 本地复核：

- `data/evomap_knowledge.db`
  - `documents=7780`
  - `atoms=97102`
  - `evidence=80465`
  - `promotion_active=201`
  - `promotion_candidate=25`
  - `promotion_staged=96334`
- `state/knowledge_v2/canonical.sqlite3`
  - 目前仍只有 `issue_domain`
- 主文档来源前几位：
  - `planning=3350`
  - `chatgptrest=2213`
  - `antigravity=1113`
  - `planning_review_plane=542`
  - `maint=446`

这说明：

- knowledge/graph 面上已经有不少内容；
- `#161` 修复后会立即提升主入口的可见 corpus；
- 但 `#129` 会成为下一波最明显的质量瓶颈。

---

## 本轮范围

### In Scope

- 修改 `openmind-memory` 默认 recall sources
- 让 `graph_scopes` 只在请求 graph 时发送
- 更新插件 README 和必要的 package/manifest 版本
- 补 plugin-side regression tests
- 补一份执行 walkthrough

### Out of Scope

- 修改 retrieval quality gate
- 修改 activity ingest promotion pipeline
- 做 authority contract 全量统一
- 扩展 bulk ingest 或 canonical promotion 策略

---

## 实现方案

### 1. 修插件默认 recall 契约

在 `openclaw_extensions/openmind-memory/index.ts`：

- 把默认 recall source 改为 `["memory", "knowledge", "graph", "policy"]`
- 把发往 `/v2/context/resolve` 的 payload 显式构造成 helper，避免未来再出现 source / graph_scopes 脱钩
- 当请求 source 不含 `graph` 时，不再发送实际 `graph_scopes`

### 2. 明确 README 口径

更新 `openclaw_extensions/openmind-memory/README.md`：

- 不再写“memory-first defaults to memory + policy”
- 改成“默认会带 memory/knowledge/graph/policy；graph detail 仍受 `graphScopes` 配置约束”

### 3. 增加回归测试

优先补两类测试：

- `tests/test_openclaw_cognitive_plugins.py`
  - 验证插件源码默认 source 已包含 `knowledge + graph`
  - 验证 `graph_scopes` 与 graph source 绑定
- 保持 `tests/test_cognitive_api.py` 现有 context/graph degrade tests 继续通过

### 4. 文档与后续问题收口

在 walkthrough 中明确：

- `#121` 已可降级为背景问题
- `#128 / #129 / #132 / #134` 仍为后续计划
- 本 PR 不关闭这些 related issues，只为 `#161` 打通热路径

---

## Follow-Up Queue

本轮执行后应继续推进：

1. `#129` 把默认 retrieval promotion gate 从 `ACTIVE + STAGED` 改到 `ACTIVE + CANDIDATE` 或更严格口径。
2. `#132` 给 activity ingest 增加自动 promote 机制，至少对高质量 commit/closeout path 生效。
3. `#128` 在 advisor / consult / MCP 结果返回链路接上 `mark_atoms_used()` 与 feedback capture。
4. `#134` 把 authority classification 做成真正的 live contract，而不是 helper-level partial convergence。

---

## 验收标准

1. OpenClaw `openmind-memory` 默认 recall 会请求 `memory + knowledge + graph + policy`。
2. graph 未启用时，payload 不再发送误导性的 `graph_scopes`。
3. plugin regression tests 覆盖新的默认 source 行为。
4. 现有 cognitive API graph/memory degraded tests 继续通过。
5. walkthrough 里清楚写明本轮已修与未修边界。
