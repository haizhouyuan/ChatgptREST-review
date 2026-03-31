# Phase 18 / Phase 19 Validation Package Review v2

## Verdict

这轮 `v2` 核验和上一轮不同：

- `Phase 18 v2`：可以签字通过
- `Phase 19 v2`：还不能完全按“当前正式 v2 artifact 路径”签字

原因不是 `Phase 18` 的 consult delivery 还坏着，而是 `Phase 19` 的默认聚合输入和 runner 输出版本号还没有真正切到 `v2`。

## Findings

### 1. Phase 18 v2 的 consult projection 修正是成立的

`chatgptrest/eval/execution_delivery_gate.py` 现在已经：

- 对 `consult_delivery_completion` 强制校验 `session_status=completed`
- 用同一份 fake consultation snapshot 同时覆盖 wait path 和 session refresh path

相关位置：

- `chatgptrest/eval/execution_delivery_gate.py`
- `tests/test_execution_delivery_gate.py`
- `docs/dev_log/artifacts/phase18_execution_delivery_gate_20260322/report_v2.json`

本次复核中，`report_v2.json` 已显示：

- `response_status = completed`
- `session_status = completed`

所以 `Phase 18 v2` 修掉了上一轮指出的假绿问题。

### 2. Phase 19 v2 仍然锚定在 v1 默认 artifact path

`chatgptrest/eval/scoped_launch_candidate_gate.py` 当前默认仍然读取：

- `docs/dev_log/artifacts/phase17_scoped_public_release_gate_20260322/report_v1.json`
- `docs/dev_log/artifacts/phase18_execution_delivery_gate_20260322/report_v1.json`

同时：

- `ops/run_scoped_launch_candidate_gate.py` 默认调用 `run_scoped_launch_candidate_gate()`，没有切到 `v2`
- `ops/run_execution_delivery_gate.py` / `ops/run_scoped_launch_candidate_gate.py` 实际 runner 输出仍写到 `report_v1.json`
- 当前 `docs/dev_log/artifacts/phase19_scoped_launch_candidate_gate_20260322/report_v2.json` 的 `details.report` 也仍记录 `report_v1.json`

这说明：

- `Phase 19 v2` 的逻辑结论未必错
- 但“现在应看的不是 v1，而是 v2 artifact” 这句话还没有完全变成 live default path

## What Still Holds

以下判断仍然成立：

- `Phase 18 v2: GO` 可以接受
- `Phase 19` 的 scope boundary 仍然写得克制，没有误抬成 full-stack proof
- 当前 public surface + covered delivery chain 的总体方向仍然是绿的

## What Is Still Missing

如果要把 `Phase 19 v2: GO` 作为当前正式门禁结论完全签字，还需要把版本切换收干净：

1. `scoped_launch_candidate_gate.py` 默认输入切到正确的 v2 artifact
2. runner 输出文件名不再继续写 `report_v1.json`
3. `Phase 19 report_v2.json` 的 `details.report` 不再引用 `phase18 report_v1.json`
4. 最好补一条测试，钉住默认路径/输出版本号

## Verification Performed

已复跑：

- `./.venv/bin/pytest -q tests/test_execution_delivery_gate.py tests/test_scoped_launch_candidate_gate.py tests/test_agent_v3_routes.py tests/test_routes_agent_v3.py -k 'execution_delivery_gate or scoped_launch_candidate_gate or controller_waits_for_final_answer or image_goal_uses_direct_job_substrate or consult_goal_and_cancel_track_underlying_jobs or deferred_returns_stream_url_and_sse or survives_router_recreation'`
- `PYTHONPATH=. ./.venv/bin/python ops/run_execution_delivery_gate.py`
- `PYTHONPATH=. ./.venv/bin/python ops/run_scoped_launch_candidate_gate.py`

结果：

- `pytest` 子集全绿（`10 passed`）
- runner 逻辑上都返回 `ok=true`
- 但 runner 实际输出路径仍是：
  - `phase18 ... report_v1.json`
  - `phase19 ... report_v1.json`

## Final Judgment

一句话收口：

- `Phase 18 v2` 已经修正到可以签字
- `Phase 19 v2` 还差最后一步版本切换收口，当前更准确的说法是：
  - gate semantics: 基本成立
  - live default artifact/version path: 仍停在 v1
