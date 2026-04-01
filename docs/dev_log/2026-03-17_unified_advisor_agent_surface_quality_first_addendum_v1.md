# 2026-03-17 Unified Advisor Agent Surface Quality-First Addendum v1

## 为什么要改

用户明确补充了一个关键约束：

- 不是在乎 Claude Code 自己多用一点 LLM
- 而是不能让 **agent 版本的 ChatgptREST 交互层** 因为省模型调用而变笨、出错、效率低

这会直接影响 public facade 的设计哲学。

## v1 / v2 计划的潜在风险

如果只强调：

- surface 收敛
- compatibility
- public MCP 变少

但没有明确写出：

- planner
- judge
- recovery-aware finalization
- complex turn 允许强模型参与

那么实现者很容易把 `/v3/agent/turn` 做成一个规则主导的薄 wrapper。  
那样虽然“接口统一了”，但结果会更笨。

## 本次修正

因此新增：

- `docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v2.md`
- `docs/dev_log/2026-03-17_unified_advisor_agent_surface_cc_task_spec_v3.md`
- `docs/dev_log/2026-03-17_unified_advisor_agent_surface_cc_agentteams_prompt_v2.md`

这些更新把以下要求写死了：

1. public facade 是 quality-first
2. 必须实现 planner / judge / recovery-aware finalization
3. 复杂任务允许使用强模型
4. 不允许为了省调用把 façade 做成 rule-only wrapper
5. CC 的 Agent Teams 任务也必须围绕这个目标来拆 lane

## 对开发方式的影响

这意味着 CC 不只是完成“接口层和兼容层”，而是要一次性把下面这些一起做完：

- `/v3/agent/*`
- planner
- judge
- public MCP
- OpenClaw convergence
- CLI/wrapper convergence
- docs + tests + PR

## 结论

这次调整是必要的。  
否则很可能做出一个“看起来更统一，实际上更低配”的 agent 层，最终违背用户想要的质量和效率目标。
