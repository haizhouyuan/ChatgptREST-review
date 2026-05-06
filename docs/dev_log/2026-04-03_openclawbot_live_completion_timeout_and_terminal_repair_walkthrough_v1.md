# 2026-04-03 OpenClawBot Live Completion Timeout And Terminal Repair Walkthrough v1

## 做了什么

这批围绕 `OpenClawBot planning live completion gate` 做了两件事：

1. 给 bootstrap ask 加独立 hard-cap
2. 把 terminal timeout 改成结构化 fail-closed，而不是返回伪 `running`

## 为什么这么做

前一版最大的问题不是“没过”，而是“现场真相不够稳定”：

- bootstrap ask 可能把整个 gate 拖很久
- 30 秒内拿不到终态时，report 只会停在 `running`
- 这样很难区分是 provider 真慢，还是 gate 自己不会老实失败

这批先把 gate 做成可信的，再继续追 provider completion。

## 我怎么验证的

### 1. 先跑单测/回归

跑了：

- `tests/test_routes_agent_v3_session_job_alignment.py`
- `tests/test_routes_agent_v3.py`
- `tests/test_openclawbot_planning_task_plane_live_completion_gate.py`
- `tests/test_run_openclawbot_planning_task_plane_live_completion_gate.py`

结果通过。

### 2. 再跑短 terminal wait 的 v4

命令思路：

- bootstrap ask 45s
- terminal wait 30s

结果：

- 没拿到终态时，report 现在会明确写 `probe_failed`
- 不再把现场包装成“仍在正常 running”

### 3. 再跑正式终态观测的 v5

命令思路：

- bootstrap ask 45s
- terminal wait 用正式窗口

结果：

- 成功拿到 `terminal_status=needs_followup`
- task / checkpoint / latest session 对齐通过
- 最终 completion 和 answer quality 仍失败

## 这批之后怎么理解现场

这批之后，`live completion` 的现状应该这样说：

- `truthfulness` 这一层已经过关
- `provider completion quality` 这一层还没过关

也就是：

- gate 现在能诚实告诉我们“没完成，而且需要 same-session repair”
- 但它还不能稳定给出最终三条 planning 结果
