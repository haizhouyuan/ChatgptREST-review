# Paperclip Repeatable Ops 8h Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the corrected real company-agent loop proof into an 8-hour repeatable operating run with monitored cycles, live Paperclip readback, and fail-closed evidence.

**Architecture:** Keep Codex2 as controller/monitor, not as a fake company worker. Paperclip companies must own real issues and produce agent-owned run evidence. The controller may create task contracts, schedule cycles, validate outputs, sync status, and remediate, but cannot count local-board/controller-only artifacts as company execution.

**Tech Stack:** Paperclip local API at `http://127.0.0.1:3100`, ToyResearch repo files, `paperclip_company_os` validators, Python/JSON evidence artifacts, Codex `/goal`, git commits.

---

## Scope

This phase starts after the corrected scoped real-agent-loop gate passed on 2026-05-08.

Already accepted baseline:

- `round5`-`round11` are downgraded to `controller/local-board simulated evidence loop`.
- Corrected real-agent-loop gate exists and has passing evidence for:
  - `PLA-76`
  - `FIN-31`
  - `PAPA-38`
  - `MEM-17`
  - `PAP-44`
  - `PAP-48`
- MiniMax / DeepSeek / Tavily / Brave remain `provider_quarantine / no-production-use`.
- Finbot remains supervised research-only.

This plan does not claim full Paperclip production autonomy. It proves repeatable operation under supervision for 8 hours.

## Non-Goals

- Do not build automatic trading, target-price generation, broker actions, production watchlists, or trade signals.
- Do not promote memory authority.
- Do not reactivate quarantined providers.
- Do not use local model routing for Paperclip system-building.
- Do not call `update_goal(status=complete)` before a minimum 8-hour wall-clock monitoring window has elapsed.
- Do not create round-number evidence loops as the main proof. New evidence must be operation cycles, not `round14`, `round15`, etc.

## Required Evidence Root

Create one run root:

```text
/vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-09_repeatable_ops_8h_monitor/
```

Minimum files:

```text
00_goal_contract.md
01_baseline/current_truth_snapshot.md
01_baseline/live_company_agent_status.json
01_baseline/live_open_issue_matrix.json
02_schedule/ops_cycle_schedule.json
02_schedule/ops_cycle_schedule.md
03_cycles/cycle_0000/
03_cycles/cycle_0030/
...
03_cycles/cycle_0800/
04_monitors/provider_quarantine_monitor.jsonl
04_monitors/finbot_policy_monitor.jsonl
04_monitors/memory_no_authority_monitor.jsonl
04_monitors/runtime_skill_mcp_monitor.jsonl
04_monitors/live_agent_health_monitor.jsonl
05_incidents/incident_register.jsonl
06_status_sync/status_sync.jsonl
07_final/8h_completion_audit.md
07_final/8h_completion_audit.json
07_final/dirty_worktree_scope.md
manifest.json
manifest_validation_result.json
json_tree_validation_result.json
```

## Operating Cadence

Run for at least 8 hours from `start_at`.

Checkpoint cadence:

- `cycle_0000`: baseline.
- `cycle_0030`, `cycle_0100`, ..., `cycle_0800`: checkpoint every 30 minutes.
- Minimum checkpoints: 17 including baseline and final.

At every checkpoint:

- Poll Paperclip health.
- Poll live company/agent status.
- Poll active/open issues for the six target companies.
- Poll latest issue runs and heartbeat runs.
- Validate provider quarantine.
- Validate Finbot research-only guard.
- Validate memory no-authority-promotion guard.
- Validate runtime and Skill-MCP health.
- Append monitor rows.
- Write a cycle closeout.

At least once every 2 hours:

- Planning must run or continue one real planning operations issue.
- Finbot must run or continue one supervised research operations issue.
- Governance must validate policy drift and guardrails.
- Memory must evaluate candidate memory deltas and keep authority writes at zero.
- Skill-MCP must perform a real usable path probe, not just a surface audit.
- Runtime must perform a real routing/fallback/capability probe, not `python --version` or `cli --help`.

## Acceptance Criteria

The goal can complete only if all of the following are true:

- Wall-clock monitoring duration is at least 8 hours.
- At least 17 checkpoint directories exist.
- Every checkpoint has:
  - Paperclip API health result.
  - live company/agent status.
  - issue matrix.
  - monitor append rows.
  - cycle closeout.
- No cycle uses `roundN` as its primary proof.
- Every company has at least two successful real agent-owned operations during the 8-hour run, except if a company has an explicit degraded-mode incident with continued monitoring and a follow-up issue.
- Every accepted company issue has:
  - `assigneeAgentId`.
  - issue run evidence or equivalent run id evidence.
  - agent-authored comment or `createdByRunId`.
  - heartbeat success.
  - agent status not `error` or `paused` at closeout.
  - readable artifact path.
  - validator pass.
- Finbot emits no investment advice, target price, automatic trading, production watchlist, broker action, or trade signal.
- Memory authority writes remain zero.
- MiniMax / DeepSeek / Tavily / Brave remain quarantined/no-production-use.
- Runtime acceptance uses real route/fallback/capability evidence, not weak smoke.
- Skill-MCP acceptance uses real usable path evidence, not surface audit only.
- `current truth`, `blocker board`, and `execution matrix` are updated with 8-hour operating status.
- Dirty worktree is classified so the next agent knows which files belong to this 8-hour ops run and which are historical noise.

## Failure Policy

Do not stop the whole goal on the first transient failure.

If a cycle fails:

- Record the failure in `05_incidents/incident_register.jsonl`.
- Keep monitoring.
- Retry at the next checkpoint unless the failure is a true external blocker.
- Create or update a Paperclip issue for remediation.
- Mark the affected company as `degraded`, not `passed`, until a later checkpoint proves recovery.

Only use `HARD_EXTERNAL_BLOCKER` if:

- The blocker is inside the active 8-hour goal.
- It cannot be worked around locally.
- All other companies continue monitoring.
- The blocker has issue id, owner, evidence path, and next required user action.

## Task Plan

### Task 1: Start From The Correct Repository

**Files:**
- Read: `/vol1/1000/projects/toyresearch/AGENTS.md`
- Read: `/vol1/1000/projects/toyresearch/paperclip_company_os/AGENTS.md`
- Read: `/vol1/1000/projects/toyresearch/docs/paperclip_production_current_truth_20260507.md`
- Read: `/vol1/1000/projects/toyresearch/docs/paperclip_company_blocker_board_20260507.md`
- Read: `/vol1/1000/projects/toyresearch/docs/paperclip_company_execution_matrix_20260507.md`

- [ ] **Step 1: Switch repository**

Run:

```bash
cd /vol1/1000/projects/toyresearch
pwd
```

Expected:

```text
/vol1/1000/projects/toyresearch
```

- [ ] **Step 2: Read entry rules**

Run:

```bash
sed -n '1,220p' /vol1/1000/projects/toyresearch/AGENTS.md
sed -n '1,180p' /vol1/1000/projects/toyresearch/paperclip_company_os/AGENTS.md
```

Expected: Paperclip stop rules and corrected evidence rules are visible.

### Task 2: Create The 8-Hour Evidence Root

**Files:**
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-09_repeatable_ops_8h_monitor/00_goal_contract.md`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-09_repeatable_ops_8h_monitor/02_schedule/ops_cycle_schedule.json`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-09_repeatable_ops_8h_monitor/02_schedule/ops_cycle_schedule.md`

- [ ] **Step 1: Write goal contract**

`00_goal_contract.md` must state:

```markdown
# Paperclip Repeatable Ops 8h Monitor Contract

- Start condition: corrected scoped real-agent-loop gate has passed.
- Run duration: minimum 8 hours wall-clock.
- Controller role: schedule, monitor, validate, remediate, and sync status.
- Company role: execute real agent-owned issues.
- Forbidden proof: controller/local-board-only closeout.
- Forbidden outputs: Finbot advice, target price, trading, production watchlist, trade signal.
- Quarantined providers: MiniMax, DeepSeek, Tavily, Brave.
- Completion rule: do not call update_goal(status=complete) before 8 hours and final audit pass.
```

- [ ] **Step 2: Write schedule**

`ops_cycle_schedule.json` must contain checkpoint ids from `cycle_0000` through `cycle_0800`.

### Task 3: Baseline Snapshot

**Files:**
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-09_repeatable_ops_8h_monitor/01_baseline/current_truth_snapshot.md`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-09_repeatable_ops_8h_monitor/01_baseline/live_company_agent_status.json`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-09_repeatable_ops_8h_monitor/01_baseline/live_open_issue_matrix.json`

- [ ] **Step 1: Capture health and live company state**

Run:

```bash
curl -sS http://127.0.0.1:3100/api/health
curl -sS http://127.0.0.1:3100/api/companies
```

Expected: Paperclip API is reachable and active company ids can be resolved.

- [ ] **Step 2: Record agent statuses**

For Planning, Finbot, Governance, Memory, Controller/Runtime, and the Skill-MCP owner surface, record all agents and statuses. Any `error` or `paused` status must create an incident and remediation issue before the first operational cycle is accepted.

### Task 4: Implement Checkpoint Cycle Evidence

**Files:**
- Create under each checkpoint: `03_cycles/cycle_HHMM/`
- Required per checkpoint:
  - `health.json`
  - `company_agent_status.json`
  - `issue_matrix.json`
  - `run_readback.json`
  - `policy_guardrails.json`
  - `cycle_closeout.md`

- [ ] **Step 1: For each checkpoint, write health evidence**

Run every 30 minutes:

```bash
curl -sS http://127.0.0.1:3100/api/health > <cycle_root>/health.json
```

Expected: health status is `ok`.

- [ ] **Step 2: Write company and issue evidence**

For each target company, fetch:

- agents.
- open issues.
- latest heartbeat runs.
- latest accepted real-agent issue readbacks.

Expected: accepted companies remain operational or have a recorded degraded incident.

### Task 5: Run Repeatable Company Operations

**Files:**
- Create/append inside each relevant company run root.
- Create Paperclip issues as needed.
- Validate each accepted issue with corrected real-agent-loop gate.

- [ ] **Step 1: Planning operations**

At least twice during the 8-hour window, Planning must execute real agent-owned work that updates the operating plan or review queue. Evidence must include issue id, run id, agent comment, artifact, validator, memory delta candidate, and closeout.

- [ ] **Step 2: Finbot supervised research operations**

At least twice during the 8-hour window, Finbot must execute real agent-owned supervised research work. It may triage sources, build opportunity cases, or prepare human review boards. It must not emit advice, target prices, automatic trading, production watchlists, broker actions, or trade signals.

- [ ] **Step 3: Governance operations**

At least twice during the 8-hour window, Governance must validate drift, quarantine boundaries, Finbot output policy, and real-agent evidence completeness.

- [ ] **Step 4: Memory operations**

At least twice during the 8-hour window, Memory must evaluate candidate deltas and maintain authority writes at zero unless the user separately authorizes promotion.

- [ ] **Step 5: Skill-MCP operations**

At least twice during the 8-hour window, Skill-MCP must prove a real usable route. Surface inventory alone is not enough.

- [ ] **Step 6: Runtime operations**

At least twice during the 8-hour window, Runtime must prove a real route/fallback/capability path. `python --version`, `git rev-parse`, and `cli --help` are not enough.

### Task 6: Monitor Append-Only Ledgers

**Files:**
- Append: `04_monitors/provider_quarantine_monitor.jsonl`
- Append: `04_monitors/finbot_policy_monitor.jsonl`
- Append: `04_monitors/memory_no_authority_monitor.jsonl`
- Append: `04_monitors/runtime_skill_mcp_monitor.jsonl`
- Append: `04_monitors/live_agent_health_monitor.jsonl`
- Append: `05_incidents/incident_register.jsonl`

- [ ] **Step 1: Append one row per checkpoint**

Each monitor row must include:

```json
{
  "cycle_id": "cycle_0030",
  "checked_at": "ISO-8601 timestamp",
  "status": "pass|degraded|fail",
  "evidence_path": "absolute path",
  "notes": "specific finding"
}
```

- [ ] **Step 2: Record incidents**

If any agent is `error` or `paused`, any issue lacks run evidence, any policy guard fails, or any API call fails after retry, append an incident row with owner and next action.

### Task 7: Final 8-Hour Audit

**Files:**
- Create: `07_final/8h_completion_audit.md`
- Create: `07_final/8h_completion_audit.json`
- Create: `07_final/dirty_worktree_scope.md`
- Create/update: `manifest.json`
- Create/update: `manifest_validation_result.json`
- Create/update: `json_tree_validation_result.json`

- [ ] **Step 1: Verify duration**

The audit must show:

- `start_at`
- `end_at`
- `duration_hours >= 8.0`
- checkpoint count >= 17

- [ ] **Step 2: Verify all company operations**

The audit must list every accepted company issue with:

- issue identifier.
- assignee agent id.
- run id or issue runs evidence.
- heartbeat status.
- agent comment evidence.
- artifact path.
- validator path.
- closeout path.

- [ ] **Step 3: Verify guardrails**

The audit must explicitly state:

- Finbot remained research-only.
- memory authority writes were zero.
- quarantined providers were not used.
- Runtime was not accepted on weak smoke.
- Skill-MCP was not accepted on surface audit only.

- [ ] **Step 4: Classify dirty worktree**

`dirty_worktree_scope.md` must split dirty files into:

- files created/modified for this 8-hour ops run.
- pre-existing unrelated noise.
- files requiring separate cleanup.

- [ ] **Step 5: Commit**

Commit only this 8-hour run's evidence, validators, and docs. Do not sweep unrelated dirty worktree into the commit.

Suggested commit:

```bash
git add docs/paperclip_ops_runs/2026-05-09_repeatable_ops_8h_monitor
git commit -m "paperclip: run repeatable ops 8h monitor"
```

## Direct `/goal` Prompt

Use this from `/vol1/1000/projects/toyresearch` in Codex2. This prompt embeds the execution plan directly so the goal runner does not depend on following a separate reference link correctly.

```text
/goal 在 /vol1/1000/projects/toyresearch 中执行 Paperclip 可重复运营 + 8 小时监控运行。目标不是再纠偏 round5-11，也不是继续堆 round12/round13/round14 pass，而是在已经通过 corrected scoped real-agent-loop gate 的基础上，证明 Paperclip 六家公司能在 8 小时内被持续调度、监控、验收和纠偏。

这是完整执行合同，不要把它简化成“写计划”。必须按下面的内嵌计划执行到 8 小时 final audit 通过。

必须先读取：
- /vol1/1000/projects/toyresearch/AGENTS.md
- /vol1/1000/projects/toyresearch/paperclip_company_os/AGENTS.md
- /vol1/1000/projects/toyresearch/docs/paperclip_production_current_truth_20260507.md
- /vol1/1000/projects/toyresearch/docs/paperclip_company_blocker_board_20260507.md
- /vol1/1000/projects/toyresearch/docs/paperclip_company_execution_matrix_20260507.md
- /vol1/1000/projects/toyresearch/docs/superpowers/plans/2026-05-09-paperclip-repeatable-ops-8h-monitor-plan.md

内嵌计划：

1. 建立唯一证据根：
   /vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-09_repeatable_ops_8h_monitor/

2. 在证据根下创建这些文件和目录：
   - 00_goal_contract.md
   - 01_baseline/current_truth_snapshot.md
   - 01_baseline/live_company_agent_status.json
   - 01_baseline/live_open_issue_matrix.json
   - 02_schedule/ops_cycle_schedule.json
   - 02_schedule/ops_cycle_schedule.md
   - 03_cycles/cycle_0000/
   - 03_cycles/cycle_0030/
   - 03_cycles/cycle_0100/
   - 03_cycles/cycle_0130/
   - 03_cycles/cycle_0200/
   - 03_cycles/cycle_0230/
   - 03_cycles/cycle_0300/
   - 03_cycles/cycle_0330/
   - 03_cycles/cycle_0400/
   - 03_cycles/cycle_0430/
   - 03_cycles/cycle_0500/
   - 03_cycles/cycle_0530/
   - 03_cycles/cycle_0600/
   - 03_cycles/cycle_0630/
   - 03_cycles/cycle_0700/
   - 03_cycles/cycle_0730/
   - 03_cycles/cycle_0800/
   - 04_monitors/provider_quarantine_monitor.jsonl
   - 04_monitors/finbot_policy_monitor.jsonl
   - 04_monitors/memory_no_authority_monitor.jsonl
   - 04_monitors/runtime_skill_mcp_monitor.jsonl
   - 04_monitors/live_agent_health_monitor.jsonl
   - 05_incidents/incident_register.jsonl
   - 06_status_sync/status_sync.jsonl
   - 07_final/8h_completion_audit.md
   - 07_final/8h_completion_audit.json
   - 07_final/dirty_worktree_scope.md
   - manifest.json
   - manifest_validation_result.json
   - json_tree_validation_result.json

3. 先写 00_goal_contract.md，必须包含：
   - Start condition: corrected scoped real-agent-loop gate has passed.
   - Run duration: minimum 8 hours wall-clock.
   - Controller role: schedule, monitor, validate, remediate, and sync status.
   - Company role: execute real agent-owned issues.
   - Forbidden proof: controller/local-board-only closeout.
   - Forbidden outputs: Finbot advice, target price, trading, production watchlist, trade signal.
   - Quarantined providers: MiniMax, DeepSeek, Tavily, Brave.
   - Completion rule: do not call update_goal(status=complete) before 8 hours and final audit pass.

4. 写 02_schedule/ops_cycle_schedule.json 和 02_schedule/ops_cycle_schedule.md：
   - start_at 为实际开始时间。
   - end_not_before 必须至少是 start_at + 8 hours。
   - checkpoint ids 必须覆盖 cycle_0000 到 cycle_0800。
   - checkpoint 间隔为 30 分钟。
   - 最少 checkpoint 数为 17。

5. 做 cycle_0000 baseline：
   - curl http://127.0.0.1:3100/api/health。
   - 读取 live companies。
   - 读取 Planning、Finbot、Governance、Memory、Skill-MCP、Runtime/Controller 相关 agents。
   - 读取 open issue matrix。
   - 如果有 error/paused agent，记录 incident，并创建或更新 remediation issue；不能把该公司计为 pass，直到后续 checkpoint 证明恢复。

6. 每 30 分钟执行一个 checkpoint。每个 03_cycles/cycle_HHMM/ 必须有：
   - health.json
   - company_agent_status.json
   - issue_matrix.json
   - run_readback.json
   - policy_guardrails.json
   - cycle_closeout.md

7. 每个 checkpoint 必须追加 monitor rows：
   - 04_monitors/provider_quarantine_monitor.jsonl
   - 04_monitors/finbot_policy_monitor.jsonl
   - 04_monitors/memory_no_authority_monitor.jsonl
   - 04_monitors/runtime_skill_mcp_monitor.jsonl
   - 04_monitors/live_agent_health_monitor.jsonl
   每条 row 必须包含 cycle_id、checked_at、status、evidence_path、notes。

8. 8 小时内六家公司必须都有可重复运营证据：
   - Planning 至少 2 次真实 agent-owned operations issue。
   - Finbot 至少 2 次真实 agent-owned supervised research operations issue。
   - Governance 至少 2 次真实 policy/drift/guardrail validation issue。
   - Memory 至少 2 次 candidate/no-authority memory operations issue。
   - Skill-MCP 至少 2 次真实 usable path probe issue，不能只做 surface audit。
   - Runtime 至少 2 次真实 route/fallback/capability probe issue，不能用 python --version、git rev-parse 或 cli --help 作为通过。

9. 所有计入通过的 issue 必须满足 corrected real-agent-loop gate：
   - assigneeAgentId 非空。
   - 有 issue run evidence 或等价 run id evidence。
   - 有 agent-authored comment 或 createdByRunId。
   - heartbeat succeeded。
   - agent status 不是 error/paused。
   - artifact path 可读。
   - validator pass。

10. Finbot guardrail：
   - 只能 supervised research-only。
   - 禁止 investment advice。
   - 禁止 target price。
   - 禁止 automatic trading。
   - 禁止 production watchlist。
   - 禁止 broker action。
   - 禁止 trade signal。
   - 如果发现任何违规词或字段，Finbot 本 cycle fail，写 incident，不能最终 pass。

11. Memory guardrail：
   - authority writes 必须为 0。
   - 只允许 candidate/no-write/governed evidence。
   - 除非用户另行明确授权，不得 promotion。

12. Provider guardrail：
   - MiniMax / DeepSeek / Tavily / Brave 保持 provider_quarantine / no-production-use。
   - 不要把 key rotation 当 blocker。
   - 不要调用这些 provider。
   - 每个 checkpoint 都要记录 quarantine monitor row。

13. Runtime guardrail：
   - 不接受 python --version、git rev-parse、cli --help 作为通过。
   - 必须有真实 route/fallback/capability probe evidence。
   - 失败时记录 degraded/incident，继续监控和 remediation。

14. Skill-MCP guardrail：
   - 不接受 surface audit only。
   - 必须有至少一个真实 usable path probe evidence。
   - 失败时记录 degraded/incident，继续监控和 remediation。

15. Failure policy：
   - 某个 cycle 失败时，不要停止整个 goal。
   - 记录 05_incidents/incident_register.jsonl。
   - 创建或更新 Paperclip remediation issue。
   - 下一个 checkpoint 继续监控。
   - 后续 checkpoint 可以证明恢复；否则 final audit 保留 degraded，不得伪造 pass。

16. 最终 audit：
   - 只有 wall-clock duration >= 8 hours 才允许 final audit。
   - 07_final/8h_completion_audit.json 必须列出 start_at、end_at、duration_hours、checkpoint_count、company_operation_counts、guardrail_results、incident_summary、final_status。
   - 07_final/8h_completion_audit.md 必须逐项解释每家公司运营证据、失败/恢复情况、guardrail 状态、剩余限制。
   - 07_final/dirty_worktree_scope.md 必须把 dirty files 分成：本次 8 小时 ops 相关、历史无关噪声、需要另行 cleanup。
   - manifest validation 和 json tree validation 必须 pass。
   - current truth / blocker board / execution matrix 必须同步 8 小时运营状态。

17. Completion rule：
   - 不得在 8 小时前调用 update_goal(status=complete)。
   - 不得因为写完 schedule 或 baseline 就 complete。
   - 不得因为某一个 cycle pass 就 complete。
   - 只能在 8 小时、checkpoint 数、六家公司重复运营、corrected validator、status sync、manifest、json tree、dirty worktree scope 全部通过后，才可调用 update_goal(status=complete)。

禁止：
- 不要新建 round14/round15 作为主证明。
- 不要把 controller/local-board-only closeout 当公司执行。
- 不要把当前 scoped goal 通过扩展声明为 Paperclip 最终生产自治完成。
- 不要把 unrelated dirty worktree 混进本次提交。
- 不要只输出“计划已写好”。
- 不要用旧 round pass 作为本 goal 的通过证据。

最终产物：
- /vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-09_repeatable_ops_8h_monitor/07_final/8h_completion_audit.md
- /vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-09_repeatable_ops_8h_monitor/07_final/8h_completion_audit.json
- /vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-09_repeatable_ops_8h_monitor/07_final/dirty_worktree_scope.md
- manifest validation pass
- json tree validation pass
- current truth / blocker board / execution matrix 已同步 8 小时运营状态
- 只提交本次 8 小时运营相关文件
```

## Immediate Follow-Up Prompt After `/goal`

Send this after the `/goal` command if Codex2 starts planning instead of executing:

```text
开始执行，不要停在计划。先 cd /vol1/1000/projects/toyresearch，读取计划文档和入口规则，创建 8 小时 evidence root，写入 00_goal_contract.md 和 cycle schedule，然后立即开始 cycle_0000 baseline。这个 goal 的完成条件是 8 小时监控窗口结束并通过 final audit，不是写完计划。
```

## Self-Review

- Spec coverage: This plan covers repeatable operation, 8-hour monitoring, six companies, Finbot guardrails, memory no-write, provider quarantine, Runtime/Skill-MCP stronger probes, checkpoint evidence, final audit, and `/goal` usage.
- Placeholder scan: No `TBD`, `TODO`, or open placeholders are present.
- Type consistency: Evidence root, checkpoint ids, issue validation fields, and final artifacts are named consistently.
