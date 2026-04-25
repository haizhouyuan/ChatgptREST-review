# Runtime And Skill Notes

## Runtime Choice

This demo intentionally uses the Paperclip `process` adapter. The child process is deterministic and local-only, so the demo does not depend on paid model adapters or external accounts.

The runtime command is:

```text
/usr/bin/env python3 /vol1/1000/projects/toyresearch/labebe-ai-design-studio/workspace/scripts/paperclip_demo_agent.py
```

The working directory is:

```text
/vol1/1000/projects/toyresearch/labebe-ai-design-studio/workspace
```

## Skill Handling

Company skills are imported into Paperclip and desired skills are recorded on each agent. The current `process` adapter does not inject skill files into the child process. This is a runtime limitation, not an omitted configuration.

The deterministic demo worker compensates by reading the workspace documents directly:

- `docs/AGENTS.md`
- `docs/DESIGN.md`
- `docs/DATA_TRUTH.md`
- `docs/FORBIDDEN_CLAIMS.md`
- `docs/ACTION_POLICY.md`
- `docs/REFERENCE_MAP.md`
- `docs/DEMO_SAMPLE_POLICY.md`

If the runtime is later changed to a model adapter with skill sync support, the same company skill registry can be reused and the desired skills should be injected by the adapter.

## MCP Handling

The real local MCP env file lives outside the portable packet under the ignored Paperclip home. The portable packet only carries templates with placeholders:

- `PAPERCLIP_API_URL`
- `PAPERCLIP_API_KEY`
- `PAPERCLIP_COMPANY_ID`
- `PAPERCLIP_AGENT_ID`
- `PAPERCLIP_RUN_ID`

Raw API keys are not stored in the package, review packet, or workspace docs.

## Process Env Contract

Paperclip injects the local control-plane values at runtime. The portable packet documents names only; it must not contain the live key values.

Required for audited smoke:

- `PAPERCLIP_API_URL`: loopback Paperclip API URL.
- `PAPERCLIP_API_KEY`: local agent API key, stored outside the packet.
- `PAPERCLIP_COMPANY_ID`: `1cb6d439-2bdf-4f63-ad9a-b5326d5546df`.
- `PAPERCLIP_AGENT_ID`: Data Truth Guard agent id for the smoke run.
- `PAPERCLIP_RUN_ID`: optional generally, required for audited mutating MCP/API calls.
- `LABEBE_AGENT_SLUG`: `data-truth-guard`.
- `LABEBE_TARGET_ISSUE_IDENTIFIER`: `LAB-SMOKE-001`.
- `LABEBE_SMOKE_RUN_TOKEN`: run idempotency token for the current audited smoke.

The Data Truth smoke worker must prefer `LABEBE_TARGET_ISSUE_IDENTIFIER` over opportunistic queue selection so the demo cannot drift to an unrelated epic.
The token prevents automatic comment/status follow-up wakes from overwriting the primary heartbeat artifact for the same audited run.
