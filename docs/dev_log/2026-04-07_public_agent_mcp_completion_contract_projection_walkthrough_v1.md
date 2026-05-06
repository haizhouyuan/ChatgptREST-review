# 2026-04-07 Public Agent MCP Completion Contract Projection Walkthrough v1

## 目的

修复 public agent MCP 在 Deep Research / 长报告场景下的答案交付断层：

- 低层 `completion_contract` 已存在
- web MCP 已投影 `answer_state / authoritative_answer_path / research finality`
- public agent MCP 仍主要依赖 `last_answer`
- 结果是 `completed + empty answer` 时，coding agent 无法稳定拿到完整正文

本批次实现的目标是把 completion contract 从 job/controller/session 一路抬到 public agent surface，并补出统一的 `advisor_agent_answer` 取数工具与 wrapper 自动补取逻辑。

## 本批次范围

代码：

- `chatgptrest/api/routes_agent_v3.py`
- `chatgptrest/mcp/agent_mcp.py`
- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`

测试：

- `tests/test_agent_mcp.py`
- `tests/test_routes_agent_v3_session_job_alignment.py`
- `tests/test_skill_chatgptrest_call.py`

## 实现要点

### 1. public session 投影 completion contract

在 `routes_agent_v3.py` 中新增 `_PUBLIC_COMPLETION_FIELDS`，并通过 `_completion_projection_fields()` 统一计算：

- `answer_state`
- `authoritative_job_id`
- `authoritative_answer_path`
- `answer_provenance`
- `research_final`
- `completion_contract`
- `canonical_answer`

数据流改为：

- `_job_snapshot()` 先补 contract 字段
- `_controller_snapshot()` 合并 child contract 字段
- `_refresh_session_state()` 将 contract 字段写回 session store
- `_session_response()` 正式对外投影这些字段

### 2. 修正 `delivery.answer_ready`

`_build_delivery_surface()` 不再只用 inline `answer` 文本判断 `answer_ready`，而是：

- 有 `answer_state` 时：`answer_ready = (answer_state == "final")`
- 没有 `answer_state` 时：回退到旧逻辑，兼容短回答/旧场景

这样可以避免 provisional research answer 被误判为 ready。

### 3. child authoritative answer 提升

`_controller_snapshot()` 现在在 controller 已 terminal 但 inline answer 缺失时，允许优先提升 child snapshot 的 authoritative answer 语义，覆盖典型的：

- controller `completed`
- child 已 `final`
- controller `delivery.answer` 为空

### 4. 新增 `advisor_agent_answer`

在 `agent_mcp.py` 增加统一工具：

- job-backed session：调用 `/v1/jobs/{job_id}/answer`
- no-job session：回退 `last_answer`
- 全无答案：返回 `no_answer_available`

这让 coding agent 不需要自己分辨 session 是否来自 web job。

### 5. wrapper 自动 canonical answer fetch

`chatgptrest_call.py` agent mode 现在在 wait 终态后：

- 检查 `answer_state == final`
- 若存在 authoritative job/path，则自动调用 `advisor_agent_answer`
- 若拉到更完整正文，则提升 `canonical_answer`，并补写 `last_answer / answer`

同时 `out-summary` 顶层摘要也同步保留：

- `canonical_answer`
- `answer_state`
- `authoritative_job_id`
- `authoritative_answer_path`
- `answer_provenance`
- `answer_fetch`

## 回归

执行：

```bash
./.venv/bin/pytest -q tests/test_agent_mcp.py tests/test_routes_agent_v3_session_job_alignment.py tests/test_skill_chatgptrest_call.py
```

结果：通过。

## 新增/覆盖的关键测试场景

1. public agent status 保留 completion contract 字段
2. `advisor_agent_answer` 从 job answer API 取回完整正文
3. `advisor_agent_answer` 对 no-job session 回退 `last_answer`
4. `advisor_agent_answer` 对无答案 session 返回结构化错误
5. `delivery.answer_ready` 在 provisional 场景不再误报
6. session response 会正式投影 completion fields
7. controller `completed + answer missing` 时优先 child authoritative answer
8. wrapper agent mode 在 `answer_state=final` 时自动拉 canonical answer 并写入 summary

## 已确认的边界

- 本批次没有改 `controller/engine.py` 的 reconcile 逻辑；那是下一批稳态修复
- 本批次没有处理 `server.py` 的 broad/admin/debug 角色收边；那是中期治理任务
- 本批次只修 public agent MCP 的答案交付契约，不改 planning/control-plane 语义

## 结论

A1 批次完成后，public agent MCP 在 Deep Research / 长报告场景下不再只能依赖 `last_answer`。coding agent 现在可以：

1. `advisor_agent_turn`
2. `advisor_agent_wait`
3. 在 `answer_state=final` 时统一走 `advisor_agent_answer`

这把低层已有的 completion contract 正式抬到了 public agent northbound surface。
