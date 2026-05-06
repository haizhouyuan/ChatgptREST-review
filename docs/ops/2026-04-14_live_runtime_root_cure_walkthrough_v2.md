# 2026-04-14 Live Runtime Root-Cure Walkthrough v2

## Summary

This round completed the last system-owned layer behind the “live runtime instability” family.

Earlier rounds had already:

- fixed send-phase truth drift
- fixed wait/export finalization gaps including issue `#211`
- tightened repair/autofix routing and budget controls
- added ChatGPT executor-side transient recovery before worker retry budget
- moved validation surfaces onto the shared sessionful MCP client

The remaining gap was narrower:

- the public wrapper could still fail in `wait`
- the same underlying session could still be resolved by direct `advisor_agent_wait` / `advisor_agent_status`
- live validation itself was using more sessions than necessary

So the final work was:

1. harden wrapper wait recovery
2. make direct script execution self-bootstrapping
3. finish with a single low-noise `thinking_heavy + claudeminmax` live proof

## Code Changes

### Shared MCP and wrapper

- [chatgptrest/integrations/mcp_http_client.py](/vol1/1000/projects/ChatgptREST/chatgptrest/integrations/mcp_http_client.py:1)
  - initialize handshake now retries once on transient sessionful HTTP failures
- [chatgptrest_call.py](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py:1)
  - adds repo-root `sys.path` bootstrap
  - keeps wrapper on the shared sessionful MCP helpers
  - refreshes MCP session on recoverable wait/status transport faults
  - preserves transport-timeout chain semantics for `still_running_possible`

### Tests

- [tests/test_chatgpt_wait_transient_recovery.py](/vol1/1000/projects/ChatgptREST/tests/test_chatgpt_wait_transient_recovery.py:1)
- [tests/test_mcp_http_error_propagation.py](/vol1/1000/projects/ChatgptREST/tests/test_mcp_http_error_propagation.py:1)
- [tests/test_skill_chatgptrest_call.py](/vol1/1000/projects/ChatgptREST/tests/test_skill_chatgptrest_call.py:1)

The narrow regression bundle for this final layer passed:

- `48 passed`

## Live Evidence

### Excess validation sessions were stopped

Per user instruction, the earlier extra live sessions were explicitly cancelled:

- `agent_sess_e58257e0b2044a76`
- `agent_sess_7cefca4c0822468b`

This froze the validation policy to a minimal-noise live boundary.

### Final live proof used `thinking_heavy`, not Pro

Final proof session:

- session: `agent_sess_96d7f56cb7af4bd0`
- route: `report`
- requested execution lane: `coding_agent`
- requested executor: `claudeminmax`
- effective execution profile: `thinking_heavy`
- final provider path: `["claudeminmax"]`

Observed terminal state:

- `status = completed`
- `wait_status = completed`
- `timed_out = false`
- wrapper returned the final answer normally
- artifact produced:
  - [result.json](/vol1/1000/projects/ChatgptREST/artifacts/controller_coding_agent/f21099b5e3f641c4bc115d3483499356/result.json)

Key summary artifact:

- [consult_summary_v3.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/live_runtime_root_cure_20260414_v4/claudeminmax/consult_summary_v3.json)

Important detail:

- this proof went through the real wrapper wait path that previously failed with `McpHttpError: transport timeout: timed out`
- after the wrapper hardening, the same class of path completed cleanly

## Assessment

Within the system boundary, the live-runtime instability has now been root-cured:

1. ChatGPT executor transient loss is handled before worker retry-budget burn.
2. MCP initialize no longer fails on a single transient sessionful-HTTP timeout.
3. The wrapper wait path no longer lags behind the underlying public MCP session contract.
4. Live validation is now intentionally low-noise and no longer depends on Pro-style stress probes.

## Remaining Boundary

This does not mean external web providers can never drift again.

The remaining irreducible risk is outside the system boundary:

- upstream verification / captcha / login interruptions
- real UI drift on ChatGPT / Gemini web surfaces
- upstream throttling or backend latency beyond local retry budgets

The root-cure is that these external failures are no longer amplified by ChatgptREST’s own control plane, wrapper, or validation surfaces.
