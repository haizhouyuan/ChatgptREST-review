# Open Source References Not Uploaded

Per user instruction, this packet does not upload open-source repository contents. Reviewers may use these public references if needed, but the requested judgment should primarily use the attached sanitized evidence.

## Multica
- Public repo: https://github.com/multica-ai/multica
- Local commit observed: `632fdde70009a5e249f4177cb1949bab8efbd8dc`
- Local observations used by sidecar, not copied as source:
  - `agent.mcp_config` is a raw JSON field; Claude runtime passes it as executable MCP config via `--mcp-config`.
  - Hermes runtime did not show an equivalent obvious `mcp_config` execution path in the local inspection.
  - CLI supports `agent skills list/set`, replacing assignments.
  - Workspace skills are explicit Multica artifacts and assigning them changes live agent behavior/prompt surface.

## Planning Hermes Skills
- These are local private skill docs, so sanitized content is included under `docs/planning_hermes_skills_*`.
