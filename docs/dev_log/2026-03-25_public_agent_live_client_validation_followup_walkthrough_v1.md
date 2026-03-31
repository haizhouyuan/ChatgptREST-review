# 2026-03-25 Public Agent Live Client Validation Follow-up Walkthrough v1

## What I did

I validated the post-`a0ca045` client experience from the real coding-agent side, not just by reading the diff.

The concrete client was:

- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`

The target surface was:

- `http://127.0.0.1:18712/mcp`

## Validation steps

1. Re-ran the same class of public-repo tasks that originally motivated the boundary fix:
   - ChatGPT public-repo review
   - Gemini public-repo review/imported-code intent
2. Ran one intentionally invalid timeout override case to check local/client-side recovery semantics.
3. Ran valid requests with explicit `session_id` values so I could look for durable server-side breadcrumbs.
4. Checked:
   - client stdout/stderr behavior
   - summary file creation
   - `controller_runs` / `advisor_runs` visibility
   - `chatgptrest-mcp.service` journal activity
5. Compared the wrapper transport path with the repo's own live validation path.

## Why two issues were opened

## ISSUE-0020

This one is a direct, concrete client bug:

1. the wrapper rejects invalid timeout combinations locally
2. but still labels the failure as `still_running_possible=true`
3. and tells the caller to recover through `advisor_agent_status`

That guidance is wrong when no remote submission happened.

## ISSUE-0021

This one is a live-client operational issue:

1. valid wrapper calls entered the MCP service
2. but the client had no crisp accepted-state confirmation
3. and I could not observe early durable run visibility during the initial validation window

I did not overclaim the exact root cause, but the wrapper/validation-path mismatch around MCP initialization is strong enough to warrant a tracked issue.

## What this does not mean

This follow-up does **not** invalidate the service-side boundary fix in `a0ca045`.

That commit still appears correct on the route semantics it set out to fix.

The new issues are follow-on client-surface problems discovered only after rerunning the task as a real client.
