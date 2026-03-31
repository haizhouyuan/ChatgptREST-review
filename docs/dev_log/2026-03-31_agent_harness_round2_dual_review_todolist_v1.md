# 2026-03-31 Agent Harness Round2 双模型复审与整改主控 Todo v1

## 目标

在当前 `ChatgptREST master@dfb8877c` 的真实实现基线上，使用**封装好的 wrapped review lane**完成一轮高标准双模型复审：

1. `Task Harness / Agent Harness` 当前实现是否已经达到 Anthropic / OpenAI / Inngest / Microsoft / LangGraph 所代表的 harness best practices 水平。
2. `opencli / CLI-Anything` 当前集成是否已经足够稳、边界是否画对、是否还有未闭环的安全/治理/实施问题。

然后：

- 按 `ChatGPT Pro` 与 `GeminiDT` 的审稿意见继续修改
- 至少做到：核心 architecture judgment、关键 contract、operator workflow、acceptance 口径达到高标准，不留明显“看起来完成”的半成品

## 硬约束

- 必须走封装好的 review workflow，不允许浏览器直连绕过。
- 必须使用 review repo + wrapped lane。
- 每个问题都要给两家模型问。
- 至少等待到**正式长答案**或 wrapped lane 的明确终态，不接受“猜测模型大概会怎么说”。
- 如果 lane 失败，先定位并修 wrapper / provider-side integration 问题，再继续。

## 本轮固定输入

- 目标实现基线：`ChatgptREST master@dfb8877c`
- 主方案：`planning/docs/2026-03-31_Agent_Harness工程调研_最终综合结论_v4.md`
- 实施计划：`planning/docs/2026-03-31_Agent_Harness全量实施计划与验收标准_v1.md`
- opencli / CLI-Anything 方案：`planning/docs/2026-03-31_ChatgptREST_opencli_CLI-Anything_集成详细实施方案_v2.md`
- 当前实现与收口文档：
  - `docs/dev_log/2026-03-31_agent_harness_implementation_walkthrough_v1.md`
  - `docs/dev_log/2026-03-31_agent_harness_completion_report_v1.md`
  - `docs/dev_log/2026-03-31_three_line_integration_closure_todolist_v1.md`
  - `docs/dev_log/2026-03-31_bootstrap_remediation_and_validation_v2.md`

## 执行步骤

- [ ] 生成 round2 review packet 文档与代码上下文索引
- [ ] 推送 current integrated source 到 public review repo 分支
- [ ] 发起 ChatGPT Pro：Task Harness 当前实现复审
- [ ] 发起 GeminiDT：Task Harness 当前实现复审
- [ ] 发起 ChatGPT Pro：opencli / CLI-Anything 当前集成复审
- [ ] 发起 GeminiDT：opencli / CLI-Anything 当前集成复审
- [ ] 等待正式长答案/终态
- [ ] 汇总四份答案并判断是否需要第二轮
- [ ] 若有明确缺口：实现修复
- [ ] 重跑相关测试 / smoke / closeout
- [ ] 如有必要，发第二轮复审
- [ ] 冻结最终结论与剩余边界

## 高标准验收口径

- 不只是“测试通过”
- 还要满足：
  - task control / durable execution / eval harness 的 layering 被外部严格审稿认可
  - `opencli` 执行 substrate 与 `CLI-Anything` untrusted artifact 边界被外部严格审稿认可
  - 对当前实现剩余缺口有明确、可执行、非敷衍的 closure list
  - 没有“phase 写完了但真实只是 scaffold”这类口径虚报

## 不纳入本轮

- 主工作树里并行的 Gemini 在制修改
- Browser Bridge extension 的真实 GUI 接线
- 与本轮 harness / opencli 主题无关的业务线工作
