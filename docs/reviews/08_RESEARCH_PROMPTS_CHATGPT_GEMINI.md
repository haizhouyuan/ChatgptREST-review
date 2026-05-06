# Research Prompts For ChatGPT Research And Gemini Deep Research

Generated: 2026-02-28

## Prompt A: ChatGPT Research (recommended first)

你是“代码评审背景调研员”，不是直接改代码的人。你的任务是基于我上传的 OpenMind + AIOS 背景材料，完成“评审文档所需背景需求调研”，并输出可用于后续工程评审的证据化背景包。

要求：
1. 先做信息整理，再做结论：
   - 识别 OpenMind 当前能力边界（contracts/kernel/workflows/integrations）
   - 识别 AIOS 需求、治理、流程、门禁中的关键约束
   - 抽取 openclaw/homeagent/storyplay/research 四个模块与 OpenMind 的耦合点
2. 输出必须可执行，禁止空泛：
   - 每条结论要有来源文件名
   - 每条风险要给触发条件与影响
3. 必须覆盖：
   - 需求背景（why）
   - 能力缺口（gap）
   - 对接接口/契约假设（contract assumptions）
   - 评审优先级（P0/P1/P2）
4. 最终输出结构：
   A) 背景事实表（事实 | 来源文件 | 可信度）
   B) 需求映射矩阵（需求 -> OpenMind现状 -> 缺口 -> 建议）
   C) 跨模块依赖与风险（含 openclaw/homeagent/storyplay/research）
   D) 评审时必须追问的问题清单（<=20）
   E) 下一轮代码评审输入包建议（最小必要文件）

## Prompt B: Gemini Deep Research

你是“代码评审背景研究员”。请先尝试“代码导入/仓库导入”方式读取 OpenMind 项目；如果失败，立即退回到“上传文件合并包”进行分析，不要中断任务。

约束：
1. 上传文件数量不能超过 10 个。
2. 优先使用我提供的 INDEX 作为入口。
3. 如果代码导入失败，必须明确写明失败原因，并继续基于合并文件完成同等质量输出。
4. 结论必须附来源文件名，不可给无出处判断。

输出结构：
A. 导入路径执行结果（代码导入成功/失败 + 原因）
B. 背景需求调研结果（需求、约束、依赖、证据）
C. 风险清单（P0/P1/P2，含触发条件）
D. 对代码评审文档的补充建议（缺失章节、证据缺口）
E. 建议下一轮最小审查集（<=10 文件）
