# 03 Governed Connector Smoke Protocol

Each connector smoke must record read-only scope, secret boundary, command/tool, result summary, artifact path, rollback/disable note, allowed downstream use, and disallowed use.

Workflow verification requires a complete read-only path from request to artifact to validator. Endpoint reachability alone is `endpoint_alive_only`, not `workflow_verified`.

Guarded connectors Readwise, Zotero, Alpaca, Daloopa, Quartr and Binance remain `candidate_to_enable` unless a current-lane read-only smoke is approved by Governance.

Smoke runner: `python3 tools/finbot_capability_smoke_runner.py --docs-root /vol1/1000/projects/toyresearch/docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform`.
