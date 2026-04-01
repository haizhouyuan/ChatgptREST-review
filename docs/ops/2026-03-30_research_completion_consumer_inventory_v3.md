# Research Completion Consumer Inventory v3

日期：2026-03-30  
范围：`completion_contract` / `canonical_answer` 收敛后的 research result consumers  
状态：v3 取代 v2 作为当前 inventory；v1/v2 保留用于回溯 Phase 1/2 决策

## 目标

把“谁还在读旧语义”从主调用链、内部消费链、monitoring / issues / soak / evidence 路径里收干净，让 research finality 默认只从：

- `completion_contract.answer_state`
- `authoritative_answer_path`
- `answer_provenance`
- `canonical_answer.ready`

派生，不再让消费者各自猜 `status == completed`、`answer.md`、`conversation_export_path` 谁更真。

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

这批已在 Phase 2 完成迁移：

| Consumer | 旧语义 | 现状 |
| --- | --- | --- |
| `ops/verify_job_outputs.py` | `answer.md` / `status=completed` | 已改为优先读 `completion_contract` 与 authoritative answer |
| `chatgptrest/evomap/knowledge/extractors/chat_followup.py` | `status=completed` + `answer.md` | 已改为只消费 authoritative final research answer |
| `chatgptrest/advisor/qa_inspector.py` | `status=completed` 即读 answer | 已改为 completed 但 non-final 时继续等待 |
| `ops/smoke_test_chatgpt_auto.py` | `status=completed` 即计入成功 | 已改为 final-ready 才计入成功 |

### P2：monitoring / issues / soak / evidence

这批已在本轮完成对齐：

| Consumer | 旧语义 | 现状 |
| --- | --- | --- |
| `ops/chatgpt_agent_shell_v0.py` | `status=completed` 即返回成功 | 已改为 authoritative-ready 前继续等待 |
| `ops/codex_cold_client_smoke.py` | `status=completed` / `answer.md` 直读 | 已改为回填 `answer_state` / `authoritative_answer_path` / provenance |
| `ops/maint_daemon.py` | incident pack 只快照 `answer.*` / job row | 已改为一并快照 `completion_contract` / `canonical_answer` / authoritative artifact |
| `chatgptrest/api/routes_issues.py` | `completed + answer_path + no error` 视为 clean | 已改为 authoritative finality 才 suppress issue |
| `chatgptrest/governance/deliverable_aggregator.py` | 直接聚合 `answer.md` | 已改为优先聚合 authoritative answer path |
| `chatgptrest/ops_shared/behavior_issues.py` | 只按短字数 /旧事件判定坏完成 | 已改为读取 `result.json` 的 `completion_contract` / `canonical_answer`，completed-but-non-final research 也会被识别 |

## 统一读取规则

研究型任务的 consumer 默认应当：

1. 先看 `status`
2. 再看 `completion_contract.answer_state`
3. 只有 `status=completed` 且 `answer_state=final` 时，才把结果当成 truly final
4. authoritative answer 路径只走 `authoritative_answer_path`
5. monitoring / issue / soak / evidence 路径优先读 `canonical_answer.ready`

## 本轮后仍保留的非阻塞旧路径

这些不是默认 consumer，不属于本轮阻断项：

| Path | 角色 |
| --- | --- |
| `ops/repair_truncated_answers.py` | repair utility，面向历史 `answer_id` 修复，不是默认 research result consumer |
| `chatgptrest/governance/manifest.py` | deliverable materialization 文件名枚举，不承担 finality 判断 |
| `chatgptrest/ops_shared/behavior_issues.py` 的 incident pack `answer.md/answer.txt` 复制 | evidence/materialization，最终判断已切到 contract |

## 当前结论

截至 v3：

- P0 在线 consumer：已迁
- P1 内部派生 consumer：已迁
- P2 monitoring / issues / soak / evidence：已迁到 `completion_contract` / `canonical_answer`

下一阶段不再是“继续迁主链 consumer”，而是：

1. 继续做 canonical answer hardening（observation -> authoritative answer reducer）
2. 让 monitoring / issues / soak 用新契约做更细的 heuristics
3. 最后清理少量历史 repair / docs / one-off utility 的旧 artifact 口径
