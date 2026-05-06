---
title: ChatgptREST新定位治理与退休收口方案
status: current governance plan
updated: 2026-04-17
owner: Codex
supersedes: docs/ops/2026-04-17_ChatgptREST新定位治理与退休收口方案_v1.md
---

# ChatgptREST新定位治理与退休收口方案 v2

## 一 本版变更目的

本版在 `v1` 的基础上，补入一条之前只在 planning/Hermes 侧被说清、但尚未正式进入 ChatgptREST 治理计划的 owner-side 问题：

**ChatGPT Web 非 Pro 约束、低价值题外发控制、以及 `requested_preset -> effective execution preset` 的可审计投影。**

这次修订的目标不是推翻 `v1`，而是把以下边界正式写进 ChatgptREST current governance：

1. planning 侧已经完成了什么；
2. ChatgptREST 侧已经有哪些局部护栏；
3. ChatgptREST owner-side 还缺哪一层统一治理闭环；
4. 这些问题在新定位里应归类为“继续投入的主路治理”，而不是 planning 仓的局部补丁。

## 二 v1 仍然成立的主判断

`v1` 的四分结论不变：

1. **保留并继续投入**
   - `automation-kernel-v1` / `automation_*`
   - job / worker / browser automation substrate
   - `/v2/context/resolve`
   - `/v2/graph/query`
   - `/v2/memory/capture`
   - 内部观测桥 `telemetry/ingest`
2. **冻结兼容**
   - `advisor_ask`
   - `advisor_agent_*`
   - `coding_agent_*`
   - `/v2/advisor/*`
   - `/v3/agent/*`
   - `consult` / 旧 facade router
3. **立即退休**
   - `qwen_web.ask` 的 current docs / examples / smoke 教学
   - “advisor-agent MCP 是默认入口”
   - “coding-agent-v1 是默认 northbound surface”
   - registry / bootstrap 里的旧 canonical surface 提示
4. **已开发但未采用**
   - `/v2/knowledge/ingest`
   - `/v2/kb/upsert`
   - `/v2/policy/hints`
   - “认知资产抽取 / 重宿主化”仍只是后续阶段路线

## 三 新增 fresh 结论：ChatGPT Web 价值/成本治理尚未 owner-side 收口

## 3.1 planning 侧已完成的部分

planning/Hermes 当前已经做完了三件事：

1. **低价值题默认禁发**
   - 系统自评题
   - 无对象泛化风险题
   - 无对象链路探针题
2. **提交模板更 object-driven**
   - 显式写入目标对象、预期读者、任务用途、证据边界
3. **以 fresh proof 证明上述 gate 生效**

也就是说，planning 侧已经不再把“低价值但容易出回执”的题，默认送去 `chatgpt_web` lane。

## 3.2 ChatgptREST 侧已经存在的局部护栏

ChatgptREST 并不是完全没有这类治理基础，当前至少已有三层局部护栏：

1. **低层 prompt / ask guard**
   - `chatgptrest/core/prompt_policy.py`
   - `chatgptrest/api/routes_jobs.py`
   - 已覆盖：
     - `live_chatgpt_smoke_blocked`
     - `trivial_pro_prompt_blocked`
     - `pro_smoke_test_blocked`
2. **wrapper / skill 层的 Pro 护栏**
   - `skills-src/chatgptrest-call/SKILL.md`
   - `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
   - 已要求：
     - trivial prompt 不要打到 ChatGPT Pro
     - smoke 默认不用 Pro
     - live ChatGPT smoke 视为例外路径
3. **executor 层的 premium fallback 逻辑**
   - `chatgptrest/executors/chatgpt_web_mcp.py`
   - 当前已存在：
     - `pro_extended -> thinking_heavy` 的 fallback 语义
     - fallback idempotency 与 meta 字段

## 3.3 真正还没收口的 owner-side 问题

虽然上面这些护栏存在，但它们还没有形成一套统一的 owner-side 治理合同。

当前仍然存在的 gap 是：

1. **低价值题治理仍然是分层碎片化的**
   - planning 侧已经能挡一类题；
   - ChatgptREST 侧有 smoke / trivial / synthetic 的局部 guard；
   - 但两边还没有共享一套“低价值外发 taxonomy”。
2. **非 Pro 默认没有做到执行面完全可审计**
   - 请求侧可能写 `preset=auto`；
   - 执行面却可能因为 policy default、premium route、fallback、deep-research normalization 等原因落成别的实际 preset；
   - 目前 evidence / provenance 还没有把这条链完全冻结成统一合同。
3. **object-driven prompt 已在 planning 侧实现，但 ChatgptREST 尚未把它提升为 shared backend 的 owner guidance**
   - 当前更多是“前台发出的 prompt 变好了”；
   - 还不是“shared backend 明确禁止低价值 / 无对象外发，并保证 premium lane 选择可解释”。

## 3.4 当前 preset 到底是谁在选

当前代码里，preset 不是由单一一层决定，而是四层串联：

### 第一层：调用方显式给定或默认补值

在 canonical public MCP `automation_ask` 上：

1. 调用方可以显式传 `provider` 和 `preset`
2. 如果不传，默认是：
   - `provider=chatgpt`
   - `preset=auto`

也就是说：

**`automation_ask` 本身不会替调用方做“智能选 preset”。**

### 第二层：旧 intelligent surface 会主动选 route/provider/preset

在 legacy/intelligent surfaces 上，server 会根据 task/route 先做一次选择：

1. `chatgptrest_advisor_ask`
   - 通过 advisor route 自动挑模型/preset
2. `/v3/agent/*`
   - 会根据 lane policy / route mapping 决定：
     - `quick_ask -> auto`
     - `analysis_heavy -> thinking_heavy`
     - `report -> pro_extended`
     - `deep_research -> deep_research`

也就是说：

**如果走的是旧 advisor / agent_v3 世界，那么 preset 可能是 server 先选出来的。**

### 第三层：server-side ask guard 可能再改一次

即使请求已经带了 preset，low-level ask guard 仍可能因 client policy 再做强制改写：

1. 不允许 Pro 的 registered client
2. smoke / trivial / synthetic ask
3. 需要降成 non-Pro 的 allow-with-limits 场景

当前代码里，`chatgpt_web.ask` 的安全 non-Pro fallback 会被改成 `auto`。

### 第四层：executor 运行时 fallback 可能再改一次

真正执行到 `chatgpt_web_mcp` 时，如果：

1. `preset=pro_extended`
2. send 阶段因为 unusual activity / blocked 状态没真正发出去

executor 还可能在运行时 fallback 到：

1. `thinking_heavy`
2. `auto`

因此，最终执行 preset 可能和请求 preset 不同。

## 3.5 这对“测试不用 Pro、真实使用因题而定”意味着什么

这个判断是对的，但要落在系统分层上：

1. **测试/探针**
   - 不应默认用 Pro
   - 优先 `preset=auto`
   - 低价值题不应作为 premium happy-path 证明
2. **真实业务场景**
   - 可以按对象、读者、用途、证据边界因题而定
   - 允许 `thinking_heavy / pro_extended / deep_research`
   - 但必须留下 premium-justification 与可审计的 preset 投影链

## 四 v2 对治理分类的新增修正

## 4.1 新增“保留并继续投入”的治理项

在 `v1` 的保留面中，新增一类明确保留并继续投入的治理能力：

| 类别 | 项目 | 决策 | 说明 |
| --- | --- | --- | --- |
| value/cost governance | ChatGPT Web 低价值题外发治理 | 保留并继续投入 | 属于 shared backend 主路治理，不是 planning 局部问题 |
| value/cost governance | `requested_preset -> effective preset` 审计合同 | 保留并继续投入 | 属于 premium lane 治理核心，不得放在 repo 外围脚本层解决 |

## 4.2 新增“不应继续放在 planning 侧独自承担”的事项

以下问题即使首先在 planning 仓被发现，也不应继续只由 planning 仓承担：

1. ChatGPT Web 非 Pro 默认约束
2. premium preset 升降级 / fallback 的证据解释
3. 低价值系统自评题的 owner-side taxonomy
4. object-driven prompt 最低合同字段

这些都属于 shared backend 的 owner responsibility。

## 五 执行计划新增 G5：ChatGPT Web 价值与 preset 治理

## G5 目标

把 planning 侧已完成的“低价值题 gate + object prompt”收口成 ChatgptREST owner-side 的统一治理合同。

## G5.0 基本原则

1. **测试治理**
   - 测试不应默认用 Pro
   - 低价值题不应进入 premium lane
   - premium lane 不应再被系统自评题充当成功样本
2. **生产治理**
   - 真实业务题允许因对象/用途而定选择 premium lane
   - 但 premium 选择必须可解释、可回溯、可审计

## G5.1 建立 shared taxonomy

目标：让 planning 侧和 ChatgptREST 侧说同一种“低价值外发”语言。

### 至少统一四类题

1. 系统自评题
2. 无对象泛化风险题
3. 无对象链路探针题
4. trivial/smoke/synthetic prompt

### 完成标准

1. planning-side gate taxonomy 与 ChatgptREST prompt policy 使用同一套分类词汇
2. owner-side docs 明确说明：
   - 哪些题默认不应外发
   - 哪些题默认不应进入 premium lane

## G5.2 冻结 preset 投影审计合同

目标：让“默认不用 Pro”从约定变成可核对证据。

### 每次 premium / fallback ask 至少要能回答

1. `requested_provider`
2. `requested_preset`
3. `effective_provider`
4. `effective_preset`
5. `selection_source`
6. `fallback_from`
7. `fallback_reason`
8. `why_premium_justified`

### 完成标准

1. `automation_*` summary / provenance 能稳定投影上述字段
2. current docs 明确区分：
   - `auto`
   - `pro_extended`
   - `thinking_heavy`
   - `deep_research`
   - `fallback`
3. 不再接受“请求侧是 auto，执行侧变 premium，但证据里说不清原因”的状态
4. 区分以下四个责任来源：
   - caller explicit request
   - legacy intelligent route default
   - server ask-guard rewrite
   - executor runtime fallback

## G5.3 建立 non-Pro default 的 owner-side 约束

目标：把“非 Pro 默认”从 wrapper 建议升级为 owner-side 规则。

### 最低要求

1. 低价值题默认不得进入 premium lane
2. 无对象题默认不得拿 premium ask 作为 happy-path 证明
3. object task 若进入 premium lane，必须留下 premium-justification
4. smoke / probe / synthetic ask 默认不应成为 current-head 成功证据

### 完成标准

1. owner-side docs 与 wrapper skill 口径一致
2. premium success evidence 必须是业务对象题，而不是系统自评题

## G5.4 将 object-driven prompt 从 planning 习惯提升为 shared contract

目标：即使前台不同，shared backend 也能要求最低对象合同。

### 最低字段

1. 目标对象
2. 预期读者
3. 任务用途
4. 证据边界

### 完成标准

1. current docs 明确这四项是推荐最小 ask contract
2. 评估与验收不再接受“只像顾问答案、不围绕对象”的 prompt

## 六 验收标准增补

除 `v1` 既有验收条件外，本版新增以下完成条件：

1. planning 侧低价值题 gate 与 ChatgptREST owner-side taxonomy 已对齐
2. `requested_preset -> effective preset` 能在 current-head 证据中被解释
3. premium lane 的 current-head 成功样本不再使用系统自评题或链路探针题
4. current docs 明确：
   - ChatGPT Web 默认非 Pro 治理不是 planning 私有规则
   - 而是 shared backend 的 owner-side 合同

## 七 一句话结论

`v1` 解决的是“新定位下保留什么、冻结什么、退休什么、哪些能力尚未采用”；  
`v2` 进一步解决的是：**planning 侧已经收口的 ChatGPT Web 低价值题 gate 和 object-driven prompt，不应停留在前台局部实现，而必须被提升为 ChatgptREST owner-side 的价值/成本治理合同。**
