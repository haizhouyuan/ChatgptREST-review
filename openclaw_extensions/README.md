# OpenClaw Cognitive-Substrate Plugins

This directory packages the OpenClaw-side integration assets for the
OpenMind cognitive substrate.

Included plugins:

- `openmind-memory`
- `openmind-graph`
- `openmind-telemetry`

Each plugin is a local OpenClaw extension package with:

- `package.json`
- `openclaw.plugin.json`
- `index.ts`
- `README.md`

Installation is handled by `scripts/install_openclaw_cognitive_plugins.py`.

Canonical current-state docs:

- Authority boundary ADR:
  - `docs/contracts/ADR-005-openmind-openclaw-chatgptrest-authority-boundary-v1.md`
- Current runtime contract:
  - `docs/integrations/2026-04-09_openclaw_cognitive_substrate_runtime_contract_v4.md`
- Wake-up packet contract:
  - `docs/contracts/2026-04-09_wakeup_packet_contract_v2.md`
- OpenMind scope inventory:
  - `docs/contracts/2026-04-09_openmind_scope_surface_inventory_v2.md`
- Crystallized-learning governance contract:
  - `docs/contracts/2026-04-09_crystallized_learning_governance_contract_v1.md`
- Multi-phase execution plan:
  - `docs/roadmaps/2026-04-09_openmind_project_scope_and_authority_execution_plan_v1.md`
- Phase execution closeout:
  - `docs/dev_log/2026-04-09_openmind_phase_execution_todo_and_closeout_v2.md`

Historical snapshot:

- `docs/integrations/openclaw_cognitive_substrate.md` is retained as the
  2026-03-08 integration snapshot and is no longer the canonical description of
  the current runtime contract.
