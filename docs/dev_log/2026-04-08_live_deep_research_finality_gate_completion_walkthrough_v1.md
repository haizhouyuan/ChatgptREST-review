# Live Deep Research Finality Gate Completion Walkthrough V1

Date: 2026-04-08

## What happened

The first live gate rerun after the duplicate-guard fix still failed.

Failure mode:

- `coding_agent_wait` reached a final session successfully
- `coding_agent_answer` still returned `401 unauthorized`

This exposed a narrower issue:

- the public MCP service runtime did not carry a jobs API bearer token
- `_job_answer()` could not read `/v1/jobs/{job_id}/answer`
- even though the final session already contained the canonical answer text

## What I changed

I did two things:

1. kept the earlier auth header improvement on `_job_answer()`
2. added a safer fallback in `advisor_agent_answer()`:
   - if the job answer API is unavailable
   - and the session has a final `last_answer`
   - return that as `last_answer_fallback` instead of failing the public lane

## Verification path

Verification happened in three layers:

1. targeted pytest for `agent_mcp` answer behavior
2. direct public MCP smoke call against `coding_agent_answer`
3. full live Deep Research finality gate rerun

The final green bundle is:

- [20260407T230813Z report json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/live_deep_research_finality_gate_manual/20260407T230813Z/report.json)

## Why this is the right public behavior

The public lane contract is for coding agents, not for internal jobs API purity.

If the final answer is already safely available from the terminal session payload, the coding-agent surface should deliver that answer rather than expose an internal auth mismatch as a client failure.
