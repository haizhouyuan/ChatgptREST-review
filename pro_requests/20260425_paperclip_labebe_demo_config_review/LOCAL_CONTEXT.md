# Local Context - Labebe Paperclip Demo Config Review

Date: 2026-04-25

## What I Read Locally

Maint source:

- `/vol1/maint/AGENTS.md`
- `/vol1/maint/docs/infra_registry.md`
- `/vol1/maint/docs/privacy_and_secret_governance.md`
- `/vol1/maint/docs/project_workspace_registry.md`
- `/vol1/maint/docs/repo_governance.md`
- `/vol1/maint/MAIN/README.md`
- `/vol1/maint/docs/2026-04-21_projects_multica_paperclip_install_and_github_http11.md`
- `/vol1/maint/docs/2026-04-23_multica_paperclip_finbot_history_audit_handoff.md`
- `/vol1/maint/docs/2026-04-23_multica_hermes_总计划_v1.md`
- `/vol1/maint/docs/2026-04-23_multica_hermes_operating_spec_v2.md`
- `/vol1/maint/docs/2026-04-24_codex_lane_and_hermes_auth_repair.md`
- `/vol1/maint/docs/control_plane/multica_native_no_write_worker_smoke_spec_v0.md`

Paperclip source:

- `/vol1/1000/projects/paperclip/doc/GOAL.md`
- `/vol1/1000/projects/paperclip/doc/PRODUCT.md`
- `/vol1/1000/projects/paperclip/doc/SPEC-implementation.md`
- `/vol1/1000/projects/paperclip/doc/DEVELOPING.md`
- `/vol1/1000/projects/paperclip/doc/DATABASE.md`
- `/vol1/1000/projects/paperclip/docs/companies/companies-spec.md`
- `/vol1/1000/projects/paperclip/docs/guides/agent-developer/writing-a-skill.md`
- `/vol1/1000/projects/paperclip/docs/agents-runtime.md`
- `/vol1/1000/projects/paperclip/docs/adapters/process.md`
- `/vol1/1000/projects/paperclip/packages/mcp-server/README.md`
- `/vol1/1000/projects/paperclip/skills/paperclip/SKILL.md`
- `/vol1/1000/projects/paperclip/skills/paperclip/references/company-skills.md`

Demo intake:

- `/vol1/1000/projects/toyresearch/my - 红队审核与建议.md`

## Multica Facts

- Multica CLI: `/home/yuanhaizhou/.local/bin/multica`
- Version: `multica 0.2.15`
- Server: `http://127.0.0.1:18782`
- App: `http://localhost:13702`
- Active runtimes observed: `codex`, `hermes`, `gemini`, `claude`, `kimi`
- OpenClaw is excluded from intended runtime pool by maint policy.
- Current Codex daemon lane should use `.codex1`, not the old `.codex2`.

## Paperclip Instance

- Paperclip URL: `http://127.0.0.1:3100`
- Health: `ok`
- Version: `0.3.1`
- Deployment mode: `local_trusted`
- Exposure: `private`
- Instance home: `/vol1/1000/projects/toyresearch/.paperclip-labebe`
- Instance ID: `labebe-demo`
- Server is running in tmux session `paperclip-labebe-demo`.
- Real API key and DB are excluded from the portable/review packet.

## Paperclip Company

- Company: `Labebe AI Design Studio`
- Company ID: `1cb6d439-2bdf-4f63-ad9a-b5326d5546df`
- Project: `Labebe AI Design Studio`
- Agents: 9
- Issues: 10 imported epics plus smoke/demo issues as needed.
- Adapter type: `process` for all 9 agents.

## Why Process Adapter

This demo is intended to prove Paperclip orchestration, governance, issue flow, skill registry, MCP configuration, and heartbeat evidence without spending paid model runtime or depending on external account access.

The process adapter runs:

```text
/usr/bin/env python3 /vol1/1000/projects/toyresearch/labebe-ai-design-studio/workspace/scripts/paperclip_demo_agent.py
```

The script reads local governance docs, selects an assigned issue, writes an artifact into `outputs`, and updates Paperclip when API access is available.

Known limitation: Paperclip currently records desired skills for process adapters, but the process adapter does not inject skill files into the child process. The script therefore reads workspace docs directly.

## Skills Configured

Company skill library includes:

- `paperclipai/paperclip/paperclip`
- `paperclipai/paperclip/paperclip-create-agent`
- `local/c25256c296/labebe-demo-governance`
- `local/eb381c0339/labebe-product-concept-workflow`
- `local/a6d9633ebd/paperclip-demo-operator`

The built-in Paperclip skills `paperclip-create-plugin` and `para-memory-files` are also present because local Paperclip skill setup imported them. They are not core to the Labebe process demo.

## MCP Config

Paperclip MCP server source:

- `/vol1/1000/projects/paperclip/packages/mcp-server`

MCP template:

- `labebe-ai-design-studio/workspace/config/mcp.paperclip.template.json`

MCP local secret env:

- `/vol1/1000/projects/toyresearch/.paperclip-labebe/instances/labebe-demo/mcp.env`
- mode `600`
- contains a local agent API key and is not included in the packet.

MCP smoke test passed using JSON-RPC initialize and `tools/list`; the server returned the Paperclip tool surface.

## Demo Goal

Build a board-ready Labebe AI Design Studio demo that turns local customer, competitor, and product signals into review-ready product design concepts and launch-test assets.

The demo must show:

- Paperclip company and org chart.
- Agent role and skill assignment.
- MCP template without raw secrets.
- Local evidence policy and forbidden claims.
- Issues representing the red-team issue tree.
- Process heartbeat evidence.
- A completed end-to-end case issue.

## Operating Conditions

- Loopback only: `127.0.0.1:3100`
- No real external accounts.
- No real customer data.
- No raw secrets in portable config.
- Demo sample data must stay labeled as demo samples.
- Human review gates required for strategy, product opportunity, safety, DFM, cost, compliance-adjacent language, and external publication.

## Current Artifacts

- Company package: `paperclip_labebe_demo_package/`
- Workspace: `labebe-ai-design-studio/workspace/`
- Runtime matrix: `labebe-ai-design-studio/workspace/config/agent-runtime-matrix.yaml`
- Skill registry: `labebe-ai-design-studio/workspace/config/skill-registry.yaml`
- MCP template: `labebe-ai-design-studio/workspace/config/mcp.paperclip.template.json`
- MCP tool policy: `labebe-ai-design-studio/workspace/config/mcp-tool-policy.yaml`
- Demo brief: `labebe-ai-design-studio/workspace/config/demo-brief.yaml`
- Case runbook: `labebe-ai-design-studio/workspace/runbooks/run-demo-case.md`
- Heartbeat artifacts: `labebe-ai-design-studio/workspace/outputs/`

## 2026-04-26 P0/P1 Closeout

- Live epic identifiers were normalized to match package source of truth: `LAB-0` through `LAB-9`.
- Target smoke issue is fixed as `LAB-SMOKE-001` / `CASE 1 - Data Truth Guard end-to-end smoke`.
- Data Truth Guard adapter env now includes `LABEBE_TARGET_ISSUE_IDENTIFIER=LAB-SMOKE-001` and `LABEBE_SMOKE_RUN_TOKEN=20260426-p0p1-final`.
- The worker now prefers the fixed smoke target and uses the smoke token to stop automatic follow-up wakes from overwriting the primary evidence file.
- Final smoke closed loop: `LAB-SMOKE-001` reached `done`, wrote `outputs/case-LAB-SMOKE-001-data-truth-guard.md`, and added a Paperclip comment containing the artifact path.
- Evidence now includes non-empty `issues_redacted.json`, `issue_consistency_check.json`, `mcp_tools_list_redacted.json`, `mcp_policy_check.json`, `artifact_ledger.json`, `package_manifest.txt`, and `secret_scan.txt`.

## What I Need From Pro

Please review whether this is now a coherent, defensible Paperclip demo configuration rather than a superficial agent list. Identify gaps in:

- skill design and assignment,
- MCP template and secret handling,
- agent configuration,
- issue tree and review gates,
- process adapter design,
- demo story for a boss presentation,
- end-to-end case acceptance,
- remaining P0/P1/P2 fixes before demo.
