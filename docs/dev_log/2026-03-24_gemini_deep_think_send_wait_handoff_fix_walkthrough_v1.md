# 2026-03-24 Gemini Deep Think Send/Wait Handoff Fix Walkthrough v1

## What changed

I fixed the Deep Think failure mode where a long-running Gemini generation was treated as a send failure instead of an in-flight run.

The practical effect is:

- Deep Think jobs that already started generating no longer burn resend attempts on the send worker
- they move into `wait`
- quota-limited runs cool down until the advertised reset time instead of looping
- no-response send failures still stay on `send`

## Why this is the right fix

The old system made a bad assumption: send should either finish with a stable answer or fail.

That assumption is acceptable for short asks. It is wrong for Deep Think.

Deep Think is a long task. The correct state machine is:

1. confirm the run was actually started
2. hand the run to `wait`
3. only resend when the send itself is unconfirmed

So the real repair was not “retry harder”. It was “stop classifying a pending run as a failed send.”

## Why autofix was not expanded

This was important because the user explicitly called out `autofix` quality.

If `autofix` starts reacting to pending Deep Think states, it becomes part of the problem:

- it adds repair noise
- it consumes maintenance budget
- it hides a broken execution model behind side effects

So the fix keeps `autofix` out of this family by making the state machine classify the run correctly earlier.

## Key regression coverage

- Deep Think pending with only base `/app` URL now enters `wait`
- Gemini jobs without any response-start evidence still remain on `send`
- existing follow-up guard behavior stays intact
- existing wait transient handling stays intact
- existing overloaded fallback coverage stays intact
- existing quota parser coverage stays intact

## Net effect

The system now distinguishes three Deep Think outcomes cleanly:

- `GeminiDeepThinkResponsePending` / `GeminiDeepThinkThreadPending`
- `GeminiDeepThinkSendUnconfirmed`
- `GeminiModeQuotaExceeded`

That is the minimum taxonomy needed to stop the resend/cooldown/autofix confusion that previously ended in `MaxAttemptsExceeded`.
