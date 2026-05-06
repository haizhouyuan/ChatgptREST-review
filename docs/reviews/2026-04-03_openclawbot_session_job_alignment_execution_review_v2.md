# 2026-04-03 OpenClawBot Session/Job Alignment Execution Review v2

## 1. v2 相比 v1 收紧了什么

`v2` 不是新的方向，而是把 `v1` 里说得过满的地方收紧到和代码完全一致。

这次确认成立的口径是：

1. `send-phase cooldown` 的手工修复投影，不再只覆盖精确的 `https://gemini.google.com/app`
2. 现在已经对齐到仓内现成的 Gemini base-app 语义：
   - `https://gemini.google.com/app`
   - `https://gemini.google.com/app?authuser=1`
3. 同时新增了“不要误伤真实 thread”的保护性测试：
   - `https://gemini.google.com/app/<conversation_id>?authuser=1` 不应被降级
   - 已有 `conversation_id` 的 cooldown 也不应被降级

## 2. 这批改动实际解决什么

这批仍然不是去修 Gemini provider 本身，而是继续收一个更靠近 `planning task plane` 真相层的问题：

> `gemini_web.ask` 在 send-phase 已经进入真实执行，但一旦落到 `cooldown / UI transient`，public session 不能把 Gemini 根页面 URL 误当成“已有可继续线程”的证据。

如果这里说错，坏结果有两个：

1. `OpenClawBot live completion gate` 会更久地卡在 `running`
2. 用户看到的 `session status` 会比底层 `job` 更乐观，形成假进展

## 3. 当前现场事实

这轮独立核到的现场口径仍然是：

1. 旧的 `fetch failed` 不是当前唯一 mouthpiece
2. 最新 live trace 已经能把 ask 发到 `gemini_web.ask`
3. 当前更真实的 blocker 是：
   - `Gemini upload menu button not found`
4. send-phase 冷却时，底层常见组合是：
   - `job_status = cooldown`
   - `phase = send`
   - `conversation_url = https://gemini.google.com/app` 或 `.../app?authuser=1`
   - `conversation_id = ""`
   - `last_error_type = UiTransientError`

这里的关键点仍然是：

`https://gemini.google.com/app` 及其 query 变体只是 Gemini 根页面，不应被当成“已有可继续同一线程”的强证据。

## 4. 代码改动

本次批次只做了窄修复：

1. `chatgptrest/api/routes_agent_v3.py`
   - `_cooldown_requires_same_session_repair(...)`
   - `_project_job_snapshot_for_public_agent(...)`
   - `_job_snapshot(...)`

### 4.1 新规则

对于 send-phase cooldown：

1. 如果有真实 `conversation_id`，仍然按已有线程对待
2. 如果 `conversation_url` 是 Gemini base-app URL，但没有 `conversation_id`
3. 并且命中：
   - `UiTransientError`
   - 或 `upload menu button not found`

则投影成：

1. `agent_status = needs_followup`
2. `next_action.type = same_session_repair`

而不是继续投影成 `running`

### 4.2 为什么这样收

这批不改：

1. Gemini provider 具体上传 UI 流程
2. 整个 session 架构
3. `_refresh_session_state` / `_upsert_session` 的大逻辑

原因没变：这些符号 blast radius 都很高。

所以这次只改“Gemini base-app URL 不能充当线程存在证据”这条判断，尽量把风险收窄。

## 5. 新增验证

新增或补齐的测试集中在：

- `tests/test_routes_agent_v3_session_job_alignment.py`

现在覆盖 4 件事：

1. helper 级：
   - root Gemini URL + no conversation_id + UiTransientError
   - 正确投影成 `same_session_repair`
2. helper 级：
   - root Gemini URL with query (`.../app?authuser=1`) + no conversation_id
   - 也应投影成 `same_session_repair`
3. helper 级：
   - real thread URL (`.../app/<id>?authuser=1`)
   - 不应被降级
4. helper 级：
   - `conversation_id` 已存在
   - 不应被降级

route 级仍验证：

1. controller session 仍在 `WAITING_EXTERNAL`
2. child job 是上述 cooldown 形态
3. `GET /v3/agent/session/{session_id}` 结果应为 `needs_followup`

这轮实际回归通过：

1. `tests/test_routes_agent_v3_session_job_alignment.py`
2. `tests/test_bi14_fault_handling.py`
3. `tests/test_routes_agent_v3_planning_task_plane.py`
4. `tests/test_openclawbot_planning_task_plane_live_completion_gate.py`
5. `tests/test_agent_v3_routes.py`

## 6. 当前判断

这批修复仍然没有把 live 主链做绿，但把口径继续收紧成了更真实的形态：

1. 当前 live blocker 仍更明确地指向 Gemini 上传 UI 问题
2. public session 不应再因为 Gemini base-app URL 而虚假乐观
3. 这批代码的价值是提升 `job/session/checkpoint` truthfulness，而不是假装 provider 已经修好

## 7. 下一步

下一批最该做的仍然是：

1. 继续查 `Gemini upload menu button not found`
2. 重跑 `OpenClawBot live completion gate`
3. 观察当前修复是否能让 live gate 更早、更真实地收口到 `needs_followup / failed`

## 8. 一句话结论

这批改动的核心不是“让主链变绿”，而是：

> 让 `OpenClawBot planning task plane` 在 Gemini send-phase 出现 UI transient 时，不再把 Gemini base-app URL 误判成可继续线程，从而减少 session 侧的假进展。
