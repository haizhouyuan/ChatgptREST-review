# 2026-04-04 W1 Live Triage And Task Truth Alignment Walkthrough v1

## 做了什么

这一批做了 4 件事：

1. 先收敛 `W1-S1` 的现场判断，确认 Gemini 单页槽与 `maint_daemon` 的竞争已经不再是当前主 blocker。
2. 连续重跑同一 canonical `requested_provider=gemini` live completion gate，拿到 `v40 / v41 / v42` 三连绿。
3. 在 fresh cancel probe 中发现一个真实 truth gap：
   - session 已 `cancelled`
   - 但 planning task / checkpoint 仍停留在 `active/running`
4. 继续向下查，发现 direct Gemini live success 也有一个类似 gap：
   - live gate 绿了
   - 但 terminal session 文件内嵌的 `control_plane.planning_task` 仍是旧快照

## 为什么要继续补代码

如果只停在 `v40-v42` 的 manifest，全局口径会过于乐观。

因为当时已经能证明：

1. provider completion 绿了
2. planning task store 能通过 `task_get` 看见 completed

但还不能证明：

1. terminal `session payload` 里内嵌的 planning truth 也同步了
2. `cancelled` 路径上的 session/task/checkpoint 真的是同一口径

这会直接影响 handoff artifact 的可信度，所以我没有把它留给后续再说，而是就地补齐。

## 代码上怎么修

只改了 `chatgptrest/api/routes_agent_v3.py`。

### 1. cancel 路径

`/v3/agent/cancel` 现在不只取消 session/job，还会：

1. 恢复该 session 的 `task_intake`
2. 对应 planning task 写 `status=cancelled`
3. 把更新后的 planning task 回填进 session 的 `control_plane`

### 2. direct Gemini completion 路径

`requested_provider=gemini` 的 direct job lane 现在会在 terminal session write 之前先写 planning checkpoint，并把更新后的 planning task 塞回 `control_plane`。

这样 terminal session 文件就不再保留旧的 `intake_received` 快照。

## 我怎么验证

### 本地回归

通过：

```bash
python3 -m py_compile \
  chatgptrest/api/routes_agent_v3.py \
  tests/test_routes_agent_v3_planning_task_plane.py

./.venv/bin/pytest -q \
  tests/test_routes_agent_v3_planning_task_plane.py \
  -k 'direct_gemini_lane_persists_completed_planning_task_to_session or cancel_syncs_planning_task_checkpoint_to_cancelled or preflight_blocked_material_action_posture or refreshes_active_entries_from_latest_session'

./.venv/bin/pytest -q \
  tests/test_routes_agent_v3.py \
  -k 'requested_gemini_code_review_uses_direct_gemini_web_lane or compact_implementation_next_steps_normalizes_direct_gemini_answer or cancelled_lifecycle_surface or preserves_cancelled_status_against_stale_controller_snapshot or session_cancelled_to_runtime_event_bus'
```

### live 证据

稳定 success：

- `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_v40/`
- `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_v41/`
- `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_v42/`

post-fix live success：

- `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_v44/`
- `state/agent_sessions/openclaw-live-planning-completion-session-2eb229c5.json`

其中 `v44` 对应 session 文件已经明确变成：

1. `session.status=completed`
2. `planning_task.status=completed`
3. `checkpoint.current_state=current_status=completed`

fresh cancel consistency probe：

- `docs/dev_log/artifacts/openclawbot_planning_task_cancel_consistency_probe_20260404_v3/`

其中：

1. `session_before_cancel.json` 还是 `running`
2. `session_after_cancel.json` 变成 `cancelled`
3. `task_after_cancel.json` 也变成 `cancelled`

## 当前冻结口径

到 2026-04-04 这轮收口后，`W1` 的正确说法是：

1. phase-1 live 主链已经可对外只声明 `requested_provider=gemini`
2. `success / fail / cancel` 已有真实 evidence
3. ChatGPT live completion 仍然 verification-blocked，明确不纳入稳定 claim
4. phase-1 材料基线当前只认：
   - direct-review: `document / spreadsheet / code`
   - preprocess-first: `audio / video / image / archive`
   - mixed: `advisory_continue`

## 下一步

下一步不该继续在 `W1` 里横向扩面了。

更合理的顺序是：

1. 用 `v44 + cancel probe v3 + v40-v42` 作为 `W1` 冻结 evidence
2. 把主工作面切到 `W2`
3. 只有当 Gemini phase-1 lane 再次回归时，才回到 `W1`
