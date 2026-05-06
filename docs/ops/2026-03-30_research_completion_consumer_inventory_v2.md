# Research Completion Consumer Inventory v2

日期：2026-03-30  
范围：`completion_contract` 收敛后的 research result consumers  
状态：v2 取代 v1 作为当前 inventory；v1 保留用于回溯 Phase 1 决策

## 目标

把“谁还在读旧语义”盘清，并明确哪些 consumer 已迁到：

- `completion_contract.answer_state`
- `authoritative_answer_path`
- `answer_provenance`

## 分级

### P0：主调用链 / 在线客户端

这批已在 Phase 1 完成迁移：

| Consumer | 状态 | 当前读取入口 |
| --- | --- | --- |
| `chatgptrest/cli.py` | migrated | `completion_contract` helper |
| `chatgptrest/mcp/server.py` | migrated | `completion_contract` helper |
| `ops/run_convergence_live_matrix.py` | migrated | `completion_contract` helper |
| `ops/antigravity_router_e2e.py` | migrated | `completion_contract` helper |

### P1：内部派生消费面

这批已在本轮完成迁移：

| Consumer | 旧语义 | 现状 |
| --- | --- | --- |
| `ops/verify_job_outputs.py` | `answer.md` / `status=completed` | 已改为优先读 `completion_contract` 与 authoritative answer |
| `chatgptrest/evomap/knowledge/extractors/chat_followup.py` | `status=completed` + `answer.md` | 已改为只消费 authoritative final research answer |
| `chatgptrest/advisor/qa_inspector.py` | `status=completed` 即读 answer | 已改为 completed 但 non-final 时继续等待 |
| `ops/smoke_test_chatgpt_auto.py` | `status=completed` 即计入成功 | 已改为 final-ready 才计入成功 |

### P2：剩余低优先级/历史 consumer

这批还没有迁，保留为下一阶段：

| Consumer | 备注 |
| --- | --- |
| `ops/chatgpt_agent_shell_v0.py` | legacy shell；非默认入口 |
| `ops/codex_cold_client_smoke.py` | 冷启动/兜底 smoke；不是主 runtime 路径 |
| `chatgptrest/api/routes_agent_v3.py` | 高层 surface，暂不直接消费 answer artifact |
| `ops/maint_daemon.py` | issue/repair lane，需与 canonical answer hardening 一起收 |

## 当前统一读取规则

研究型任务的 consumer 默认应当：

1. 先看 `status`
2. 再看 `completion_contract.answer_state`
3. 只有 `status=completed` 且 `answer_state=final` 时，才读取 authoritative answer
4. authoritative answer 路径只走 `authoritative_answer_path`
5. provenance 只走 `answer_provenance`

## 剩余工作

下一阶段不再优先扩大 consumer 数量，而是：

1. 做 canonical answer hardening
2. 把 monitoring / issues / soak 进一步对齐 `completion_contract`
3. 再清剩余 P2 legacy consumer
