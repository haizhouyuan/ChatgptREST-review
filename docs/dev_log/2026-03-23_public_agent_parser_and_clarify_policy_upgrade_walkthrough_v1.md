## Walkthrough

### Why this slice was done now

The previous commits already exposed canonical `task_intake` and same-session `contract_patch` on the public MCP surface. The next bottleneck was quality:

- message-only asks still collapsed into raw objective text
- `thinking_heavy` route selection had improved, but clarify policy still behaved too much like generic research gating
- clarify responses still lacked enough machine-readable structure for coding agents to self-repair

This slice addresses those three points together.

### Implementation notes

1. Added a new lightweight parser in `chatgptrest/advisor/message_contract_parser.py`
2. Wired parser output into `build_task_intake_spec(...)`
3. Wired parser output into `normalize_ask_contract(...)`
4. Added `clarify_reason_code` to strategy planning
5. Updated clarify policy so `thinking_heavy + analysis_heavy + core contract present` can execute without unnecessary clarify
6. Expanded `/v3/agent/turn` clarify diagnostics to include machine-readable codes and resubmit payloads

### Test additions

- parser fallback into canonical intake
- machine-readable clarify reason code
- `thinking_heavy` mid-completeness execution path
- clarify response now includes `recommended_resubmit_payload`

### Scope boundary

This change intentionally does **not** introduce a heavy natural-language parser. The parser is a conservative labeled-line fallback, not a semantic extraction engine.

It also does **not** replace explicit contract ingress. Explicit `task_intake` remains the preferred path.
