根据 2026-04-25 的本地上下文和配置包，我的结论是：**已经从“表面 agent demo”升级成了“可审计 Paperclip demo 配置”，但还没有达到“可验收闭环 demo”的标准。** 它现在有公司、项目、9 个 agent、任务树、skill、MCP 模板、数据真相政策、禁用声明、运行矩阵、heartbeat 输出和 runbook；这已经明显不是只有 agent 名字的空壳。审阅目标本身也明确要求证明 Paperclip 控制面、配置治理、证据与本地闭环，而不是证明 AI 能自动完成完整产品设计。 本地上下文也确认 Paperclip 实例为 `0.3.1 / local_trusted / private`，9 个 agent 均为 `process` adapter，真实 API key 和 DB 未进入 portable packet，MCP 本地 secret env 也在包外。

但是，**当前最核心的闭环证据不合格**：`evidence/issues_redacted.json` 是 0 字节；`outputs/heartbeat-data-truth-guard.json` 显示选中的 issue 是 `LAB-2`，标题却是 `EPIC 1 - Data Truth Foundation`；而 `.paperclip.yaml` 里 `EPIC 1 - Data Truth Foundation` 应该是 `LAB-1`，`LAB-2` 应该是 `EPIC 2 - Product Opportunity Radar`。这会让审阅者无法确认 Paperclip issue tree、运行 case、状态流转和 artifact 之间的对应关系。

我的打分：**78 / 100**。
达到 90 分前，必须先修复 P0：让一个明确命名的 smoke issue 从 `todo → in_progress → done`，生成 artifact，写 Paperclip comment，并导出非空 issue evidence。

---

## 1. 总体判断

**已升级，但未闭环。**

已经合格的部分：

* `paperclip_labebe_demo_package/.paperclip.yaml` 定义了 9 个 agent、1 个 project、10 个 task/epic、process adapter、状态和优先级。
* `labebe-ai-design-studio/workspace/config/agent-runtime-matrix.yaml` 定义了运行方式、loopback、外部账号禁用、真实客户数据禁用、人审门禁。
* `skill-registry.yaml` 定义了 Paperclip 基础 skill、治理 skill、产品概念 workflow skill、demo operator skill。
* `mcp.paperclip.template.json` 使用 placeholder，不包含真实 key。
* `docs/DATA_TRUTH.md`、`FORBIDDEN_CLAIMS.md`、`ACTION_POLICY.md`、`DEMO_SAMPLE_POLICY.md` 构成了数据真相和禁用边界。
* `scripts/paperclip_demo_agent.py` 能读取本地治理文档、写 `outputs`、在有 API env 时选 issue 并更新 Paperclip。
* 本地上下文说明 MCP smoke 已通过 `initialize` 和 `tools/list`，但这个 smoke transcript 没有进入 evidence 包。

仍不合格的部分：

* 当前 evidence 不能证明 10 个 issue 已正确导入。
* 当前 evidence 不能证明 `CASE 1 - Data Truth Guard end-to-end smoke` 已跑完并 done。
* 当前 issue identifier 和 title 存在漂移。
* live `desiredSkills` 与 `skill-registry.yaml`/agent frontmatter 不一致。
* runbook 对 Pro/审阅者复现不够：没有精确的目标 issue ID、触发步骤、导出步骤、预期 JSON 字段。
* MCP 只证明能列工具，没有证明工具白名单、禁用策略、mutation gating。

---

## 2. P0 / P1 / P2 问题清单

### P0-1：当前 smoke case 没有闭环，且 evidence 不能证明 issue tree

**证据位置：**

* `pro_requests/20260425_paperclip_labebe_demo_config_review/evidence/issues_redacted.json`
* `labebe-ai-design-studio/workspace/outputs/heartbeat-data-truth-guard.json`
* `labebe-ai-design-studio/workspace/outputs/case-LAB-2-data-truth-guard.md`
* `labebe-ai-design-studio/workspace/runbooks/run-demo-case.md`

**问题：**

`issues_redacted.json` 是 0 字节。审阅者无法从 packet 看到 10 个 imported epics、目标 smoke issue、状态、assignee、comment、closeout。

`heartbeat-data-truth-guard.json` 里：

```json
"selected_issue": {
  "identifier": "LAB-2",
  "title": "EPIC 1 - Data Truth Foundation",
  "status": "in_progress"
},
"paperclip_update": {
  "next_status": "in_progress"
}
```

这不是 runbook 要求的 `CASE 1 - Data Truth Guard end-to-end smoke`，也没有变成 `done`。

**影响：**

老板演示时如果说“端到端 case 已闭环”，证据对不上；Pro 审阅者也无法复现 issue 状态和 artifact/comment 的链路。

**修复动作：**

1. 重新导出 `issues_redacted.json`，至少包含：

   * 10 个 epic issue；
   * 1 个 smoke issue；
   * issue id、identifier、title、status、assignee agent、priority、comments count、latest comment redacted body。
2. 修正 `scripts/paperclip_demo_agent.py` 的 issue 选择逻辑，不要只按 assignee + status 排序选择第一个 issue。
3. 增加显式目标参数，例如：

   * `LABEBE_TARGET_ISSUE_IDENTIFIER=LAB-SMOKE-001`
   * 或 `LABEBE_TARGET_ISSUE_ID=<local issue id>`
4. 重新跑 smoke，让 evidence 显示：

   * selected issue = `LAB-SMOKE-001`
   * title = `CASE 1 - Data Truth Guard end-to-end smoke`
   * status before = `todo` 或 `in_progress`
   * next_status = `done`
   * artifact path 存在
   * Paperclip comment 已写入

---

### P0-2：issue identifier/title 漂移，破坏审计链路

**证据位置：**

* `paperclip_labebe_demo_package/.paperclip.yaml`
* `paperclip_labebe_demo_package/tasks/01-data-truth-foundation/TASK.md`
* `paperclip_labebe_demo_package/tasks/02-product-opportunity-radar/TASK.md`
* `outputs/heartbeat-data-truth-guard.json`
* `outputs/case-LAB-2-data-truth-guard.md`

**问题：**

`.paperclip.yaml` 定义：

```yaml
01-data-truth-foundation:
  identifier: "LAB-1"
02-product-opportunity-radar:
  identifier: "LAB-2"
```

但 heartbeat artifact 显示：

```text
Paperclip issue: LAB-2
Issue title: EPIC 1 - Data Truth Foundation
```

这说明 live Paperclip issue 与 package source of truth 不一致，可能是 import 顺序、手工修改、旧 issue 残留或 identifier 赋值漂移。

**影响：**

这是审计性 P0。Paperclip demo 的核心就是 issue/agent/artifact 追踪，如果 issue identifier 不能信，后续 review gates 也不能信。

**修复动作：**

导出 live issues 后做一次一致性校验：

```text
LAB-0 = EPIC 0 - CEO Strategy Approval
LAB-1 = EPIC 1 - Data Truth Foundation
LAB-2 = EPIC 2 - Product Opportunity Radar
LAB-3 = EPIC 3 - VOC to Product Concept
...
LAB-9 = EPIC 9 - Boss Demo Production
```

然后二选一：

* 修 live DB issue identifier/title，使其与 `.paperclip.yaml` 一致；
* 或重新清空该 demo company 的 issue tree 后从 package 重导入。

修复后把校验结果写入：

```text
evidence/issues_redacted.json
evidence/issue_consistency_check.json
```

---

### P0-3：runbook 描述的是 end-to-end smoke，但当前脚本默认会抢错 issue

**证据位置：**

* `runbooks/run-demo-case.md`
* `scripts/paperclip_demo_agent.py`

**问题：**

runbook 要求创建或复用：

```text
CASE 1 - Data Truth Guard end-to-end smoke
```

并期望 Data Truth Guard 将其 done。

但脚本 `_select_issue()` 当前按以下顺序选 issue：

```python
order = {"in_progress": 0, "in_review": 1, "todo": 2, "backlog": 3, "blocked": 4}
```

如果 Data Truth Guard 已经有一个 `in_progress` epic，它会优先选择该 epic，而不是新建的 `todo` smoke issue。当前 evidence 正是这种结果。

**影响：**

即使现场按 runbook 创建 smoke issue，heartbeat 也可能不跑 smoke issue，因此 demo 不能稳定闭环。

**修复动作：**

改成显式目标优先：

```python
target_identifier = os.environ.get("LABEBE_TARGET_ISSUE_IDENTIFIER", "").strip()

if target_identifier:
    candidates = [
        issue for issue in candidates
        if str(issue.get("identifier") or "") == target_identifier
    ]
else:
    candidates.sort(
        key=lambda issue: (
            0 if "end-to-end smoke" in str(issue.get("title") or "").lower() else 1,
            order.get(str(issue.get("status")), 99),
            str(issue.get("identifier") or ""),
        )
    )
```

并在 `.paperclip.yaml` 的 Data Truth Guard adapter env 中为 smoke demo 临时加入：

```yaml
LABEBE_TARGET_ISSUE_IDENTIFIER: "LAB-SMOKE-001"
```

演示完再移除或改回普通模式。

---

## 3. P1 问题

### P1-1：live desiredSkills 与 skill registry 不一致

**证据位置：**

* `workspace/config/skill-registry.yaml`
* `paperclip_labebe_demo_package/agents/*/AGENTS.md`
* `evidence/agents_redacted.json`
* `evidence/skills_redacted.json`

**问题：**

`skill-registry.yaml` 说：

* `paperclip-create-agent` 只给 `product-innovation-director`
* `labebe-product-concept-workflow` 给 7 个产品/设计/营销 agent
* `paperclip-demo-operator` 给所有 agent
* `labebe-demo-governance` 给所有 agent

但 `agents_redacted.json` 显示几乎所有 agent 都带：

```text
paperclip-create-agent
paperclip-create-plugin
para-memory-files
```

这与 registry 的“最小必要 skill”设计不一致。虽然本地上下文说明 built-in skills 是本地 Paperclip skill setup 自动带入、不是 Labebe demo 核心，但 live desiredSkills 仍会在审阅里造成“权限过宽/配置不一致”的印象。

**修复动作：**

最佳方案：live agent desiredSkills 与 `skill-registry.yaml` 对齐。

最低可接受方案：在 `skill-registry.yaml` 增加一段：

```yaml
ambient_paperclip_builtin_skills:
  paperclip-create-plugin:
    attached_by_setup: true
    used_by_demo: false
    risk: should_not_be_invoked
  para-memory-files:
    attached_by_setup: true
    used_by_demo: false
    risk: should_not_be_invoked
```

但我更建议直接 detach：

* `paperclip-create-agent`：只保留给 `product-innovation-director`
* `paperclip-create-plugin`：从所有 demo agent 移除
* `para-memory-files`：从所有 demo agent 移除，除非你能解释它的审计价值

---

### P1-2：process adapter 的 env contract 没有写清楚

**证据位置：**

* `.paperclip.yaml`
* `workspace/config/agent-runtime-matrix.yaml`
* `scripts/paperclip_demo_agent.py`
* `runbooks/run-demo-case.md`

**问题：**

`.paperclip.yaml` 每个 agent adapter env 只显式写了：

```yaml
LABEBE_AGENT_SLUG: "data-truth-guard"
```

但脚本要真正选 issue 和更新 Paperclip，需要：

```text
PAPERCLIP_API_URL
PAPERCLIP_API_KEY
PAPERCLIP_COMPANY_ID
PAPERCLIP_AGENT_ID
PAPERCLIP_RUN_ID  # mutation 追踪时应有
```

当前 evidence 里 `heartbeat-data-truth-guard.json` 的确有 agent_id/company_id 并成功更新了 Paperclip，说明本地运行时可能注入了这些变量。但包内 runbook 没有告诉审阅者这些 env 是 Paperclip 自动注入、mcp.env 注入，还是手工 shell 注入。

**影响：**

Pro/审阅者不能判断“为什么本地能更新 Paperclip，而 portable packet 只能 dry-run”。

**修复动作：**

在 `runbooks/run-demo-case.md` 增加一节：

```markdown
## Runtime Env Contract

The process adapter must receive:

- PAPERCLIP_API_URL: http://127.0.0.1:3100
- PAPERCLIP_COMPANY_ID: 1cb6d439-2bdf-4f63-ad9a-b5326d5546df
- PAPERCLIP_AGENT_ID: Data Truth Guard agent id from Paperclip
- PAPERCLIP_API_KEY: local agent API key, stored outside packet
- PAPERCLIP_RUN_ID: optional but required for audited mutating MCP/API calls
- LABEBE_AGENT_SLUG: data-truth-guard
- LABEBE_TARGET_ISSUE_IDENTIFIER: LAB-SMOKE-001
```

不要放真实 key，只说明来源和 placeholder。

---

### P1-3：MCP 配置安全方向正确，但没有工具白名单/禁用策略

**证据位置：**

* `workspace/config/mcp.paperclip.template.json`
* `workspace/config/mcp.env.example`
* `skills/paperclip-demo-operator/references/mcp-usage.md`
* `LOCAL_CONTEXT.md`

**当前优点：**

* `PAPERCLIP_API_URL` 是 loopback。
* `PAPERCLIP_API_KEY` 是 `${PAPERCLIP_API_KEY}` placeholder。
* `mcp.env.example` 没有真实 key。
* 本地 secret env 在 packet 外，且本地上下文说明权限为 `600`。
* MCP smoke test 已通过 `initialize` 和 `tools/list`。

**问题：**

`tools/list` 返回了 Paperclip tool surface，但包里没有：

* `evidence/mcp_tools_list_redacted.json`
* MCP tool allowlist
* MCP mutation denylist
* 哪些工具允许只读
* 哪些工具允许写 comment/status
* 哪些工具禁止 create agent / import skill / update adapter / delete company / secret 操作

**修复动作：**

新增：

```text
workspace/config/mcp-tool-policy.yaml
evidence/mcp_tools_list_redacted.json
evidence/mcp_policy_check.json
```

建议策略：

```yaml
schema: labebe-paperclip-demo/mcp-tool-policy/v1
default: deny
allow_read_only:
  - health/read instance
  - list companies
  - read company
  - list agents
  - read agent
  - list skills
  - list issues
  - read issue
allow_mutation_only_for_target_smoke:
  - checkout issue
  - create issue comment
  - update issue status
conditions:
  company_id: 1cb6d439-2bdf-4f63-ad9a-b5326d5546df
  issue_identifier: LAB-SMOKE-001
  require_paperclip_run_id: true
deny:
  - create agent
  - update agent adapter config
  - delete agent
  - delete company
  - import unreviewed skill
  - update secret
  - expose secret
  - call external account
```

真实 tool 名称应以 `tools/list` 导出的实际名称为准，不要只写抽象类别。

---

### P1-4：package 不够自包含，很多配置使用绝对路径

**证据位置：**

* `.paperclip.yaml`
* `workspace/config/agent-runtime-matrix.yaml`
* `workspace/config/mcp.paperclip.template.json`
* `workspace/config/skill-registry.yaml`
* `paperclip_labebe_demo_package/configs/*.yaml`

**问题：**

大量路径硬编码为：

```text
/vol1/1000/projects/toyresearch/...
/vol1/1000/projects/paperclip/...
```

对原机器可运行，但对 Pro/审阅者复现不友好。

`paperclip_labebe_demo_package/configs/*.yaml` 不是实际配置内容，而是：

```yaml
see: /vol1/1000/projects/toyresearch/labebe-ai-design-studio/workspace/config/...
```

这会让 company package 本身不像完整 portable package。

**修复动作：**

1. `paperclip_labebe_demo_package/configs/` 直接复制完整 YAML，不要只写 `see:`。
2. 增加 `.env.example`：

```bash
LABEBE_WORKSPACE_ROOT=/vol1/1000/projects/toyresearch/labebe-ai-design-studio/workspace
PAPERCLIP_REPO_ROOT=/vol1/1000/projects/paperclip
PAPERCLIP_API_URL=http://127.0.0.1:3100
```

3. `.paperclip.yaml` 保留本机绝对路径，但旁边加 `paperclip.local.template.yaml`，说明替换变量后的路径。
4. runbook 明确：外部 reviewer 不需要真实 key；只能做 static review 和 no-API dry run，本机 operator 才能做 live Paperclip update。

---

### P1-5：当前 “end-to-end case” 其实只是 Data Truth 单 agent smoke

**证据位置：**

* `runbooks/run-demo-case.md`
* `outputs/case-LAB-2-data-truth-guard.md`
* `skills/labebe-product-concept-workflow/SKILL.md`

**问题：**

`labebe-product-concept-workflow` 描述的端到端链路包括：

```text
VOC → competitor → opportunity → concept brief → image prompt → design review → DFM/safety → asset matrix
```

但当前 runbook 的 case 只验证：

```text
Data Truth Guard reads docs → writes heartbeat artifact → comments issue → marks done
```

这对证明 Paperclip 控制面闭环是足够的，但对证明 “Labebe AI Design Studio turns signals into concept/launch assets” 不够。

**修复动作：**

把 case 分成两层：

```text
Case A: Control-plane smoke
- Data Truth Guard
- 1 issue
- 1 artifact
- 1 comment
- status done

Case B: Board narrative E2E
- LAB-1 Data Truth
- LAB-2 Opportunity Radar
- LAB-3 VOC Concept Brief
- LAB-6 Design Director Review
- LAB-7 DFM/Safety blocked gate
- LAB-8 Asset Matrix draft/demo
```

15 分钟老板演示用 Case A 现场跑，Case B 用预生成 artifact + Paperclip issue trail 展示。

---

## 4. P2 问题

### P2-1：Multica/runtime 只是背景事实，没有进入 package contract

本地上下文列出了 Multica CLI、version、server、active runtimes、OpenClaw 排除、Codex `.codex1` lane 等事实。 但 `agent-runtime-matrix.yaml` 只写了 Paperclip `process` adapter，没有写 Multica 是 demo 非执行路径。

这不是 P0，因为本 demo 可以完全 process-only。但为了审阅一致性，建议加：

```yaml
multica_boundary:
  used_in_this_demo: false
  observed_runtimes:
    - codex
    - hermes
    - gemini
    - claude
    - kimi
  excluded:
    - openclaw
  codex_lane: ".codex1"
  reason: "Paperclip demo uses deterministic process adapter; Multica runtime integration is future work."
```

这样审阅者不会误以为 Multica 缺配置。

---

### P2-2：agent 指令不错，但缺少输出 schema 和状态转移规则

每个 `agents/*/AGENTS.md` 都有角色、职责、禁用行为，这是合格的第一版。

弱点是缺：

* 输入文件清单；
* 输出 artifact schema；
* issue 状态转移规则；
* review gate owner；
* 对失败/blocked 的 comment 模板；
* 对 source label 的最小字段要求。

建议每个 agent 增加：

```markdown
## Inputs
- docs/DATA_TRUTH.md
- data/review_signal_samples.csv
...

## Required Artifact
- path pattern:
- required header:
- required sections:
- required source labels:

## Status Rules
- todo/backlog → in_progress only after checkout
- in_progress → in_review when artifact exists
- in_review → done only after human gate or smoke title
- blocked when required review is missing
```

---

### P2-3：heartbeat evidence 版本不一致

8 个 heartbeat JSON 是旧格式，只包含：

```json
agent, status, timestamp_utc, summary, missing_required_docs, paperclip_agent_id, paperclip_company_id
```

只有 `heartbeat-data-truth-guard.json` 是新格式，包含：

```json
selected_issue, artifact, paperclip_update, api_error
```

建议用当前脚本重新跑 9 个 agent，或者在 evidence README 里说明：

```text
Only heartbeat-data-truth-guard.json is the full live closeout proof.
The other heartbeat files are role-presence smoke artifacts.
```

老板演示前最好全部重新生成，避免 UI 上看起来像 stale evidence。

---

### P2-4：缺 artifact ledger / secret scan evidence

当前包内没有：

```text
evidence/artifact_ledger.json
evidence/secret_scan.txt
evidence/package_manifest.txt
```

建议增加：

```json
{
  "artifact": "labebe-ai-design-studio/workspace/outputs/case-LAB-SMOKE-001-data-truth-guard.md",
  "sha256": "...",
  "size_bytes": 1234,
  "source_labels": ["demo_policy", "demo_sample"],
  "contains_raw_secret": false,
  "paperclip_issue_identifier": "LAB-SMOKE-001",
  "paperclip_status_after": "done"
}
```

---

## 5. skills 设计审阅

### 现状判断

**第一版合理。** 3 个 local skills 的分工是清楚的：

1. `labebe-demo-governance`
   管数据真相、禁用声明、人审门禁、source labels。

2. `labebe-product-concept-workflow`
   管 VOC、竞品、机会、概念、设计评审、DFM、安全、资产矩阵。

3. `paperclip-demo-operator`
   管 Paperclip heartbeat、issue、artifact、demo replay。

这个拆分比把所有内容塞进一个大 skill 更好，也比过早拆成 10 个 micro-skills 更适合第一版。

### 应该保留的设计

* `governance` 和 `operator` 不要合并。一个管 claim truth，一个管 Paperclip 操作，边界正确。
* `labebe-product-concept-workflow` 作为第一版 umbrella workflow 是可以的，因为 process adapter 不做真正 skill injection，拆太细没有收益。
* `data-truth-guard` 不需要 product workflow skill；它的职责是守门，不是产出概念。

### 应该调整的设计

**当前最大问题不是 skill 写得不好，而是 live assignment 不一致。**

应修成：

```text
All agents:
- paperclip
- labebe-demo-governance
- paperclip-demo-operator

Product/Design/Market agents:
- labebe-product-concept-workflow

Only Product Innovation Director:
- paperclip-create-agent

Nobody in first demo unless explicitly needed:
- paperclip-create-plugin
- para-memory-files
```

### 90 分前建议补充的 skill

新增一个轻量 skill：

```text
labebe-artifact-contract
```

职责：

* artifact header；
* source labels；
* human review field；
* issue identifier；
* artifact hash；
* secret scan；
* status transition evidence。

这会比继续扩展产品 workflow 更有审计价值。

---

## 6. MCP 配置审阅

### 当前是否足够安全？

**对 local-only demo 基本安全；对可审计 mutation demo 还不够。**

安全点：

* URL 是 `127.0.0.1:3100`。
* API key 是 placeholder。
* 本地 `mcp.env` 不在 packet。
* 本地上下文说明 `mcp.env` mode 是 `600`。
* 没有真实外部账号。
* 没有真实 customer data。
* 不要求真实 API key/token。

不足点：

* 没有导出 `tools/list` 结果。
* 没有 MCP allowlist。
* 没有 MCP mutation policy。
* 没有说明哪些 mutating tools 必须绑定 `PAPERCLIP_RUN_ID`。
* 没有禁止 agent/skill/adapter/secrets 变更的机器可读策略。
* 模板依赖绝对路径 `/vol1/1000/projects/paperclip/cli/node_modules/tsx/...`，可运行但不够 portable。

### 建议

MCP 第一版只允许做三类事：

```text
1. Read:
   health, company, agents, skills, issues, comments

2. Controlled write:
   checkout target smoke issue
   comment on target smoke issue
   patch target smoke issue status

3. Deny:
   create/update/delete agents
   update adapterConfig
   import skills
   update secrets
   delete company/project/issue
   call external accounts
```

同时将 `PAPERCLIP_RUN_ID` 加入模板：

```json
"PAPERCLIP_RUN_ID": "${PAPERCLIP_RUN_ID}"
```

这样 comment/status mutation 能挂到 heartbeat run。

---

## 7. agent 配置审阅

### 当前完整度

**角色定义足够清楚，但运行/验收配置偏弱。**

9 个 agent 选择合理，没有过度膨胀：

* Product Innovation Director
* Data Truth Guard
* VOC Intelligence Analyst
* Competitive Radar Analyst
* Design Strategy Agent
* Design Director Agent
* DFM & Safety Preflight Agent
* Concept-to-Market Agent
* Demo Producer Agent

这符合“少而强”的 demo 方向。

### 主要弱点

1. **live skills 过宽**
   `paperclip-create-agent`、`paperclip-create-plugin`、`para-memory-files` 不应出现在多数 agent 的 desiredSkills。

2. **没有 per-agent artifact contract**
   例如 VOC agent 应输出 requirement map，DFM agent 应输出 risk/preflight checklist，Concept-to-Market agent 应输出 asset matrix。现在多是自然语言规则。

3. **review gates 不是机器可读**
   `agent-runtime-matrix.yaml` 有 `human_review_required_for`，但 task/agent/status 之间没有强约束。

4. **没有预算/权限/adapter mutation 禁止字段**
   `.paperclip.yaml` 只有 adapter config，没有 agent permissions、budget、allowed actions。如果 Paperclip 支持这些字段，应补；如果不支持，应在 `agent-runtime-matrix.yaml` 显式声明“由 policy 文档约束，不由平台强制”。

5. **Data Truth smoke 与设计链路割裂**
   当前 Data Truth 能跑，但没有证明 LAB-2/LAB-3/LAB-6/LAB-8 的 artifact contract。

### 建议补充

给每个 agent 增加一个 `contract` block，例如：

```yaml
agent_contracts:
  voc-intelligence-analyst:
    allowed_inputs:
      - data/review_signal_samples.csv
      - docs/DATA_TRUTH.md
    required_outputs:
      - outputs/voc-requirement-map-*.md
    blocked_claims:
      - representative sentiment
      - verified demand
    next_review_gate: data-truth-guard
```

---

## 8. process adapter 是否适合作为第一版 demo

**适合，而且应该保留。**

原因：

* 第一版目标是证明 Paperclip control plane、治理、issue flow、skill registry、MCP、heartbeat evidence，不是证明模型创意能力。
* process adapter 是 deterministic，适合老板演示，不依赖付费模型、不依赖外部账号、不受模型 latency 和 token 影响。
* 本地上下文也明确：process adapter 当前记录 desired skills，但不会把 skill 文件注入 child process；脚本因此直接读 workspace docs。这个限制已经被如实记录。

老板演示里应该这样解释：

> “今天这个 live smoke 是飞行模拟器，不是完整 AI 推理。我们故意用 deterministic process adapter 来证明 Paperclip 可以管理公司、agent、issue、skill、MCP、heartbeat、artifact、review gate。真正的 AI 创意生成可以后续替换成 Codex/Claude/HTTP creative service，但控制面、审批面和证据链不变。”

这句话很关键。它避免老板误解：

* Paperclip 不是生图/CAD/营销投放引擎；
* process adapter 不是 AI reasoning；
* demo 的价值是治理、审计、可控执行闭环。

替代方案不是把第一版全换成 LLM adapter。更好的路线是：

```text
主路径：process adapter live smoke
辅路径：一个可选 non-mutating LLM/HTTP artifact demo
兜底：预生成 concept artifacts + Paperclip issue trail
```

---

## 9. demo 背景、任务、目标、运行条件、验收条件是否完整

### 背景与目标

基本完整。

`demo-brief.yaml` 已经说清楚：

* purpose；
* business context；
* control plane context；
* main goal；
* operating conditions；
* success criteria；
* known limits。

`COMPANY.md` 和 `PROJECT.md` 也能说明 demo 是私有本地、red-team gated、只用本地 demo data。

### 任务树

10 个 epic 覆盖完整：

```text
LAB-0 CEO Strategy Approval
LAB-1 Data Truth Foundation
LAB-2 Product Opportunity Radar
LAB-3 VOC to Product Concept
LAB-4 Sketch-to-Concept Lab
LAB-5 Custom Toy Kitchen Builder
LAB-6 Design Director Review
LAB-7 DFM / Safety / Cost Preflight
LAB-8 Concept-to-Market Asset Matrix
LAB-9 Boss Demo Production
```

这个结构适合老板演示。

### 运行条件

完整但需要更精确：

现在写了 loopback、无真实账号、无真实客户数据、无 raw secrets、人审 gates。还应补：

* Paperclip health endpoint check；
* tmux session name；
* workspace root；
* Paperclip repo root；
* process adapter env contract；
* target smoke issue；
* expected artifact path；
* evidence export commands。

### 验收条件

目前偏叙述型，不够机器可验收。

建议把 success criteria 改成：

```yaml
acceptance:
  health:
    - evidence/paperclip_health.json.status == ok
  company:
    - company_id matches all configs
  agents:
    - count == 9
    - adapterType == process for all
  skills:
    - local governance skill compatible
    - local workflow skill compatible
    - live desiredSkills match registry
  mcp:
    - template contains no raw key
    - tools/list exported
    - allowlist policy present
  smoke:
    - issue_identifier == LAB-SMOKE-001
    - selected_issue.title contains end-to-end smoke
    - artifact exists
    - paperclip_update.next_status == done
    - issue comment includes artifact path
  safety:
    - no real external account
    - no raw secret grep hits
    - all sample outputs labeled demo_sample/demo_policy
```

---

## 10. 最推荐的端到端案例跑法

### 目标

证明一个最小闭环：

```text
Paperclip issue → assigned agent → process heartbeat → local artifact → Paperclip comment → status done → evidence export
```

### 准备

创建或修正一个目标 issue：

```text
Identifier: LAB-SMOKE-001
Title: CASE 1 - Data Truth Guard end-to-end smoke
Assignee: Data Truth Guard
Status: todo
Priority: high
```

### 修改 adapter env

在 Data Truth Guard 的 process adapter env 中加入：

```yaml
LABEBE_AGENT_SLUG: "data-truth-guard"
LABEBE_TARGET_ISSUE_IDENTIFIER: "LAB-SMOKE-001"
```

API key 仍然只放本地 env，不进 packet。

### 触发

从 Paperclip UI 触发 Data Truth Guard heartbeat，或用本地已授权 API 触发。

### 预期输出

本地 artifact：

```text
labebe-ai-design-studio/workspace/outputs/case-LAB-SMOKE-001-data-truth-guard.md
```

heartbeat JSON：

```text
labebe-ai-design-studio/workspace/outputs/heartbeat-data-truth-guard.json
```

字段必须满足：

```json
{
  "agent": "data-truth-guard",
  "status": "ok",
  "missing_required_docs": [],
  "selected_issue": {
    "identifier": "LAB-SMOKE-001",
    "title": "CASE 1 - Data Truth Guard end-to-end smoke"
  },
  "artifact": ".../outputs/case-LAB-SMOKE-001-data-truth-guard.md",
  "paperclip_update": {
    "next_status": "done"
  },
  "api_error": null
}
```

Paperclip issue 必须有 comment：

```text
Demo heartbeat completed.
Agent: data-truth-guard
Artifact: outputs/case-LAB-SMOKE-001-data-truth-guard.md
Source labels: demo_sample, demo_policy
Human review required...
```

### 导出 evidence

最终 evidence 包应有：

```text
evidence/paperclip_health.json
evidence/agents_redacted.json
evidence/skills_redacted.json
evidence/issues_redacted.json
evidence/mcp_tools_list_redacted.json
evidence/mcp_policy_check.json
evidence/output_files.txt
evidence/artifact_ledger.json
evidence/secret_scan.txt
```

---

## 11. 最终 smoke case 验收清单

### A. Paperclip 实例

* [ ] `paperclip_health.json.status == "ok"`
* [ ] `deploymentMode == "local_trusted"`
* [ ] `deploymentExposure == "private"`
* [ ] `authReady == true`
* [ ] Paperclip URL 是 `http://127.0.0.1:3100`

### B. Company / Project / Issue

* [ ] Company ID 在以下文件中一致：

  * `LOCAL_CONTEXT.md`
  * `agent-runtime-matrix.yaml`
  * `skill-registry.yaml`
  * `mcp.paperclip.template.json`
  * evidence JSON
* [ ] `issues_redacted.json` 非空
* [ ] 10 个 epic identifier/title 完全匹配 `.paperclip.yaml`
* [ ] `LAB-SMOKE-001` 存在
* [ ] `LAB-SMOKE-001` assignee 是 Data Truth Guard
* [ ] smoke 运行后 status 是 `done`

### C. Agents

* [ ] `agents_redacted.json` 有 9 个 agent
* [ ] 9 个 agent 全部 `adapterType == process`
* [ ] 没有 stale `running` 状态，除非正处于现场运行
* [ ] desiredSkills 与 `skill-registry.yaml` 一致
* [ ] `paperclip-create-agent` 只给 Product Innovation Director
* [ ] `paperclip-create-plugin` 和 `para-memory-files` 不作为 demo 核心 skill 展示

### D. Skills

* [ ] `labebe-demo-governance` compatible，attachedAgentCount = 9
* [ ] `labebe-product-concept-workflow` attached 到 7 个产品/设计/营销 agent
* [ ] `paperclip-demo-operator` attachedAgentCount = 9
* [ ] skill docs 包含 source labels、review gates、artifact header
* [ ] process adapter skill injection limitation 已在 runbook 明确说明

### E. MCP

* [ ] `mcp.paperclip.template.json` 只有 placeholder，没有 raw key
* [ ] `mcp.env.example` 只有 placeholder
* [ ] `mcp_tools_list_redacted.json` 已导出
* [ ] `mcp-tool-policy.yaml` 存在
* [ ] 默认 deny
* [ ] 只允许读 company/agent/skill/issue
* [ ] mutation 只允许 target smoke issue checkout/comment/status
* [ ] 禁止 agent create/update、adapterConfig update、skill import、secret update、company delete

### F. Artifact

* [ ] `outputs/case-LAB-SMOKE-001-data-truth-guard.md` 存在
* [ ] artifact header 包含：

  * Paperclip issue
  * Owner agent
  * Source labels
  * Human review required
  * Output status
* [ ] artifact 没有 production safety/compliance/cost/market demand claims
* [ ] artifact 明确标记 demo/sample/policy
* [ ] artifact path 出现在 Paperclip comment
* [ ] artifact ledger 记录 sha256/size/secret scan 结果

### G. No secrets / no external action

* [ ] evidence 包 secret scan 无 raw API key/token
* [ ] 没有真实 customer data
* [ ] 没有真实 marketplace/ad/email/CRM action
* [ ] 所有外部发布、成本、安全、DFM、compliance-adjacent 内容仍是 human review gate

---

## 12. 15 分钟老板演示结构

### 0:00–1:00 — 设定边界

核心话术：

> “今天不是演示 AI 自动发明产品并直接上线，而是演示 Paperclip 如何作为 Labebe AI Design Studio 的本地控制面：组织 agent、分配 issue、执行 heartbeat、留下证据、卡住风险。”

画面：

* `demo-brief.yaml`
* Paperclip health
* Company dashboard

### 1:00–2:30 — 公司与组织图

展示：

* Labebe AI Design Studio company
* 9 个 agent
* Product Innovation Director 作为 lead
* Data Truth / VOC / Competitor / Design / DFM / Market / Demo Producer 分工

强调：

> “这不是一个聊天窗口，是一个有职责、汇报线和任务板的 AI 团队控制台。”

### 2:30–4:00 — 数据真相与禁用声明

展示：

* `DATA_TRUTH.md`
* `FORBIDDEN_CLAIMS.md`
* `ACTION_POLICY.md`
* `DEMO_SAMPLE_POLICY.md`

强调：

> “demo sample 不能变成市场事实；安全、成本、认证、发布都必须人审。”

### 4:00–5:30 — Skill 和 MCP

展示：

* `skill-registry.yaml`
* `mcp.paperclip.template.json`
* `mcp.env.example`

强调：

> “真实 key 不在包里；MCP 是本地 loopback；第一版只允许 Paperclip 控制面操作。”

如果已修 MCP allowlist，现场展示 `mcp-tool-policy.yaml`。

### 5:30–8:30 — Live smoke

现场触发：

```text
LAB-SMOKE-001
CASE 1 - Data Truth Guard end-to-end smoke
```

展示状态变化：

```text
todo → in_progress → done
```

展示输出：

* heartbeat JSON
* artifact markdown
* Paperclip comment

核心话术：

> “这个 deterministic process adapter 是为了证明控制面闭环，不是为了证明完整 AI 推理。”

### 8:30–10:30 — 从 smoke 扩展到产品设计链路

展示任务树：

* LAB-1 Data Truth
* LAB-2 Product Opportunity
* LAB-3 VOC to Product Concept
* LAB-6 Design Director Review
* LAB-7 DFM/Safety blocked
* LAB-8 Asset Matrix draft/demo

强调：

> “真实业务链路会分阶段推进，每个阶段都有 review gate。”

### 10:30–12:00 — 风险板

展示：

* `LAB-7` blocked
* safety/cost/DFM review gate
* forbidden claims

核心话术：

> “我们把风险显性化，而不是藏在漂亮 demo 后面。”

### 12:00–13:30 — 后续路线

展示：

```text
Phase 1: process adapter deterministic smoke
Phase 2: one optional LLM/HTTP creative service
Phase 3: controlled concept artifact chain
Phase 4: front-end AI Design Studio showpiece
```

强调：

> “Paperclip 控制面不变，执行层可以替换。”

### 13:30–15:00 — 要老板拍板的事项

明确要决策：

* 是否批准继续做 Case B：board narrative E2E
* 是否允许接一个非外部发布的 LLM/HTTP creative service
* 是否批准前端 AI Design Studio showpiece
* 是否保持真实账号和外部发布禁用

---

## 13. 到 90 分还差什么

从 78 到 90，需要完成这 7 件事：

1. **修 P0 smoke**
   `LAB-SMOKE-001` 必须真实 done，artifact/comment/evidence 全部对齐。

2. **修 issue identifier/title drift**
   `LAB-1`、`LAB-2` 等 live issue 必须和 `.paperclip.yaml` 一致。

3. **导出非空 issue evidence**
   `issues_redacted.json` 不能是 0 字节。

4. **修 desiredSkills mismatch**
   移除或解释 `paperclip-create-agent`、`paperclip-create-plugin`、`para-memory-files` 的过宽 attachment。

5. **补 MCP tool policy 和 tools/list evidence**
   不能只说 MCP smoke passed，要把工具面和禁用策略放进包里。

6. **补可复现 runbook**
   包含 env contract、target issue、触发方式、预期 JSON 字段、导出证据步骤。

7. **补 artifact ledger / secret scan**
   让审阅者能验证 output 文件、hash、secret-free、source labels、review gates。

达到这些后，这个 demo 就可以比较自信地说：

> “Paperclip 作为本地控制面，已经能承载 Labebe AI Design Studio 的 agent、issue、skill、MCP、heartbeat、artifact 和 human review gate，并能跑通一个可审计 smoke case。”

现在还只能说：

> “配置骨架和治理设计已经成型，但 smoke closeout 和 evidence export 还没达标。”
