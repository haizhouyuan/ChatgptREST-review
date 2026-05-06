# 2026-04-14 Live Runtime Root-Cure Execution Plan v3

## Why v3 Exists

`v2` defined the code-side root-cure work. After that landed, one more system-owned gap was confirmed:

- the repo wrapper `skills-src/chatgptrest-call/scripts/chatgptrest_call.py` could still lose the terminal state during `advisor_agent_wait`
- a direct `advisor_agent_wait` / `advisor_agent_status` against the same session could succeed
- so the remaining drift was no longer provider-only; it was wrapper wait recovery plus test-policy noise

This version freezes the final plan with the new validation boundary the user asked for:

- minimize live session count
- do not use ChatGPT Pro for validation
- prefer `thinking_heavy`
- keep one real `claudeminmax` MCP scenario as the live proof

## Final Root-Cause Statement

The system-owned instability had three layers:

1. Provider/executor transient loss
   - ChatGPT wait/send still over-relied on worker retry budget after runtime page/transport loss
2. MCP transport drift
   - sessionful MCP initialize was missing transient retry
3. Wrapper recovery drift
   - the wrapper wait path could still fail even when the same session was recoverable through status/wait on the server side

The root-cure target is therefore:

- recover local transient runtime failures before worker retry budget
- keep MCP sessionful HTTP resilient to transient initialize faults
- make wrapper wait recovery no weaker than the underlying public MCP/session contract

## Completed Code Work

### 1. ChatGPT executor transient recovery

- ChatGPT wait/send transient failures now run executor-side self-check first
- transient page/transport loss is retried or resumed locally before worker retry budget is consumed
- verification/manual blockers fail closed into explicit follow-up states

### 2. MCP initialize hardening

- `mcp_http_initialize_handshake(...)` now retries once on transient sessionful-HTTP initialize failures
- covered families include:
  - deadline exceeded
  - stream timeout
  - transport timeout / transport error
  - connection refused / connection closed
  - SSE stream ended without JSON-RPC response

### 3. Wrapper wait-path root-cure

- `chatgptrest_call.py` now bootstraps repo root into `sys.path` before importing repo modules
- wrapper MCP calls now use the shared sessionful MCP helpers
- wait recovery now:
  - tolerates recoverable wait transport failure
  - checks status on the same session
  - refreshes MCP session for the next read-only wait/status attempt
  - preserves `still_running_possible=true` when recovery exhausts after a real transport timeout chain

## Validation Policy v3

Per user instruction, the live validation posture is now:

- minimal live session count
- no ChatGPT Pro validation turns
- prefer `thinking_heavy`
- prefer a single `requested_executor=claudeminmax` session over broad multi-session live sweeps

This policy is part of the root-cure boundary because excess live probes were themselves creating avoidable noise.

## Final Success Standard

This work counts as complete only if all of the following are true:

1. ChatGPT transient runtime loss is handled inside the executor before worker retry-budget escalation.
2. MCP initialize is resilient enough that the public MCP surface does not flap on a single transient SSE timeout.
3. The wrapper no longer loses terminal state on a session that the underlying public MCP can still resolve.
4. One real low-noise live scenario succeeds with:
   - `execution_profile=thinking_heavy`
   - `requested_execution_lane=coding_agent`
   - `requested_executor=claudeminmax`
5. The remaining unreduced risk is external-only:
   - upstream web verification / captcha / login
   - real site/UI drift
   - provider/backend throttling outside local retry budget
