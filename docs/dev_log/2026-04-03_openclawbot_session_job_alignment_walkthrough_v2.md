# 2026-04-03 OpenClawBot Session/Job Alignment Walkthrough v2

## 本次相对 v1 补了什么

`v1` 已经把 send-phase cooldown 的 truthfulness bug 收掉了一半，但红队指出两个缺口：

1. 只覆盖了精确的 `.../app`
2. 没有证明“不会误伤真实 Gemini thread”

这次 `v2` 就只补这两个点，没有扩大改动面。

## 代码上怎么收

这次继续只动 `chatgptrest/api/routes_agent_v3.py` 的窄判定：

1. 不再用字符串 `endswith('/app')`
2. 改为复用仓内已有的 Gemini base-app helper 语义

因此现在这条规则同时覆盖：

1. `https://gemini.google.com/app`
2. `https://gemini.google.com/app?authuser=1`

同时排除：

1. `https://gemini.google.com/app/<conversation_id>`
2. 已经存在 `conversation_id` 的情况

## 为什么不继续扩面

`routes_agent_v3.py` 的 blast radius 还是高。

GitNexus 对 `_job_snapshot` 仍给出 `CRITICAL` 风险，因为它直接挂着：

1. `_wait_for_job_completion`
2. `_refresh_session_state`
3. `get_session`
4. `stream_session`

所以这次继续坚持：

1. 不碰 provider executor
2. 不碰 session 总状态机
3. 不碰更大的任务层设计

只把“Gemini base-app 的 canonical 识别”补对。

## 验证

这轮实际跑过：

1. `python3 -m py_compile chatgptrest/api/routes_agent_v3.py tests/test_routes_agent_v3_session_job_alignment.py`
2. `./.venv/bin/pytest -q tests/test_routes_agent_v3_session_job_alignment.py tests/test_bi14_fault_handling.py tests/test_routes_agent_v3_planning_task_plane.py tests/test_openclawbot_planning_task_plane_live_completion_gate.py tests/test_agent_v3_routes.py`

## 当前结论

这批仍然不是 live green 批次，而是 truthfulness 批次的补强版。

它现在解决的是：

1. `needs_followup` 不再只覆盖最窄的 `/app`
2. 也不会把真实 Gemini thread 错降成 repair
