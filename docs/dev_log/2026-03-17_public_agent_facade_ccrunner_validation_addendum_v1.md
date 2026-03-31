# Public Agent Facade CCrunner Validation Addendum v1

Date: 2026-03-17

## Purpose

Record the post-fix Claude Code runner validation attempts for the public agent facade takeover.

## Runner Status

The detached runner transport issue was fixed earlier in the shared skill launcher by:

- preferring `setsid`
- redirecting stdin from `/dev/null`

That fix remains valid. Runner start, handshake, PID tracking, status updates, and cancellation all behaved correctly during this addendum.

## Validation Attempts

### Attempt 1

- run id: `ccjob_20260317T060503Z_d7ff7268`
- prompt scope: broad regression + focused code review

Observed:

- worker started successfully
- Claude command PID was registered
- status heartbeat advanced normally
- no result artifact was produced
- no worktree mutations were made
- task remained in `running` until manually cancelled

### Attempt 2

- run id: `ccjob_20260317T061021Z_414d7dc2`
- prompt scope: narrower regression-only plus minimal focused review

Observed:

- same behavior as attempt 1
- healthy runner state, but no terminal output and no file changes
- manually cancelled

### Attempt 3

- run id: `ccjob_20260317T061233Z_cdf92984`
- prompt scope: one targeted pytest command only

Observed:

- same behavior again
- runner transport remained healthy
- Claude process stayed alive but produced no terminal JSON and no worktree changes
- manually cancelled

## Conclusion

For this task, the remaining instability was not the CCrunner transport layer. The runner launched reliably, kept heartbeats, and accepted cancellation. The blocker was Claude Code itself hanging during model execution for these prompts.

Acceptance for this batch therefore remained based on:

- local pytest validation
- direct code review
- direct Git/worktree inspection

## Recommended Follow-up

- try a different Claude runner preset or provider relay for the next independent validation pass
- keep the current CCrunner launcher fix; do not revert it
- if future Claude Code runs continue to hang without output, treat that as a separate model/runtime issue rather than a runner orchestration issue
