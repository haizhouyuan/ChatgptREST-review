# 2026-03-25 Low-Level Ask Identity Guard Walkthrough v1

## 这次为什么要做

主线目标不是再加一层泛化 prompt moderation，而是把 low-level ask 入口改成：

- 先知道“是谁”
- 再判断“有没有权限”
- 最后只对灰区 automation ask 做 intent 审核

这样才能把真正危险的来源和工作负载分开：

- `Codex / Claude Code / Antigravity` 继续统一走 public advisor-agent MCP
- `openclaw / planning / 其他 automation wrapper` 只有在登记身份后，才允许碰 low-level ask
- `smoke / test / extractor / sufficiency gate` 不再能匿名或模糊身份地占 live web ask 容量

## 实现顺序

### 1. 先建 registry

新增 `ops/policies/ask_client_registry.json`，把低层 ask caller 按角色分成：

- `interactive_trusted`
- `automation_registered`
- `maintenance_internal`
- `testing_only`

同时登记：

- 允许哪些 surface
- 允许哪些 kind
- 能不能碰 live ChatGPT / Gemini / Qwen / deep_research / Pro
- 是否只跑 deterministic guard，还是允许 Codex classify

### 2. 再把 guard 接进 `/v1/jobs`

`create_job_route()` 现在对 web ask 先做：

1. resolve client identity
2. authz / trust-class gate
3. deterministic intent block
4. optional Codex classify
5. 再走已有 prompt policy

这样做的结果是：

- identity 缺失/未登记会优先暴露
- interactive coding client 不会再被 `allow_direct_live_chatgpt_ask` 绕回旧入口
- automation caller 进库前就会被 canonicalize 成稳定 `client_id`

### 3. 把例外收紧成 maintenance-only

以前某些路径还把 `params.allow_direct_live_chatgpt_ask=true` 当紧急逃生口。现在它不再能给 interactive/unregistered caller 开后门。

真正的 low-level 维护例外只剩：

- `chatgptrest-admin-mcp`
- `chatgptrestctl-maint`
- 其他未来明确登记为 `maintenance_internal` 的 client

### 4. 给 gray-zone automation 接 Codex schema classify

deterministic 规则可以稳定挡住 smoke/test/microtask，但挡不住所有“看起来像真的 review，实际上又很低价值”的 automation ask。

这次只把 Codex classify 放给 `planning-wrapper` / `openclaw-wrapper` 这类 gray-zone automation，用 `ops/schemas/ask_guard_decision.schema.json` 约束输出，避免把所有请求都先送去跑一轮额外模型。

## 结果

现在 low-level ask 的治理顺序变成：

- public MCP 负责交互式高层 turn
- low-level ask 负责少数登记过的 automation / maintenance caller
- 未登记来源默认进不来
- 低价值 microtask 默认进不来
- 可疑 gray-zone automation ask 走 Codex classify，再决定是否放行

## 这版没有做什么

- 没有把所有自动化项目都迁到 public advisor-agent MCP
- 没有改 public agent 自身的 route/provider/controller 逻辑
- 没有替换已有 prompt policy；这次是把 identity/authz/intention gate 放到了它前面

## 后续建议

1. 把 registry 扩成真正的 client onboarding 流程，而不是只靠维护者手工补 profile。
2. 对未登记 legacy caller 做 live inventory，逐个补 `source_repo` / `entrypoint` / owner。
3. 后续如果 `openclaw` / `finbot` 真的要复用 public advisor-agent MCP，也必须以 `automation_registered` 身份接入，而不是和 interactive coding client 共用权限模型。
