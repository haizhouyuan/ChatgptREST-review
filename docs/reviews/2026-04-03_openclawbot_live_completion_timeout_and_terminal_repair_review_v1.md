# 2026-04-03 OpenClawBot Live Completion Timeout And Terminal Repair Review v1

## 1. 这批改动解决了什么

这批不是把 `OpenClawBot` live completion 直接做绿，而是把它从“容易卡很久、30 秒内只会看到 running、现场真相不稳定”推进成两种都可信的状态：

1. bootstrap ask 有独立 hard-cap，过长不会无限拖住 gate
2. terminal polling 如果在限定时间内拿不到终态，会 fail-closed 成结构化 `probe_failed`
3. 如果给足 terminal wait，gate 现在能拿到真实终态，并把 `same_session_repair` / planning task / checkpoint 对齐关系一起记录下来

对应代码面：

- [openclawbot_planning_task_plane_live_completion_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/openclawbot_planning_task_plane_live_completion_gate.py)
- [run_openclawbot_planning_task_plane_live_completion_gate.py](/vol1/1000/projects/ChatgptREST/ops/run_openclawbot_planning_task_plane_live_completion_gate.py)
- [test_openclawbot_planning_task_plane_live_completion_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_openclawbot_planning_task_plane_live_completion_gate.py)
- [test_run_openclawbot_planning_task_plane_live_completion_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_run_openclawbot_planning_task_plane_live_completion_gate.py)

## 2. 这批实际验证到了什么

### 2.1 v4 证明短 terminal wait 也会诚实失败

我先用较短的 terminal timeout 重跑了一版 live gate：

- [v4 manifest](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260403_v4/manifest.json)
- [v4 report json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260403_v4/report_v1.json)
- [v4 report md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260403_v4/report_v1.md)

结果不是假装 `running`，而是明确：

- `terminal_status=probe_failed`
- `error=terminal_wait_timeout status=running session_id=...`

这证明：

- 30 秒内没拿到终态时，gate 不会再冒充“还在正常进行”
- live completion 这条线已经具备可信 fail-closed 行为

### 2.2 v5 证明给足 terminal wait 后可以拿到真实终态

然后我把 bootstrap ask 仍压到 45 秒，但把 terminal wait 放回正式观测窗口，再跑了一版：

- [v5 manifest](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260403_v5/manifest.json)
- [v5 report json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260403_v5/report_v1.json)
- [v5 report md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260403_v5/report_v1.md)

这次结果已经不再是 `probe_failed`，而是：

- `terminal_status=needs_followup`
- `num_passed=4`
- `num_failed=2`

通过的检查是：

- `openclaw_live_terminal_observable`
- `planning_task_visible_after_terminal`
- `planning_checkpoint_terminal_alignment`
- `actionable_fail_closed_if_not_completed`

没通过的仍然是：

- `final_completion_ok`
- `answer_quality_ok`

这说明当前现场已经达到：

- 终态可观察
- task plane 可观察
- checkpoint 与 terminal 状态对齐
- 未完成时会给出可执行 repair，而不是模糊 running

### 2.3 v5 现在能稳定证明的范围

v5 当前能稳定证明的是：

- session 可以收口到 `needs_followup`
- `same_session_repair` 会被明确暴露出来
- planning task 与 checkpoint 会在非绿终态下继续保持可见和对齐

但 v5 当前还不能单独证明某一个更细的 provider 根因已经被最终冻结。

## 3. 我对这批的独立判断

### 3.1 现在可以明确说的

现在可以安全冻结成这些说法：

- live completion gate 已经从“可能假绿/假 running”推进成 `truthful fail-closed`
- bootstrap ask 与 terminal wait 已经解耦，gate 不再因为 bootstrap 卡住而无限拖长
- 当前现场已经能稳定拿到 `needs_followup + same_session_repair` 这类终态
- planning task / checkpoint / latest session 对齐已经被 live evidence 证明过一次

### 3.2 现在还不能说的

现在还不能说：

- live completion 已经做绿
- final completion / answer quality 已经通过
- Feishu/OpenClawBot 真实聊天 ingress 已经完成 live proof
- phase-1 整体已经完成

### 3.3 当前剩余 gap

当前这条线剩余的是 provider-side final completion / answer quality 问题，而不是 truthfulness 问题：

- 当前 v5 仍然没有拿到 `completed` 终态
- 这意味着 session 虽然能诚实收口到 `needs_followup`，但还没有稳定交付最终三条 planning 结果
- 所以 `answer_quality_ok` 和 `final_completion_ok` 仍未过线

## 4. 测试与验证

通过的回归：

- `python3 -m py_compile chatgptrest/eval/openclawbot_planning_task_plane_live_completion_gate.py ops/run_openclawbot_planning_task_plane_live_completion_gate.py tests/test_openclawbot_planning_task_plane_live_completion_gate.py tests/test_run_openclawbot_planning_task_plane_live_completion_gate.py`
- `./.venv/bin/pytest -q tests/test_openclawbot_planning_task_plane_live_completion_gate.py tests/test_run_openclawbot_planning_task_plane_live_completion_gate.py`

这批重点新增覆盖了：

- bootstrap timeout hard-cap 上下界
- terminal wait timeout fail-closed
- runner env timeout override
