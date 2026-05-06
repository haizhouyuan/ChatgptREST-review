# 2026-04-25 MCP status / follow-up answer / readiness fix v1

## 背景

本轮修复来自 control-plane sidecar 外审链路的三个实际问题：

1. `automation_job_status` MCP tool 调用时报 `NameError: _build_jobs_request is not defined`。
2. follow-up 外审 job 在复用父 conversation 时，可能把旧 assistant 长回答误收为当前问题答案。
3. 部分 job 已经 `completed` 且有 answer artifact，但 `/v1/jobs/{job_id}/answer` 返回 `409 answer not ready`。

这些不是独立表层问题，根因都指向同一类缺陷：运行时完成判定和可观测状态没有完全锚定到 canonical API / conversation export / answer artifact。

## 根因与修复

### 1. MCP status tool 使用了不存在的 legacy helper

`chatgptrest/mcp/agent_mcp.py::automation_job_status` 仍在调用旧的 `_build_jobs_request` / `_read_json_response` / `_structured_http_error_result` helper，但该文件当前其他 job-kernel MCP tools 已改为委托 `chatgptrest.mcp.server` 的 canonical kernel。

修复：

- `automation_job_status` 改为委托 `_job_kernel_module().chatgptrest_job_get(...)`。
- 新增 `tests/test_agent_mcp_job_status.py`，验证 job id trim、ctx 透传和 canonical kernel delegation。

### 2. follow-up stale answer 没有 fail-closed

事故样本中，conversation export 已经正确匹配到当前 user turn，但当前 user turn 后只有短 partial / in-progress assistant；与此同时 DOM/current answer 是一段长且看似 final 的旧 assistant 回答。旧逻辑只在 export 已有当前 answer 时才覆盖旧 DOM answer；当 export 缺当前 reply 时，`_should_downgrade_when_export_missing_reply()` 看到 DOM answer 足够长且质量像 final，就错误放行。

修复：

- 新增 `_current_answer_matches_pre_match_assistant(...)`，基于 export 的 `matched_user_index` 检测 current answer 是否来自当前 user turn 之前的 assistant turn。
- 在 `matched && missing export answer` 分支先运行该检测；若命中并且 `answer_source == matched_in_progress_partial`，fail-closed 为 `conversation_export_missing_reply`，不再把旧 DOM answer 标记 completed。
- 复用同一 helper 替换后续“export 有当前 answer 时覆盖旧 DOM answer”的重复内联逻辑，同时移除隐藏的 `_common_prefix_len` 未定义风险。
- 新增测试覆盖：
  - 旧 assistant answer 可被识别。
  - `matched_in_progress_partial` + old assistant DOM answer 必须 downgrade。
  - 正常 export lag + 真实 DOM answer 仍可通过，避免过度阻断。

### 3. completed answer readiness 被短答案启发式误伤

`answer_chunk_route` 动态计算 canonical readiness 时，会调用 `_completion_quality_for_job()`。这里有两个问题：

- 短答案质量检查用 `_REPO_ROOT / answer_path` 读 artifact，无法覆盖配置化 `CHATGPTREST_ARTIFACTS_DIR`，导致测试/外置 artifacts 场景读不到文件后进入 legacy `<400 chars` 兜底。
- 即使 `classify_answer_quality(...)` 已判定短答案是 `final`，代码仍继续掉入 legacy `<400 chars = suspect_short_answer`。

修复：

- `_completion_quality_for_job()` 增加可选 `cfg` 参数，使用 `job_artifacts.resolve_artifact_path(cfg.artifacts_dir, answer_path)` 读取 answer artifact。
- 当内容分类返回 `final` 时直接返回 `final`，只有读不到或分类非 final 时才继续 legacy fallback。
- `rescue_followup_shortcircuited` 加入 semantic finality events；子任务短路继承父任务 answer artifact 时，不再被子 web ask 的短答案启发式误判为 provisional。

## 修改文件

- `chatgptrest/mcp/agent_mcp.py`
- `chatgptrest/worker/worker.py`
- `chatgptrest/api/routes_jobs.py`
- `tests/test_agent_mcp_job_status.py`
- `tests/test_conversation_export_missing_reply_policy.py`

## 验证

已使用项目 `.venv` 运行：

```bash
.venv/bin/python -m pytest \
  tests/test_conversation_export_missing_reply_policy.py \
  tests/test_longest_candidate_extraction.py \
  tests/test_agent_mcp_job_status.py \
  tests/test_public_agent_mcp_validation.py -q
```

结果：31 passed。

```bash
.venv/bin/python -m pytest \
  tests/test_rescue_followup_guard.py \
  tests/test_contract_v1.py::test_completed_suspect_short_answer_stays_provisional \
  tests/test_contract_v1.py::test_completed_suspect_short_answer_answer_route_returns_409 \
  tests/test_conversation_export_missing_reply_policy.py \
  tests/test_longest_candidate_extraction.py \
  tests/test_agent_mcp_job_status.py \
  tests/test_public_agent_mcp_validation.py -q
```

结果：35 passed。

```bash
.venv/bin/python -m pytest \
  tests/test_worker_and_answer.py \
  tests/test_min_chars_completion_guard.py \
  tests/test_deep_research_export_guard.py \
  tests/test_deep_research_markdown_override.py \
  tests/test_conversation_export_reconcile.py \
  tests/test_rescue_followup_guard.py \
  tests/test_tool_payload_answer_guard.py -q
```

结果：通过。

## 剩余风险

- `worker.py` 和 `_completion_quality_for_job()` 都是高影响面路径，本轮只做 targeted 回归；后续发布前建议跑更宽的 job API / MCP / worker 套件。
- follow-up stale answer 的根治仍依赖 conversation export 能提供正确 `matched_user_index`。如果 export 不可用，本轮不会尝试猜测旧答案来源，而是保持原有 DOM 路径。
- `rescue_followup_shortcircuited` 被定义为 finality event，是为了表达“子任务权威 answer 来自父任务 artifact”。如果未来 short-circuit 复制的是非 final 父任务，需要在 guard 处阻断，而不是在 answer route 再猜测。
