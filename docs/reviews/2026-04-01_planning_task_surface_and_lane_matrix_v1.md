# 2026-04-01 Planning Task Surface and Lane Matrix v1

## 1. 目的

这份矩阵只回答一个很实际的问题：

> 对 `planning/` 里的不同任务，默认应该从哪个 surface 进入，在哪个 workbench 里做，什么时候才需要调 ChatgptREST 的专项 lane。

它不是实现设计文档，也不是删旧层方案。

它的作用是先给第一阶段一个稳定的“默认使用法”，避免继续混用：

1. 主工作台
2. 远程入口
3. capture 入口
4. canonical northbound
5. internal provider lane

## 2. 先冻结 5 条总规则

### 2.1 规则一：先选工作台，不先选模型

对 `planning/` 第一阶段，默认决策顺序应该是：

1. 先判断这是不是需要长时间连续推进的工作
2. 如果是，先选 `Codex / Claude Code / Antigravity`
3. 只有当任务确实需要外部专项能力时，才再决定是否调 `ChatGPT Web / Gemini Web / consult`

### 2.2 规则二：`tmuxagent(8702)` 不是另一种 lane

`tmuxagent(8702)` 只是：

1. 远程访问
2. 远程控制
3. 手机/网页入口

它底下仍然是你已经开的 `Codex / Claude Code / Antigravity` pane。

### 2.3 规则三：飞书只先做 capture / dispatch

当前阶段不要把 `Feishu / OpenClawBot` 承诺成可替代 workbench 的主工作台。

它当前更适合：

1. 扔材料
2. 发任务
3. 收回执
4. 轻跟进

### 2.4 规则四：public MCP 是 canonical northbound，不是用户工作台

当任务需要进入 ChatgptREST 的 agent/orchestration 面时，默认 northbound 是：

1. public MCP `http://127.0.0.1:18712/mcp`
2. `advisor_agent_turn/status/cancel/wait`

但这件事应尽量藏在工作流背后，不要让“选 MCP 还是选 REST”变成用户日常心智负担。

### 2.5 规则五：专项 lane 默认后置

`chatgpt_web.ask / gemini_web.ask / consult` 只在满足专项条件时启用：

1. `chatgpt_web.ask`
   - 需要 ChatGPT Web premium reasoning / report / review
2. `gemini_web.ask`
   - 需要 Gemini DeepThink / Deep Research / Drive / imported-code / second opinion
3. `consult`
   - 高风险、争议大、需要双审或多审

## 3. Matrix A — `planning/` 任务类型 -> 默认 surface / lane

| 任务类型 | 典型产物 | 默认主工作台 | 默认远程入口 | 默认 capture 入口 | 默认 northbound | 默认专项 lane posture | 何时升级到 consult | 不建议默认路径 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 人员与绩效 | 人员规划、编制建议、岗位说明、述职晋升材料 | `Codex / Claude Code / Antigravity` | `tmuxagent(8702)` | `Feishu / OpenClawBot` 只收材料 | public MCP，如需 agent/orchestration | 通常不需要专项 lane | 涉及组织重大调整、编制争议、晋升判断冲突时 | 不要默认走 `chatgpt_web.ask` 或 `gemini_web.ask` 单独完成整件事 |
| 项目群管理 | 项目现状诊断、里程碑、风险清单、行动项 | `Codex / Claude Code / Antigravity` | `tmuxagent(8702)` | 飞书可发需求与补材料 | public MCP | 一般先不用专项 lane；复杂项目可后置 second opinion | 项目是否立项、阶段是否切换、重大风险是否升红时 | 不要默认从 `/v1/jobs kind=*web.ask` 起手 |
| 业务项目规划与导入 | 客户项目方案、量产导入、测试门禁、合作路径 | `Codex / Claude Code / Antigravity` | `tmuxagent(8702)` | 飞书适合丢外来文件、会议纪要 | public MCP | 需要专项研究时再调 `gemini_web.ask` 或 `chatgpt_web.ask` | 对外承诺、重大商务判断、技术路线冲突时 | 不要把飞书聊天窗口当唯一主工作台 |
| 战略规划与预算 | 年度规划、五年规划、预算方案、资源投入建议 | `Codex / Claude Code / Antigravity` | `tmuxagent(8702)` | 飞书可发素材包 | public MCP | 可后置 `chatgpt_web.ask` 做长 reasoning / 报告打磨；非默认 | 涉及董事长口径、重大资源取舍时 | 不要默认直接走 broad/admin MCP 旧工具 |
| 研究与调研 | 研究结论稿、claim ledger、gap note、决策摘要 | `Codex / Claude Code / Antigravity` | `tmuxagent(8702)` | 飞书可收外部文章、材料包 | public MCP | `gemini_web.ask` 适合 Deep Research/大文件；`chatgpt_web.ask` 适合 premium synthesis | 结论将直接影响决策、证据冲突大时 | 不要把研究任务全部压成单轮 ask |
| 汇报与表达 | 领导摘要、汇报稿、逐页内容稿、客户沟通稿 | `Codex / Claude Code / Antigravity` | `tmuxagent(8702)` | 飞书可收临时口径与补件 | public MCP | `chatgpt_web.ask` 可用于高质量成稿/改写；非默认起手 | 重大汇报、外部高风险表述时 | 不要默认先走 `consult`，会过重 |
| 外来资料吸收与会议沉淀 | 纪要、ASR 摘要、行动项、情报简报、变更建议 | `Codex / Claude Code / Antigravity` | `tmuxagent(8702)` | `Feishu / OpenClawBot` 在这类任务里价值最高 | public MCP | 一般不需要专项 lane；海量材料或复杂研究补充时再调 Gemini | 对事实判断分歧大、要入库的稳定结论有争议时 | 不要把原始转写直接丢给低层 ask 后就当完成 |
| 方法、模板与流程治理 | 模板、入口治理、记忆变更单、技能/流程规范 | `Codex / Claude Code / Antigravity` | `tmuxagent(8702)` | 飞书只适合收零散意见 | public MCP | 通常不需要专项 lane | 规范会影响多人工作方式、需要双审时 | 不要默认走飞书链路做复杂治理工作 |

## 4. Matrix B — P0 验收场景 -> 默认路径

| 验收场景 | 默认用户路径 | 默认工作方式 | 专项 lane 是否默认开启 | 说明 |
| --- | --- | --- | --- | --- |
| `AC-01` 人员规划 | `Codex / Claude Code / Antigravity` | 长任务、反复对齐、持续改稿 | 否 | 先做结构化规划，不先做多模型复核 |
| `AC-02` 项目现状诊断 | `Codex / Claude Code / Antigravity` | 读入口、拉台账、判断阶段、产出建议 | 否 | 先保证入口正确和口径一致 |
| `AC-03` 研究到决策稿 | `Codex / Claude Code / Antigravity` + 必要时 public MCP | 先整理证据，再转判断稿 | 否，但最容易后置 Gemini / consult | 这是最适合后置专项 lane 的场景之一 |
| `AC-04` 汇报材料 | `Codex / Claude Code / Antigravity` | 先判断对象，再做结构与成稿 | 否 | 可在末段调用 ChatGPT lane 做表达打磨，但不默认 |
| `AC-05` 会议沉淀 | `Feishu / OpenClawBot` 或 `tmuxagent(8702)` 先收材料，再进主工作台 | 先 intake，再结构化沉淀 | 否 | 这是最适合让飞书承担 capture 价值的场景 |

## 5. Matrix C — 输入材料 -> 默认入口

| 输入材料类型 | 默认入口 | 默认后续落点 | 说明 |
| --- | --- | --- | --- |
| 已在本机仓库中的文档、台账、报告 | `Codex / Claude Code / Antigravity` | 直接在主工作台处理 | 不需要绕飞书 |
| 手机上临时看到的消息、微信转发、截图 | `Feishu / OpenClawBot` 或 `tmuxagent(8702)` | 先进 capture，再转主工作台 | 飞书更适合“先接住”，不是“直接做完整长任务” |
| 会议录音、转写、资料包 | 飞书可先扔，随后转主工作台 | `planning/` 对应治理对象 | 后续重点是正确分类、沉淀、入库 |
| 大文件、需要 Drive/imported-code 的材料 | 主工作台发起，必要时后置 Gemini | public MCP -> Gemini lane | 不建议先从低层 `/v1/jobs` 直接起手 |
| 需要高风险双审的问题包 | 主工作台发起 | public MCP -> consult | 由主工作台控制问题 framing，更稳 |

## 6. Matrix D — 什么时候该用哪个专项 lane

| lane | 默认用途 | 应触发条件 | 不应默认触发的场景 |
| --- | --- | --- | --- |
| `chatgpt_web.ask` | premium reasoning / review / report polish | 需要 ChatGPT Web 特定质量、长 reasoning、成稿打磨 | 普通纪要、普通项目诊断、普通规划草案 |
| `gemini_web.ask` | Deep Research / DeepThink / Drive / imported-code | 研究密集、附件重、需要 Gemini 特长、需要 second opinion | 日常所有 planning 任务 |
| `consult` | 双审 / 多审 / 高风险复核 | 重大判断、争议结论、重要汇报或决策前复核 | 所有任务默认开启 |

## 7. 默认使用法 v1

如果不想每次都重新判断，第一阶段可以先按下面的默认法执行：

1. **长任务、要读历史、要反复改稿**
   - 直接进 `Codex / Claude Code / Antigravity`
2. **人在手机上，但本质还是要继续已有 workbench**
   - 走 `tmuxagent(8702)`
3. **只是要先把材料接住**
   - 走 `Feishu / OpenClawBot`
4. **任务需要进入 ChatgptREST 的 agent/orchestration 面**
   - 默认 public MCP
5. **任务需要专项模型能力**
   - 再后置 `chatgpt_web.ask` / `gemini_web.ask` / `consult`

## 8. 第一阶段最该避免的 6 个误用

1. 把 `Feishu / OpenClawBot` 当成可直接替代主工作台的默认入口。
2. 把 `tmuxagent(8702)` 当成一条新的模型 lane，而不是现有 workbench 的远程控制面。
3. 把 `chatgpt_web.ask / gemini_web.ask` 当成所有 planning 任务的默认起点。
4. 把 `consult` 当成日常默认模式。
5. 把 broad/admin MCP 旧工具教给普通工作流。
6. 把 low-level `/v1/jobs kind=*web.ask` 当成第一阶段 planning 主流程。

## 9. 一句话结论

对 `planning/` 第一阶段，最稳的默认使用法不是“先选模型”，而是：

> 先在 `Codex / Claude Code / Antigravity` 这类主工作台里做任务；需要远程继续时用 `tmuxagent(8702)`；需要先把材料接住时用 `Feishu / OpenClawBot`；只有在专项能力、重研究、大附件或高风险复核时，才后置调用 ChatgptREST 的 `chatgpt_web.ask / gemini_web.ask / consult` lane。
