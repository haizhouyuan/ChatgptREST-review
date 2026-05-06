---
title: ChatgptREST新定位治理与退休收口方案 Walkthrough
status: completed
updated: 2026-04-17
owner: Codex
supersedes: docs/ops/2026-04-17_ChatgptREST新定位治理与退休收口方案_walkthrough_v2.md
---

# ChatgptREST新定位治理与退休收口方案 Walkthrough v3

## 为什么要出 v3

`v2` 已经把以下问题纳入治理：

1. ChatGPT Web 非 Pro 约束
2. 低价值题外发控制
3. `requested_preset -> effective preset` 审计

但进一步核对代码后，发现 `v2` 还不够高，原因有三：

1. 真正的问题不只是 preset，而是**执行层选择权**没有冻结；
2. `gemini auto` 不是一个真实 non-Pro 档，而是被规范化成 `pro`；
3. requested/effective/rewrite/fallback 仍主要靠 artifact 和日志反推，还不是正式 contract。

所以 `v3` 的目的，是把治理方案从 “preset governance” 升级为：

1. 执行层选择权治理
2. provider capability matrix 治理
3. 审计字段一等化
4. legacy surface 去权

## 这次补了什么

1. 明确写出 provider capability matrix 是根因的一部分：
   - `chatgpt` 有真实 `auto/non-Pro`
   - `gemini` 没有真实 `auto/non-Pro`
   - `gemini auto = alias_to_pro`
2. 新增 `G4.5`：
   - 是否外发
   - 外发到哪条 lane
   - 是否允许 premium
   必须前置冻结，不能由 ChatgptREST 在后端静默升级
3. 强化 `G5`：
   - `G5.0` provider capability matrix
   - `G5.1` provider-specific non-Pro policy
   - `G5.2` requested/effective/rewrite/fallback 进入正式 schema
   - `G5.3` legacy surface 去权
4. 把 `object-driven prompt` 和 premium gate 合并治理，避免继续把系统自评题当 premium happy-path 证据。

## 与 v2 相比，口径哪里变了

### v2 更像在说

1. 测试别默认用 Pro
2. premium ask 要能解释 preset 投影

### v3 改成

1. 先冻结 execution lane decision rights
2. 再冻结 provider capability truth
3. 再把 requested/effective/rewrite/fallback 做成正式 contract
4. 最后剥离 legacy route 对默认口径的污染

## 当前最重要的 repo 事实

1. canonical public MCP `automation_ask` 本身不会智能替 caller 选 preset
2. legacy/intelligent surfaces 仍会主动代选 provider/preset
3. `ask_guard` 的 safe non-Pro fallback 不覆盖 `gemini_web.ask`
4. `gemini auto` 当前不是低成本默认，而是兼容 alias 到 `pro`

## 本轮产出

1. 新治理方案：
   - `docs/ops/2026-04-17_ChatgptREST新定位治理与退休收口方案_v3.md`
2. 新 walkthrough：
   - `docs/ops/2026-04-17_ChatgptREST新定位治理与退休收口方案_walkthrough_v3.md`
3. README 索引切到 `v3`

## v3 的结论

`v2` 是正确方向，但还停留在 preset 层。  
`v3` 把它提升为完整 owner-side 治理口径：

1. 先冻结 execution lane decision rights
2. 再冻结 provider capability matrix
3. 再把审计字段做成正式 schema
4. 再逐步去掉 legacy surface 的默认解释权
