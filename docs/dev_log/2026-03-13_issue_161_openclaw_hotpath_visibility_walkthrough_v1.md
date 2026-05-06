# Issue #161 OpenClaw Hot-Path Visibility Walkthrough v1

**日期**: 2026-03-13  
**分支**: `codex/issue-161-implementation-20260313`  
**Issue**: `#161`

---

## 做了什么

### 1. 把 `openmind-memory` 默认 recall 改成 knowledge-aware

在 `openclaw_extensions/openmind-memory/index.ts` 中：

- 默认 source 从 `memory + policy` 改成 `memory + knowledge + graph + policy`
- 新增 `buildResolveContextRequest()`，把 `/v2/context/resolve` 的 payload 构造集中到一个 helper
- 继续透传 `session_key / account_id / agent_id / role_id / thread_id / repo`

这样 OpenClaw 主热路径默认就会去读取已经存在的 knowledge/graph 面，而不是只吃 memory continuity。

### 2. 修掉 `sources` 和 `graph_scopes` 的脱钩

同一处 helper 里：

- 只有当 source 包含 `graph` 时才发送 `graph_scopes`
- 不再无条件发送 `graph_scopes`

这让插件默认契约和服务端退化语义保持一致，也避免继续制造“好像请求了 graph，其实没有”的假象。

### 3. 更新插件说明和版本

更新了：

- `openclaw_extensions/openmind-memory/README.md`
- `openclaw_extensions/openmind-memory/package.json`
- `openclaw_extensions/openmind-memory/openclaw.plugin.json`

README 已改成“默认 hot-path 会请求 memory/knowledge/graph/policy”，并保留 `graphScopes` 只控制 graph detail 的说明。

### 4. 补 plugin regression tests

在 `tests/test_openclaw_cognitive_plugins.py` 中：

- 校验默认 source 常量现在包含 `knowledge + graph`
- 校验新 helper 存在
- 校验 `requestGraph` 判断存在
- 校验 `graph_scopes` 只在 graph source 启用时注入

这类插件测试在当前仓库是源码契约回归，不依赖额外 TypeScript 运行器。

---

## 为什么现在这么做

复核当前相关 issue 后，结论是：

- `#121` 已经把 memory identity/degraded semantics 打了底
- `#161` 当前仍是最直接的热路径 blocker
- `#129` 和 `#132` 依然成立，但属于“读到以后质量/升格怎么控”的下阶段问题
- `#134` 仍是 authority contract 的独立整治项，不应和 `#161` 混在一个 PR 里

所以本轮策略是：

- 只修热路径默认契约
- 不在同一 PR 顺手重构 retrieval/promotion/authority
- 但在执行计划里明确把 `#128/#129/#132/#134` 保留下来

---

## 验证

执行过的验证：

- `python3 -m py_compile tests/test_openclaw_cognitive_plugins.py tests/test_cognitive_api.py`
- `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_openclaw_cognitive_plugins.py tests/test_cognitive_api.py`

结果：

- 通过
- `tests/test_cognitive_api.py` 现有 graph/memory degrade 测试未被破坏

---

## 本轮未做

- 没有修改 `chatgptrest/evomap/knowledge/retrieval.py` 的 staged retrieval 默认值
- 没有修改 `chatgptrest/evomap/activity_ingest.py` 的 auto-promotion 路径
- 没有把 authority contract 完整统一到单一 live store policy

---

## 下一步建议

1. 以 `#129` 为下一条主线，先把 retrieval quality gate 收紧。
2. 之后接 `#132`，让 activity ingest 不再长期积压在 `STAGED`。
3. 再处理 `#128`，把 feedback / usage 真正接进返回路径。
