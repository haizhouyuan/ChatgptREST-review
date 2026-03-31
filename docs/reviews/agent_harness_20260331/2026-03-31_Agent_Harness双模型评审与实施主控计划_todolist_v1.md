# 2026-03-31 Agent Harness 双模型评审与实施主控计划 TodoList v1

状态：in_progress
负责人：Codex
目标：把 Agent Harness / Task Harness 的外部双模型评审、综合判断、总体实现计划、Claude Code 实施与严格验收串成单一闭环，避免上下文压缩后丢失要求。

## 一、冻结输入

### A. 主方案文档
- `planning/docs/2026-03-31_Agent_Harness工程调研_最终综合结论_v4.md`

### B. 配套方案文档
- `planning/docs/2026-03-31_ChatgptREST_opencli_CLI-Anything_集成详细实施方案_v2.md`

### C. 审计来源包
- `planning/docs/sources/agent_harness_2026-03-31/`
- `planning/docs/sources/agent_harness_2026-03-31/source_registry.json`

### D. 外部长答工件
- `ChatgptREST/artifacts/jobs/ed787d3706a1421bb6e4a1911701f138/answer.md` 作为 ChatGPT Pro 既有正式长答参考
- `/tmp/gemini_agent_harness_answer_v3.txt` 作为 Gemini 既有正式长答参考

### E. 本地代码基线
- `chatgptrest/advisor/task_intake.py`
- `chatgptrest/advisor/task_spec.py`
- `chatgptrest/kernel/artifact_store.py`
- `chatgptrest/eval/evaluator_service.py`
- `chatgptrest/eval/decision_plane.py`
- `chatgptrest/quality/outcome_ledger.py`
- `chatgptrest/core/completion_contract.py`
- `chatgptrest/kernel/work_memory_manager.py`
- `chatgptrest/kernel/work_memory_importer.py`
- `planning/scripts/planning_bootstrap.py`

## 二、这轮必须完成的结果

1. review repo / review packet 整理完成，且包含 `v4`、`v2`、必要代码与上下文。
2. ChatGPT Pro 对 `v4` 和 `v2` 都给出正式长答。
3. GeminiDT 对 `v4` 和 `v2` 都给出正式长答。
4. 四份正式长答全部落盘并可审计。
5. 必要时做第二轮追问，直到结论足够稳定，不以“似乎够了”为结束条件。
6. 形成一份高目标、全量、可执行的总体实现计划。
7. 用 Claude Code runner 启动 `claudeminmax`，并用 agent teams 做实施。
8. 对 Claude 产出做严格验收，不以“看上去完成”为完成标准。

## 三、双模型评审问题集

### 问题 1：Task Harness / Agent Harness 主方案（v4）
评审对象：
- `v4.md`
- 原文审计包
- 关键代码基线

要求回答：
1. 架构判断是否成立。
2. 哪些点是高价值吸收，哪些是过度设计。
3. 哪些关键缺口仍未被方案覆盖。
4. 对 ChatgptREST 的最优落地顺序。
5. 必须推翻/重写的部分。
6. 验收标准与失败模式。

### 问题 2：opencli / CLI-Anything 集成方案（v2）
评审对象：
- `v2.md`
- `opencli` clone
- `CLI-Anything` clone
- ChatgptREST 现有 capability governance / skill registry / market gate / routes_agent_v3

要求回答：
1. 分层判断是否成立。
2. `Phase 1` POC 方案是否足够稳。
3. 风险边界是否收得够紧。
4. 哪些设计仍然危险或不现实。
5. 第一批实现范围与验收门槛。

## 四、评审质量门槛

### 允许通过的评审
- 明确引用代码/文档/路径
- 明确指出成立、不成立、待证实项
- 给出实施顺序、风险、验收标准
- 至少达到“长答、非表面摘要”水平

### 不允许当作有效评审的输出
- 只讲方向，不落到现有代码
- 不区分主张/证据/推断
- 把 public repo review 和 GeminiDT 通道搞混
- 没有明确 high-risk / must-fix 点
- 过短、泛泛而谈、明显未读代码

## 五、执行通道要求

### ChatGPT Pro
- 优先使用现有 ChatgptREST review workflow。
- 需要 review repo / public repo / 附件时，必须给足上下文。
- 必须拿到正式长答案，不接受“只有一段短摘要”。

### GeminiDT
- 只能走 `gemini_web.ask` 或其上的 public advisor-agent surface。
- 禁止走 Gemini CLI、Gemini API key、普通文本模型替代。
- 同样必须拿到正式长答案。

## 六、review repo / packet 要求

review 包中必须包含：
- `v4.md`
- `v2.md`
- 原文审计包索引
- 关键代码文件
- `REVIEW_CONTEXT.md`
- `REVIEW_SOURCE.json`
- 清晰的两个问题与回答格式要求

如果 review repo 需要 curated subset：
- 必须是 review-safe 子集
- 不能丢关键代码
- 不能只上传文档不上传实现上下文

## 七、是否需要第二轮追问的判断标准

满足任一条件，必须第二轮：
- Pro 和 Gemini 结论冲突且未解释
- 对同一高风险点给出相反判断
- 任一模型没有真正审到现有代码
- 输出没有回答“实施顺序 / must-fix / 验收标准”
- 输出仍停留在“方向正确”层面

## 八、总体实现计划的质量门槛

最终总体实现计划必须包含：
1. 架构目标与非目标
2. 模块级改动清单
3. 状态机 / contract / schema 设计
4. API / CLI / operator surface 变更
5. durable execution / eval harness / promotion 设计
6. 与现有 `completion_contract / canonical_answer / work-memory` 的精确衔接
7. 迁移策略、兼容策略、回滚策略
8. 测试矩阵
9. live 验证门槛
10. 里程碑与退出标准

## 九、Claude Code 实施要求

执行工具：
- `claudecode-agent-runner`
- `hcom-agent-teams`

执行模式：
- 用 `claudeminmax`
- 允许多 agent 并行，但写入范围必须切分清楚
- 所有工作都必须留下 evidence

Claude 实施验收门槛：
1. 不能只提交文档或空壳 scaffold
2. 测试必须真实跑过
3. 长答/长任务场景必须 fail closed
4. 关键契约不能靠最新 event 猜
5. 完成态不能以短答案伪装
6. 必须有回滚与 operator 面
7. 必须补 walkthrough / runbook

## 十、当前待办清单

- [ ] 生成/整理 review packet
- [ ] 同步到 review repo
- [ ] 发出 ChatGPT Pro 问题 1
- [ ] 发出 ChatGPT Pro 问题 2
- [ ] 发出 GeminiDT 问题 1
- [ ] 发出 GeminiDT 问题 2
- [ ] 等待四份正式长答
- [ ] 判断是否需要第二轮
- [ ] 如需第二轮，补发追问并收答
- [ ] 产出双模型综合判断
- [ ] 产出总体实现计划
- [ ] 启动 Claude Code Agent Team
- [ ] 做严格验收
- [ ] 输出最终交付包

## 十一、禁止事项

- 不得用短答或中间态代替正式长答
- 不得把浏览器里偶然看到的内容当唯一真相源
- 不得把 review repo workflow 和 GeminiDT 通道混用
- 不得在没有足够代码上下文的情况下发低质量评审请求
- 不得因为上下文压缩就丢掉评审标准、验收门槛和实施边界
