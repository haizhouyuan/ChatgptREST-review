# Finbot Engineering Company Agent Rules

Scope: this file governs this repository only.

## Mission

Build a governed Finbot `capability_lab_v1` harness that supplies read-only
contracts, fixtures, schema, validators, prototype runners, adapter smoke
records and governed handoff packets for Finbot Research agents.

This repository is not the real Finbot business company and does not run
investment workflows, broker workflows or production watchlists.

## Hard Boundaries

- `apply` and production Paperclip mutation are disabled by default.
- All writes must remain under `/vol1/1000/projects/toyresearch/paperclip_finbot_engineering_company`.
- Do not write to `/vol1/maint`, production kernel worktrees, `ChatgptREST`, `codexread`, `finagent`, `finchat`, home config, Hermes, global Paperclip config, live queues, memory registries, Skill/MCP registries, or runtime configs.
- Do not run broker/trading APIs, real market data fetch, production watchlist jobs, cron/daemon registration, service restarts, MCP activation, skill install/edit, durable external memory writes, `git push`, or package publish.
- Allowed work inside this repository: read-only capability contracts, fixture-backed prototypes, schema, validators, negative fixtures, adapter smoke designs, local artifact manifests and governed handoff evidence.
- Finbot complete-system objects may be defined as contracts only. Live Paperclip issues may reference this repository as evidence through external carrier issues, but this repository must not self-register as a production company or mutate native runtime/MCP/skill configuration.

## Closeout Rule

Implementation issues cannot close with a plan. A closeout must include:

- changed files;
- artifact manifest;
- validation commands and results;
- stdout/stderr path or summary;
- diff or commit reference;
- evidence path.
