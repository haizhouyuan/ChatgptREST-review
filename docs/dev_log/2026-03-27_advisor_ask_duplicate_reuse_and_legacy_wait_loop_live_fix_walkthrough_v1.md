# 2026-03-27 advisor_ask duplicate reuse and legacy wait-loop live fix walkthrough v1

## What was observed

- Users still saw repeated test/trivial threads in ChatGPT even after the earlier prompt-policy and worker guard work.
- Live replay of a recent completed `advisor_ask` did not reuse the existing job; it created a fresh deep-research job instead.
- The old `测试` thread mapped to `job_id=a27f36762eab46b68b16672f8a9aaa2c` and had a long history of `completion_guard_downgraded -> wait_requeued`.

## Why the first dedupe rollout was incomplete

The first rollout keyed duplicate reuse on the current hashed `request_fingerprint`.

That works for newly created advisor asks, but older rows in `jobs.client_json.request_fingerprint` were stored in the legacy readable format. When the same question was replayed later, the query looked for the hash and did not find the older row, so the controller ran again and created a new ChatGPT conversation.

## What changed in code

`_find_recent_advisor_ask_duplicate(...)` in `chatgptrest/api/routes_advisor_v3.py` now accepts both:

- `request_fingerprint`
- raw duplicate identity fields: `question`, `intent_hint`, `session_id`, `user_id`, `role_id`

The SQL now matches either:

1. exact hashed `request_fingerprint`, or
2. exact legacy-equivalent request identity:
   - same `input_json.question`
   - same `client_json.intent_hint`
   - same `session_id`
   - same `user_id`
   - same `role_id`

This keeps the newer hash-based dedupe path, while still protecting old rows from reopening fresh conversations.

## What changed in runtime proof

1. Worker/API were already reloaded to the newer binaries from the earlier fix.
2. The legacy trivial job `a27f36762eab46b68b16672f8a9aaa2c` was checked again and had finally terminated as `completed`.
3. A live replay of the same substantive `advisor_ask` request was run twice:
   - before fallback fix: created `2bb887ed37ac45e8bb42d3657c74a891`
   - after fallback fix + API reload: returned `duplicate_reused=true` and reused that same job with no new row created

## Why this matters

Without this fallback, users could still see what looks like “the system keeps asking the same thing again” whenever the original job was old enough to predate the new fingerprint format.

After this fix, the service fails closed in the desired direction:

- old trivial leftovers terminate
- old equivalent advisor asks reuse
- new duplicate advisor asks reuse

## Cleanup note

The smoke-created duplicate-validation job `2bb887ed37ac45e8bb42d3657c74a891` was canceled after proof collection so it would not continue running unnecessarily.
