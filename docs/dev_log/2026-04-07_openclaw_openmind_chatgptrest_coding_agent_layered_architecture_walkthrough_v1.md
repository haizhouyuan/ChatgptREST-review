# 2026-04-07 OpenClaw / OpenMind / ChatgptREST / Coding-Agent Layered Architecture Walkthrough v1

日期：2026-04-07

## 为什么写这份文档

本轮用户连续追问的核心不是某个 bug，而是：

1. `OpenClaw`
2. `OpenMind plugins`
3. `ChatgptREST`
4. `Codex / Claude Code`

这四层到底谁该当脑子、谁该当桥、谁该当真相层。

需要一份能给 Claude Code 评审的正式架构文档，而不是继续用对话临时解释。

## 这份方案的核心判断

1. `OpenMind plugins` 不该继续承担复杂项目主脑，而应该降级成桥接层
2. `OpenClaw` 不应继续这么弱，应该加强到项目关联与任务编排层
3. `ChatgptREST` 应保留为 task/checkpoint/handoff 的结构化真相层
4. `Codex / Claude Code` 更适合作为复杂项目的长期主脑

## 输出

正式评审文档：

- `docs/reviews/2026-04-07_openclaw_openmind_chatgptrest_coding_agent_layered_architecture_for_claude_v1.md`

## 预期用途

让 Claude Code 审核以下判断是否成立：

1. 当前混乱根因是否被正确识别
2. 四层职责边界是否合理
3. 厚薄分工是否正确
4. 项目状态、项目定义、项目关联、深度执行分别放在哪一层最稳
