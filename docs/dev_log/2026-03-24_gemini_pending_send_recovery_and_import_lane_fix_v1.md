# 2026-03-24 Gemini Pending Send Recovery And Import Lane Fix v1

## 背景

GeminiDT 当前的两类主要可用性问题不是同一个根因：

1. `deep_think` 文本评审会在 send 阶段长时间等待后落成 `MaxAttemptsExceeded`。
2. `repo import` 路径在 Gemini tools/import 交互层失败后，会被误当成 runtime 故障触发 `repair.autofix`，形成低质量噪音。

本次修复针对的是这两个底层问题，而不是简单增加重试次数。

## 根因

### 1. Gemini pending send 被错误 replay 成空壳

Gemini ask/pro/deep_think 的 idempotency 记录在某些中断场景下会停留在：

- `status=in_progress`
- `sent=true`
- `conversation_url=""`
- 没有最终 `result`

旧逻辑在 replay 这类记录时，只会返回一个空的 `in_progress` 包，没有 thread URL，也没有 wait handoff 标志。结果是：

- send worker 不能把任务交给 `wait`
- 后续尝试继续在 send 阶段消耗 attempts
- 最后被 generic cooldown / `MaxAttemptsExceeded` 收口

### 2. Gemini repo import 不应进入 runtime autofix

`_gemini_import_code_repo()` 在 tools/import 不可用时，旧逻辑会抛出 generic runtime 错误。维护侧随后把它归成“浏览器/driver 抖动”，进而触发：

- `restart_driver`
- `restart_chrome`

这对 repo import lane 本身通常无效，还会污染 repair history / memory / runbook。

## 修复

### A. Gemini pending send replay 改成 wait-recovery

文件：

- `chatgpt_web_mcp/providers/gemini/ask.py`

新增 `_gemini_idempotency_replay_result()`，统一处理 Gemini ask/pro/pro_thinking/pro_deep_think 的 replay 分支。

当 replay 命中以下条件时：

- `sent=true`
- `status=in_progress`
- 没有稳定 thread URL
- 没有最终结果

现在不再返回空壳，而是显式返回：

- `conversation_url=https://gemini.google.com/app`
- `error_type=GeminiSendPendingRecovery`
- `wait_handoff_ready=true`
- `wait_handoff_reason=idempotency_sent_without_thread`

这样 send worker 和 full-phase executor 都会把这轮 ask 交给 `wait/sidebar recovery`，而不是继续在 send 里烧 attempts。

### B. Gemini repo import 变成显式 lane-unavailable 语义

文件：

- `chatgpt_web_mcp/providers/gemini/core.py`
- `chatgpt_web_mcp/providers/gemini_helpers.py`
- `chatgptrest/executors/sre.py`

`_gemini_import_code_repo()` 在 tools/import 不可用时，现在会抛出：

- `Gemini import code unavailable: ...`

并被分类成：

- `GeminiImportCodeUnavailable`

SRE fast-path 对这类错误不再 route 到 `repair.autofix`，而是收成：

- `route=manual`
- `runtime_fix={}`

含义是：这属于 review transport / channel 问题，不应继续靠 runtime restart 自激。

## 验证

通过的回归：

- `tests/test_gemini_idempotency_replay_recovery.py`
- `tests/test_gemini_wait_conversation_hint.py::test_gemini_full_send_with_replayed_pending_recovery_enters_wait`
- `tests/test_worker_and_answer.py::test_gemini_send_phase_with_pending_recovery_requeues_wait`
- `tests/test_worker_and_answer.py::test_worker_does_not_treat_gemini_base_app_url_as_thread_url`
- `tests/test_worker_and_answer.py::test_gemini_wait_phase_missing_thread_url_timeout_tags_issue_family`
- `tests/test_worker_and_answer.py::test_gemini_wait_phase_no_progress_timeout_tags_issue_family`
- `tests/test_gemini_mode_selector_resilience.py::test_gemini_import_code_unavailable_classification`
- `tests/test_sre_fix_request.py::test_gemini_import_lane_unavailable_does_not_route_runtime_fix`
- `tests/test_gemini_wait_conversation_hint.py::test_gemini_full_send_with_deep_think_pending_enters_wait`
- `tests/test_worker_and_answer.py::test_gemini_send_phase_with_response_evidence_requeues_wait`
- `tests/test_gemini_mode_selector_resilience.py::test_gemini_import_code_not_found_classification`
- `tests/test_gemini_deep_think_overloaded.py`

另外 `py_compile` 通过：

- `chatgpt_web_mcp/providers/gemini/ask.py`
- `chatgpt_web_mcp/providers/gemini/core.py`
- `chatgpt_web_mcp/providers/gemini_helpers.py`
- `chatgptrest/executors/sre.py`

## 边界

这次修复的是：

- pending send 的 handoff 语义
- repo import unavailable 的错误分类与自净化边界

这次没有完成的事：

- 还没有重新拿到新的 live GeminiDT 评审答案
- 还不是新的 live provider proof
- 还没有把 repo import lane 做成稳定生产功能，只是先防止它继续误触 runtime autofix

## 提交

- `92dbc67` `fix: recover gemini pending sends and quiet import autofix`
