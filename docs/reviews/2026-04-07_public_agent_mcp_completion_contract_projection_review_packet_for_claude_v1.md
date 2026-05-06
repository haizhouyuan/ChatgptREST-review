# 2026-04-07 Public Agent MCP Completion Contract Projection Review Packet for Claude v1

## 评审目标

请聚焦审核本批次 A1 改动是否正确完成以下收口：

1. `completion_contract` 是否已从 job snapshot 一路投影到 public session / public MCP
2. `delivery.answer_ready` 是否不再在 provisional research 场景误报
3. `advisor_agent_answer` 是否覆盖 job-backed 与 no-job 两类 session
4. wrapper agent mode 是否真正不再只依赖 `last_answer`
5. 是否存在旧客户端兼容性回归

## 本批次改动文件

- `chatgptrest/api/routes_agent_v3.py`
- `chatgptrest/mcp/agent_mcp.py`
- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
- `tests/test_agent_mcp.py`
- `tests/test_routes_agent_v3_session_job_alignment.py`
- `tests/test_skill_chatgptrest_call.py`

## 重点核查的数据流

应检查以下链路是否贯通：

`_job_snapshot()`
→ `_controller_snapshot()`
→ `_refresh_session_state()`
→ `_session_response()`
→ `advisor_agent_status / advisor_agent_wait`
→ `advisor_agent_answer`
→ `chatgptrest_call.py` agent mode

## 需要重点红队的场景

### 场景 1：Deep Research final artifact

预期：

- `advisor_agent_wait` 返回 `answer_state=final`
- 若 `last_answer` 为空但 authoritative answer 已落盘，session 仍应可恢复完整正文
- `advisor_agent_answer` 能返回完整正文

### 场景 2：completed 但 provisional

预期：

- `answer_ready` 必须为 false
- wrapper 不能误把 provisional 当成 final

### 场景 3：no-job session

预期：

- `advisor_agent_answer` 能回退 `last_answer`
- 不抛异常

### 场景 4：普通短回答

预期：

- 现有行为兼容
- 没有 contract 字段时仍可按旧逻辑工作

## 已知未覆盖项

这些不属于本批次：

- `controller/engine.py` reconcile contract-aware 化
- `server.py` 角色收边
- project-scoped substrate / authority anchor / OpenClaw 路由治理

## 建议评审问题

1. `_controller_snapshot()` 当前 child 提升条件是否还缺漏口？
2. `_build_delivery_surface()` 的 `answer_state` 优先是否足够兼容非 research 场景？
3. `_session_response()` 是否投影了所有必要 contract 字段，还是还缺 `action_hint` 一类提示？
4. `advisor_agent_answer` 是否还需要额外返回 `completion_contract` 或 `canonical_answer` 元数据？
5. wrapper 自动 canonical fetch 是否存在过度 fetch 或错误升级 `last_answer` 的风险？
