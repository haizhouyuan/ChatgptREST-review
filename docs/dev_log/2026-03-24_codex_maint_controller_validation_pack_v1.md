# Codex Maint Controller Validation Pack v1

日期：2026-03-24

## 目标

把 `codex_maint_controller_blueprint_v2` 的关键承诺落成可重复执行的验证包，而不是只停留在单元测试和设计文档。

## 验证范围

- canonical run ledger 固定在 `sre.fix_request` lane
- `taskpack/*` 只是 lane artifacts 的标准化投影
- incident 侧 `codex/*` 只是 mirror/pointer
- maint fallback / runtime fix escalation 都复用 canonical lane
- recurring action preferences 能从 maint memory 注入 escalation context
- operator attach 能从 canonical lane 或 incident pointer 解析 attach target
- 既有 `repair.autofix` guardrails 没被 controller 改坏

## 实现

- 验证模块：[codex_maint_controller_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/codex_maint_controller_validation.py)
- 运行脚本：[run_codex_maint_controller_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_codex_maint_controller_validation.py)
- 回归测试：[test_codex_maint_controller_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_codex_maint_controller_validation.py)

## 执行命令

```bash
python3 -m py_compile chatgptrest/eval/codex_maint_controller_validation.py ops/run_codex_maint_controller_validation.py tests/test_codex_maint_controller_validation.py
./.venv/bin/pytest -q tests/test_codex_maint_controller_validation.py
PYTHONPATH=. ./.venv/bin/python ops/run_codex_maint_controller_validation.py
```

## 结果

- validation runner：`8/8` 通过
- 报告：
  - [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/codex_maint_controller_validation_20260324/report_v1.json)
  - [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/codex_maint_controller_validation_20260324/report_v1.md)

## 边界

- 这是 lane-backed maintenance control plane proof
- 不是 external provider / public-agent live proof
- 不是 tmux/TUI attach UX 完整体验收
