# GStack / AgencyAgents Intake Research For Paperclip

Date: 2026-04-27

## 1. Conclusion

The useful move is not to install another agent stack.

Use **GStack** as a review and QA method library. Extract five lightweight Paperclip gates:

1. CEO / wow review gate
2. Design review gate
3. Browser QA gate
4. CSO / MCP policy gate
5. Ship / checkpoint gate

Use **AgencyAgents** only as a role-card reference. It is a large catalog of specialist personas, useful for role writing, deliverable expectations and success metrics. It should not become a Paperclip runtime dependency.

Paperclip should remain the control plane:

```text
Paperclip = orgs + projects + issues + artifacts + evidence + gates + approvals
GStack = source of review/QA/security/checkpoint patterns
AgencyAgents = source of role-card shape and specialist vocabulary
Execution = Codex / Claude Code / Kimi Code / MiniMax / scripts / browser / local models
```

## 2. Sources Checked

### Local

- `/vol1/1000/projects/gstack/README.md`
- `/vol1/1000/projects/gstack/ARCHITECTURE.md`
- `/vol1/1000/projects/gstack/qa/SKILL.md`
- `/vol1/1000/projects/gstack/design-review/SKILL.md`
- `/vol1/1000/projects/gstack/plan-ceo-review/SKILL.md`
- `/vol1/1000/projects/gstack/cso/SKILL.md`
- `/vol1/1000/projects/gstack/ship/SKILL.md`
- `/vol1/1000/projects/gstack/checkpoint/SKILL.md`
- `/vol1/1000/projects/gstack/browse/SKILL.md`
- `/vol1/maint/docs/2026-04-23_multica_hermes_operating_spec_v2.md`

Local GStack version signals:

```text
VERSION: 0.16.4.0
package.json version: 0.16.2.0
```

The version mismatch reinforces the need to treat the local copy as a reference snapshot unless a separate dependency update decision is made.

### External

- `https://github.com/garrytan/gstack`
- `https://github.com/msitarzewski/agency-agents`

External GStack README describes it as a Claude Code workflow stack with CEO, designer, reviewer, QA, CSO and release-engineer style specialists. External AgencyAgents README describes a multi-tool catalog of specialized agent personalities, with support for Claude Code, Copilot, Antigravity, Gemini CLI, OpenCode, OpenClaw, Cursor, Aider, Windsurf and Kimi Code.

## 3. Why GStack Helps Paperclip

GStack's strongest contribution is not the persona names. It is its insistence that work must be inspected as rendered product, reviewed under multiple lenses, and closed with evidence.

The patterns that matter for Paperclip:

| GStack Area | What It Contributes | Paperclip Use |
|---|---|---|
| `/plan-ceo-review` | Premise challenge, 10x check, implementation alternatives, dream-state mapping, review sections | Boss-demo and plan gate before implementation |
| `/design-review` | First impression, rendered design system extraction, AI-slop detection, responsive screenshots, design scoring | Website and video-gallery visual gate |
| `/qa` | Browser-first exploration, screenshots, repro evidence, health score, regression baseline | DTC prototype and Boss Gallery QA gate |
| `/cso` | Attack surface census, secrets, dependency, CI/CD, LLM security, skill supply chain, STRIDE, confidence gates | MCP / CLI / skill / browser harness policy gate |
| `/ship` | Pre-flight, test coverage, scope drift, plan completion, verification, review army, PR body evidence | Paperclip issue closeout and release gate |
| `/checkpoint` | Session state, decisions, remaining work, resume path | Long-running agent continuity |
| `/browse` | Real Chromium, localhost bearer token, screenshots, ARIA snapshots, responsive checks | Browser harness architecture reference |

This directly addresses failures already seen in the Labebe/Paperclip work:

- pages that technically open but visually fail;
- mockups that look generic or AI-generated;
- demos that show process instead of business result;
- unverifiable claims in AI-generated marketing;
- long-running work losing context;
- issue completion being confused with product readiness.

## 4. Why GStack Should Not Be Imported Whole

Do not put GStack itself into the Paperclip runtime as a hard dependency.

Reasons:

1. Its skill files include heavy preamble behavior: update checks, telemetry prompts, routing injection, proactive suggestions, session timeline and learnings.
2. Its workflow assumes Claude Code skill invocation semantics. Paperclip must support multiple adapters and runtimes.
3. It can write to `~/.gstack` and project files as part of its own lifecycle. Paperclip needs a clear evidence ledger and controlled artifact locations.
4. Direct installation would blur responsibility: when something fails, it becomes unclear whether the owner is Paperclip, GStack, Claude Code, a child runtime or the browser daemon.
5. The maint operating spec already says external projects should be mined for patterns and skills, not blindly merged.

Therefore:

```text
Allowed:
- extract checklists
- extract output schemas
- extract scoring rubrics
- extract browser/security design ideas
- create Paperclip-native gates inspired by GStack

Not allowed:
- vendor GStack wholesale
- let GStack mutate Paperclip routing
- require GStack telemetry/proactive behavior
- make GStack the control plane
- call GStack output "Paperclip evidence" without Paperclip artifact capture
```

## 5. Paperclip Gate Templates To Add

### Gate 1: CEO / Wow Review Gate

Purpose:

- Stop weak plans before implementation.
- Force the question: is this the right problem, and will the result impress the decision maker?

Use for:

- Labebe DTC prototype direction.
- AI Wow Gallery concept.
- Paperclip org/project creation.
- High-risk skill or browser harness changes.

Required artifact:

```text
ceo_wow_review.md
```

Required sections:

1. Current state
2. Actual user / decision-maker outcome
3. Premise challenge
4. Three implementation approaches
5. 10x version
6. What must be explicitly out of scope
7. Failure modes
8. Acceptance criteria
9. Evidence required before close

Pass criteria:

- It states a concrete business or user outcome.
- It proposes at least two credible approaches.
- It identifies the demo's first 30 seconds.
- It names the weakest assumption.
- It names what will not be built.

### Gate 2: Design Review Gate

Purpose:

- Prevent generic AI-looking UI and weak visual judgment.

Use for:

- Labebe pure DTC prototype.
- Boss Gallery.
- Presentation pages.
- Video landing pages.

Required artifact:

```text
design_review_report.md
screenshots/
design_baseline.json
```

Required checks:

1. First impression in one word.
2. The first three things the eye sees.
3. Brand/product unmistakable in first viewport.
4. Actual rendered fonts/colors/heading scale extracted.
5. Desktop/mobile/tablet screenshots.
6. AI-slop blacklist check.
7. Touch target and text overflow check.
8. Motion purpose check.
9. Design score and AI-slop score.
10. Top five fixes.

Pass criteria:

- No horizontal mobile overflow.
- Product/brand visible in first viewport.
- Screenshot evidence exists for each major page.
- AI-slop score is not lower than B.
- Design score is B+ or better before external review.

### Gate 3: Browser QA Gate

Purpose:

- Validate the product like a user, not like source code.

Use for:

- Any website/prototype/demo URL before showing to the user or Pro.
- Any browser automation harness comparison.

Required artifact:

```text
browser_qa_report.md
qa_baseline.json
screenshots/
```

Required checks:

1. HTTP 200 for all entry URLs.
2. Console errors after initial load and key interactions.
3. Navigation flow.
4. PDP/cart/search/filter or main demo flow.
5. Mobile viewport.
6. Broken link check.
7. Core interactions clicked.
8. Health score.

Pass criteria:

- Health score >= 90 for boss-facing demos.
- No P0/P1 functional issues.
- No blank/white/black key surfaces.
- Screenshots attached.

### Gate 4: CSO / MCP Policy Gate

Purpose:

- Keep skill/MCP/CLI/browser automation changes from leaking secrets or creating invisible risk.

Use for:

- New skill installation.
- MCP profile changes.
- Browser automation access to ChatGPT/Pro/Kimi/Gemini.
- MiniMax key or media-generation workflows.
- Paperclip child-runtime permissions.

Required artifact:

```text
runtime_policy_review.md
secret_surface_map.md
```

Required checks:

1. New secret access.
2. New filesystem write scope.
3. New network access.
4. New browser cookie/session access.
5. MCP versus CLI versus skill boundary.
6. Prompt/skill supply-chain risk.
7. LLM tool-call validation.
8. Artifact redaction rule.
9. Rollback plan.

Pass criteria:

- No secret values in artifacts.
- Permissions documented per runtime profile.
- High-risk actions require human approval or explicit issue gate.
- Browser and ChatGPTREST experiments are isolated from production lanes.

### Gate 5: Ship / Checkpoint Gate

Purpose:

- Make issue closure mean evidence-backed completion, not "the agent said done."

Use for:

- Every Paperclip issue transition to `done`.
- Long-running child agent handoff.
- Pro review packet closeout.

Required artifact:

```text
closeout.md
checkpoint.md
evidence_manifest.json
```

Required checks:

1. Original acceptance criteria listed.
2. Each criterion mapped to evidence file or URL.
3. Commands/tests/screenshots/video frames listed.
4. Known limitations.
5. Claims not proven.
6. Next issue if incomplete.
7. Resume instructions.

Pass criteria:

- Every success claim has an evidence pointer.
- Cancelled or superseded work is not counted as success.
- Unknowns are named.
- The next agent can continue without reading the whole conversation.

## 6. AgencyAgents Intake Policy

AgencyAgents is useful because it has many specialist role cards across engineering, design, marketing, sales, product, testing and operations. That maps well to Paperclip agent design.

But it is too broad to import directly.

Use it this way:

```text
Role-card reference only.
No bulk install.
No automatic runtime dependency.
No unreviewed prompt files copied into global agent paths.
```

Allowed extraction:

- role name;
- mission;
- when to use;
- deliverables;
- success metrics;
- communication style;
- collaboration boundaries.

Paperclip role-card schema:

```yaml
role_id:
org:
project_scope:
mission:
not_responsible_for:
inputs_required:
outputs_required:
success_metrics:
evidence_required:
handoff_contract:
tools_allowed:
risk_limits:
fresh_agent_validation:
```

Candidate AgencyAgents references for the current program:

| Paperclip Need | AgencyAgents-Style Reference |
|---|---|
| Labebe visual direction | UI Designer, UX Architect, Brand Guardian, Visual Storyteller |
| DTC conversion | Growth Hacker, SEO Specialist, Paid Media Creative Strategist |
| Short video / media | TikTok Strategist, Short-Video Editing Coach, Video Optimization Specialist |
| Product intelligence | Product Manager, Trend Researcher, Feedback Synthesizer |
| Security and runtime policy | Security Engineer, SRE, Code Reviewer |
| Skill governance | Technical Writer, Codebase Onboarding Engineer, Senior Project Manager |

## 7. Mapping Into Current Paperclip Org Plan

The existing recommendation still stands:

```text
Create three orgs first:
1. Labebe Growth Studio
2. AI Runtime Governance
3. Multica Archive

Keep Skill Foundry and Browser/Vision Lab as projects inside AI Runtime Governance until they grow large enough to split.
```

GStack-derived gates should be owned by `AI Runtime Governance`, then applied to `Labebe Growth Studio`.

Proposed new issues:

| Issue | Org | Purpose |
|---|---|---|
| `AIR-GOV-006` | AI Runtime Governance | Extract GStack gate templates into Paperclip-native docs |
| `AIR-GOV-007` | AI Runtime Governance | Define Paperclip issue closeout evidence contract |
| `AIR-GOV-008` | AI Runtime Governance | Define MCP / skill / CLI / browser policy gate |
| `LAB-GS-008` | Labebe Growth Studio | Apply GStack-style design and browser QA gates to DTC prototype |
| `LAB-GS-009` | Labebe Growth Studio | Apply CEO/wow gate to AI Boss Gallery A-F |
| `SKILL-006` | AI Runtime Governance | Evaluate AgencyAgents role-card patterns and create Paperclip role schema |
| `BV-006` | AI Runtime Governance | Compare GStack browser architecture with ChatGPTREST/browser-use/opencli approach |

## 8. Implementation Path

### Phase A: Pattern Extraction

Inputs:

- GStack local skill files.
- GStack external README.
- AgencyAgents external README.
- Maint operating spec.

Outputs:

- this research doc;
- Paperclip gate issue additions;
- gate templates.

### Phase B: Gate Templates

Create:

```text
paperclip_runtime_duel/docs/gates/ceo_wow_review_gate.md
paperclip_runtime_duel/docs/gates/design_review_gate.md
paperclip_runtime_duel/docs/gates/browser_qa_gate.md
paperclip_runtime_duel/docs/gates/runtime_policy_gate.md
paperclip_runtime_duel/docs/gates/ship_checkpoint_gate.md
```

or equivalent locations in the Paperclip repo after checking its local docs structure.

### Phase C: Apply To Labebe

Before building the next Labebe website prototype:

1. Run CEO / wow review gate on the design direction.
2. Build primary and fallback DTC prototypes.
3. Run design review gate on both.
4. Run browser QA gate on both.
5. Use the result to decide what to show to the user and what to ask Pro.

Before updating AI Wow Gallery:

1. Run CEO / wow review gate.
2. Run claim gate / runtime policy gate.
3. Run browser QA and video QA.
4. Close with evidence manifest.

### Phase D: Apply To Runtime Governance

Before adding or changing skills/MCPs:

1. Run runtime policy gate.
2. Require fresh-agent validation.
3. Record usage/failure event.
4. Curator updates skill or marks it experimental/deprecated.

## 9. Decisions For User Later

No decision is needed before recording this as the working direction.

Decisions needed before active Paperclip execution:

1. Whether to create only three orgs first or all five orgs immediately.
2. Whether the gate docs live inside `paperclip_runtime_duel` or the main Paperclip repo.
3. Whether GStack-style gates are advisory at first or required for `done` transitions.
4. Whether AgencyAgents role-card extraction should be done by one curator agent or split by org.

My recommendation:

```text
Start advisory for one iteration.
Make gates required only after the first Labebe prototype and AI Wow Gallery run prove the artifacts are not too heavy.
```

## 10. Current Judgment

GStack should materially raise the quality bar for Paperclip because it provides the missing bridge between "agent did work" and "a human would believe this is ready."

AgencyAgents is useful, but not in the critical path. It can help define agent roles after the control gates are in place.

Priority order:

```text
1. GStack-derived gates
2. Browser / visual evidence harness
3. Skill/runtime policy gate
4. AgencyAgents role-card extraction
```

