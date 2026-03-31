# Completion Contract Phase 2 Internal Consumer Alignment Walkthrough v1

日期：2026-03-30

## 为什么继续做这轮

Phase 1 已经把 P0 consumer 和 runtime health 收到 `completion_contract`。  
剩下的问题不是 runtime 内核本身，而是内部派生消费面仍会：

- 直接把 `status=completed` 当 final
- 直接读 `answer.md`
- 不区分 provisional research 和 final research

这会继续制造“内核说一套，内部工具猜一套”。

## 本轮改了什么

### 1. 补了更窄的 completion helper

在 `chatgptrest/core/completion_contract.py` 新增：

- `is_authoritative_answer_ready()`
- `resolve_authoritative_answer_artifact()`

目的：

- 把“什么时候可以真正读取 authoritative answer”收成单一 helper
- 把 artifact 解析也收成统一入口

### 2. 迁了 4 条 P1 consumer

- `ops/verify_job_outputs.py`
  - 优先读取 `completion_contract`
  - verify report 会显式写出 `answer_state` / `authoritative_answer_path` / `answer_provenance`
  - `completed` 但 non-final research 会打 `completed_not_final`

- `chatgptrest/evomap/knowledge/extractors/chat_followup.py`
  - `JobData` 现在会暴露 `completion_contract` / `answer_state` / `authoritative_answer_path`
  - authoritative answer 优先走 contract path
  - extractor 只消费 authoritative final research answer

- `chatgptrest/advisor/qa_inspector.py`
  - `_wait_and_read()` 遇到 completed 但 non-final research 时继续等待
  - 不再提前读 partial answer

- `ops/smoke_test_chatgpt_auto.py`
  - 只有 authoritative final 才算 smoke success
  - completed 但 non-final 会落成 `completed_not_final`

## 测试

新增：

- `tests/test_verify_job_outputs.py`
- `tests/test_chat_followup_extractor.py`

扩展：

- `tests/test_qa_inspector.py`
- `tests/test_smoke_test_chatgpt_auto.py`

定向验证：

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_ops_endpoints.py \
  tests/test_cli_chatgptrestctl.py \
  tests/test_mcp_unified_ask_min_chars.py \
  tests/test_convergence_live_matrix.py \
  tests/test_antigravity_router_e2e.py \
  tests/test_verify_job_outputs.py \
  tests/test_chat_followup_extractor.py \
  tests/test_qa_inspector.py \
  tests/test_smoke_test_chatgpt_auto.py
```

结果：通过。

## 这轮之后的状态

`completion_contract` 现在不只是对外 surface 的新字段，也已经成为：

- verify
- extractor
- qa inspector
- smoke

这几条内部消费链的默认读取规则。

## 剩余项

下一阶段继续做：

1. canonical answer hardening
2. monitoring / issues / soak 对齐新契约
3. 剩余 P2 legacy consumer 清退
