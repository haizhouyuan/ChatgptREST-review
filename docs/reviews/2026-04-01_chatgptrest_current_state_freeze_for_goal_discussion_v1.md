# 2026-04-01 ChatgptREST 现状冻结稿 v1

## 目的

这份文档不是继续扩散调查，而是把下一阶段“目标讨论”需要共享的现状基线先冻结下来，避免后续讨论又回到端口漂移、runtime 真假、文档口径冲突这些旧问题上。

## 已冻结的当前事实

### 1. ChatgptREST 已经不是单一 OpenClaw 窄插件后端

按代码与运行态现实，它现在更接近：

- execution substrate
- advisor runtime
- public-agent governance facade
- cognitive substrate
- workspace / delivery side-effect plane
- task_runtime foundation

所以“它是不是已经独立了”这个问题，答案是：

> 它已经演化成多平面集成宿主；OpenClaw 仍是第一类集成方，但不再定义唯一产品叙事。

### 2. 现网默认 northbound / serving 事实

以 `2026-04-01` 这轮代码核验与 live probe 为准：

- `18711` 是统一 FastAPI host
- `18712` 是 public advisor-agent MCP
- `18713` 不是集成态默认 advisor host；它只能被视为 dedicated advisor 进程的可选端口

当前 repo 内活动维护文档、runtime registry、maint memory、health/bootstrap 链都已对齐到这组事实。

### 3. 已确认的问题不是单纯 prose drift

本轮已确认：

> `advisor_v3=18713` 旧事实曾经进入机器治理链，并通过 bootstrap packet 暴露给 agent。

这不是单纯“文档过时”，而是会影响 agent 判断 runtime reality 的代码级治理问题。

### 4. 这条机器治理链已完成首轮修复

本轮已经修完并提交：

- `ops(runtime): fix advisor runtime fact drift`
  - commit `88a8518b`
- `docs(runtime): align advisor host guidance`
  - commit `1284b092`

已收口的面包括：

- runtime registry
- HTTP liveness 规则
- bootstrap quick runtime snapshot
- maint bootstrap memory
- deep health probe 对 advisor 的漏检
- `AGENTS.md`
- Feishu webhook 活动运维文档

## 不应混入架构结论的事实

### 1. Workspace token 失效是时点 incident，不是架构否定

`WorkspaceService().auth_state()` 在 `2026-04-01` 的 live 结果里出现了 `invalid_grant`。这说明当前 Google token 失效，但不应据此推出“workspace 只是伪能力”。

更准确的口径是：

- workspace plane 作为正式 side-effect / delivery 面是成立的
- 当前 auth 状态是否可用，是 live runtime 健康问题

### 2. 历史文档保留时间截面，不等于当前口径

仓内仍有不少 dated dev log / audit / review 文档保留 `18713` 叙述。它们应被视为历史截面，而不是现网 authority source。

下一阶段讨论应以：

- 当前代码
- 当前活动维护文档
- 当前 runtime probe / bootstrap packet

作为主事实源。

## 下一阶段真正该讨论的问题

到这里为止，高清现状已经基本够用了。接下来不该继续纠缠“现在到底在哪个端口”，而应该进入这些目标问题：

### 1. authority matrix

需要冻结：

- 哪个 plane 是默认 northbound entry
- 哪个 plane 拥有 completion authority
- 哪个 plane 只是 governance / tooling / substrate

### 2. retirement matrix

需要明确：

- `/v1/jobs`
- `/v2/advisor/*`
- `/v3/agent/*`
- public MCP
- cognitive / workspace / task_runtime

分别是谁的 primary surface，哪些是 default，哪些是 maintenance-only，哪些只是 incubating subsystem。

### 3. repo 级产品句子

需要给 ChatgptREST 一个不再自相矛盾的 repo-level frozen sentence。

当前我建议的候选句是：

> ChatgptREST 是 execution substrate + advisor/runtime + public-agent governance 的集成宿主；OpenClaw 是第一类 shell/runtime integration，但不再定义其唯一产品叙事。

## 本稿用途

这份冻结稿只服务下一阶段目标讨论，不替代详细调查文档。

详细证据仍以前两份 review 为准：

- `docs/reviews/2026-04-01_chatgptrest_positioning_drift_code_runtime_reality_review_v1.md`
- `docs/reviews/2026-04-01_chatgptrest_positioning_drift_code_runtime_reality_review_v2.md`
