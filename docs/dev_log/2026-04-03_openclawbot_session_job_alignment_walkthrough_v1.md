# 2026-04-03 OpenClawBot Session/Job Alignment Walkthrough v1

## 本次做了什么

完成了一批窄修复：

1. 更新 `send-phase cooldown` 的 public projection 规则
2. 新增 session/job 对齐测试
3. 更新 `AGENTS.md`

## 为什么做这批

在继续追 `OpenClawBot live green` 之前，现场出现了一个更真实的问题：

1. ask 已经能进入 `gemini_web.ask`
2. 真实 send-phase 会遇到 `Gemini upload menu button not found`
3. 但 public session 仍有机会保持 `running`

这会让：

1. live completion gate 卡太久
2. 用户误以为“只是还在跑”，而不是“已经需要修复”

## 代码上怎么收

这次没有大改 session 系统，只改了一条判定：

如果：

1. `job_status = cooldown`
2. `phase = send`
3. 只有 `https://gemini.google.com/app` 根页面 URL
4. 没有 `conversation_id`
5. 命中 `UiTransientError / upload menu button not found`

则不再当成 `running`，而投影成：

1. `needs_followup`
2. `same_session_repair`

## 为什么不动更大的地方

`_refresh_session_state` 和 `_upsert_session` 的 blast radius 都是 `CRITICAL`。

所以这次故意不去碰：

1. 整体 session state machine
2. provider executor
3. 大范围 controller/session 逻辑

而是先收最窄、最确定的一条真 bug。

## 验证

这次跑过：

1. `python3 -m py_compile chatgptrest/api/routes_agent_v3.py tests/test_routes_agent_v3_session_job_alignment.py`
2. `./.venv/bin/pytest -q tests/test_routes_agent_v3_session_job_alignment.py tests/test_bi14_fault_handling.py tests/test_routes_agent_v3_planning_task_plane.py tests/test_openclawbot_planning_task_plane_live_completion_gate.py`

## 当前结论

这批不是 live green 批次，而是 truthfulness 批次。

它把当前主链问题从：

- “看起来还在跑”

推进成：

- “Gemini send-phase UI transient 的状态应该更早、更真实地暴露出来”
