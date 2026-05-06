# Phase 18 / Phase 19 Validation Package Review v1

## Verdict

`Phase 18` 和 `Phase 19` 这包不能按当前口径直接签字通过。

主问题不在测试红，而在 `Phase 18` 的一个 delivery gate 自身存在漏断言，导致 `Phase 19` 的聚合结论也被带偏。

## Findings

### 1. consult delivery gate 漏掉了 session terminal status 一致性

`chatgptrest/eval/execution_delivery_gate.py` 的 `consult_delivery_completion` check 只断言了：

- `http_status == 200`
- `response_status == completed`
- `consultation_id == cons-1`

但它自己在 `details` 里也记录了 `session_status`，却没有把它纳入 expectations。

相关位置：

- `chatgptrest/eval/execution_delivery_gate.py`
- `docs/dev_log/artifacts/phase18_execution_delivery_gate_20260322/report_v1.json`

本次复核里，artifact 明确显示：

- `response_status = completed`
- `session_status = failed`

也就是说，这条 gate 当前并没有真正证明 “consult completion 的 public response + persisted session projection” 是一致的；它只证明了 turn response 自己完成了。

这不是文档措辞问题，而是 gate coverage gap。

### 2. Phase 19 仍然继承 Phase 18 的假绿结论

`chatgptrest/eval/scoped_launch_candidate_gate.py` 只是读取：

- `docs/dev_log/artifacts/phase17_scoped_public_release_gate_20260322/report_v1.json`
- `docs/dev_log/artifacts/phase18_execution_delivery_gate_20260322/report_v1.json`

然后检查两个 artifact 的 `overall_passed/num_failed`。

因此只要 `Phase 18` 的 consult delivery check 漏断言，`Phase 19` 就会把这个漏网状态继续聚合成 `GO`。

这不推翻 `Phase 19` 作为 scoped aggregate gate 的设计，但说明它当前的输入质量还不够硬。

## What Still Holds

这轮并不是整包都失效。以下结论仍然成立：

- `controller_wait_to_terminal_delivery` 通过
- `direct_image_job_delivery` 通过
- `deferred_stream_terminal_done` 通过
- `persisted_session_rehydration` 通过
- `Phase 19` 作为 aggregate gate 的边界定义仍然是克制的，没有误写成 full-stack proof

## Recommended Fix

最小修复建议：

1. 在 `consult_delivery_completion` check 中把 `session_status` 纳入 expectations，预期应为 `completed`
2. 如果当前 fake consult path 无法维持 `completed` session projection，就补齐测试夹具或实现侧存储
3. 重新生成 `Phase 18` artifact
4. 再重新跑 `Phase 19`

## Verification Performed

已复跑：

- `./.venv/bin/pytest -q tests/test_execution_delivery_gate.py tests/test_scoped_launch_candidate_gate.py tests/test_agent_v3_routes.py tests/test_routes_agent_v3.py -k 'execution_delivery_gate or scoped_launch_candidate_gate or controller_waits_for_final_answer or image_goal_uses_direct_job_substrate or consult_goal_and_cancel_track_underlying_jobs or deferred_returns_stream_url_and_sse or survives_router_recreation'`
- `python3 -m py_compile chatgptrest/eval/execution_delivery_gate.py chatgptrest/eval/scoped_launch_candidate_gate.py ops/run_execution_delivery_gate.py ops/run_scoped_launch_candidate_gate.py tests/test_execution_delivery_gate.py tests/test_scoped_launch_candidate_gate.py`
- `PYTHONPATH=. ./.venv/bin/python ops/run_execution_delivery_gate.py`
- `PYTHONPATH=. ./.venv/bin/python ops/run_scoped_launch_candidate_gate.py`

结果：

- `pytest` 子集全绿（`9 passed`）
- `py_compile` 通过
- 两个 gate 脚本都返回 `ok=true`

正因为 gate 和测试都绿，但 artifact 里仍暴露出 `session_status=failed`，所以这次评审结论是：**实现/测试还少一条关键一致性断言。**
