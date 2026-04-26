# Runtime Duel Shared Target Brief

## Purpose

Create a direct Paperclip comparison between local runtime aliases:

- `Claude Code`: local Claude Code CLI/client lane, run through Paperclip `claude_local`. The actual provider/model must be reported from run evidence; do not assume it is an official Anthropic model.
- `Kimi`: native Kimi Code CLI, run through a local Paperclip `kimi_cli` adapter.
- `Claude Code Kimi`: local Claude Code compatibility lane, run through Paperclip `claude_local` with command `/home/yuanhaizhou/.local/bin/claudekimi`. This is the requested "Claude Code + Kimi model route" lane. If Paperclip aggregate `usageJson` conflicts with raw stream-json model fields, record the conflict and do not describe it as official Claude output.

Both lanes must solve the same content-generation target with the same constraints, output schema, evidence base, and 100-point rubric.

## Target

Produce a boss-ready "wow demo" content pack for **Labebe AI Design Studio as an AI team control plane**.

The output must help a boss immediately see:

1. Paperclip is the governance and orchestration layer, not a magic black-box generator.
2. The Labebe demo can show organization, issues, heartbeats, evidence, approvals, and artifacts.
3. The content is premium, concrete, and safe enough for internal executive review.
4. The design and growth story feels differentiated, not generic AI marketing copy.

## Mandatory Source Material

Use these local sources as the evidence base:

- `/vol1/1000/projects/toyresearch/sdd.md`
- `/vol1/1000/projects/toyresearch/my - 红队审核与建议.md`
- `/vol1/1000/projects/toyresearch/paperclip_labebe_demo_package/COMPANY.md`
- `/vol1/1000/projects/toyresearch/paperclip_labebe_demo_package/configs/demo-brief.yaml`
- `/vol1/1000/projects/toyresearch/paperclip_labebe_demo_package/configs/mcp-tool-policy.yaml`
- `/vol1/1000/projects/toyresearch/paperclip_labebe_demo_package/docs/RUNTIME_AND_SKILL_NOTES.md`

Do not claim you read internet sources. This demo is local-context only.

## Deliverable Contract

Write a single Markdown artifact with these exact sections:

1. `# Executive Demo Narrative`
2. `## What The Boss Should See In 90 Seconds`
3. `## Control Plane Architecture`
4. `## Same-Goal Generation Plan`
5. `## The Premium Labebe Demo Concept`
6. `## Visual And Interaction Direction`
7. `## Agent Organization And Workflow`
8. `## Governance, MCP, Skills, And Secrets Policy`
9. `## Acceptance Criteria`
10. `## Evidence Ledger`
11. `## Risks And Open Decisions`
12. `## Final Self-Score`

The artifact must include:

- A concise 90-second demo script.
- A clear Paperclip org chart and workflow.
- A concrete creative concept for Labebe AI Design Studio.
- A "same task, different runtime" comparison framing.
- A clear note that the comparison is between local runtime aliases as configured on this machine.
- Runtime evidence must be graded precisely:
  - If `usageJson.model` / `usageJson.provider` exists in run evidence, cite it as run evidence.
  - If model is only present in Paperclip agent `adapterConfig`, call it configured model evidence.
  - If provider is inferred from a CLI ecosystem or maint runbook rather than emitted by the run, label it as an inference, not "from run evidence".
- Evidence labels: `Fact`, `Inference`, `Hypothesis`.
- No fabricated metrics, customer claims, certifications, or launch promises.
- A self-score out of 100 using `brief/rubric_100.yaml`.

## Output Path

Each runtime must also save its artifact:

- Claude lane: `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs/claude_code_demo.md`
- Kimi lane: `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs/kimi_demo.md`
- Claude Code Kimi lane: `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs/claude_kimi_code_demo.md`

If the runtime cannot write the file, it must include the complete artifact in the Paperclip issue comment.

## Quality Bar

Target score: **95+ / 100**.

This is intentionally high. A passing answer should feel like a board-demo package, not a normal assistant answer.
