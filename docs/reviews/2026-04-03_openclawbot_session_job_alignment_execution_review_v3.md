# 2026-04-03 OpenClawBot Session/Job Alignment Execution Review v3

## 1. v3 相比 v2 收紧了什么

`v3` 继续只做口径和证据收口，不扩大功能面。

这次新增成立的两点是：

1. “不误伤真实 Gemini thread” 已经补到 route/session 层，不再只停留在 helper 层
2. 文档口径改成和代码完全一致：
   - 这批修复的新增重点是 Gemini canonical base-app variants
   - 但代码仍保留更早的 `URL-less send cooldown -> same_session_repair` 语义

## 2. 这批改动实际解决什么

这批仍然不是去修 Gemini provider 本身，而是继续收一个更靠近 `planning task plane` 真相层的问题：

> `gemini_web.ask` 在 send-phase 已经进入真实执行，但一旦落到 `cooldown / UI transient`，public session 不能把 Gemini 根页面 URL 误当成“已有可继续线程”的证据；同时也要保持现有的 URL-less send cooldown repair 语义不被破坏。

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
   - `conversation_url = https://gemini.google.com/app` 或 `.../app?authuser=1`，也可能暂时为空
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

### 4.1 当前规则

对于 send-phase cooldown：

1. 如果有真实 `conversation_id`，仍然按已有线程对待
2. 如果 `conversation_url` 是 Gemini base-app URL，但没有 `conversation_id`
3. 或者 `conversation_url` 暂时为空，但仍处于 send-phase cooldown
4. 并且命中：
   - `UiTransientError`
   - 或 `upload menu button not found`

则投影成：

1. `agent_status = needs_followup`
2. `next_action.type = same_session_repair`

而不是继续投影成 `running`

这里要明确：

- `v3` 的新增重点是 Gemini canonical base-app 语义补齐
- 但代码没有删除原有的 URL-less send cooldown repair 语义

### 4.2 为什么这样收

这批不改：

1. Gemini provider 具体上传 UI 流程
2. 整个 session 架构
3. `_refresh_session_state` / `_upsert_session` 的大逻辑

原因没变：这些符号 blast radius 都很高。

所以这次只改“Gemini base-app URL 不能充当线程存在证据”这条判断，并补齐它的 canonical 变体与非误伤测试。

## 5. 新增验证

测试集中在：

- `tests/test_routes_agent_v3_session_job_alignment.py`

现在覆盖 5 件事：

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
5. route 级：
   - real Gemini thread child job
   - `GET /v3/agent/session/{session_id}` 仍保持 `running/check_status`

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
3. 真实 Gemini thread 不会因为这批修复被误降成 repair
4. 这批代码的价值是提升 `job/session/checkpoint` truthfulness，而不是假装 provider 已经修好

## 7. 下一步

下一批最该做的仍然是：

1. 继续查 `Gemini upload menu button not found`
2. 重跑 `OpenClawBot live completion gate`
3. 观察当前修复是否能让 live gate 更早、更真实地收口到 `needs_followup / failed`

## 8. 一句话结论

这批改动的核心不是“让主链变绿”，而是：

> 让 `OpenClawBot planning task plane` 在 Gemini send-phase 出现 UI transient 时，不再把 Gemini base-app URL 误判成可继续线程，并补齐真实 thread 非误伤验证，从而减少 session 侧的假进展。
