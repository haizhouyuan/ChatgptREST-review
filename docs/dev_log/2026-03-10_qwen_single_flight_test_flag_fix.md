# 2026-03-10 qwen single-flight test flag fix

## Context

`pytest -q -x -vv` 在推进到两组 qwen 相关用例时失败：

- `tests/test_conversation_single_flight.py::test_qwen_create_job_blocks_when_conversation_has_active_ask`
- `tests/test_conversation_url_kind_validation.py::*qwen*`
- `tests/test_leases.py::test_retryable_qwen_cdp_limit_becomes_needs_followup`

这些用例里的首个 `/v1/jobs` 请求返回的不是预期的 `200` 或 `400`，而是：

- `409`
- `detail.error = provider_disabled`

这说明失败并不是 qwen conversation single-flight / conversation-url 校验回归，而是测试没有显式打开 `CHATGPTREST_QWEN_ENABLED`。

## Root Cause

当前宿主默认保持 `qwen_web.*` 关闭，`routes_jobs.py` 会在未启用时直接拒绝 `qwen_web.ask`。

这几组测试都在验证 qwen 行为，但都隐式依赖了宿主默认启用 qwen，这个前提已经不成立。

## Change

做了两处收口：

- 在 `test_qwen_create_job_blocks_when_conversation_has_active_ask` 内显式：
  - `monkeypatch.setenv("CHATGPTREST_QWEN_ENABLED", "1")`
- 在 `tests/test_conversation_url_kind_validation.py` 的文件级 fixture 内显式：
  - `monkeypatch.setenv("CHATGPTREST_QWEN_ENABLED", "1")`
- 在 `test_retryable_qwen_cdp_limit_becomes_needs_followup` 内显式：
  - `monkeypatch.setenv("CHATGPTREST_QWEN_ENABLED", "1")`

这样测试环境会主动声明自己需要 qwen provider，而不是把 host feature flag 假设写死在用例里。

## Validation

- `./.venv/bin/pytest -q tests/test_conversation_single_flight.py -q`
- `./.venv/bin/pytest -q tests/test_conversation_url_kind_validation.py -q`
- `./.venv/bin/pytest -q tests/test_leases.py -k qwen_cdp_limit -vv`
- `./.venv/bin/python -m py_compile tests/test_conversation_single_flight.py`
- `./.venv/bin/python -m py_compile tests/test_conversation_url_kind_validation.py`
- `./.venv/bin/python -m py_compile tests/test_leases.py`

结果：通过。
