# Research Completion Consumer Inventory v1

日期：2026-03-30

目标：把“谁还在读旧研究完成语义”盘清，并明确第一批迁移边界。这里的重点不是全仓 grep 命中数，而是按真实运行影响分级。

## Canonical Read Rule

研究型任务消费者默认只读：

- `completion_contract.answer_state`
- `completion_contract.authoritative_answer_path`
- `completion_contract.answer_provenance`

解释：

- `status` 继续表示执行/终态语义
- 对 research long-running jobs，只有 `completion_contract.answer_state=final` 才代表真正 final
- `answer.md` / `conversation_export_path` / `events.jsonl` 只属于 materialization / evidence / process 层，不再单独承担 finality 语义

## P0 Consumers

这些路径属于在线客户端、MCP、主运维调用链，已经在本轮完成第一批迁移。

| path | 旧读取方式 | 新读取方式 | 状态 |
|---|---|---|---|
| `chatgptrest/cli.py` | `status == "completed"` 后直接抓 answer | `is_research_final()` + `get_authoritative_answer_path()` | migrated |
| `chatgptrest/mcp/server.py` | `status == "completed"` 就内联 answer / 提示 fetch_answer | `answer_state` + `authoritative_answer_path` + `answer_provenance` | migrated |
| `ops/run_convergence_live_matrix.py` | `status == "completed"` / `conversation_export_path` | `answer_state` + `authoritative_answer_path` | migrated |
| `ops/antigravity_router_e2e.py` | `status == "completed"` 就抓 answer | `answer_state` + `authoritative_answer_path` + `answer_provenance` | migrated |

## P1 Consumers

这些路径会影响内部派生视图、知识提取、观测与排障，但不直接决定 MCP/CLI 主结果面。下一轮继续迁。

| path | 当前状态 | 备注 |
|---|---|---|
| `chatgptrest/evomap/knowledge/extractors/chat_followup.py` | still reads legacy `status == "completed"` | 应迁到 completion contract，避免把 provisional research 误当 final |
| `ops/verify_job_outputs.py` | still mixes status / answer chars / export heuristics | 适合作为 canonical answer hardening 的第一批内部 consumer |
| `ops/smoke_test_chatgpt_auto.py` | still treats `status == "completed"` as primary success gate | 与 runtime smoke/ops smoke 对齐 |
| `ops/chatgpt_agent_shell_v0.py` | legacy path | 只保底，不做主入口 |

## P2 Consumers

这些属于测试、历史脚本、证据/说明文档，不应在 Phase 1 阻塞主链迁移。

- `tests/*` 中直接断言 `status == "completed"` 但不承载 research finality 语义的路径
- `docs/dev_log/*`、历史 review 文档
- `docs/dev_log/artifacts/*` evidence plane

## Health Surface

本轮新增 machine-readable health：

- `GET /health/runtime-contract`
- `GET /v1/health/runtime-contract`

最小输出：

- `service_identity`
- `allowlist_enforced`
- `allowlisted`
- `runtime_contract_ok`
- `completion_contract_version`
- `mcp_surface_version`

作用：

- 不再靠经验判断 allowlist drift / token 注入 / runtime contract 是否漂移
- 为后续 smoke、systemd preflight、ops dashboard 提供统一读面

## Next Slice

下一轮优先做：

1. `chat_followup.py`
2. `verify_job_outputs.py`
3. smoke / monitoring / issue tooling 对齐 `completion_contract`

Phase 2 不做大爆炸对象层重构，先把 observation -> final answer 的规则进一步显式化，再决定是否需要独立 canonical answer record 存储层。
