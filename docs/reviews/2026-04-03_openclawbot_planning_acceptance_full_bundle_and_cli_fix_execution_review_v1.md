# 2026-04-03 OpenClawBot Planning Acceptance Full Bundle And CLI Fix Execution Review v1

## 本批目标

把 `W1` 从“局部 acceptance 成立”收紧成：

1. `OpenClawBot planning acceptance pack` 默认覆盖全部 7 类 planning task 与 branch case
2. runner 可以直接以脚本方式运行，不再因为缺少 repo import path 而失败
3. 自动测试能约束：
   - full bundle default
   - direct-python CLI
   - non-repo cwd
   - `overall_pass=false` 时返回非零

## 实际改动

1. `ops/export_openclawbot_planning_task_plane_acceptance_pack.py`
   - 在脚本顶层显式注入 `REPO_ROOT` 到 `sys.path`
   - 把默认 artifact 输出目录提升到 `..._v3`
2. `tests/test_openclawbot_planning_task_plane_acceptance.py`
   - 保留原有 3 场景 targeted pack 测试
   - 新增 full-bundle default 验证
   - 新增 direct-python CLI from non-repo cwd 验证
   - 新增 CLI 默认 full bundle 验证
   - 新增 `main()` 失败返回码验证
3. 生成了新的全量 evidence：
   - `docs/dev_log/artifacts/openclawbot_planning_task_plane_acceptance_pack_20260403_v3/manifest.json`
   - `docs/dev_log/artifacts/openclawbot_planning_task_plane_acceptance_pack_20260403_v3/report_v1.md`

## 验证结果

### 自动测试

已通过：

1. `python3 -m py_compile ops/export_openclawbot_planning_task_plane_acceptance_pack.py tests/test_openclawbot_planning_task_plane_acceptance.py`
2. `./.venv/bin/pytest -q tests/test_openclawbot_planning_task_plane_acceptance.py`
3. `./.venv/bin/pytest -q tests/test_routes_agent_v3_planning_task_plane.py`

### Evidence

`v3` acceptance pack 结果：

1. `overall_pass=true`
2. `scenarios=7`
3. `passed=7`
4. `failed=0`
5. `branch_passed=true`

## 这批完成后代表什么

现在可以更强地宣称：

1. `OpenClawBot planning task plane` 的 acceptance pack 不再只是 3 类局部样例
2. `W1` 的“全量 planning task acceptance”已经在当前 mock acceptance 面上通过
3. 下一批可以从 `W1` 切到 `W2`，也就是把 task truth layer 从 phase-1 continuity 扩成 planning 主线

## 还没有宣称的部分

这批没有宣称：

1. `OpenClawBot` 材料 intake 已完成
2. task truth layer 已经完整做成
3. Anthropic harness / EvoMap 已落地
4. 整个 planning agent 计划已完成
