# Task 6 Memory Layer Contract

Generated: 2026-05-11T12:45:00+08:00

## Scope

This packet covers Paperclip Real OS Acceptance Plan Task 6: Memory substrate with fresh-agent blind tests.

Allowed packet files:

- `memory_layer_contract.md`
- `current_truth_ledger.jsonl`
- `authority_ledger.jsonl`
- `verbatim_registry.jsonl`
- `fresh_agent_blind_tests.json`
- `closeout.md`
- `validator_result.json`, produced by `python3 scripts/real_os_acceptance_validate_memory.py`

The packet is designed for a fresh agent that does not have full chat history. The fresh agent must use only this packet and the source paths named inside it.

## Layer Rules

### Current Truth Ledger

`current_truth_ledger.jsonl` records current execution facts that can drive the next action. It is not a place for durable policy promotion. Every row must name a source path and a freshness basis.

### Authority Ledger

`authority_ledger.jsonl` is restricted to Governance-approved rules only. A row is valid only when `approval_status` is `governance_approved_rule`.

Forbidden in the authority ledger:

- candidate memory deltas promoted as authority;
- sandbox or challenger provider state promoted as authority;
- provider production use without a later Governance approval artifact;
- full-chat-history recollections as authority.

### Verbatim Registry

`verbatim_registry.jsonl` stores source pointers and short exact excerpts. It is evidence-pointer material only. It cannot override current truth or the authority ledger.

### Candidate And Sandbox Material

Candidate memory, sandbox outputs, provider projections, and no-write smoke results may be useful evidence. They must stay outside `authority_ledger.jsonl` unless Governance explicitly approves promotion in a later issue with workflow proof.

## Fresh-Agent Blind Test Rule

Each blind test must satisfy all of the following:

- `uses_full_chat_history` is false;
- allowed inputs are only this memory/current-truth packet;
- the result names one correct next action;
- the result cites ledger ids or source paths;
- at least two of the three tests improve over the no-memory baseline.

## Current Next Action

The next agent should run:

```bash
python3 scripts/real_os_acceptance_validate_memory.py
```

Then it should use `validator_result.json` and this closeout packet as the Task 6 evidence path. No commit is part of this task.
