# Summary

Hardened `request_cancel(...)` so wait-phase `in_progress` jobs can terminalize immediately instead of sitting on `cancel_requested_at` until a wait worker happens to reclaim them.

# Problem

Before this patch, `chatgptrest/core/job_store.py:request_cancel(...)` behaved like this:

- `queued` job: transition straight to `canceled`
- terminal job: no-op
- any other non-terminal job: only set `cancel_requested_at`

That meant a wait-phase job with:

- `status=in_progress`
- `phase=wait`

would still remain visible as `in_progress` after `/cancel`, sometimes for a long time if the wait worker backlog was large.

This was the exact operational pain called out in handoff v2 section 3.3 / 5.5.

# Fix

In [job_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/job_store.py):

- kept the existing generic `cancel_requested_at` fallback for non-wait active work
- added a narrow fast-path only for:
  - `status = in_progress`
  - `phase = wait`

The fast-path splits into two safe cases:

1. active valid wait lease:
   - use existing `store_canceled_result(...)` with the current lease owner/token
   - transition immediately to `canceled`

2. wait lease already missing/expired:
   - transition directly to `canceled`
   - clear stale lease fields
   - write canonical `result.json`

Non-wait active work still preserves old behavior. I did **not** change send/full cancellation semantics in this patch.

# Why This Boundary

`request_cancel(...)` has a critical blast radius because it feeds both:

- `/v1/jobs/{job_id}/cancel`
- `agent_v3` session cancel via `_cancel_job(...)`

So this patch intentionally avoids “make all in-progress cancellation immediate”.

Only wait-phase work is safe to收口 here because it is already in the polling / deferred side of the state machine. This reduces backlog pain without changing live send/full execution semantics.

# Tests

Focused regression set:

```bash
./.venv/bin/pytest -q \
  tests/test_leases.py::test_cancel_wait_phase_with_active_lease_finalizes_immediately \
  tests/test_leases.py::test_cancel_wait_phase_with_expired_lease_finalizes_immediately \
  tests/test_contract_v1.py::test_cancel_queued_writes_result_json \
  tests/test_cancel_attribution.py::test_cancel_requested_event_includes_request_metadata
```

Passed.

Added coverage for:

- wait-phase cancel with an active lease finalizing immediately
- wait-phase cancel with an expired lease finalizing immediately

# Notes

While running a broader `tests/test_leases.py` sweep, `test_retryable_ask_extends_max_attempts` still failed independently at job creation (`400` on `gemini_web.ask`). This looks unrelated to the wait-cancel patch and was not introduced here; the targeted cancel regression set above passed cleanly.
