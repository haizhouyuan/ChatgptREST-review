# Paperclip Runtime Duel Pro Review Packet

Review date: 2026-04-26

## Request To Pro

Please judge whether this Paperclip demo is genuinely high-quality and has a "wow" factor for an internal boss demo. Do not browse the web and do not switch to Deep Research. Use only the attached local artifacts and general product/design judgment.

Please answer:

1. Is the demo close to a 100-point executive-quality package, or merely structurally complete?
2. Which lane produces the stronger same-goal content: Claude Code local CLI/client lane or native Kimi CLI lane?
3. What are the top issues that must be fixed before calling this demo "near 100"?
4. Are the runtime truth statements and evidence boundaries honest enough?
5. What concrete iteration would most increase the boss-facing wow factor without fabricating metrics or claims?

## Local Runtime Truth

- Paperclip server: local instance at `http://127.0.0.1:3100`.
- Company: `Runtime Duel Studio - Claude Code vs Kimi`.
- Company id: `1d9f885c-d2ac-4411-9b74-f91240ef2a72`.
- Project id: `9d403310-324f-4855-bee4-524180f35e0c`.
- Claude issue: `RUN-1`, id `a0ff7e79-98b5-43a4-8a3e-e12252a70343`.
- Kimi issue: `RUN-2`, id `5ee772bb-6b03-4a42-b319-db3f3cc662f4`.

Important: these are local runtime aliases, not brand claims.

- `Claude Code`: Paperclip `claude_local` adapter, local CLI/client lane. Latest run evidence reports `MiniMax-M2.7` with `provider: anthropic`.
- `Kimi`: external Paperclip `kimi_cli` adapter running native `kimi-direct`, configured as `model: kimi-for-coding`. Kimi run evidence currently has `usageJson: null`, so Kimi model is configured-model evidence rather than run-emitted model/provider evidence.

## Latest Runs

| Lane | Latest run id | Status | Issue status | Artifact |
|------|---------------|--------|--------------|----------|
| Claude Code | `7138e76f-786f-4035-9d65-1e8afce24d63` | succeeded | done | `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs/claude_code_demo.md` |
| Kimi | `fdab01aa-99f7-40bc-b77a-5a7272f5edaa` | succeeded | done | `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs/kimi_demo.md` |

## Current Deterministic Scorecard

Deterministic rubric checks structure, evidence traceability, required sections, policy hygiene, and self-score parsing. It does not judge taste.

| Lane | Deterministic score | Self-score | Evidence hits | SHA256 |
|------|---------------------|------------|---------------|--------|
| Claude Code | 100 | 100 | 17 | `7d45908360071f5556097113cd9ae593d6f9a30f9c838b69fa4a52d60593f5f2` |
| Kimi | 100 | 97 | 8 | `dcde0322a563980dc9d2612e4fde2abc59bce39aa20646516556440fa52d3adf` |

Secret scan result: pass, 0 findings.

## What Was Iterated Before This Review

- Created a separate Paperclip company for the runtime duel instead of modifying the existing Labebe demo company.
- Added external `kimi_cli` adapter with Paperclip issue context, skills, instructions, and auto issue closeout.
- Created shared brief, 100-point rubric, agent instructions, runtime-duel skills, MCP policy/ledger, scoring script, run script, and evidence exporter.
- Ran Kimi once, found an imprecise Claude lane description, reopened RUN-2, and reran Kimi.
- Ran Claude once, found `TBD` placeholders for Kimi evidence, reopened RUN-1, and reran Claude.
- Local pre-Pro review found Kimi incorrectly described provider as "from run evidence" even though Kimi `usageJson` is null; canceled the first Pro submit before prompt send, reopened RUN-2, and reran Kimi with configured-model evidence wording.
- Reopened RUN-1 again so Claude consumed Kimi v3 and removed the stale Kimi provider wording.
- Re-exported evidence and reran secret scan after both final runs.

## Attachments To Inspect

- `claude_code_demo.md`: Claude Code lane final content artifact.
- `kimi_demo.md`: Kimi lane final content artifact.
- `scorecard.json`: deterministic scoring result.
- `runtime_config_redacted.json`: Paperclip company/agent/adapter config with secrets redacted.
- `run_matrix.json`: latest Paperclip heartbeat run evidence.
- `artifact_ledger.json`: artifact paths, sizes, hashes.
- `secret_scan.json`: local secret scan result.
- `MANIFEST.md`: evidence package index.

## Known Boundaries

- This is a local-context demo. It must not claim internet research, real customer validation, production launch readiness, or safety certification.
- The Labebe demo content is based on local files under `/vol1/1000/projects/toyresearch`, especially `sdd.md` and `my - 红队审核与建议.md`.
- The live Labebe control-plane smoke and P0/P1 remediation were handled separately; this packet focuses on the new runtime duel company and same-goal generation quality.
- If the demo feels "complete but not stunning," please be direct and propose the minimum iteration needed to make it feel executive-demo quality.
