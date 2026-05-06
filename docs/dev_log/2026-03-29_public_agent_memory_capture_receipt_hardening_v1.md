---
title: public agent memory capture receipt hardening
version: v1
date: 2026-03-29
status: committed
owner: codex
---

# 2026-03-29 Public Agent Memory Capture Receipt Hardening v1

## What Changed

1. `memory.capture` 新增 strict provenance 模式。
   - `/v2/memory/capture` 现在支持 `require_complete_identity=true`
   - 若 identity envelope 缺 `session_key / agent_id / account_id / thread_id / source_ref`，服务端不再继续写入 partial memory，而是显式返回 blocked receipt

2. public agent surface 新增 `memory_capture` receipt。
   - `/v3/agent/turn`
   - `/v3/agent/session/{session_id}`
   - public MCP `advisor_agent_turn`
   现在都能透出同一份 capture 回执

3. public agent turn 新增显式 capture 请求。
   - `advisor_agent_turn(..., memory_capture={...})`
   - `/v3/agent/turn` body 也可直接传 `memory_capture`
   - 回执会进入 `effects.memory_capture`

## Why

这次修的是系统级联验里的真实断点：

- `memory.capture` 服务本身已经可用，但 public advisor-agent surface 不返回 capture receipt
- 客户端无法区分“turn completed”与“capture completed”
- `partial lineage` 之前默认被静默接受，不利于四端正式验收

## Verification

已通过：

```bash
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_cognitive_api.py -k 'memory_capture'
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_routes_agent_v3.py -k 'memory_capture_receipt or deferred_accepts_lifecycle'
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_agent_mcp.py -k 'memory_capture_request or forwards_deferred_delivery_mode'
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_routes_agent_v3.py tests/test_agent_mcp.py tests/test_openmind_memory_business_flow.py
python3 -m py_compile \
  chatgptrest/api/routes_agent_v3.py \
  chatgptrest/api/routes_cognitive.py \
  chatgptrest/cognitive/memory_capture_service.py \
  chatgptrest/mcp/agent_mcp.py
```

## Remaining Gap

这次只补了 ChatgptREST owner-side：

- public agent surface 现在可以显式请求 capture 并读取 receipt
- 但前端 runtime 是否能稳定提供完整 identity，仍取决于各客户端
- OpenClaw / Antigravity 仍要继续把 hook/tool context 的 `sessionId / agentAccountId / threadId` 补齐，才能把 `partial` 真正压到最少
