# 2026-03-17 Unified Advisor Agent Surface CC Task Spec v3

## v3 调整

这版在 `v2` 基础上新增一个硬要求：

**public agent facade 必须 quality-first，不允许为了省 agent-layer LLM 调用，把控制层做成过度简化的规则机。**

也就是说，你实现的不是一个“统一入口的薄 wrapper”，而是一个真正更聪明、更稳的 agent control loop。

## 总目标

一次性完成 unified public advisor-agent facade 的完整第一阶段交付，并且：

- 质量优先
- 可用更强模型/更多模型辅助
- 全量完成测试
- 准备 PR 供审核

## 必做范围

### A. Public `/v3/agent/*`

必须完成：

- `POST /v3/agent/turn`
- `GET /v3/agent/session/{session_id}`
- `POST /v3/agent/cancel`

但注意：这不是单纯 contract shell。

`turn` 内部必须体现完整 control loop：

1. planner
2. execution
3. judge
4. if needed: retry / escalate / recover
5. final delivery

### B. Planner

必须实现一个 facade-level planner，负责：

- 理解用户意图
- 结合附件与上下文
- 决定真正执行 lane
- 生成结构化 execution plan

Planner 可以而且应该在复杂场景下使用强模型，不要为了省调用退化成低质量 heuristics。

至少这些场景不能只靠 cheap rules：

- ambiguous tasks
- code review / architecture review
- dual-model review
- deep research
- attachment-heavy tasks
- prior recovery-touched sessions

### C. Judge

必须实现一个 facade-level judge，负责：

- 判断结果是否真正满足用户目标
- 判断是否错误 completed
- 判断是否应该重试或升级 lane
- 对 recovery 后结果重新验收

Judge 不能只看 `min_chars`。

至少要有：

- deterministic quality gate
- semantic/LLM judge for复杂或高风险任务

### D. Recovery-aware finalize

如果发生：

- retry
- cooldown recovery
- needs_followup recovery
- attachment recovery

最终交付前必须重新过 judge。

### E. Public MCP facade

新增独立 public MCP server：

- `chatgptrest_agent_mcp_server.py`
- public MCP 模块
- `ops/start_agent_mcp.sh`
- `ops/systemd/chatgptrest-agent-mcp.service`

只暴露：

- `advisor_agent_turn`
- `advisor_agent_cancel`
- 可选 `advisor_agent_status`

MCP 返回必须是 public agent 语义，不是 raw low-level job response。

### F. OpenClaw convergence

修改：

- `openclaw_extensions/openmind-advisor/index.ts`

要求：

- 保留 `openmind_advisor_ask`
- 统一改打 `/v3/agent/turn`
- 去掉内部 `ask|advise` 双分支
- 去掉手写 `wait/answer`
- 让 OpenClaw 拿到的 contract 也是 quality-first agent contract

### G. CLI / wrapper convergence

修改：

- `chatgptrest/cli.py`
- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`

要求：

- 新增 `chatgptrest agent turn|status|cancel`
- wrapper 默认变成 agent-first
- provider/preset 只保留为 expert override

### H. Docs and compatibility

必须同步：

- `docs/runbook.md`
- `docs/client_projects_registry.md`
- contract docs
- relevant OpenClaw/OpenMind docs
- fresh client quickstart

并保持以下旧入口继续工作：

- `/v1/jobs/*`
- `/v2/advisor/ask`
- `/v2/advisor/advise`
- `chatgptrest-mcp`

## Agent Teams 执行方式

继续使用 Claude Code 官方 Agent Teams。

建议 lane 调整为 6 个：

1. `http-facade`
   - `/v3/agent/*`
   - schemas
   - controller glue

2. `planner-judge`
   - planner
   - judge
   - recovery-aware finalization

3. `public-mcp`
   - public MCP server
   - start/systemd

4. `openclaw-adapter`
   - `openmind-advisor`
   - plugin tests

5. `cli-wrapper`
   - `chatgptrest/cli.py`
   - `chatgptrest_call.py`
   - docs sync

6. `integrator-review`
   - merge outputs
   - run tests
   - run stronger review pass
   - prepare PR

### Agent Teams 质量规则

- 不要因为 teammate 已“功能完成”就过早收工
- integrator-review 必须对整个 diff 做一次高质量 review
- 必要时可以使用更强模型、更多模型辅助，目标是减少返工，不是压缩调用量

## 明确的质量优先策略

以下事项允许使用强模型或额外 LLM 调用：

- planner
- semantic judge
- route adjudication
- difficult recovery decision
- final review of public contract / OpenClaw / MCP compatibility

禁止的错误优化：

- 为了省一次 planner 调用，改用明显脆弱的规则判断
- 为了省 judge 调用，直接把 suspect completion 交付
- 为了省 cross-check，放过 public API / MCP / plugin contract drift

## 最低测试要求

至少要实际通过：

- `./.venv/bin/pytest -q tests/test_mcp_advisor_tool.py tests/test_advisor_v3_end_to_end.py`
- `./.venv/bin/pytest -q tests/test_openclaw_cognitive_plugins.py`
- `./.venv/bin/pytest -q tests/test_skill_chatgptrest_call.py tests/test_cli_improvements.py`
- 所有新增 agent API / MCP tests

如果 router/security 相关代码有变：

- `./.venv/bin/pytest -q tests/test_routes_advisor_v3_security.py`

建议额外跑相关更广回归，并把结果写进最终 JSON。

## PR 要求

不是只做本地完成态，而是要准备可审核 PR。

如果 GitHub auth 可用：

- push branch
- create PR

如果不可用：

- 明确写出 blocker
- 说明 branch / commits 已 ready

## 最终返回格式

只返回 JSON：

```json
{
  "status": "succeeded" | "blocked" | "failed",
  "branch": "feat/public-advisor-agent-facade",
  "summary": "short summary",
  "commits": ["sha subject", "..."],
  "tests": [
    {"command": "pytest ...", "status": "passed|failed|not_run", "details": "short note"}
  ],
  "pull_request": {
    "status": "opened|ready_local|blocked",
    "url": "string or empty",
    "branch": "string",
    "base": "string",
    "blocker": "string or empty"
  },
  "walkthrough_path": "absolute path or empty string",
  "changed_files": ["path", "..."],
  "residual_risks": ["...", "..."],
  "notes": ["...", "..."]
}
```
