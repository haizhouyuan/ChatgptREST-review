# 2026-04-04 W1 MCP HTTP Transport and Same-Runtime Reclaim Alignment v1

## 1. Why this batch existed

After the previous W1 stabilization batch, the live problem narrowed again. Queue starvation by `repair.autofix` was reduced, but Gemini live sends were still repeatedly failing with `McpHttpError: SSE stream timeout (deadline exceeded)` and then cycling through the same blank no-thread state.

The next useful question became: are we still paying unnecessary time in the transport and idempotency layers before we even get a truthful provider verdict?

## 2. What changed

### 2.1 same-runtime blank Gemini reclaim

Changed [idempotency.py](/vol1/1000/projects/ChatgptREST/chatgpt_web_mcp/idempotency.py) so ChatgptREST-owned Gemini idempotency keys can reclaim blank `in_progress` records within the same runtime after a short bounded window (`30s`).

Independent judgment: this is valuable because Gemini blank no-thread failures are exactly the kind of case where the system should recover the existing work item, not remain wedged behind a stale unsent record from the same runtime.

### 2.2 transport / tool-call error observability

Changed [mcp_http_client.py](/vol1/1000/projects/ChatgptREST/chatgptrest/integrations/mcp_http_client.py) and [mcp_http.py](/vol1/1000/projects/ChatgptREST/chatgptrest/driver/backends/mcp_http.py) so empty exceptions no longer collapse into unhelpful strings.

Independent judgment: this is not just nice-to-have logging. It is what made the current blocker legible as `SSE stream timeout (deadline exceeded)` instead of generic empty transport failure.

### 2.3 no fresh-session retry on deadline timeout

Changed [mcp_http_client.py](/vol1/1000/projects/ChatgptREST/chatgptrest/integrations/mcp_http_client.py) so `McpHttpClient.call_tool()` no longer blindly retries once with a fresh session for every `McpHttpError`.

It now retries only for likely session/transport-establishment problems, and **does not** fresh-session replay `deadline exceeded` / `stream timeout` failures.

Independent judgment: this is the correct boundary. A fresh-session retry is useful when MCP session state likely rotated or the request never established cleanly. It is wasteful when the underlying tool call already spent most of the timeout budget and then ended in a deadline timeout. In that case, replaying the whole request again just doubles latency and muddies the live evidence.

## 3. Tests

Green tests for this batch:

- [test_driver_idempotency_upload_hash.py](/vol1/1000/projects/ChatgptREST/tests/test_driver_idempotency_upload_hash.py)
- [test_mcp_http_error_propagation.py](/vol1/1000/projects/ChatgptREST/tests/test_mcp_http_error_propagation.py)

Additional regressions re-run because `McpHttpToolCaller` has higher blast radius:

- [test_openclawbot_planning_task_plane_live_completion_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_openclawbot_planning_task_plane_live_completion_gate.py)
- [test_run_openclawbot_planning_task_plane_live_completion_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_run_openclawbot_planning_task_plane_live_completion_gate.py)

## 4. Near-live evidence

After restarting the send worker with this transport change, the next live Gemini send job was:

- `job_id=00de875559984b909842f32d4a69564b`

Observed state after one fresh run:

- `status=in_progress`
- `phase=send`
- `last_error_type=UiTransientError`
- `last_error=<TimeoutError: empty error>`
- no thread URL yet

Relevant worker journal evidence now shows:

- the job consumed a single `executor=89s` send cycle on the fresh worker
- the old repeated `gemini send attempt ... SSE stream timeout` pattern is no longer the dominating visible symptom in the same way as before the transport retry tightening

This does **not** mean live completion is green. It means the transport layer is less likely to replay the same deadline-bound request and inflate the latency envelope.

## 5. What this batch proved

This batch proved 3 things:

1. same-runtime Gemini blank in-progress reclaim now has a narrower, more useful recovery window;
2. transport errors are easier to diagnose;
3. MCP fresh-session replay is no longer obviously doubling some deadline-bound Gemini send failures.

## 6. What is still not done

This batch still does not complete W1.

Still open:

1. Gemini live completion remains unstable under the current gate contract.
2. The provider still reaches no-thread timeout-style failure in live conditions.
3. ChatGPT live lane remains verification-blocked.

## 7. Current judgment

This batch is another narrowing move. It removes low-value transport replay and reduces ambiguity. The remaining problem is now even more clearly inside the real Gemini live completion path, not inside generic MCP session retry behavior.
