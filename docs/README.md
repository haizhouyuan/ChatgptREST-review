# ChatgptREST 文档索引（从这里开始）

目标：把“做过什么 / 为什么这么做 / 代码在哪 / 出问题先看哪”集中到一个入口，方便你从文档追溯到历史开发与修复。

## 建议阅读顺序（5 分钟快速定位）

1) `docs/ops/2026-03-25_agent_maintainer_entry_v1.md`：正式 maintainer entry（先判断 plane / worktree / runtime-state 边界）。
2) `docs/ops/2026-03-25_document_plane_guide_v1.md`：当前 guidance 与 `docs/dev_log/` 的 history/proposal/reference 口径。
3) `docs/contract_v1.md`：对外 REST v1 契约（/v1/jobs、/wait、/answer、/conversation…）。
4) `docs/runbook.md`：启动/重启/排障清单（端口、env、脚本、常见故障，含 `Incident-Class Runbook` 与 Codex 唤醒执行合同）。
5) `docs/repair_agent_playbook.md`：Repair Agent 权限/步骤/规则（自动修复执行基线）。
6) `docs/handoff_chatgptrest_history.md`：历史问题与修复记录（按问题→代码路径→提交/测试）。
7) `docs/ops/2026-03-25_worktree_policy_v1.md`：worktree 分类与禁行动作。
8) `docs/ops/2026-03-25_artifact_retention_policy_v1.md`：artifact / `.run/` 保留策略与禁行动作。
9) `docs/dev_log/artifacts/INDEX_v1.md`：evidence plane 索引（只用于找 validation/review 证据，不当 current guidance）。
10) `docs/ops_rollout_plan_p0p1p2_safe_enable_20251228.md`：哪些能力“已合入但默认不启用”，以及启用策略。
11) `docs/chatgpt_web_ui_reference.md`：ChatGPT Web UI 快照参考（本地自动生成，默认不入 git；指向 `artifacts/ui_snapshots/`）。
12) `skills-src/chatgptrest-call/SKILL.md`：给 Codex/agent 的统一调用入口（`chatgptrestctl` wrapper）。
13) `artifacts/monitor/open_issue_list/latest.md`：当前 open / in_progress issue 视图（自动导出）。
14) `artifacts/monitor/open_issue_list/history_tail.md`：最近 issue 生命周期演进快照（自动导出）。

## “追溯到之前的开发内容”怎么做（推荐工作流）

### 1) 从文档定位到代码路径/提交

- 先在 `docs/handoff_chatgptrest_history.md` 里按症状关键词搜（例如 `Error in message stream` / `idempotency` / `conversation_export` / `Answer now`）。
- 记录下对应条目的 `Files:`、`Tests:`、（如果有）提交号/PR。

### 2) 用 git 把“文档条目 → 具体改动”对齐

常用命令：

```bash
# 查看某个里程碑提交做了什么（含变更文件列表）
git show <commit>

# 只看某个热点文件的演进
git log --oneline -- chatgptrest/worker/worker.py

# 精确到行：是谁/何时引入的
git blame chatgptrest/worker/worker.py
```

### 3) 用作业产物/DB 还原一次真实故障

- 产物：`artifacts/jobs/<job_id>/`（`request.json`、`events.jsonl`、`result.json`、`answer.md`、`conversation.json`…）
- DB：`state/jobdb.sqlite3`（`jobs` / `job_events` / `idempotency` / `rate_limits`）
- Driver 持久状态：`state/driver/`（blocked/cooldown/idempotency 等）

## 文档分类导航

### 对外契约 / 使用方式

- `docs/contract_v1.md`

### 运维 / 排障 / 安全启用策略

- `docs/ops/2026-03-25_agent_maintainer_entry_v1.md`（正式 maintainer entry）
- `docs/ops/2026-03-25_document_plane_guide_v1.md`（当前 guidance 与 dev_log 档案的读取规则）
- `docs/ops/2026-03-25_worktree_policy_v1.md`（worktree 分类与禁行动作）
- `docs/ops/2026-03-25_artifact_retention_policy_v1.md`（artifact / `.run/` 保留策略）
- `docs/ops/2026-03-25_monitor_artifact_budget_retention_proposal_v1.md`（`artifacts/monitor/*` 的 budget / tier / guard 提案）
- `docs/ops/2026-03-25_maint_daemon_jsonl_cleanup_execution_plan_v1.md`（`maint_daemon/maint_*.jsonl` 的 dry-run / approval / apply 执行方案）
- `docs/ops/2026-03-29_skill_market_source_intake_guide_v1.md`（skill market allowlist / quarantine intake / operator CLI）
- `docs/dev_log/2026-03-30_chatgptrest_mcp_runtime_contract_hardening_walkthrough_v1.md`（ChatgptREST MCP/runtime 可用性硬化：identity 收敛、research completion contract、attachment false-positive 修复）
- `docs/ops/2026-03-30_research_completion_consumer_inventory_v1.md`（research completion consumer 分级清单；P0/P1/P2 迁移顺序）
- `docs/dev_log/2026-03-30_completion_contract_phase1_consumer_migration_walkthrough_v1.md`（Phase 1 consumer-first 收敛：helper、P0 迁移、runtime-contract health）
- `docs/ops/2026-03-30_research_completion_consumer_inventory_v2.md`（research completion consumer v2；P1 internal consumer 已迁移）
- `docs/dev_log/2026-03-30_completion_contract_phase2_internal_consumer_alignment_walkthrough_v1.md`（Phase 2 internal consumer 对齐：verify/extractor/qa/smoke 改为读 completion contract）
- `docs/ops/2026-03-30_research_completion_consumer_inventory_v3.md`（research completion consumer v3；P2 monitoring / issues / soak / evidence 已对齐 canonical answer）
- `docs/dev_log/2026-03-30_completion_contract_phase3_canonical_answer_and_monitor_alignment_walkthrough_v1.md`（Phase 3 canonical answer hardening：issue/maint_daemon/behavior issue/deliverable aggregator 对齐）
- `docs/runbook.md`
- `docs/ops_rollout_plan_p0p1p2_safe_enable_20251228.md`
- `docs/maint_daemon.md`（常驻维护/证据包/可观测性设计）
- `docs/repair_agent_playbook.md`（Repair Agent 自动修复动作规范）
- `docs/dev_log/artifacts/INDEX_v1.md`（evidence plane 索引）

### 历史开发与问题修复（最适合“追溯”）

- `docs/handoff_chatgptrest_history.md`（主时间线：问题 → 代码 → 测试/证据）
- `docs/handoff_gemini_drive_attachments_20251230.md`（Gemini Drive 附件：设计、证据、关键代码点）
- `artifacts/monitor/open_issue_list/history_tail.md`（最近一段 issue 状态变化的自动快照）

### 当前 open issue / 演进投影（自动导出）

- `artifacts/monitor/open_issue_list/latest.json`
- `artifacts/monitor/open_issue_list/latest.md`
- `artifacts/monitor/open_issue_list/history_tail.json`
- `artifacts/monitor/open_issue_list/history_tail.md`

### Review 落盘（按提交/PR）

- `docs/reviews/`（Pro/Gemini 的 code review 输出、覆盖度审查、guardrails 评审等；文件名通常包含日期与 commit/PR 线索）

### UI/风控/反检测资料

- `docs/chatgpt_web_ui_reference.md`（本地自动生成；gitignore）
- `docs/检测风险预防.md`（本地备忘：可能未纳入 git）
- `docs/深度伪装geminipro20260103.md`（本地备忘：可能未纳入 git）

### 其它杂项备忘

- `docs/反向 SSH 隧道.md`（本地备忘：可能未纳入 git）
