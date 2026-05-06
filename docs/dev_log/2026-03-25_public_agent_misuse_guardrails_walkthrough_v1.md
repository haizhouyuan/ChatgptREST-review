# Public Agent Misuse Guardrails Walkthrough v1

Date: 2026-03-25
Repo: ChatgptREST

## Walkthrough

1. 先排查最近几小时的 `state/agent_sessions` 与 service journal。
   结论不是 ChatgptREST 自己在乱起会话，而是外部 caller 把很多内部小步骤错误地走成了 public `advisor_agent_turn`。

2. 识别出两类高频噪音：
   - extractor / sufficiency gate microtask 被包装成 public-agent turn
   - 同一类重型 review/research 在 running 期间被重复提交

3. 先手动取消了确认属于 stray batch 的 running sessions，止住现网噪音。

4. 然后把服务端修复收在两层窄 surface：
   - `chatgptrest/mcp/agent_mcp.py`
     public MCP turn 透传真实 MCP caller identity
   - `chatgptrest/api/routes_agent_v3.py`
     public-agent misuse / duplicate guard

5. 特意避开了 `build_task_intake_spec()`。
   GitNexus 显示这个 intake 核心函数 blast radius 是 `CRITICAL`，所以这次没有把护栏塞进 canonical intake normalizer，而是留在 `agent_v3` ingress 上，减少回归面。

6. 新行为：
   - public MCP caller 不再全部落成 generic `mcp-agent`
   - obvious extractor / sufficiency gate prompt 会直接 400
   - 重复重型 public-agent turn 会直接 409，并把已有 session 返给客户端

7. 定向回归通过后，再同步更新：
   - `docs/contract_v1.md`
   - `docs/runbook.md`
   - `skills-src/chatgptrest-call/SKILL.md`

## Commands run

```bash
./.venv/bin/python -m py_compile \
  chatgptrest/mcp/agent_mcp.py \
  chatgptrest/api/routes_agent_v3.py \
  tests/test_agent_mcp.py \
  tests/test_routes_agent_v3.py

./.venv/bin/pytest -q tests/test_agent_mcp.py tests/test_routes_agent_v3.py
```

## Outcome

这轮改动的目标不是调 controller 路由策略，而是先把 public-agent ingress 的 misuse 面和排障可观测性收紧。现网再出现大批相同 `deep_research` session 时，至少能更快看出是哪个 MCP caller 触发，以及在 ingress 侧更早失败。
