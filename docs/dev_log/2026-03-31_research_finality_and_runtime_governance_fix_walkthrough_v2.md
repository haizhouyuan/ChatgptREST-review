# 2026-03-31 Research Finality And Runtime Governance Fix Walkthrough v2

## 本版补的最后一刀

v1 已经修住了：

- parent provisional -> child authoritative resolution
- stale intermediate job cleanup
- maintenance timer live 治理
- attachment contract 对 slash 概念词的误判

但 v1 还留了一个漏口：

- `status=completed`
- 没有 `completion_guard_*` semantic event
- 仅由 `completion_quality` 判为 `suspect_short_answer` / `suspect_meta_commentary`

这种情况下，旧逻辑仍会把 contract 标成 `final`。

## 代码修复

提交：`3a9e5b4` `Fix nonfinal completion quality gating`

涉及：

- [completion_contract.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/completion_contract.py)
- [test_contract_v1.py](/vol1/1000/projects/ChatgptREST/tests/test_contract_v1.py)
- [test_job_view_progress_fields.py](/vol1/1000/projects/ChatgptREST/tests/test_job_view_progress_fields.py)

### 1. completed 分支改成显式吸收非 final completion_quality

`build_completion_contract(...)` 现在不再只认：

- `completion_guard_completed_under_min_chars`

而是统一认：

- `completion_quality != final`

对 `status=completed` 的 job：

- `completed_under_min_chars` -> `answer_state=provisional`
- `suspect_short_answer` -> `answer_state=provisional`
- `suspect_meta_commentary` -> `answer_state=provisional`
- 其他非 final quality -> `answer_state=provisional`

`completion_contract_from_job_like(...)` 的 legacy fallback 也同步收紧，避免旧 `result.json` 直读方继续误判。

### 2. 新回归

- `tests/test_contract_v1.py`
  - `completed + suspect_short_answer -> /result.answer_state=provisional`
  - `completed + suspect_short_answer -> /answer returns 409`
  - legacy `completion_contract_from_job_like(...)` 对 `suspect_short_answer` 也返回 `provisional`

- `tests/test_job_view_progress_fields.py`
  - 原来两条 “final answer” fixture 过短，实际会踩到 `<400 chars` 的旧保守降级
  - 现在改成真正超过阈值的 final 文本，保证测试表达的是“final 内容仍应 final”

## 测试

执行：

```bash
./.venv/bin/pytest -q \
  tests/test_contract_v1.py \
  tests/test_job_view_progress_fields.py \
  tests/test_mcp_unified_ask_min_chars.py \
  tests/test_attachment_contract_preflight.py \
  tests/test_backlog_janitor.py \
  tests/test_health_probe.py \
  tests/test_leases.py
```

结果：`exit code 0`

## live 动作

执行：

```bash
systemctl --user restart \
  chatgptrest-api.service \
  chatgptrest-mcp.service \
  chatgptrest-worker-send.service \
  chatgptrest-worker-wait.service
```

结果：

- `chatgptrest-api.service` = `active`
- `chatgptrest-mcp.service` = `active`
- `chatgptrest-worker-send.service` = `active`
- `chatgptrest-worker-wait.service` = `active`

说明：

- live 运行面已经加载这次补丁
- 由于本机当前没有可直接复用的 API token 环境暴露给 shell，本次 live 核验仍采用：
  - service restart
  - `health_probe`
  - in-process API regression
  组合验证，而没有再对 live `/v1/jobs/{id}` 做一次 tokenized HTTP 读取

## 结论

这次补完后，research finality 的内部漏口已经闭合到：

- semantic guard 非 final
- quality classifier 非 final
- legacy result fallback 非 final

三条都会统一落到：

- `completion_contract.answer_state=provisional`
- `canonical_answer.ready=false`
- `/v1/jobs/{job_id}/answer -> 409`

不会再出现“`completion_quality=suspect_short_answer`，但 contract 仍是 `final`”的内部自相矛盾状态。
