# 2026-04-03 OpenClawBot Session/Job Alignment Execution Review v1

## 1. 这批改动解决什么

这批不是去修 Gemini provider 本身，而是先收一个更靠近 `planning task plane` 真相层的问题：

> `gemini_web.ask` 在 send-phase 已经进入真实执行，但一旦落到 `cooldown / UI transient`，public session 有机会继续挂在 `running`，把根页面 URL 误当成“已有可继续对话线程”的证据。

这会直接带来两个坏结果：

1. `OpenClawBot live completion gate` 长时间卡在 `running`
2. 用户看到的 `session status` 比底层 `job` 更乐观，形成假进展

## 2. 当前现场事实

这轮独立核到的新事实是：

1. 旧的 `fetch failed` 不是当前唯一口径
2. 最新 live trace 已经能把 ask 发到 `gemini_web.ask`
3. 最新非绿 evidence 表明当前更真实的 blocker 是：
   - `Gemini upload menu button not found`
4. send-phase 冷却时，底层常见组合是：
   - `job_status = cooldown`
   - `phase = send`
   - `conversation_url = https://gemini.google.com/app`
   - `conversation_id = ""`
   - `last_error_type = UiTransientError`

这里的关键点是：

`https://gemini.google.com/app` 只是 Gemini 根页面，不应被当成“已有可继续同一线程”的强证据。

## 3. 代码改动

本次只做了窄修复：

1. `chatgptrest/api/routes_agent_v3.py`
   - `_cooldown_requires_same_session_repair(...)`
   - `_project_job_snapshot_for_public_agent(...)`
   - `_job_snapshot(...)`

### 3.1 新规则

对于 send-phase cooldown：

1. 如果有真实 `conversation_id`，仍然按已有线程对待
2. 如果只有通用根页面 URL（例如 `.../app`）且没有 `conversation_id`
3. 并且命中：
   - `UiTransientError`
   - 或 `upload menu button not found`

则投影成：

1. `agent_status = needs_followup`
2. `next_action.type = same_session_repair`

而不是继续投影成 `running`

### 3.2 为什么这样收

这批不改：

1. Gemini provider 具体上传 UI 流程
2. 整个 session 架构
3. `_refresh_session_state` / `_upsert_session` 的大逻辑

原因是这些符号 blast radius 都很高。

所以这次只改“根页面 URL 不能充当线程存在证据”这条判断，尽量把风险收窄。

## 4. 新增验证

新增测试文件：

- `tests/test_routes_agent_v3_session_job_alignment.py`

覆盖两件事：

1. helper 级：
   - root Gemini URL + no conversation_id + UiTransientError
   - 正确投影成 `same_session_repair`
2. route 级：
   - controller session 仍在 `WAITING_EXTERNAL`
   - child job 是上述 cooldown 形态
   - `GET /v3/agent/session/{session_id}` 结果应为 `needs_followup`

同时回归了：

1. `tests/test_bi14_fault_handling.py`
2. `tests/test_routes_agent_v3_planning_task_plane.py`
3. `tests/test_openclawbot_planning_task_plane_live_completion_gate.py`

## 5. 当前判断

这批修复没有把 live 主链做绿，但把口径收紧成了更真实的形态：

1. 当前 live blocker 已经更明确是 Gemini 上传 UI 问题
2. public session 不应再因为根页面 URL 而虚假乐观

所以这批属于：

> 先把 `job/session/checkpoint` 的 truthfulness 往前推一层，而不是假装 provider 已经修好。

## 6. 下一步

下一批最该做的仍然是：

1. 继续查 `Gemini upload menu button not found`
2. 重跑 `OpenClawBot live completion gate`
3. 观察新修复是否能让 live gate 更早、真实地收口到 `needs_followup / failed`

## 7. 一句话结论

这批改动的核心不是“让主链变绿”，而是：

> 让 `OpenClawBot planning task plane` 在 Gemini send-phase 出现 UI transient 时，不再把根页面 URL 误判成可继续线程，从而减少 session 侧的假进展。
