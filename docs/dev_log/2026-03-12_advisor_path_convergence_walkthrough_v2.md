# Advisor Path Convergence Walkthrough v2

**Date**: 2026-03-12  
**Branch**: `codex/advisor-path-convergence-20260312`  
**Follow-up to**: PR `#147` review feedback

## Trigger

在 PR147 首轮提交后，重新核对 [2026-03-12_pr147_advisor_path_convergence_review_v2.md](./2026-03-12_pr147_advisor_path_convergence_review_v2.md) 识别出的 3 个问题：

1. `openmind-advisor` 默认行为从同步返回结果变成异步只返回 `job_id`
2. `waitForCompletion=true` 时只抓第一段 answer chunk，长答案会静默截断
3. `/v2/advisor/advise` 的 `request_metadata.trace_id` 在未显式传入 trace 时不会回填真实执行 trace

## Fixes Applied

### 1. 恢复插件默认兼容语义

- 将 `openmind-advisor` 的默认 `defaultMode` 从 `ask` 恢复为 `advise`
- 保留 `ask + waitForCompletion` 作为显式 opt-in 路径
- 同步更新 manifest help 和 README 文案
- 将插件 manifest version 提升到 `2026.3.12`

### 2. 补齐 answer 分页拉取

- `waitForAdvisorJob()` 改为按 `next_offset` 循环拉取 `/v1/jobs/{job_id}/answer`
- 累积所有 `chunk` 并拼接成完整 `answer`
- 增加分页护栏：`next_offset` 不前进或页数超过 `128` 时标记 `truncated=true`
- 将分页结果暴露到 `answer_result`，便于后续排障

### 3. 回填 `advise` 路径真实 trace

- 新增 `_merge_request_metadata()`
- 当调用方没有显式传入 `trace_id` 时，用 `api.advise()` 返回的真实 trace 回填 `request_metadata.trace_id`
- 若调用方已经显式传入 `trace_id`，则保留原始输入，不做覆盖

## Tests

执行通过：

```bash
python3 -m py_compile \
  chatgptrest/api/routes_advisor_v3.py \
  tests/test_advisor_v3_end_to_end.py \
  tests/test_openclaw_cognitive_plugins.py

/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_advisor_v3_end_to_end.py \
  tests/test_openclaw_cognitive_plugins.py

/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_routes_advisor_v3_security.py \
  tests/test_feishu_ws_gateway.py
```

新增/强化覆盖点：

- `test_v3_advise_backfills_request_metadata_trace_id_from_runtime_result`
- `test_openmind_plugin_sources_expose_expected_hooks_and_tools`
- `test_openmind_plugins_default_to_integrated_host_port`

## Remaining Gap

- 本机 worktree 仍然没有本地 `./node_modules/.bin/tsc`，所以这轮依然没有跑 TypeScript 编译检查
- 目前通过 source assertions 锚定了插件关键逻辑，但还没有真正执行一个 Node 级插件集成测试
