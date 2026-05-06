# ChatgptREST Ops Runbook

This is an operator-focused checklist for keeping the ChatgptREST stack healthy and for cutover from direct `chatgptMCP` calls.

## Stack & Ports (default)

- Chrome (GUI, logged-in; CDP): `http://127.0.0.1:9222` (or `http://127.0.0.1:${CHROME_DEBUG_PORT}`)
- Qwen Chrome (GUI, logged-in; dedicated CDP, no proxy): `http://127.0.0.1:9335` (optional; disabled in the default single-user baseline unless explicitly enabled)
- ChatgptREST driver MCP server (internal; StreamableHTTP): `http://127.0.0.1:18701/mcp`
- chatgptMCP (external MCP server; legacy fallback): `http://127.0.0.1:<port>/mcp`
  - 注意：**外部 chatgptMCP 不能和内部 driver 共享同一个端口同时运行**。
  - 想切到外部 chatgptMCP：要么停掉内部 driver，要么把其中一个改端口。
- ChatgptREST (REST API): `http://127.0.0.1:18711`
- ChatgptREST public MCP adapter (automation-kernel-v1 shared surface): `http://127.0.0.1:18712/mcp`
- ChatgptREST admin MCP adapter (optional, internal only): `http://127.0.0.1:18715/mcp`
- ChatgptREST Dashboard Control Plane (read-only operator UI): `http://127.0.0.1:8787`

Quick health endpoints:
- `GET /healthz`
- `GET /health/runtime-contract`
- `GET /v1/health/runtime-contract`
- `GET /v1/ops/status` (includes `build.git_sha` + `build.git_dirty` for version drift checks, plus `active_incident_families`, `active_open_issues`, `active_issue_families`, `stuck_wait_jobs`, and `ui_canary`-derived attention hints)
- Dashboard app: `GET http://127.0.0.1:8787/healthz`

Periodic health probe:

```bash
cd /vol1/1000/projects/ChatgptREST
PYTHONPATH=. ./.venv/bin/python ops/health_probe.py --fix --json
systemctl --user enable --now chatgptrest-health-probe.timer chatgptrest-ui-canary.timer
systemctl --user list-timers chatgptrest-health-probe.timer chatgptrest-ui-canary.timer --all --no-pager
```

Notes:

- `ops/health_probe.py` writes the latest snapshot to `artifacts/monitor/health_probe/latest.json`.
- OpenMind KB search DB resolution honors `OPENMIND_KB_SEARCH_DB`, then `OPENMIND_KB_PATH`; memory resolution honors `OPENMIND_MEMORY_DB`.
- If those env vars are unset and the process runs under an isolated Codex `HOME`, the probe falls back to the login user's passwd home before reporting missing OpenMind DBs. This avoids false `kb_fts` / `memory` failures when live DBs are under `/home/yuanhaizhou/.openmind`.
- `needs_followup` / `blocked` / `cooldown` stale jobs are reported as attention candidates. Prefer the backlog janitor or an explicit operator action over hand-editing job rows.

Host memory / earlyoom first response:

```bash
free -h
ps -ef | rg '[e]arlyoom' || true
sudo -n tail -40 /var/log/earlyoom/earlyoom_kills_$(date +%F).log
systemctl --user show chatgptrest-api.service chatgptrest-mcp.service chatgptrest-dashboard.service \
  chatgptrest-driver.service chatgptrest-worker-send.service chatgptrest-worker-wait.service \
  chatgptrest-chrome.service -p Id -p ActiveState -p MainPID -p NRestarts --no-pager
PYTHONPATH=. ./.venv/bin/python ops/health_probe.py --fix --json | jq '.checks[] | select(.check=="earlyoom_recent_kills")'
```

Notes:

- Treat repeated Uvicorn `Shutting down`, Chrome CDP drops, Playwright `TargetClosedError`, and dashboard `Connection refused` as possible earlyoom symptoms before attributing them to ChatGPT Web, Cloudflare, or 429.
- Current host policy is documented in `/etc/default/earlyoom`; after the 2026-04-28 incident it uses `-m 3,2` and avoids ChatgptREST / `chrome-profile` / GitNexus processes.
- `ops/health_probe.py` has an `earlyoom_recent_kills` check. It reads `/var/log/earlyoom/earlyoom_kills_<date>.log` and reports kills in the last 15 minutes as health attention.
- The current host grants `yuanhaizhou` traverse/read ACLs for the earlyoom log path so user-level health probes can read the sanitized postkill log without sudo.
- If logrotate/new-date ACLs drift, `ops/health_probe.py` falls back to `sudo -n tail -c` for the earlyoom log. A permission error should still be treated as an ops signal, but it should not hide the rest of the health snapshot.
- The tracked `chatgptrest-health-probe.service` uses `TimeoutStartSec=180`; do not reduce it back to 60 seconds, because low-memory periods can delay oneshot startup enough to create false timer failures.
- If ChatgptREST processes are already running with high `oom_score_adj`, a root operator can temporarily lower the current service cgroup processes while a durable slice-level fix is evaluated.

Runtime contract health:

- `GET /health/runtime-contract` and `GET /v1/health/runtime-contract` are the machine-readable checks for:
  - public MCP service identity
  - allowlist enforcement / allowlisted state
  - runtime contract drift
  - current `completion_contract` / MCP surface versions
- When debugging “MCP can start but first request fails” or allowlist/env drift, prefer these endpoints before running a live ask.

Answer readiness / follow-up guard checks:

- `GET /v1/jobs/{job_id}/answer` is gated by canonical readiness, not raw `status=completed`. If it returns 409, inspect `detail.answer_state`, `detail.canonical_ready`, and `detail.authoritative_answer_path`; then verify the artifact exists under `CHATGPTREST_ARTIFACTS_DIR`.
- For concise completed web answers, the route reads the answer artifact from the configured artifacts directory and trusts `classify_answer_quality(...)=final`; only genuinely suspicious short answers remain provisional.
- Follow-up jobs that reuse a conversation must not finalize from a DOM answer that matches an assistant turn before the current matched user turn. If export has the user turn but only a partial/in-progress reply, this is a wait/downgrade condition, not a completed answer.
- Rescue follow-up short-circuiting is only for parent-completion races. If it triggers, the child job copies the parent answer artifact and records `rescue_followup_shortcircuited` as the finality event.

MCP status check:

- `automation_job_status` is the public MCP status tool for coding agents. It must stay equivalent to canonical job-kernel `chatgptrest_job_get`; if it fails with missing legacy helper names, the public MCP adapter has drifted from `automation-kernel-v1`.

Fresh Codex client entry:
- `docs/codex_fresh_client_quickstart.md` — 给新启动、没有维护背景的 Codex 客户端的最小入口说明

Machine-first repo cognition entry:
- `./.venv/bin/python scripts/chatgptrest_bootstrap.py --task "<task>" --runtime quick`
  - 输出 `bootstrap-v1` JSON，默认给 coding agent 做 cold-start 快照
  - 至少先看：`detected_planes`、`runtime_snapshot`、`task_relevant_symbols`、`change_obligation_validation`、`surface_policy`
- `./.venv/bin/python scripts/check_doc_obligations.py --diff HEAD`
  - 检查当前改动集的 doc obligations、baseline tests、缺失 doc update
- `./.venv/bin/python scripts/chatgptrest_closeout.py --agent codex --status completed --summary "..."`
  - 先跑 doc obligation gate，再代理到 shared closeout script
- `chatgptrestctl` 也暴露了同一套入口：
  - `chatgptrestctl repo bootstrap --task "..."`
  - `chatgptrestctl repo doc-obligations --diff HEAD`
  - `chatgptrestctl repo closeout --agent codex --status completed --summary "..."`

## Planning Review Maintenance Harness

目标：

- 对 canonical EvoMap DB 做 promotion inventory 盘点
- 对 planning review reviewed promotion 机制做 refresh-only maintenance
- 在需要 reviewer JSON 时导出前后态证据包，而不是直接改 promotion 算法

常用命令：

```bash
cd /vol1/1000/projects/ChatgptREST

# 只做 promotion inventory 盘点
python3 ops/report_evomap_promotion_inventory.py \
  --db data/evomap_knowledge.db \
  --output-dir artifacts/monitor/evomap/promotion_inventory

# 跑一次 refresh-only maintenance harness（默认安全模式）
python3 ops/run_planning_review_maintenance.py

# 带 reviewer JSON + copy apply 的验证模式
python3 ops/run_planning_review_maintenance.py \
  --review-json /abs/path/reviewer.json \
  --apply-db-copy artifacts/monitor/planning_review_maintenance/validation/evomap_copy.db
```

systemd：

```bash
cd /vol1/1000/projects/ChatgptREST
bash ops/systemd/install_user_units.sh
systemctl --user enable --now chatgptrest-planning-review-maintenance.timer
systemctl --user status chatgptrest-planning-review-maintenance.timer --no-pager
```

说明：

- `chatgptrest-planning-review-maintenance.timer` 默认只跑 refresh-only harness，不做 live apply
- `ops/run_planning_review_maintenance.py` 会输出：
  - `pre_inventory/`

## Wake-Up Packet Harness

目标：

- 对当前 project-scoped substrate truth 编译一个真实 `wake_up_packet`
- 验证 authority anchor / active memory / retrieved knowledge / runtime handoff 四层是否都可追溯
- 为 OpenClaw / public automation lane 提供当前 packet contract 的 acceptance artifact

常用命令：

```bash
cd /vol1/1000/projects/ChatgptREST

python3 ops/run_wakeup_packet_harness.py \
  --query "调研行星滚柱丝杠产业链关键玩家和国产替代进展" \
  --project-id prs \
  --trace-id trace-phase2-wakeup-prs \
  --account-id acct-phase2 \
  --agent-id advisor \
  --role-id planning \
  --thread-id thread-phase2 \
  --planning-task-id planning-task-phase2-prs \
  --planning-task-type research_decision \
  --planning-status in_progress \
  --planning-next-step "freeze the next research decision memo" \
  --planning-pending-action "review promoted atoms" \
  --planning-pending-action "align authority anchor"
```

说明：

- contract doc：`docs/contracts/2026-04-09_wakeup_packet_contract_v1.md`
- packet-quality contract：`docs/contracts/2026-04-09_wakeup_packet_quality_contract_v1.md`
- canonical runtime doc：`docs/integrations/2026-04-09_openclaw_cognitive_substrate_runtime_contract_v3.md`
- harness 默认输出到 `artifacts/monitor/wakeup_packet_harness/<stamp>/`
- packet markdown 现在会附带 `Packet quality receipt`
- 真实 packet 若出现 `degraded=true`，不要把它当 harness 失败；先看 `degraded_sources`
- 当前 compiler 是 fail-open 设计：packet 编译失败不应阻断 `/v3/agent/turn` 主链

### Batch Packet Quality Harness

目标：

- 对 canary projects 批量编译真实 packet
- 产出 `auto_usefulness_score`、`comparison_digest` 和 adjusted degraded ratio
- 明确区分 raw degraded 与已声明外部 gap 之后的 gating 结果

常用命令：

```bash
cd /vol1/1000/projects/ChatgptREST

./.venv/bin/python ops/run_wakeup_packet_batch_harness.py \
  --output-root artifacts/monitor/wakeup_packet_batch_harness \
  --strict
```

说明：

- 默认 canary cohort 目前是 `shortmobility` 和 `prs`
- `--strict` 会按 packet-quality contract 的默认阈值检查：
  - success rate `>=0.95`
  - adjusted degraded ratio `<=0.20`
  - median auto usefulness score `>=4.0`
- raw `degraded_ratio` 仍会原样保留在 summary 里
- adjusted degraded ratio 只会排除已声明外部 gap：
  - `personal_graph_empty`
  - `memory_identity_missing`
  - `captured_memory_identity_missing`
  - `work_memory_identity_partial`

## Project Context Harness

目标：

- 对 live `_project_context.md` authority anchors 做 schema / freshness / body-section lint
- 明确哪些 anchor 只是可解析，哪些已经达到 production-grade authority-anchor 要求
- 为 canary project roster 产出可归档的 governance evidence

常用命令：

```bash
cd /vol1/1000/projects/ChatgptREST

python3 ops/run_project_context_harness.py \
  --project-id shortmobility \
  --project-id prs \
  --output-dir artifacts/monitor/project_context_harness/$(date -u +%Y%m%dT%H%M%SZ) \
  --strict
```

说明：

- contract doc：`docs/contracts/2026-04-09_project_authority_anchor_contract_v1.md`
- harness 默认检查：
  - required frontmatter fields
  - required body sections
  - anchor freshness
  - authority-doc existence / staleness
- `--strict` 时，只要出现 lint fail 或请求的 `project_id` 找不到，就返回非零退出码
- `updated` 仍可保留，但 production-grade freshness 以 `last_reviewed_at` 为准

## EvoMap Recall Production Benchmark

目标：

- 把 recall / entity recall / project-scope ranking 从“感觉变好”变成 frozen baseline 对比
- 明确低置信度时应该 `answer / clarify / abstain` 中的哪一种
- 把 promotion throughput 的 recent-window blank reason 指标纳入同一阶段证据包

常用命令：

```bash
cd /vol1/1000/projects/ChatgptREST

./.venv/bin/python ops/run_evomap_recall_production_benchmark.py \
  --output-root artifacts/monitor/evomap_recall_production_benchmark

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
./.venv/bin/python ops/report_evomap_promotion_inventory.py \
  --output-dir artifacts/monitor/evomap_promotion_inventory/$STAMP \
  --stamp $STAMP \
  --recent-window-days 7
```

说明：

- benchmark case set：`ops/data/evomap_recall_benchmark_v1.json`
- canonical contract：`docs/contracts/2026-04-09_evomap_recall_production_benchmark_contract_v1.md`

## Crystallized Learning Governance

目标：

- 把 interaction-learning crystal 从“存在于 packet 里”提升为“可治理、可报告、可 shadow 观察”
- 明确 active crystal / superseded candidate / denied preference 的数量与风险姿态
- 给后续 canary 扩大使用前的 shadow 证据留档

常用命令：

```bash
cd /vol1/1000/projects/ChatgptREST

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
python3 ops/report_crystallized_learning_governance.py \
  --output-dir artifacts/monitor/crystallized_learning_governance/live/$STAMP
```

说明：

- canonical contracts：
  - `docs/contracts/2026-04-09_crystallized_learning_governance_contract_v1.md`
  - `docs/contracts/2026-04-09_wakeup_packet_contract_v2.md`
- `wakeup_packet_receipt` 现在会透出：
  - `has_crystallized_learning`
  - `crystallized_learning.projection_mode`
  - `crystallized_learning.stable_preference_keys`
  - `crystallized_learning.superseded_count`
- 当前 runtime posture 是 `shadow`
- live memory 可能合法地返回 `0` active crystals；这不算失败，只表示当前 host 还没有进入 audited user-correction replay 阶段
- shadow fixture evidence 当前已冻结在：
  - `artifacts/monitor/crystallized_learning_governance/fixture/20260409T054241Z/`
- current PR-3 low-confidence posture:
  - `answer`: top-1 和 top-3 都够强
  - `clarify`: 有部分相关性但仍不足
  - `abstain`: top-1 明显不贴题且 top-3 也太薄
- promotion inventory 现在会同时输出：
  - historical blank reason total
  - `recent_blank_promotion_reason_ratio`

## OpenMind Production Regression And Rollback

目标：

- 把当前支持的 backend 主链收成一套可重复跑的 release regression bundle
- 覆盖 core runtime、public MCP、OpenClaw stack rebuild 等仍受支持的生产面
- 不再把 retired advisor/planning control-plane 当成 regression 目标

常用命令：

```bash
cd /vol1/1000/projects/ChatgptREST

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
python3 ops/run_openmind_production_regression.py \
  --output-dir artifacts/monitor/openmind_production_regression/$STAMP
```

Rollback env:

```bash
export CHATGPTREST_ENABLE_CRYSTALLIZED_LEARNING_PACKET_PROJECTION=0
export CHATGPTREST_ENABLE_WAKEUP_PACKET_PROJECTION=0
```

说明：

- canonical release-flag doc：
  - `docs/contracts/2026-04-09_openmind_release_flag_matrix_v1.md`
- bundle summary 会同时输出 feature flag matrix 和每个 regression bundle 的 pass/fail
- 推荐 rollback 顺序：
  1. 先关 `CHATGPTREST_ENABLE_CRYSTALLIZED_LEARNING_PACKET_PROJECTION`
  2. 再视情况关 `CHATGPTREST_ENABLE_WAKEUP_PACKET_PROJECTION`
  3. 重启相关 ChatgptREST 服务
  4. 用 `wake_up_packet_receipt.feature_flags` 验证实际生效状态

## OpenMind Production Health

目标：

- 用一条命令回答 packet / recall / promotion / crystal 四个核心健康问题
- 把 PR-2 / PR-3 / PR-4 的单项证据面拉成 operator 可读的生产健康摘要
- 给 PR-7 提供真实可执行的 first-response path

常用命令：

```bash
cd /vol1/1000/projects/ChatgptREST

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
python3 ops/report_openmind_production_health.py \
  --output-root artifacts/monitor/openmind_production_health
```

说明：

- canonical metric contract：
  - `docs/contracts/2026-04-09_openmind_production_health_metric_contract_v1.md`
- rollup 会刷新并汇总 4 条证据面：
  - wake-up packet batch harness
  - EvoMap recall production benchmark
  - EvoMap promotion inventory
  - crystallized-learning governance report
- 输出的 Markdown report 必须能直接回答：
  - 当前 packet 有没有在 canary 上退化
  - recall 是否相对 frozen baseline 漂移
  - promotion 是否被 blank reason / 无 active atom source 卡住
  - crystal 是否存在 churn / denied preference / 高风险样本

Packet degradation first response：

1. 先看 rollup 里的 `domains.packet` 和 `operator_questions.packet`
2. 打开 packet sub-artifacts，确认具体 degraded case 和 `degraded_sources`
3. 如需临时止血，再回到 `OpenMind Production Regression And Rollback` 章节按顺序关闭 crystal / packet projection

Recall drift first response：

1. 先看 `domains.recall.delta.top3_hit_rate_relative_gain`
2. 检查 `attention_cases` 是否出现 project mis-association / clarify / abstain 上升
3. 再回看 recall benchmark report，而不是直接改 runtime ranking

Promotion blockage first response：

1. 看 `domains.promotion.likely_blockers.recent_blank_promotion_reason_ratio`
2. 检查 `sources_without_active_atoms` / `projects_without_active_atoms`
3. 检查 `domains.promotion.critical_rollout`：
   - `buckets_without_servable_atoms`
   - `buckets_without_active_atoms`
   - `bounded_to_noncritical_only`
4. 若只剩 `planning_controlled` 缺 active，可运行：

```bash
./.venv/bin/python ops/run_planning_controlled_active_promotion.py --live
```

5. `bounded_to_noncritical_only=true` 表示当前 warn 已被收敛到非关键 backlog，可继续 canary watch；只有 critical buckets 缺 `servable` 或缺 `active` 时才应视为 rollout blocker
6. 只在 blocker 证据清楚后再考虑 bulk promotion 或 archive 动作

Crystal conflict first response：

1. 看 `domains.crystal.false_positive_rate`
2. 看 `denied_preference_occurrences` 和 `high_risk_samples`
3. 如果这里有异常，不要先改 support semantics；先维持 `shadow` posture 并检查 governance 样本

## OpenMind Canary Rollout

目标：

- 冻结 OpenMind 生产 canary cohort
- 用最新的 production health + production regression 结果自动生成 rollout decision
- 明确区分：
  - `canary-ready`
  - `watch-window active`
  - `go-live ready`

常用命令：

```bash
cd /vol1/1000/projects/ChatgptREST

python3 ops/report_openmind_canary_scorecard.py \
  --output-root artifacts/monitor/openmind_canary_scorecard
```

说明：

- canonical rollout contract：
  - `docs/contracts/2026-04-09_openmind_canary_rollout_contract_v1.md`
- canonical graduation contract：
  - `docs/contracts/2026-04-09_openmind_production_graduation_contract_v1.md`
- frozen cohort file：
  - `ops/data/openmind_canary_cohort_v1.json`
- scorecard 会消费：
  - latest `openmind_production_health`
  - latest `openmind_production_regression`
- decision 含义：
  - `launch_canary_watch`：允许启动或继续 7 天 watch window，但不等于 full go-live
  - `go_live`：watch window 已经结束且 release gates 仍满足
  - `hold`：存在 fail domain、regression 失败，或出现未批准的 warning domain

### Watch-window ledger

目标：

- 把 canary launch 从一次性 scorecard 变成可审计的时间序列
- 每天固化一条 watch-window ledger，记录 scorecard、health、regression 和 domain transition

Daily watch automation:

```bash
./.venv/bin/python ops/run_openmind_daily_watch.py \
  --output-root artifacts/monitor/openmind_daily_watch
```

systemd units:

- `ops/systemd/chatgptrest-openmind-daily-watch.service`
- `ops/systemd/chatgptrest-openmind-daily-watch.timer`

Enable:

```bash
systemctl --user daemon-reload
systemctl --user enable --now chatgptrest-openmind-daily-watch.timer
systemctl --user --no-pager status chatgptrest-openmind-daily-watch.timer chatgptrest-openmind-daily-watch.service
```
- 给最终 graduation gate 提供直接可用的日级证据

常用命令：

```bash
cd /vol1/1000/projects/ChatgptREST

python3 ops/report_openmind_watch_window_ledger.py \
  --output-root artifacts/monitor/openmind_watch_window_ledger
```

说明：

- ledger 是 `watch-window active` 的日级证据，不是新的 release gate
- canonical fields：
  - `decision`
  - `launch_posture`
  - `rollout_posture`
  - `watch_day_index`
  - `domain_transitions`
- operator 每天至少确认一次：
  - regression 仍是绿
  - 没有新 fail domain
  - 没有新 unapproved warn domain
  - 若 `promotion=warn`，仍然是已批准且可解释的 backlog warning

### Graduation gate

目标：

- 在 watch window 结束时，把最新 scorecard + ledger + health + regression 收成一个单一毕业决策

## Retired Feishu / Advisor Control-Plane Canaries

The former Feishu ingress canary and direct assistant-first Feishu proxy targeted the retired advisor/planning control plane. They are no longer maintained. Use `ops/health_probe.py`, `ops/run_openmind_production_regression.py`, dashboard health, and public MCP smoke tests instead.

## Wait-phase answer stalls (`WaitNoProgressTimeout`)

ChatGPT Pro / thinking lanes can surface real progress **before** a final answer is ready:

- the wait executor may return a growing partial answer in `result.answer`
- the conversation export may expose active finalization metadata (`pro_progress`, `is_finalizing`)

The worker now records these as explicit progress signals before evaluating the no-progress timeout. This prevents a real in-flight answer from being mislabeled as a stall just because the latest poll is still `status=in_progress`.

When auditing a “job has thread URL but no final answer yet” incident, check the event stream in this order:

1. `wait_partial_answer_progressed`
2. `wait_active_finalization_progressed`
3. `wait_active_finalization_observed`
4. `wait_no_progress_timeout`

Interpretation:

- `*_progressed` means the current poll advanced the answer or finalization state and should reset the stall anchor.
- `wait_partial_answer_echo_observed` means the wait layer saw text that overlaps the current user prompt. It is diagnostic evidence only and must not reset the no-progress anchor.
- `wait_active_finalization_observed` without a matching `*_progressed` means the worker saw the same in-progress tool/finalization state again, so the no-progress timer is still allowed to expire.
- For Pro / thinking presets, a live active-finalization export (`active_count` / `in_progress_count` > 0) uses a separate grace window before `WaitNoProgressTimeout`, because ChatGPT can keep internal tool/finalization work stable for much longer than the normal short-answer stall threshold before publishing the final text.
- Active-finalization is scoped to the latest user turn in the export. A stale `tool` message from an earlier turn must not keep a later follow-up alive forever.
- `wait_partial_answer_progressed` is only real progress when the stored preview head or answer length advances. Re-reading the same prompt echo / DOM text must not refresh the no-progress anchor.
- Deep Research may export a short visible status card such as `Update ... Researching` while the report is still running. Treat this as pending research, not a final answer. The worker records `deep_research_pending_from_export` and `wait_deep_research_pending_observed`, releases the wait job, and does not consume normal browser retry budget for that poll.
- `wait_no_progress_timeout` remains the fail-closed path when the answer text and finalization progress both stop moving for too long.
- For Pro / research jobs with `min_chars`, a backend-complete assistant answer under the threshold is not waitable progress. If export metadata says the selected assistant is complete and has a final finish type, treat the short answer as a quality/follow-up condition instead of repeatedly re-exporting until `WebRetryBudgetExceeded`.
- If a Pro / thinking answer is short and has no usable `Thought for ...` observation, the executor may trigger same-thread regenerate. A regenerate result of `in_progress` is real progress and should move the job into wait; a failed or unavailable regenerate must fail closed as `needs_followup`, not preserve the original short answer as `completed`.
- If a completed follow-up looks provisional in `/v1/jobs/{job_id}` or public MCP even though `artifacts/jobs/<job_id>/result.json` records `completion_contract.answer_state=final`, inspect the event order. A later `completion_contract_recorded(answer_state=final)` must override an earlier `completion_guard_downgraded` diagnostic event in the public projection.
- If a human/operator writes only a short continuation nudge in the same ChatGPT conversation, such as `please continue` or `卡住了，请继续`, the export reconciler may continue scanning the later assistant answer instead of treating the thread as contaminated. This is deliberately narrow: substantive second user turns that change scope, switch to Deep Research, add another project, or add new requirements still fail closed as `ConversationThreadContaminated`.

Knobs:

- `CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS` — normal non-Deep-Research wait stall threshold.
- `CHATGPTREST_WAIT_ACTIVE_FINALIZATION_NO_PROGRESS_TIMEOUT_SECONDS` — Pro/thinking active-finalization stall threshold; default `2700` seconds.
- `CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS` — Deep Research stall threshold.
- `CHATGPTREST_DEEP_RESEARCH_PENDING_RETRY_AFTER_SECONDS` — retry spacing for visible Deep Research pending/status-card output; default `600` seconds, clamped to `60..3600`.

## ChatGPT Deep Research send timeout

The global send cap protects the queue from long blocking sends, but ChatGPT Deep Research can legitimately spend longer than a normal ask while uploading attachments and enabling the Deep Research tool before `prompt_sent_at`. If `deep_research=true` and the caller does not explicitly pass `send_timeout_seconds`, ChatgptREST applies `CHATGPTREST_CHATGPT_DEEP_RESEARCH_SEND_TIMEOUT_SECONDS` as a send-timeout floor (default `240` seconds). This keeps live systems that still configure `CHATGPTREST_DEFAULT_SEND_TIMEOUT_SECONDS=60` from cutting off Deep Research before the prompt is sent.

If the job still exhausts send retries before a conversation URL exists, inspect:

- `mcp_attachment_staged` for file count and total staged bytes
- `browser_retry_scheduled` for retry cadence and provider retry budget
- `web_send_retry_exhausted` for the safe next action and suggested retry params

Do not immediately open parallel ChatGPT Web jobs. Retry the same request only after confirming no prompt was sent, preferably with `send_timeout_seconds >= 240` or a slimmer attachment set.

## Conversation export backend 429

ChatGPT conversation export first tries the logged-in backend API and may fall back to DOM messages. A backend `HTTP 429` with successful DOM fallback is still a degraded export, not a clean success. The worker writes:

- `conversation_export_backend_rate_limited`
- `conversation_export_skipped` with `reason=global_429_cooldown` while the shared cooldown is active
- `conversation_export_backend_skipped` when a force export is still needed during the shared cooldown and the worker deliberately calls the driver with `backend_mode=dom_only`

Cooldown knobs:

- `CHATGPTREST_CONVERSATION_EXPORT_429_COOLDOWN_SECONDS` defaults to `600`
- `CHATGPTREST_CONVERSATION_EXPORT_429_COOLDOWN_MAX_SECONDS` defaults to `3600`
- `CHATGPTREST_CONVERSATION_EXPORT_DOM_DURING_429_COOLDOWN` defaults to `true`

If these events appear during Pro review waits, do not start additional same-conversation export polling jobs. Let the existing wait job continue. While the shared backend cooldown is active, non-force exports are skipped; force exports use DOM-only export so the evidence chain can still be reconciled without probing the backend API again.

## ChatGPT frontend 429 modal

The browser-visible ChatGPT modal `modal-conversation-history-rate-limit` is stronger evidence than a backend export `HTTP 429`: it means the shared ChatGPT Web session is already being rate-limited. The driver now records `blocked_state.reason=frontend_rate_limit`, returns `ChatGPTFrontendRateLimit`, and uses a stop-the-world blocked state instead of a retryable send cooldown.

Operational response:

- Stop or pause send/wait workers and any timer that can submit ChatGPT Web work before collecting more evidence.
- Do not run `clear_blocked`, `self_check`, `capture_ui`, regenerate, refresh, export polling that requires UI, or new same-session follow-ups until the blocked-state cooldown expires.
- Use `chatgpt_web_blocked_status` or `state/driver/chatgpt_blocked_state.json` to confirm `frontend_rate_limit`.
- Treat this as a human/browser-session protection event, not as a normal retryable transient.

Implementation guardrails:

- Driver-side blocked enforcement disallows all ChatGPT UI actions while `blocked_state.reason=frontend_rate_limit`; only non-UI status probes should run.
- If any ChatGPT UI tool sees the modal in a Playwright exception path, it must return `status=blocked` + `ChatGPTFrontendRateLimit`, not `cooldown`, `in_progress`, or generic `error`.
- `repair.check` and `repair.autofix` must skip ChatGPT `self_check`, `capture_ui`, `refresh`, `regenerate`, and `clear_blocked` while the frontend rate-limit blocked state is active.
- `/v1/jobs` rejects new `chatgpt_web.*` job submissions with HTTP 429 while the ChatGPT frontend submit gate is active. This includes direct low-level export/extract jobs such as `chatgpt_web.conversation_export`, not only `chatgpt_web.ask`. Idempotent replays of an already-created job still return the existing job view; Gemini/Qwen/provider-neutral jobs are not blocked by this ChatGPT-specific gate.
- The same submit gate also recognizes `blocked_state.reason=manual_pro_session`. This is the canonical human ChatGPT Pro exclusive-use lock; do not fake this as a provider 429.

Cooldown knob:

- `CHATGPT_FRONTEND_RATE_LIMIT_COOLDOWN_SECONDS` defaults to at least `3600`.
- `CHATGPTREST_BLOCK_CHATGPT_SUBMIT_ON_FRONTEND_RATE_LIMIT` defaults to `true`.
- `CHATGPTREST_CHATGPT_FRONTEND_BLOCK_STATE_FILE` optionally points the API submit gate at `state/driver/chatgpt_blocked_state.json`; when unset, the API checks the repo default `state/driver/chatgpt_blocked_state.json` and the DB cooldown key `chatgpt_web_frontend_rate_limit`.

## Manual ChatGPT conversation harvest

Human-created ChatGPT Web conversations can be exported through the public MCP
automation surface without sending a new prompt:

- `automation_conversation_fetch(conversation_url=...)` creates a read-only `chatgpt_web.conversation_export` job, defaults to `backend_mode=dom_only`, and starts background waiting.
- `automation_result(job_id=...)` returns the rendered full-conversation markdown once the export job completes.
- `automation_conversation_get(job_id=...)` returns the raw conversation export in chunks.
- `automation_conversation_find(conversation_url=...)` finds local jobs already associated with that ChatGPT conversation URL or id.

For local browser discovery, run:

```bash
PYTHONPATH=. ./.venv/bin/python ops/manual_chatgpt_conversation_harvest.py --once
PYTHONPATH=. ./.venv/bin/python ops/manual_chatgpt_conversation_harvest.py --once --submit
```

To enable periodic scanning, install the opt-in timer:

```bash
ln -sf /vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-manual-conversation-harvest.service ~/.config/systemd/user/chatgptrest-manual-conversation-harvest.service
ln -sf /vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-manual-conversation-harvest.timer ~/.config/systemd/user/chatgptrest-manual-conversation-harvest.timer
systemctl --user daemon-reload
systemctl --user enable --now chatgptrest-manual-conversation-harvest.timer
```

Safety contract:

- The scanner only reads Chrome CDP `/json/list` and creates conversation-export jobs; it never sends prompts.
- Manual Pro holds and frontend 429 holds still block `chatgpt_web.*` job creation; do not clear those holds just to harvest.
- DOM-only export is the default to avoid backend conversation API 429 amplification.
- When the driver reuses a human-owned ChatGPT conversation tab, it does not close that tab after export and does not bring it to the foreground unless `CHATGPTREST_CDP_BRING_EXISTING_PAGE_TO_FRONT=1` is explicitly set for debugging.

## Manual ChatGPT Pro watch guard

When a human is using ChatGPT Pro in the same browser profile, start the manual Pro watch guard before doing other work:

```bash
systemctl --user start chatgptrest-manual-pro-watch-guard.service
```

The guard is fail-closed and intentionally ChatGPT-specific:

- writes `state/driver/chatgpt_blocked_state.json` with `reason=manual_pro_session`;
- writes a durable DB-backed ChatGPT Web hold with `reason=manual_pro_session`;
- sets DB pause `mode=all`, `reason=auto_blocked:manual_pro_watch_guard`, which provides compatibility with older claim paths while the durable hold blocks ChatGPT Web claims independently of pause;
- removes `state/driver/chatgptrest_manual_pro_watch_allow_web_automation`, so the systemd `ConditionPathExists` gate also prevents manual restarts of driver/send/wait during the hold;
- uses a persistent allow file under repo state, not `/run/user/$UID`; a host reboot must not accidentally leave ChatGPT Web automation permanently disabled after the manual hold has been released;
- masks the protected driver/send/wait units with `systemctl --user mask --runtime`, because wait workers use `Restart=always` and a plain stop is not a strong enough invariant;
- watches `artifacts/mcp_calls.jsonl` for new `chatgpt_web_*` calls after guard start;
- watches `chatgptrest-driver.service`, `chatgptrest-worker-send.service`, and `chatgptrest-worker-wait.service`;
- watches active queued/in-progress `chatgpt_web.%` jobs without relying on projected-only fields such as `phase_detail`;
- immediately writes incident evidence under `artifacts/monitor/manual_pro_watch_guard/<timestamp>/` and stops the protected units on violation.

One-shot smoke:

```bash
PYTHONPATH=. ./.venv/bin/python ops/manual_pro_watch_guard.py --duration-seconds -1 --dry-run
```

Do not treat a quiet monitor as success unless the guard has also seeded the manual Pro lock and worker pause. Passive sampling is insufficient for this incident class.

Stopping the guard service is not a release. The durable DB hold, missing systemd allow file, and runtime unit masks remain active so another agent cannot accidentally resume ChatGPT Web by killing the observer, clearing generic pause, or restarting protected units. To end the manual Pro window:

```bash
systemctl --user stop chatgptrest-manual-pro-watch-guard.service
PYTHONPATH=. ./.venv/bin/python ops/manual_pro_watch_guard.py \
  --release \
  --release-reason "human Pro session ended" \
  --confirm-release-manual-pro-session
```

## Attachment staging roots

`input.file_paths` are intentionally not accepted from every local project path. Accepted roots are:

- the ChatgptREST repo root;
- `ChatgptREST/tmp/`;
- `/tmp/chatgptrest_uploads/`;
- explicit entries in `CHATGPTREST_EXTRA_ALLOWED_FILE_ROOTS`.

Do not copy project attachments into arbitrary `/tmp/...` to bypass the policy. Either stage them under a sanctioned upload root that preserves provenance in the submission log, or add the project attachment directory to `CHATGPTREST_EXTRA_ALLOWED_FILE_ROOTS` as an explicit runtime decision.

Public MCP automation calls now do the sanctioned staging step automatically for explicit file attachments that already exist on the local filesystem but live outside the accepted roots. The staged copies are written under `/tmp/chatgptrest_uploads/mcp_staged/<date>/<idempotency-key>/...`, the submitted job client metadata includes `mcp_attachment_staging.files[]` with original path, staged path, SHA-256, and byte count, and job events include `mcp_attachment_staged`. Disable only for diagnosis with `CHATGPTREST_MCP_STAGE_OUTSIDE_ALLOWED_FILE_PATHS=0`; if overriding `CHATGPTREST_MCP_ATTACHMENT_STAGING_ROOT`, keep it under an API-accepted root or the fallback root will be used.

## Low-level ChatGPT Web ask admission

Registered low-level ask clients can still be blocked before a job is created. This is intentional: an admission-time rejection is cheaper and safer than letting a duplicate or competing Pro job reach the shared ChatGPT browser session.

Current production guardrails:

- recent equivalent requests return HTTP `409` with `low_level_ask_duplicate_recently_submitted`;
- `input.file_paths` now participate in duplicate detection by same filename, size, and SHA-256 content when files are readable under allowed roots, so restaging the same packet in a different temp directory does not bypass dedupe;
- `internal-submit-wrappers` and `planning-wrapper` are ChatGPT Web single-flight by kind: a second `chatgpt_web.ask` while another one from the same registered client is `queued` or `in_progress` returns HTTP `429` with `low_level_ask_client_kind_concurrency_exceeded`;
- Gemini Web jobs are not blocked by the ChatGPT-specific kind limit unless the client-wide `max_in_flight_jobs` limit is also reached.

Client response guidance:

- `409 low_level_ask_duplicate_recently_submitted`: reuse the existing job id from `existing_job_id`.
- `429 low_level_ask_client_kind_concurrency_exceeded`: wait for the listed `active_job_ids` to finish, or switch to a non-ChatGPT Web provider if the task can tolerate it.
- `429 low_level_ask_client_concurrency_exceeded`: the registered client-wide in-flight limit is full. Do not resubmit with new idempotency keys. Inspect `active_jobs` / `active_job_ids`, follow `retry_after_seconds`, or cancel only a confirmed stale/superseded job with an explicit reason.
- Do not work around these responses with a new idempotency key or a different staging directory.

## ChatGPT Pro attachment-count cap

ChatGPT’s composer UI has a practical attachment-count cap. Large Pro review asks that try to upload too many individual files can fail in send-phase with symptoms like:

- `RuntimeError: Upload not confirmed in UI: <filename>`
- the last few files never appear in the composer chip list
- long send-phase runtime with no `conversation_url`

ChatgptREST now pre-bundles oversized **text-like** attachment sets for `chatgpt_web.ask` before they reach the browser surface:

- generated files:
  - `CHATGPT_ATTACH_BUNDLE.md`
  - `CHATGPT_ATTACH_INDEX.md`
- event:
  - `chatgpt_attachments_bundled`

This keeps the upload count under the ChatGPT UI cap while preserving readable context for Pro asks. If a request still exceeds the cap after bundling (for example many unsupported/binary files), inspect the job’s `chatgpt_attachments_bundle_failed` or send-phase error and reduce the attachment set intentionally instead of retrying the same oversized payload.

## ChatGPT send-phase transport timeout triage

Not every `send`-phase timeout means “the prompt probably went out”. Treat these cases differently:

- **same-session repair required**
  - use when there is thread evidence or the UI clearly entered a verification/challenge state
  - typical symptom: `chatgpt_send_manual_repair_fail_closed`
- **safe retry of unsent send**
  - use when transport/self-check timed out **and** ChatgptREST has explicit evidence that idempotency `sent=false` with no recovered thread URL
  - this remains retryable cooldown and must **not** be collapsed into same-session repair

If you are debugging a send timeout, look for `send_phase_evidence` in the job error/event payloads:

- `idempotency_sent`
- `recovered_conversation_url`
- `requested_conversation_url`
- `safe_to_retry_send`

Interpretation:

- `idempotency_sent=false` + no recovered thread URL => safe to retry the send path
- recovered thread URL or thread evidence => same-session repair path

## ChatGPT wait-phase suspect partials

For ChatGPT Pro / thinking presets, a wait-phase job can enter a bad state where the thread only emits:

- a short meta-commentary preamble, or
- an empty/placeholder in-progress assistant turn,

without producing the real final answer.

ChatgptREST now treats this as a distinct recovery class:

- if wait no-progress fires on a stable ChatGPT thread
- and the visible answer is still blank / suspiciously short
- and the job is on a Pro/thinking preset

the worker may issue a **single same-thread `chatgpt_web_regenerate`** before escalating to `WaitNoProgressTimeout`.

Observability:

- `wait_regenerate_requested`
- `wait_regenerate_failed`

Use these to distinguish:

- genuine “waited long enough, still no answer”
- vs “we hit the short-preamble / stuck-thinking pattern and already tried one same-thread regenerate”

## API Rejection Audit

When clients report that ChatgptREST "failed before Pro/Deep Research started", first check whether the request was rejected before job creation.

Structured rejection rows are written to:

```text
artifacts/monitor/api_rejections/YYYYMMDD.jsonl
```

Covered status codes:

- 400
- 401
- 403
- 409
- 429

Covered surfaces:

- `/v1/jobs`
- `/v1/ops`
- `/v1/issues`

Rows include sanitized client identity and correlation fields, including `Idempotency-Key`, `X-Client-Name`, `X-Client-Instance`, and `X-Request-ID`. Authorization values are never written.

High-risk Web ask requests that reference local review/audit bundles without `input.file_paths` now fail closed during create:

```text
CHATGPTREST_FAIL_CLOSED_HIGH_RISK_ATTACHMENT_CONTRACT_ON_CREATE=1
```

Default: enabled. Disable only for controlled executor-level regression tests.

Worker claim transactions also have a short local SQLite lock retry before surfacing to the outer worker loop:

```text
CHATGPTREST_WORKER_CLAIM_DB_LOCK_RETRY_ATTEMPTS=4
CHATGPTREST_WORKER_CLAIM_DB_LOCK_RETRY_BASE_MS=200
```

These retries only cover transient `database is locked` / busy classes. Filesystem panic classes such as readonly DB and disk-full still follow the fatal DB handling path.

## Tunnel-First Ingress

ChatgptREST is an automation/control-plane service. It should be reached through localhost, SSH tunnel, or Tailscale-style private tunnel, not a public HTTP reverse proxy.

Runtime default:

```text
CHATGPTREST_REJECT_PUBLIC_INGRESS=1
```

When enabled, the API rejects requests whose real client IP is public/global with HTTP 403:

```text
detail.error=public_ingress_blocked
detail.error_type=PublicIngressBlocked
```

Allowed by default:

- `127.0.0.1` / `::1`
- RFC1918/private addresses
- link-local / reserved addresses
- Tailscale/CGNAT `100.64.0.0/10`

Emergency allowlist for a fixed public admin IP:

```text
CHATGPTREST_PUBLIC_INGRESS_ALLOW_CIDRS=203.0.113.10/32
```

Use this only as a temporary exception. The intended access pattern is:

```bash
ssh -N \
  -L 18711:127.0.0.1:18711 \
  -L 18712:127.0.0.1:18712 \
  <user>@<host>
```

Then use:

- REST: `http://127.0.0.1:18711`
- public MCP: `http://127.0.0.1:18712/mcp`

The optional `chatgptrest-homepc-tunnel.service` reverse tunnel must use a slow restart backoff. If HomePC is offline or the route to `192.168.1.17:22` is down, a 10-second restart loop creates avoidable journal/process churn during already degraded host conditions. The tracked drop-in sets `RestartSec=300` and `StartLimitBurst=3`.

If a public reverse proxy remains active for unrelated websites on the same host, it must not proxy ChatgptREST API/MCP paths. The application-layer ingress guard is defense in depth, not a replacement for closing the public route at nginx/firewall.

## ChatGPT Pro / Thinking Finality Triage

When a Pro/thinking job returns quickly, looks shallow, truncates, or echoes the prompt, do not diagnose from the visible page alone. Inspect the job events and conversation export:

```bash
cd /vol1/1000/projects/ChatgptREST
jq -r 'select(.type|test("model_observed_export|completion_guard_downgraded|conversation_export_missing_reply_ignored|wait_active_finalization"))' \
  artifacts/jobs/<job_id>/events.jsonl
```

Important distinctions:

- `model=5.2 pro` plus export `thinking_effort=extended` means model selection succeeded, even if the web UI did not show an obvious thinking trace.
- For high-value Pro review/research contracts, model metadata is not enough. If the job lacks a usable `Thought for ...` / `thinking_observation` trace, the thought guard should same-thread regenerate or fail closed, even when the answer is longer than `min_chars`.
- A matched assistant message with `status=in_progress`, missing `is_complete=true`, or missing `finish_type` is not final evidence for Pro/thinking jobs.
- `answer_chars >= min_chars` is insufficient when export shows the current assistant turn is still generating.
- `answer_chars >= min_chars` is also insufficient when a Pro review/research job completed without thinking-path evidence. Check for `_thought_guard.reason=missing_thought_for_research_answer` and `error_type=ThoughtGuardMissingTrace`.
- If send-stage timeout was hit and export cannot prove completion, the job must continue in wait phase, not store a canonical answer.
- If a Pro follow-up loops with a constant prompt echo and `best_role=tool`, inspect message timestamps. An `in_progress` tool node older than the latest user prompt is stale export state, not evidence that the current answer is still generating.
- Repeated prompt echo (`wait_partial_answer_echo_observed`) plus no current-turn assistant text should be allowed to terminalize through `WaitNoProgressTimeout`; do not keep sending corrective prompts into the same thread.

Relevant thought-guard toggles:

```text
CHATGPTREST_THOUGHT_GUARD_AUTO_REGENERATE=1
CHATGPTREST_THOUGHT_GUARD_REQUIRE_TRACE_FOR_RESEARCH=1
CHATGPTREST_THOUGHT_GUARD_REQUIRE_THOUGHT_FOR=0
```

`REQUIRE_TRACE_FOR_RESEARCH` is the default protection for external-review and long Pro asks. `REQUIRE_THOUGHT_FOR` is stricter and applies the missing-trace rule beyond research contracts; only enable it deliberately.

Related regression notes:

- `docs/dev_log/2026-04-27_pro_thinking_fast_answer_partial_finality_rca_v1.md`
- `docs/dev_log/2026-04-27_pro_research_thinking_trace_guard_v1.md`

## Client Cutover (high level)

Goal: clients stop calling chatgptMCP’s `chatgpt_web_*` directly.

- For REST clients: use `POST /v1/jobs` + `/wait` + `/answer`.
- For Codex/Claude Code/Antigravity: point MCP to ChatgptREST public MCP (`http://127.0.0.1:18712/mcp`) and use `automation_*` tools by default. Public MCP no longer exposes retired advisor/coding-agent compat tools as maintained shared tools.
- Do not configure other coding agents to call ChatgptREST REST endpoints directly when the public MCP is available.
- Prefer the systemd-managed `chatgptrest-mcp.service` or `ops/start_mcp.sh`; both load env and the public MCP entrypoint now fail-fast if `OPENMIND_API_KEY` and `CHATGPTREST_API_TOKEN` are both missing.
- For high-risk automation lanes, enable `CHATGPTREST_REQUIRE_EXPLICIT_MCP_CANCEL_REASON=1` and call `automation_job_cancel(job_id=..., reason="...")`; this prevents external review / governance jobs from being canceled with only an auto-generated `mcp_cancel:<job_id>` attribution.
- If a client reports that `automation_job_cancel` has no `reason` argument, the running MCP tool schema or client session is stale. Restart `chatgptrest-mcp.service`, restart the client session, and verify with `ops/run_public_agent_mcp_validation.py`; that probe now checks the live `automation_job_cancel` input schema, not just the tool name.
- Audit known coding-agent configs and repair Antigravity drift in place with `python3 ops/check_public_mcp_client_configs.py --fix`.
- Keep the admin MCP (`http://127.0.0.1:18715/mcp`) for ops/debug clients that still need the legacy broad surface.

## Disk / Artifacts Cleanup

Artifacts can grow without bound on long-running hosts. Cleanup old terminal job directories:

```bash
cd /vol1/1000/projects/ChatgptREST
.venv/bin/python ops/cleanup_artifacts.py --days 14 --dry-run
.venv/bin/python ops/cleanup_artifacts.py --days 14
```

`maint_daemon/maint_*.jsonl` 的预算治理先走 dry-run，不直接删文件：

```bash
cd /vol1/1000/projects/ChatgptREST
.venv/bin/python ops/maint_daemon_jsonl_cleanup.py
```

默认输出到：

- `artifacts/monitor/reports/maint_daemon_jsonl_cleanup/<timestamp>/inventory_before.json`
- `artifacts/monitor/reports/maint_daemon_jsonl_cleanup/<timestamp>/inventory_before.md`
- `artifacts/monitor/reports/maint_daemon_jsonl_cleanup/<timestamp>/compression_sample.json`
- `artifacts/monitor/reports/maint_daemon_jsonl_cleanup/<timestamp>/dry_run_plan.json`
- `artifacts/monitor/reports/maint_daemon_jsonl_cleanup/<timestamp>/dry_run_plan.md`

说明：

- 当前工具只做 dry-run，不执行压缩、删除、迁移。
- 默认口径对齐 `docs/ops/2026-03-25_maint_daemon_jsonl_cleanup_execution_plan_v1.md`：
  - 最新两个日包保护
  - 少量 closed 日包保 raw
  - 中间窗口投影为 `would_compress`
  - 更老窗口投影为 `would_summarize_only`

## Incidents Cleanup (stale)

The incident table is append-heavy; old incidents can linger as `status=open` even when no longer recurring.

Resolve incidents that have not been seen recently (dry-run by default):

```bash
cd /vol1/1000/projects/ChatgptREST
.venv/bin/python ops/incidents_cleanup.py --older-than-days 14 --limit 200
.venv/bin/python ops/incidents_cleanup.py --older-than-days 14 --limit 200 --apply
```
