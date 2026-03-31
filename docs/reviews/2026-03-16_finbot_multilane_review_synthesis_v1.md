## 背景

目标不是继续把 `finbot` 做成“更会写摘要的 scout”，而是把它推进到：

- 单入口：`main`
- 单投研执行体：`finbot`
- 内部多 lane 协作：`claim / skeptic / expression / decision`

这轮先做充分调研，再做原型，不封闭问题，而是把代码库、已有产物、live dossier 一并打包给外部模型做开放式评审。

## 调研输入

本轮外部调研分三类：

1. Agent / multi-lane 最佳实践
   - Anthropic, *Building effective agents*
   - LangGraph, *Multi-agent architectures*
   - LangGraph, *Context engineering for multi-agent systems*
   - OpenAI, *Building agents / eval-driven tool systems*
2. Dashboard 信息设计
   - Stephen Few, *Information Dashboard Design*
   - 投资人决策面板的“只展示决策相关事实，不展示原始噪音”原则
3. 双模型开放性评审
   - ChatGPT Pro consult：成功
   - Gemini Web consult：失败，原因 `GeminiCaptcha`

## 打包给外部模型的材料

实际送审的材料包括：

- `chatgptrest/finbot.py`
- `chatgptrest/dashboard/service.py`
- `chatgptrest/dashboard/templates/investor_opportunity_detail.html`
- live artifact
  - `artifacts/finbot/opportunities/tsmc-cpo-cpo-d519030bd1/latest.json`
  - `artifacts/finbot/opportunities/tsmc-cpo-cpo-d519030bd1/latest.md`
- review packet
  - `docs/reviews/2026-03-16_finbot_multilane_review_packet_v1.md`

## 外部反馈收敛

### 共识

外部最佳实践和本项目现状共同指向一个结论：

- 不应该把系统升级成多个常驻 OpenClaw agent
- 应该保留：
  - 单 ingress
  - 单 `finbot`
  - 内部 lane 分工

### ChatGPT Pro 评审要点

成功返回的 consult job：

- `ac3f7b225edd46d98f13b04b76d3c093`

核心建议：

1. 机会深挖不能只有单线性 `brief -> dossier`
2. 需要拆成：
   - Scout
   - Claim / Evidence
   - Skeptic / Anti-thesis
   - Expression comparison
   - Decision synthesis
3. Dashboard 不应先展示 raw data，而应展示：
   - what changed
   - why it matters
   - what is investable now
   - what blocks action
4. 研究输出必须把“支持性 claim”和“反证”都结构化，而不是只给一段 narrative

### Gemini 结果

Gemini Web 这轮没有产出可用长答：

- job：`5e9efcc98828481f98881ad5f8b98b42`
- 状态：`needs_followup`
- 原因：`GeminiCaptcha`

因此本轮不是严格意义的“双模型完整对照”，而是：

- `ChatGPT Pro` 有效
- `Gemini` 被 provider 环境阻塞
- 再辅以公开最佳实践资料进行交叉约束

## 原型裁定

最终采取的产品架构不是“多 agent 常驻集群”，而是：

### 1. 对外

- `main`：单入口
- `finbot`：单投研执行体

### 2. 对内

`finbot` 内部按 lane 运行：

- `claim`
- `skeptic`
- `expression`
- `decision`

### 3. 设计理由

这样做的优点：

- 不分叉记忆
- 不引入多 agent 调度噪音
- 更容易把同一机会的多视角分析收敛到一个 dossier
- 后续若某个 lane 负载过大，再拆成真正独立子 agent 也更自然

## 当前阶段的成功标准

本轮不是追求“全系统终局”，而是验证三件事：

1. 真实机会能不能从单线性 dossier 升级成多 lane dossier
2. lane 结果能不能落成稳定 artifact
3. investor dashboard 能不能把这些 lane 结果以人类可消费的方式展示出来

## 结论

这轮调研后的明确结论是：

**`finbot` 的正确升级路径不是“多建几个常驻 agent”，而是“单 ingress、单 finbot、内部多 lane”。**

下一阶段如果继续升级，优先顺序应是：

1. claim ledger 真正结构化
2. skeptic lane 的反证质量进一步提升
3. expression lane 接入更明确的 peer/valuation discipline
4. decision lane 接入更强的 posture / forcing-event policy
