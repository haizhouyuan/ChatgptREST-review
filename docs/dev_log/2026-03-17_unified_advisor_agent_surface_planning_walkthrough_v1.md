# 2026-03-17 Unified Advisor Agent Surface Planning Walkthrough v1

## 背景

当前用户真实想要的不是“更多 tools”，而是：

- Codex
- Antigravity
- Claude Code
- OpenClaw/OpenMind

都能像在和一个统一的 advisor agent 交互，而不是分别学习：

- MCP 低层工具
- jobs 提交/等待/取答案
- advisor ask / advise 差异
- provider / preset / wait 细节

因此这次工作没有继续在现有入口上打补丁，而是先做一轮完整的 surface inventory，再给出统一收敛蓝图和可执行 task spec。

## 调查结论

### 1. 入口并不只有 Codex / Claude Code / Antigravity

实际还存在以下接入面：

- `chatgptrest-mcp.service`
- `/v1/jobs/*`
- `/v1/advisor/advise`
- `/v2/advisor/advise`
- `/v2/advisor/ask`
- `openclaw_extensions/openmind-advisor`
- `openclaw_extensions/openmind-memory`
- `openclaw_extensions/openmind-graph`
- `chatgptrest/cli.py`
- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
- ChatgptREST 到 OpenClaw 的 internal adapter

### 2. 最大问题不是“缺能力”，而是暴露层级不对

最明显的几个结构性裂缝：

- 普通客户端能看到过多 low-level MCP tools
- OpenClaw advisor 插件仍分成 `ask|advise` 双后端语义
- wrapper CLI 还是 provider-first，而不是 agent-first
- `/v2/advisor/ask` 已经很高层，但仍然泄露 job / provider / route 语义

### 3. 已有底座足够，不需要重写核心内核

仓里已经有可以复用的统一层基础：

- `ControllerEngine`
- `/v2/advisor/ask`
- `/v2/advisor/advise`
- `standard_entry_pipeline()`
- existing jobs / repair / consult / image lanes

所以正确方向不是重造 orchestrator，而是：

- 新增 public facade
- 把旧能力降到 internal/admin substrate
- 逐步迁移客户端

## 本次产出

### 1. 正式蓝图

新增：

- `docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v1.md`

核心内容：

- 当前 surface inventory
- target architecture
- public vs internal surface split
- OpenClaw/OpenMind 收敛策略
- CLI / wrapper 收敛策略
- rollout batches
- Definition of Done

### 2. Claude Code task spec

新增：

- `docs/dev_log/2026-03-17_unified_advisor_agent_surface_cc_task_spec_v1.md`

这份 spec 直接约束第一轮开发范围：

- `/v3/agent/*`
- `chatgptrest-agent-mcp`
- OpenClaw advisor plugin convergence
- CLI / wrapper convergence
- tests / docs / closeout

## 为什么推荐先做 public facade + public MCP

如果只做 `/v3/agent/turn`，Codex/Claude Code 仍然会在 MCP 里看到 50 多个工具，用户体感不会改善。

如果只做 public MCP，而不先把后端 contract 收敛到 `/v3/agent/*`，那只是换了个名字包装旧碎片，后续 OpenClaw / CLI 还是会继续分裂。

因此推荐第一轮直接做：

- public HTTP facade
- public MCP facade
- OpenClaw advisor plugin 改走同一 contract
- wrapper CLI 改成 agent-first

这是最小的“真正改变用户体感”的批次。

## 风险控制

蓝图明确要求：

- additive change
- 旧 `/v1/jobs/*` 继续保留
- 旧 `/v2/advisor/ask|advise` 继续保留
- 旧 `chatgptrest-mcp` 继续保留

也就是说，这不是高风险替换，而是一次 public entry convergence。

## 验证与交接

本轮是调查和规划，没有改产品代码，也没有跑业务测试。

但我已完成：

- 代码和文档级入口盘点
- OpenClaw/OpenMind 插件调用链核对
- wrapper CLI / admin CLI 入口核对
- 版本化蓝图落盘
- Claude Code 任务规格落盘

下一步交接方式：

- 在 clean worktree 中让 Claude Code 按 task spec 开发
- 开发完成后再由我做 PR 级验收和测试/部署判断
