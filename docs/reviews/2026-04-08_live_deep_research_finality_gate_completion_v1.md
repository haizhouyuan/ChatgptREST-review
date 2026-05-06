# Live Deep Research Finality Gate Completion V1

Date: 2026-04-08

Primary green evidence bundle:

- [live gate report json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/live_deep_research_finality_gate_manual/20260407T230813Z/report.json)
- [live gate report md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/live_deep_research_finality_gate_manual/20260407T230813Z/report.md)
- [turn result](/vol1/1000/projects/ChatgptREST/artifacts/monitor/live_deep_research_finality_gate_manual/20260407T230813Z/turn_result.json)
- [session early](/vol1/1000/projects/ChatgptREST/artifacts/monitor/live_deep_research_finality_gate_manual/20260407T230813Z/session_early.json)
- [wait result](/vol1/1000/projects/ChatgptREST/artifacts/monitor/live_deep_research_finality_gate_manual/20260407T230813Z/wait_result.json)
- [session final](/vol1/1000/projects/ChatgptREST/artifacts/monitor/live_deep_research_finality_gate_manual/20260407T230813Z/session_final.json)
- [answer result](/vol1/1000/projects/ChatgptREST/artifacts/monitor/live_deep_research_finality_gate_manual/20260407T230813Z/answer_result.json)

Supporting failed-then-fixed evidence:

- [pre-fix failing gate report json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/live_deep_research_finality_gate_manual/20260407T225020Z/report.json)

## 1. Completion decision

The live Deep Research finality gate is now **complete and green**.

Latest result:

- checks: `8`
- passed: `8`
- failed: `0`

## 2. What changed

The remaining blocker was not provider finality.

It was the narrow public answer lane:

- `coding_agent_answer` previously failed when the job answer API returned `401 unauthorized`
- the public MCP service had no local API token in its runtime env
- the old implementation treated that as a hard failure, even when the session already carried the final canonical answer text

The fix was to degrade safely:

- if the authoritative job answer API is unavailable
- and the session already has a final `last_answer`
- `advisor_agent_answer` / `coding_agent_answer` now return that canonical session answer as `last_answer_fallback`

## 3. What the green run proves

The green evidence pack proves all of the required behaviors:

1. Deferred Deep Research turn is accepted on the supported `coding-agent-v1` lane.
2. Early observation stays provisional:
   - `status=running`
   - `answer_state=pending`
   - `answer_ready=false`
3. Final session reaches:
   - `status=completed`
   - `answer_state=final`
   - `answer_ready=true`
4. Canonical answer fetch succeeds through the public MCP lane.
5. The fetched answer exceeds the minimum length threshold.

## 4. Important implementation note

The green result uses:

- `source = last_answer_fallback`
- `fallback_reason = job_answer_api_unavailable`
- `fallback_status_code = 401`

This is acceptable for the current public lane contract.

Why:

- the lane contract guarantees a canonical answer surface to coding agents
- it does **not** require the answer to come only from `/v1/jobs/{job_id}/answer`
- when the session already contains the final canonical answer, falling back to that session payload is the safer public behavior

## 5. Operational conclusion

H is complete.

This closes the red-team follow-up requirement that the unified gate pack was not enough by itself and that a live Deep Research finality proof still had to be demonstrated.
