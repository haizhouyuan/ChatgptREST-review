# Labebe AI Design Studio — Shared Boss Demo Pack
**Lane:** Claude Code Kimi (Paperclip shared-runtime synthesis lane)
**Runtime route:** `/home/yuanhaizhou/.local/bin/claudekimi` through Paperclip `claude_local`
**Model evidence:** raw stream-json in `claudeKimi_run.json` reports `model: kimi-for-coding`; Paperclip aggregate `usageJson` also reports the Claude Code default/accounting metadata (`claude-sonnet-4-6` / `anthropic`), so the aggregate field is treated as a wrapper metadata conflict, not as the upstream model truth for this lane.
**Artifact path:** `outputs/claude_kimi_code_demo.md`
**Evidence base:** Local files only — no internet sources, no fabricated metrics
**Companion artifacts:** `outputs/claude_code_demo.md` (Claude lane) · `outputs/kimi_demo.md` (Kimi lane)

---

## Executive Demo Narrative

**What this demo proves:** Paperclip is the local control plane for Labebe AI Design Studio — not a magic AI box, but an orchestration and governance layer that organizes agents, assigns issues, executes heartbeats, captures evidence, and gates risky claims behind human review. The Runtime Duel proves that two different local runtimes — Claude Code and Kimi — can produce the same governed output from the same control plane.

The demo is intentionally scoped to a **deterministic process adapter** running on loopback. This is a flight simulator, not full AI reasoning. The value is in the control plane: auditable issue-to-artifact chains, skill registries, MCP tool policies, and evidence ledgers that a boss can trust without needing to verify every AI output.

> *"Today you will not see AI autonomously inventing and launching a toy product. You will see Paperclip run an AI team: organized, gated, evidenced, and stoppable. And you will see that the control plane works no matter which runtime is at the wheel."*

**Runtime truth:** The Claude Code Kimi lane runs through Paperclip's `claude_local` adapter, but its configured command is the local `claudekimi` wrapper. The wrapper routes Claude Code-compatible calls to the Kimi coding endpoint, and the raw stream-json messages in the run log report `model: kimi-for-coding`. Paperclip's aggregate `usageJson` still reports Claude Code default/accounting metadata (`claude-sonnet-4-6` / `anthropic`), so this artifact records the conflict explicitly instead of treating the aggregate field as upstream model truth. The duel compares output quality and governance discipline, not brand prestige.

**Fact:** Both individual lane artifacts (`claude_code_demo.md` and `kimi_demo.md`) were produced from the identical evidence base and rubric, and both passed deterministic rubric scoring at 100/100. *(Source: `outputs/evidence/scorecard.json`)*

---

## What The Boss Should See In 90 Seconds

### 0:00–0:15 — The Setup
Show the Paperclip company dashboard at `http://127.0.0.1:3100`.
- Company: **Labebe AI Design Studio**
- 9 agents, all `process` adapter (deterministic, loopback)
- 10 issues (LAB-0 through LAB-9) covering product concept pipeline
- Skills: governance, product workflow, demo operator

**Boss takeaway:** A real AI team control console, not a chatbot.

### 0:15–0:35 — The Duel Framing
Show both lane artifacts side by side: `claude_code_demo.md` and `kimi_demo.md`.
- Same 12-section schema, same evidence base, same rubric
- Different prose style, different creative emphasis
- Same governance discipline, same fact labels, same forbidden claims

**Boss takeaway:** Paperclip is runtime-agnostic. The control plane enforces quality no matter which engine is driving.

### 0:35–0:55 — Live Smoke Run
Trigger `LAB-SMOKE-001` ("CASE 1 - Data Truth Guard end-to-end smoke") on the Data Truth Guard agent.
Watch the issue move: `todo → in_progress → done`.

Show in real time:
1. `paperclipCheckoutIssue` — agent claims the issue
2. Artifact written to `outputs/case-LAB-SMOKE-001-data-truth-guard.md`
3. `paperclipAddComment` — comment written to the issue
4. `paperclipUpdateIssue` — status set to `done`

**Boss takeaway:** Every action is issue-bound, agent-assigned, and evidenced.

### 0:55–1:15 — Where The AI Cannot Go
Show the blocked issue `LAB-7` (DFM / Safety / Cost Preflight) and the `FORBIDDEN_CLAIMS.md` list.
- No agent can claim real customer demand, verified safety certification, or production launch date without human sign-off.
- MCP tool policy shows: no `create agent`, no `update adapter`, no `delete company`, no `update secret`.

**Boss takeaway:** Paperclip has gates, not just automation.

### 1:15–1:30 — The Synthesis
> *"Two runtimes, one control plane, zero ungoverned claims. That's the Labebe AI Design Studio."*

**Boss takeaway:** The demo is not about which AI is smarter. It is about whether your team can manage, audit, and trust the AI output — regardless of the engine.

---

## Control Plane Architecture

### Paperclip as Governance Layer

```
┌─────────────────────────────────────────────────────┐
│  Paperclip Control Plane  (http://127.0.0.1:3100)  │
│                                                     │
│  Company: Labebe AI Design Studio                  │
│  Company ID: 1cb6d439-2bdf-4f63-ad9a-b5326d5546df │
│  Deployment: local_trusted / private / loopback      │
└──────────────────┬──────────────────────────────────┘
                   │
     ┌─────────────┼─────────────────────────────────┐
     │             │                                 │
  ┌──▼──┐    ┌────▼────┐    ┌─────────────────┐   │
  │Issue │    │ Skills  │    │  MCP Tool Policy │   │
  │Tree  │    │Registry │    │  allow/deny list │   │
  │LAB-0 │    │3 skills │    │  read-only except│   │
     │    │    │attached│    │  LAB-SMOKE-001   │   │
  ┌──▼────▼┐  └─────────┘    └─────────────────┘   │
  │Agents  │                                            │
  │ 9 ×   │                                            │
  │process│                                            │
  │adapter│                                            │
  └────────┘                                            │
```

### Runtime Alias Separation — The Duel Matrix

| Lane | Runtime | Adapter | Model/Provider Evidence | Evidence Source | Artifact |
|------|---------|---------|------------------------|-----------------|----------|
| **Claude Code** | `claude_local` | Paperclip `claude_local` | `MiniMax-M2.7` / `anthropic` | `claude_run.json` `usageJson.model` + `usageJson.provider` | `claude_code_demo.md` |
| **Kimi** | `kimi_cli` | Paperclip `kimi_cli` | `kimi-for-coding` (configured only) | `runtime_config_redacted.json` `adapterConfig.model`; `kimi_run.json` confirms `usageJson: null` | `kimi_demo.md` |
| **Claude Code Kimi** (this artifact) | `claude_local` | Paperclip `claude_local` command `/home/yuanhaizhou/.local/bin/claudekimi` | `kimi-for-coding` in raw stream-json; aggregate `usageJson` conflict: `claude-sonnet-4-6` / `anthropic` | `claudeKimi_run.json` log stream + agent `adapterConfig.command` | `claude_kimi_code_demo.md` |

**Fact:** All three lanes share the same company, same issue tree, same skill registry, same MCP policy. The runtime alias ensures lane isolation — one lane's agent config cannot affect another's.

**Inference:** The fact that all three artifacts converged on the same 12-section schema, same evidence labels, and same governance boundaries proves that Paperclip's control plane is the dominant variable in output quality, not the runtime brand.

### Issue/Agent/Heartbeat/Artifact Flow

```
Issue assigned
    │
    ▼
Agent heartbeat fires
    │  (PAPERCLIP_RUN_ID injected by Paperclip)
    ▼
process adapter reads workspace docs
    │
    ▼
Artifact written to outputs/
    │
    ├── Paperclip comment ← paperclipAddComment (status: Demo heartbeat completed.)
    └── Issue status update ← paperclipUpdateIssue (target: LAB-SMOKE-001 only)
```

MCP mutations are gated by `PAPERCLIP_RUN_ID` and limited to `LAB-SMOKE-001`.

### Paperclip Env Injection Contract

For the process adapter to reach Paperclip, these env vars are injected at runtime by Paperclip (not stored in the portable packet):

| Variable | Purpose | Stored in packet? |
|----------|---------|------------------|
| `PAPERCLIP_API_URL` | Loopback Paperclip API | Template only — no raw key |
| `PAPERCLIP_API_KEY` | Local agent key | Never — lives outside packet |
| `PAPERCLIP_COMPANY_ID` | Company ID | Yes (name only, not secret) |
| `PAPERCLIP_AGENT_ID` | Agent ID for this run | Injected at runtime |
| `PAPERCLIP_RUN_ID` | Run traceability | Injected at runtime for mutations |
| `LABEBE_TARGET_ISSUE_IDENTIFIER` | Smoke target | Yes (value: `LAB-SMOKE-001`) |

**Fact:** Raw API keys are never in the portable packet or evidence export. Evidence files use `PAPERCLIP_API_KEY` placeholder.

---

## Same-Goal Generation Plan

Both Claude Code and Kimi lanes produce an identical-schema artifact from the same evidence base. This is a **controlled comparison**, not a race. The shared lane (this artifact) synthesizes both outputs into a unified boss demo pack.

### Shared Constraints
- Evidence base: local files only (no internet)
- Output schema: 12-section boss demo pack
- Scoring rubric: `rubric_100.yaml` (100-point)
- Target score: 95+

### What Each Lane Owns

| Concern | Claude Code Lane | Kimi Lane | Shared Lane (this artifact) |
|---------|-----------------|-----------|----------------------------|
| Artifact | `claude_code_demo.md` | `kimi_demo.md` | `claude_kimi_code_demo.md` |
| Self-score | 100/100 | 97/100 | Targets 95+ |
| Creative emphasis | Control-plane precision, four stage moments | Six demo stations, two-skin design system | Synthesis: best of both |
| Wow factor | Premium toy/home lifestyle concept | SpaceSmart Foldable Learning Tower + custom kitchen builder | Unified 6-station narrative |
| Governance | Fact/Inference/Hypothesis, 16 evidence entries | Fact/Inference/Hypothesis, 8 evidence entries | Combined ledger with cross-lane citations |
| Model truth | `MiniMax-M2.7` from run evidence | `kimi-for-coding` from adapterConfig | `claudekimi` route cites raw stream-json `kimi-for-coding` and separately records the aggregate `usageJson` conflict |

### Cross-Lane Comparison — What Stayed Constant

**Fact:** Both artifacts contain all 12 required sections with zero missing. *(Source: `scorecard.json`, `missingSections: []` for both lanes)*

**Fact:** Both artifacts labeled claims with `Fact`, `Inference`, or `Hypothesis`. Claude lane: 29 Facts, 4 Inferences, 3 Hypotheses. Kimi lane: 34 Facts, 6 Inferences, 8 Hypotheses. *(Source: `scorecard.json`, `labelCounts`)*

**Fact:** Neither artifact contained fabricated external metrics, fake customer claims, or secrets. Both passed deterministic rubric scoring. *(Source: `scorecard.json`, `score: 100` for both lanes)*

### Cross-Lane Comparison — Where They Differed

| Dimension | Claude Lane | Kimi Lane | Shared Lane Resolution |
|-----------|------------|-----------|----------------------|
| 90-second script | Four stage moments (dashboard, smoke, blocked gate, concept pipeline) | Eight-beat montage with product shots and scorecards | Combined: dashboard + smoke + blocked gate + concept pipeline + scorecard close |
| Visual direction | Paperclip dashboard + artifact split view | Two-skin design system (consumer warm + control room dark) | Both: Paperclip UI for control plane, two-skin frontend for product layer |
| Agent contracts | Per-agent header requirements | Per-agent role + adapter + review gate tables | Combined: org chart + role table + header contract |
| Open decisions | Phase 2 LLM, frontend showpiece, artifact ledger automation | Case B scope, LLM adapter, frontend build, external accounts, LangGraph | Unified decision table with recommended options |

**Inference:** The differences are stylistic and creative, not structural or governance-related. Both lanes correctly identified the same P0 gaps (smoke closure, issue identifier drift, desiredSkills mismatch). Both correctly labeled the same runtime evidence classes.

### Verification

The rubric has a **fail condition** on missing evidence ledger and missing self-score. All lanes must include a completed `## Evidence Ledger` and `## Final Self-Score` section.

---

## The Premium Labebe Demo Concept

### Elevator Pitch
Labebe AI Design Studio is a **red-team-gated AI product design team** that turns voice-of-customer (VOC) signals, competitor data, and design briefs into concept assets — but never ships a claim, a cost figure, or a safety certification without a human gate.

The product concept is a **toy/home lifestyle brand** — premium materials, modular design, parent-child interaction focus. The AI team's job is to surface opportunity and generate concepts; a human boss owns the go/no-go.

**Fact:** Labebe is a scenario-based children's growth-space brand with 46 SKUs across furniture, rockers/ride-ons, pretend-play, and activity/educational toys. *(Source: `sdd.md`, DATA_TRUTH section)*

### Stage Moments

**Moment 1 — The Dashboard (wow):** A single Paperclip company view shows 9 agent cards, a 10-issue pipeline board, and a live heartbeat ticker. Each agent has a role, a skill set, and a current assignment. The word "team" is literal, not metaphorical.

**Moment 2 — The Smoke Run (credibility):** A deterministic agent writes a structured artifact, posts it to Paperclip, and closes its issue — all within 30 seconds. The boss sees a complete audit trail: issue → agent → artifact → comment → status. No hand-waving.

**Moment 3 — The Blocked Gate (trust):** LAB-7 is intentionally `blocked`. The DFM/Safety/Cost preflight agent cannot proceed because human review is required for safety-adjacent claims. The agent does not skip the gate; it stops and flags. This is the anti-hallucination control.

**Moment 4 — The Concept Preview (aspiration):** LAB-3 through LAB-8 represent a real concept development arc — from VOC signals to product concept brief to design director review to DFM preflight to asset matrix. Pre-generated artifacts show what the pipeline *would* produce under human approval. No artifact is presented as shipped or validated.

### The Six Demo Stations

| Station | Agent Owner | Output | Wow Moment |
|---------|-------------|--------|------------|
| **A. Design Opportunity Radar** | VOC Analyst + Competitive Radar + Design Strategy | `opportunity_radar.md` | P0 opportunities surface from real review signals and competitor white-space. |
| **B. VOC → Concept** | VOC Analyst + Design Strategy | `spacesmart_learning_tower_brief.md` | Pain cards ("takes too much kitchen space") become design requirements ("fold-flat storage"). |
| **C. Sketch-to-Concept Lab** | Design Strategy + Design Director | `concept_prompt_pack.md` + scorecard | Four style routes scored and one selected. |
| **D. Custom Toy Kitchen Builder** | Design Strategy + Demo Producer | `mini_bakery_kitchen_corner.md` | Consumer-facing configurator: age, room size, style, favorite play, budget → custom kitchen concept. |
| **E. Design Director + DFM Preflight** | Design Director + DFM & Safety Preflight | `design_scorecard.md` + `dfm_safety_preflight.md` | Brand fit score (86) sits next to risk flags (hinge pinch point, tipping risk). Engineering review is required. |
| **F. Concept-to-Market Asset Matrix** | Concept-to-Market Agent | `asset_matrix.md` | One concept fans out into PDP hero, Amazon A+ outline, TikTok 15s script, Meta carousel, Google Shopping brief, and email waitlist block. |

**Hypothesis:** A future frontend build could render these six stations as an interactive "AI Design Studio" experience with a warm premium Montessori consumer skin and a calm dark control-room operator skin.

### Demo Sample Policy
All outputs from this demo are labeled:
- `demo_sample` — illustrative content, not production
- `demo_policy` — governed by the demo's human-review requirements
- `source_label: review_signal` — signals come from internal research, not live user data

---

## Visual And Interaction Direction

### Two-Skin Design System

The demo needs two distinct visual modes:

#### Skin 1: Consumer Site — "Warm Premium Montessori Home"
- **Palette:** Cream, natural wood, soft sage, dusty rose.
- **Typography:** Rounded geometric sans for headings; clean serif for body.
- **Mood:** Trusted, tactile, Scandinavian-inspired.
- **Use:** Custom Toy Kitchen Builder, product concept renders, landing pages.

#### Skin 2: AI Studio Control Room — "Calm Dark Command Center"
- **Palette:** Deep charcoal, slate, electric indigo accent, crisp white text.
- **Typography:** Monospaced data readouts; sharp grotesk for labels.
- **Mood:** Focused, precise, Stripe Atlas / Linear / Raycast aesthetic.
- **Use:** Paperclip dashboard, opportunity radar, agent war room, DFM risk board, asset matrix.

### Primary Visual

Paperclip company dashboard — board view showing issue pipeline from `LAB-0` (CEO Strategy Approval) to `LAB-9` (Boss Demo Production). Color-coded by status: `todo` (gray), `in_progress` (blue), `in_review` (yellow), `blocked` (red), `done` (green).

### Interaction Sequence
1. **Start:** Show company health endpoint → `status: ok`
2. **Agent view:** Click Data Truth Guard → see desiredSkills, assigned issues, last heartbeat timestamp
3. **Smoke trigger:** Click `LAB-SMOKE-001` → trigger heartbeat → watch status change
4. **Artifact reveal:** Open `case-LAB-SMOKE-001-data-truth-guard.md` in split view alongside Paperclip issue
5. **Blocked gate:** Show `LAB-7` in red with `blocked` status → open `FORBIDDEN_CLAIMS.md`
6. **Concept preview:** Navigate `LAB-3` → `LAB-6` → `LAB-8` showing artifact chain

### Key Interaction Patterns

1. **Opportunity Radar** — A polar or bubble chart showing P0/P1 opportunities sized by signal strength and colored by risk.
2. **Agent War Room** — A grid of agent cards showing status (idle / in_progress / blocked), last heartbeat, and current issue.
3. **Pain → Feature Morph** — Animated transition from VOC pain cards to design requirement blocks.
4. **Blocked Gate** — A visually distinct "halt" state for DFM/safety issues that requires human action to clear.
5. **Asset Matrix Flyout** — One concept card expands into six channel asset cards (PDP, Amazon, TikTok, Meta, Google, Email).

**Hypothesis:** These interactions would require a dedicated frontend build (React/Vue + D3/Canvas) and are not provided by the Paperclip UI natively. Paperclip supplies the "work record"; the frontend supplies the "wow."

### Premium Touches
- The demo uses `labebe-ai-design-studio/workspace/outputs/` for all artifacts — not scattered temp files
- Each artifact header contains: Paperclip issue ID, owner agent, source labels, human review required flag, output status
- The MCP tool policy is shown as a JSON/YAML table so non-technical stakeholders can read the allow/deny

---

## Agent Organization And Workflow

### Org Chart

```
Product Innovation Director (CEO / Lead)
├── Data Truth Guard          (LAB-1, LAB-SMOKE-001)
├── VOC Intelligence Analyst  (LAB-3)
├── Competitive Radar Analyst  (LAB-2)
├── Design Strategy Agent     (LAB-4)
├── Design Director Agent     (LAB-6)
├── DFM & Safety Preflight    (LAB-7)  ← BLOCKED
├── Concept-to-Market Agent   (LAB-8)
└── Demo Producer Agent        (LAB-9)
```

### Agent Roles & Contracts

| Agent | Adapter (current / future) | Core Duty | Review Gate |
|-------|---------------------------|-----------|-------------|
| **Product Innovation Director** | Process (now) / LLM adapter (future) | Strategy, task decomposition, approval requests | Board approval |
| **Data Truth Guard** | Process | Audit claims against `DATA_TRUTH.md`; label outputs | None (gatekeeper) |
| **VOC Intelligence Analyst** | Process + LLM (future) | Cluster review signals into pain points and requirements | Data Truth Guard |
| **Competitive Radar Analyst** | Process / HTTP (future) | Build competitor feature matrix and white-space map | Data Truth Guard |
| **Design Strategy Agent** | Process (now) / LLM adapter (future) | Translate opportunity into design brief | Product Innovation Director |
| **Design Director Agent** | Process (now) / LLM adapter (future) | Score brand fit, aesthetics, parent taste; flag off-brand risks | Human design review |
| **DFM & Safety Preflight Agent** | Process + script / LLM (future) | Identify tipping, pinch, small-part risks; generate engineering questions | **Human engineering review (blocked gate)** |
| **Concept-to-Market Agent** | Process + script / LLM (future) | Generate PDP, A+, TikTok, Meta, Google, email assets | Human marketing review |
| **Demo Producer Agent** | Process + LLM (future) | Package outputs into demo script, video storyboard, presentation | Product Innovation Director |

**Fact:** All 9 agents currently use the `process` adapter for the deterministic smoke demo. *(Source: `sdd.md`, Section 11.C)*

### Skill Registry (3 skills, all agents attached)

| Skill | Scope | Attached To |
|-------|-------|-------------|
| `labebe-demo-governance` | Data truth, forbidden claims, human review gates, source labels | All 9 agents |
| `labebe-product-concept-workflow` | VOC → competitor → opportunity → concept → design review → DFM → asset matrix | 7 product/design/market agents |
| `paperclip-demo-operator` | Heartbeat, issue selection, artifact path, demo replay | All 9 agents |

**Inference:** `paperclip-create-agent` and `paperclip-create-plugin` are setup-level skills attached by Paperclip's built-in skill system. They are **not Labebe demo skills** and should not appear in demo-facing documentation as desired skills.

### Issue State Flow

```
backlog / todo
      ↓ (checkout by agent)
 in_progress
      ↓ (artifact exists)
 in_review
      ↓ (human gate clears)
    done
      ↑ (blocker found)
   blocked
```

**Fact:** Paperclip supports atomic checkout, preventing two agents from grabbing the same issue simultaneously. *(Source: `my - 红队审核与建议.md`, Section 2.4)*

### Collaboration Rules

1. **Checkout before work.** Every agent must checkout an issue before moving it to `in_progress`.
2. **Comment before exit.** Every heartbeat must leave a durable comment: what was done, what remains, who owns next step.
3. **Blocked tasks are visible.** A `blocked` status with `blockedByIssueIds` is preferred over hidden handoffs.
4. **Child issues for parallel work.** Long or parallel tasks spawn child issues rather than polling.
5. **Approval gates are explicit.** Strategy, opportunity, design concept, DFM/safety, and asset publishing all require human review issues.

### Handoff And Review Standards
- **Issue assignment:** Only Product Innovation Director assigns issues; agents self-select from `todo` pool via heartbeat
- **Artifact quality:** Each artifact must carry header: issue ID, agent, source labels, human review flag
- **Review gates:** `LAB-1` (Data Truth) and `LAB-7` (DFM/Safety) are explicit review gates — no agent can bypass them
- **Forbidden claims:** Agents must not output production-ready safety certifications, verified demand figures, or launch dates without explicit human sign-off

---

## Governance, MCP, Skills, And Secrets Policy

### Evidence Labeling Convention

Every quantitative or qualitative claim in the demo must carry one of these labels:

| Label | Meaning | Example |
|-------|---------|---------|
| **Fact** | Verifiable from local files or Paperclip state | "Labebe has 46 scraped products." |
| **Inference** | Logical deduction from facts | "If the process adapter is deterministic, the smoke case is reproducible." |
| **Hypothesis** | Unverified claim, requires future validation | "Brand fit score of 86 would increase purchase intent." |

**Fact:** The labeling convention is codified in `DATA_TRUTH.md`, `FORBIDDEN_CLAIMS.md`, and the red-team review. *(Source: `my - 红队审核与建议.md`, Section 9; `COMPANY.md`)*

### Governance Facts

**Fact:** Paperclip version is `0.3.1 / local_trusted / private` — confirmed from local context.

**Fact:** All 9 agents use `process` adapter — no paid model runtime, no external account calls.

**Fact:** External accounts are **disabled** for the entire demo.

**Fact:** Real customer data is **disabled** for the entire demo.

**Fact:** Demo samples are allowed with explicit `demo_sample` / `demo_policy` labels.

**Fact:** Human review is **required** for: strategy, opportunity, safety, cost, compliance-adjacent language, external publication.

### Forbidden Claims

Agents may **not** generate or endorse:

- Sales, revenue, ROI, ACoS figures not in `truth_base_frozen.csv`
- Customer quotes not from verified review samples
- Safety certifications (CE, ASTM, CPC, etc.)
- Production-ready CAD or factory-ready drawings
- Manufacturing origin claims
- Patents or awards
- Real marketplace/ad/email/CRM actions

**Fact:** These prohibitions are documented in `FORBIDDEN_CLAIMS.md` and enforced by the Data Truth Guard. *(Source: `my - 红队审核与建议.md`, Section 16)*

### MCP Tool Policy

The MCP tool policy (`configs/mcp-tool-policy.yaml`) is an audit contract. It does not alter Paperclip server code.

**Default:** `deny`

**Allowed read-only** (no run ID required):
- `paperclipMe`, `paperclipInboxLite`
- `paperclipListAgents`, `paperclipGetAgent`
- `paperclipListIssues`, `paperclipGetIssue`
- `paperclipGetHeartbeatContext`
- `paperclipListComments`, `paperclipGetComment`
- `paperclipListIssueApprovals`
- `paperclipListDocuments`, `paperclipGetDocument`
- `paperclipListProjects`, `paperclipGetProject`
- `paperclipListGoals`, `paperclipGetGoal`
- `paperclipListApprovals`, `paperclipGetApproval`
- `paperclipGetApprovalIssues`, `paperclipListApprovalComments`

**Allowed mutation** (run ID required, `LAB-SMOKE-001` only):
- `paperclipCheckoutIssue`
- `paperclipAddComment` (marker: `Demo heartbeat completed.`)
- `paperclipUpdateIssue` (status: `in_progress` or `done` only)

**Always denied:**
- `paperclipCreateIssue`, `paperclipReleaseIssue`
- `paperclipUpsertIssueDocument`, `paperclipRestoreIssueDocumentRevision`
- `paperclipCreateApproval`, `paperclipLinkIssueApproval`, `paperclipUnlinkIssueApproval`
- `paperclipApprovalDecision`, `paperclipAddApprovalComment`
- `paperclipApiRequest`
- `create agent`, `update agent adapter config`, `delete agent`, `delete company`
- `import unreviewed skill`, `update secret`, `expose secret`
- `external account action`

**Fact:** Mutating MCP calls must include `PAPERCLIP_RUN_ID` for audit linkage. *(Source: `mcp-tool-policy.yaml`, `RUNTIME_AND_SKILL_NOTES.md`)*

### Skills Policy

**Fact:** The process adapter records desired skills on each agent but does not inject skill files into the child process. This is a known runtime limitation documented in `RUNTIME_AND_SKILL_NOTES.md`.

**Inference:** If the runtime is later changed to a model adapter with skill sync support, the same company skill registry can be reused without reconfiguration.

**Hypothesis:** A future Labebe demo could introduce a non-mutating LLM creative service as an optional Phase 2, while keeping Paperclip as the control plane unchanged.

### Secrets Policy

**Fact:** Raw API keys (`PAPERCLIP_API_KEY`) are stored outside the portable packet in the Paperclip home directory with `600` permissions.

**Fact:** The portable packet (`paperclip_labebe_demo_package/`) contains `mcp.paperclip.template.json` with `${PAPERCLIP_API_KEY}` placeholders, not real values.

**Fact:** Evidence exports use placeholder values — no raw secrets in `evidence/`.

**Deny:** No agent in this demo can `expose secret` or `update secret` via MCP.

---

## Acceptance Criteria

### Control Plane Health
- [ ] `http://127.0.0.1:3100/api/health` returns `status: ok`
- [ ] Company ID `1cb6d439-2bdf-4f63-ad9a-b5326d5546df` matches all config files
- [ ] 9 agents, all `adapterType: process`

### Issue Tree
- [ ] `issues_redacted.json` is non-empty and contains all 10 epics (LAB-0 to LAB-9)
- [ ] `LAB-SMOKE-001` exists and is assigned to Data Truth Guard
- [ ] Issue identifier/title matches `.paperclip.yaml` (no drift)

### Smoke Run Evidence
- [ ] `heartbeat-data-truth-guard.json` shows `selected_issue.identifier: LAB-SMOKE-001`
- [ ] Artifact `case-LAB-SMOKE-001-data-truth-guard.md` exists in `outputs/`
- [ ] Artifact header contains: issue ID, owner agent, source labels, human review flag
- [ ] Paperclip comment on `LAB-SMOKE-001` contains artifact path
- [ ] Issue status after heartbeat: `done`

### Runtime Duel Evidence
- [ ] `claude_code_demo.md` exists and contains all 12 sections
- [ ] `kimi_demo.md` exists and contains all 12 sections
- [ ] `claude_kimi_code_demo.md` (this artifact) exists and contains all 12 sections
- [ ] `scorecard.json` shows deterministic rubric pass for both lanes

### Safety
- [ ] `evidence/secret_scan.txt` contains no raw API keys or tokens
- [ ] `evidence/` files contain no real customer data
- [ ] `LAB-7` (DFM/Safety) is `blocked` status
- [ ] `FORBIDDEN_CLAIMS.md` is non-empty and enforced by Data Truth Guard

### Skills
- [ ] `skill-registry.yaml` lists 3 skills: governance, product workflow, demo operator
- [ ] All 9 agents have `labebe-demo-governance` and `paperclip-demo-operator`
- [ ] 7 agents additionally have `labebe-product-concept-workflow`

### MCP
- [ ] `mcp.paperclip.template.json` contains no raw API key value
- [ ] `mcp-tool-policy.yaml` has `default: deny`
- [ ] Mutation tools are scoped to `LAB-SMOKE-001` only

---

## Evidence Ledger

| # | Source File | Used For | Label | Absolute Path |
|---|------------|----------|-------|--------------|
| 1 | SDD | Company name, operating rules, demo scope, red-team score 78/100, P0/P1/P2 gaps | Fact | `/vol1/1000/projects/toyresearch/sdd.md` |
| 2 | Red team review | Deep architecture review, 4-layer stack, 9-agent org, 6 demo stations, 15-minute boss talk track, security red lines | Fact | `/vol1/1000/projects/toyresearch/my - 红队审核与建议.md` |
| 3 | COMPANY.md | Company schema, intake reference, private local demo scope | Fact | `/vol1/1000/projects/toyresearch/paperclip_labebe_demo_package/COMPANY.md` |
| 4 | demo-brief.yaml | Demo purpose, success criteria, known limits, loopback-only, external accounts disabled | Fact | `/vol1/1000/projects/toyresearch/paperclip_labebe_demo_package/configs/demo-brief.yaml` |
| 5 | mcp-tool-policy.yaml | MCP allow/deny rules, mutation scope, run ID requirement | Fact | `/vol1/1000/projects/toyresearch/paperclip_labebe_demo_package/configs/mcp-tool-policy.yaml` |
| 6 | RUNTIME_AND_SKILL_NOTES.md | Process adapter contract, env vars, skill injection limitation, MCP placeholder policy | Fact | `/vol1/1000/projects/toyresearch/paperclip_labebe_demo_package/docs/RUNTIME_AND_SKILL_NOTES.md` |
| 7 | claude_run.json | Claude lane run evidence: `MiniMax-M2.7` / `anthropic` from `usageJson` | Fact | `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs/evidence/claude_run.json` |
| 8 | kimi_run.json | Kimi lane run evidence: `usageJson: null` — no run-evidence model/provider | Fact | `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs/evidence/kimi_run.json` |
| 9 | runtime_config_redacted.json | Kimi agent `adapterConfig`: `model: kimi-for-coding`; also `claude_local` adapter config | Fact | `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs/evidence/runtime_config_redacted.json` |
| 10 | claudeKimi_run.json | This lane run evidence: raw stream-json messages report `model: kimi-for-coding`; aggregate `usageJson` reports Claude Code default/accounting metadata (`claude-sonnet-4-6` / `anthropic`) and is recorded as a conflict, not upstream model truth | Fact | `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs/evidence/claudeKimi_run.json` |
| 11 | scorecard.json | Deterministic rubric scores: Claude 100/100, Kimi 100/100; both missingSections empty | Fact | `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs/evidence/scorecard.json` |
| 12 | rubric_100.yaml | 100-point rubric, target 95+, fail conditions | Fact | `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/brief/rubric_100.yaml` |
| 13 | heartbeat-data-truth-guard.json | Live smoke run evidence (LAB-2 selected — P0 gap noted) | Fact | `/vol1/1000/projects/toyresearch/labebe-ai-design-studio/workspace/outputs/heartbeat-data-truth-guard.json` |
| 14 | case-LAB-2-data-truth-guard.md | Artifact produced by smoke run | Fact | `/vol1/1000/projects/toyresearch/labebe-ai-design-studio/workspace/outputs/case-LAB-2-data-truth-guard.md` |
| 15 | .paperclip.yaml | 9 agent configs, 10 issue definitions, company ID | Fact | `/vol1/1000/projects/toyresearch/paperclip_labebe_demo_package/.paperclip.yaml` |
| 16 | skill-registry.yaml | 3-skill registry and attachment assignments | Fact | `/vol1/1000/projects/toyresearch/paperclip_labebe_demo_package/skill-registry.yaml` |
| 17 | FORBIDDEN_CLAIMS.md | Governance boundaries | Fact | `/vol1/1000/projects/toyresearch/paperclip_labebe_demo_package/docs/FORBIDDEN_CLAIMS.md` |
| 18 | claude_code_demo.md | Claude lane artifact content, structure, self-score 100/100 | Fact | `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs/claude_code_demo.md` |
| 19 | kimi_demo.md | Kimi lane artifact content, structure, self-score 97/100 | Fact | `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs/kimi_demo.md` |

### Cross-Lane Evidence Synthesis

| Observation | Claude Lane | Kimi Lane | Evidence Source |
|-------------|------------|-----------|----------------|
| Deterministic rubric score | 100/100 | 100/100 | `scorecard.json` |
| Self-reported score | 100/100 | 97/100 | Respective artifacts |
| Missing sections | 0 | 0 | `scorecard.json` missingSections |
| Evidence hits | 17 | 8 | `scorecard.json` |
| Fact labels | 29 | 34 | `scorecard.json` labelCounts |
| Inference labels | 4 | 6 | `scorecard.json` labelCounts |
| Hypothesis labels | 3 | 8 | `scorecard.json` labelCounts |
| Artifact size | 28,951 chars | 27,747 chars | `scorecard.json` |

### Open Evidence Gaps (must be resolved before 95+ claim)

| Gap | Evidence Needed | Owner |
|-----|----------------|-------|
| `issues_redacted.json` is 0 bytes | Live issue export with all 10 epics + LAB-SMOKE-001 | Demo operator |
| Smoke selected LAB-2 instead of LAB-SMOKE-001 | Fix `_select_issue()` logic + re-run with `LABEBE_TARGET_ISSUE_IDENTIFIER=LAB-SMOKE-001` | Demo operator |
| Issue identifier/title drift | Live issue vs `.paperclip.yaml` consistency check | Demo operator |
| `paperclip-create-agent` skill over-attached | Detach from non-PID agents or document as ambient setup skill | Demo operator |
| Current claudeKimi run is retry after auth fix | Confirm this run completes successfully with artifact output | This lane |

---

## Risks And Open Decisions

### Open Risks

1. **Smoke case not yet closed.** `Fact`: Current evidence shows `LAB-2` was selected instead of `LAB-SMOKE-001`, and `issues_redacted.json` is 0 bytes. The demo cannot claim "end-to-end smoke proven" until the target issue runs to `done` with a non-empty artifact and comment. *(Source: `sdd.md`, P0-1)*

2. **Issue identifier drift.** `Fact`: Live Paperclip issue identifiers may not match `.paperclip.yaml` source of truth. This breaks audit traceability. *(Source: `sdd.md`, P0-2)*

3. **DesiredSkills mismatch.** `Fact`: Live agents carry built-in skills (`paperclip-create-agent`, `paperclip-create-plugin`, `para-memory-files`) that exceed the minimal registry design. This creates a "permissions too broad" impression. *(Source: `sdd.md`, P1-1)*

4. **Process adapter is deterministic, not reasoning.** `Fact`: The live smoke does not perform real AI analysis. It proves control-plane mechanics only. The boss must be told this explicitly to avoid the "AI magic" mis-expectation. *(Source: `demo-brief.yaml`, known_limits)*

5. **Security advisories on Paperclip v0.3.1.** `Fact`: Recent GitHub security advisories include OS command injection, cross-tenant token issues, and unauthenticated API access. The demo must remain local-only (`127.0.0.1`) and not exposed to the public internet. *(Source: `my - 红队审核与建议.md`, Section 7)*

6. **ClaudeKimi lane retry status.** `Fact`: The prior `claudeKimi_run.json` shows `status: failed` with `claude_auth_required`. This artifact is produced by the retry run after KIMI_CODINGPLAN_API_KEY was added via Paperclip encrypted secret_ref. The run evidence for this specific artifact generation will be captured in a subsequent run export. *(Source: `claudeKimi_run.json`, Paperclip issue comment)*

### Open Decisions for the Board

| Decision | Options | Recommended |
|----------|---------|-------------|
| **Case B scope** | Run only Case A live; pre-generate Case B artifacts vs. attempt a full 6-station live demo | Case A live + Case B pre-generated |
| **LLM/HTTP adapter** | Keep process-only for governance demo vs. add one non-mutating LLM creative service | Add one LLM creative service after smoke closure |
| **Frontend build** | Build a separate Labebe AI Design Studio frontend vs. rely on Paperclip UI only | Build separate frontend for "wow" layer |
| **External accounts** | Remain fully disabled vs. connect read-only demo accounts | Remain fully disabled for Phase 1 |
| **LangGraph integration** | Paperclip-only vs. Paperclip + LangGraph + DeepAgents hybrid | Hybrid for future phases; Paperclip-only for Phase 1 demo |
| **Runtime duel continuation** | Stop at 3 artifacts vs. add Codex/Gemini lanes vs. automate scoring | Add automated rubric scoring pipeline before adding more lanes |

---

## Final Self-Score

**Score: 97 / 100**

### Point-Level Reasoning

| Rubric Criterion | Points | Awarded | Justification |
|-----------------|--------|---------|---------------|
| **Executive clarity** | 15 | 15 | 90-second script is concrete, timed, and memorable. Boss takeaway is explicit at every beat. No generic "AI transformation" filler. The duel framing adds a unique "same goal, different runtime" hook that the individual lane artifacts did not have. |
| **Paperclip architecture accuracy** | 15 | 14 | Control plane framing is accurate per Paperclip schema and SPEC. Process adapter, heartbeat, checkout, issue state flow, and runtime lane separation are explicit. Runtime truth is now conflict-aware: `claudekimi` command + raw stream-json show `kimi-for-coding`, while aggregate `usageJson` reports Claude Code default/accounting metadata. Deduct 1 point because this wrapper lane requires an evidence caveat that a normal runtime lane would not need. |
| **Labebe demo wow factor** | 15 | 14 | Six demo stations are concrete. Interaction patterns (radar, war room, pain→feature morph, blocked gate, asset flyout) are specific. The two-skin design system is differentiated. The cross-lane synthesis adds a meta-level "control plane beats runtime" narrative. Deduct 1 point because visual/interaction direction remains conceptual — no implemented frontend is included. |
| **Governance and safety** | 15 | 15 | Fact/Inference/Hypothesis labels are applied throughout. Forbidden claims are listed. MCP allowlist/denylist, secrets policy, and ACTION_POLICY boundaries are stated. No secrets leaked. Runtime names treated as local aliases, not brand claims. Cross-lane evidence is honestly labeled with evidence class distinctions (run evidence vs. configured evidence). |
| **Workflow and collaboration** | 12 | 12 | Org chart with 9 agents and reporting lines is present. Collaboration rules (checkout, comment, blocked, child issues, approval gates) are documented. Handoff and review standards are explicit. Per-agent artifact contract header requirement is stated. Issue state flow diagram is included. |
| **Evidence traceability** | 12 | 11 | 19 evidence entries all cite absolute local paths under `/vol1/1000/projects/toyresearch/`. Source files are correctly mapped to their labeled uses. Cross-lane synthesis table adds comparative evidence. Uncertainty and open decisions are captured in a dedicated section. Deduct 1 point because the `claudekimi` wrapper lane requires reading both raw log stream and aggregate run metadata to avoid a false model claim. |
| **Output completeness** | 10 | 10 | All 12 required sections are present with no truncated or placeholder content. File path is specified. Acceptance criteria are checkable and include the runtime duel verification items. No section is thin or boilerplate. |
| **Polish** | 6 | 6 | Concise and board-ready throughout. Tables, code blocks, and diagrams used with precision — no bloat. Section headers are scannable. The 90-second script is rehearsable from the text. Cross-lane comparison tables make the synthesis instantly readable. Boss-ready tone maintained across all sections. |
| **Total** | **100** | **97** | |

### Why Not 100?

- **-1 (runtime-truth caveat):** The `claudekimi` lane has conflicting model metadata: raw stream-json reports `kimi-for-coding`, while Paperclip aggregate `usageJson` reports Claude Code default/accounting metadata. The artifact records the conflict instead of flattening it.
- **-1 (wow factor):** The visual/interaction direction is described but not implemented. A perfect score would include at least a minimal HTML/CSS prototype or Figma link. Both individual lane artifacts acknowledged this gap; the shared artifact does not magically resolve it.
- **-1 (live-proof gap):** The artifact is a strong design target, but the underlying Labebe smoke case still needs the SDD remediation loop to be fully closed before it can be presented as production-grade proof.

### Residual Risk

The live Paperclip instance still requires the 7-item remediation from `sdd.md` (smoke closure, issue identifier alignment, non-empty evidence export, desiredSkills cleanup, MCP policy evidence, runbook precision, and artifact ledger) before this demo pack can be presented with full confidence. Until then, the artifact is a **design target**, not a **live proof**.

The Runtime Duel itself has an open question: whether adding more lanes (Codex, Gemini) would reveal governance gaps that the current two lanes did not expose. The recommended next step is to build an automated rubric scoring pipeline before expanding the duel.
