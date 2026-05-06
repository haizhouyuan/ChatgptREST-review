# 2026-04-03 OpenClawBot Session/Job Alignment Walkthrough v3

## 本次相对 v2 又收了什么

`v2` 已经把 Gemini canonical base-app query 变体补上了，但红队还指出两点：

1. 文档把这批修复描述得比代码更窄
2. “不误伤真实 thread” 还只停在 helper 级

这次 `v3` 就只收这两件事。

## 代码上这次没有再扩功能

运行时代码没有新增分支。

这次只补了一条 route-level 正向测试，证明：

1. child job 是 real Gemini thread
2. `conversation_id` 已存在
3. route/session 结果仍保持 `running/check_status`

所以这次是：

1. 证据补强
2. 文档收口

不是新功能批次。

## 文档口径怎么改

这次把口径改成和代码完全同构：

1. 新增重点确实是 Gemini canonical base-app 识别
2. 但代码仍然保留了更早的 `URL-less send cooldown -> same_session_repair` 语义
3. 所以不能把这批改动讲成“纯 Gemini base-app 专项修复”

## 验证

这轮实际跑过：

1. `./.venv/bin/pytest -q tests/test_routes_agent_v3_session_job_alignment.py tests/test_agent_v3_routes.py tests/test_bi14_fault_handling.py`

前一轮已通过的更宽回归仍成立：

1. `tests/test_routes_agent_v3_planning_task_plane.py`
2. `tests/test_openclawbot_planning_task_plane_live_completion_gate.py`

## 当前结论

这批仍然不是 live green 批次，而是 truthfulness 批次的收口版。

它现在解决的是：

1. Gemini canonical base-app 识别已经对齐
2. 真实 Gemini thread 的 route-level 非误伤也已有证据
3. 文档口径不再跑在代码前面
