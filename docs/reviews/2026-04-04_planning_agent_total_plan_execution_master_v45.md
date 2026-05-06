# 2026-04-04 Planning agent total plan execution master v45

## Delta from v44

This version freezes one more `W1` batch:

1. fixed retryable send extension counting so the cap now applies per job, not per error label
2. added a regression proving `ToolCallError -> InfraError` can no longer earn two separate send extensions on the same job
3. kept the plan focused on live proof, not on paper-only optimism

## Current W1 status

`W1` remains `in_progress`.

### Closed in this batch

1. A real send-side semantics bug was fixed in `job_store`: retryable send extension count no longer resets when the error label changes.
2. The lease layer now has regression proof for that cross-error-type case.

### Still open after this batch

1. Real OpenClawBot live completion is still not yet re-proven green on this new code.
2. We still need fresh live evidence showing whether the chain now terminalizes faster.
3. If it still stalls, the next remaining focus is session terminal projection and/or remaining provider-side churn.

## Updated judgment

The current `W1` path is now cleaner in two ways:

1. the executor side is less wasteful on deadline-exceeded exceptions
2. the job-store side no longer lets the same send chain keep extending because the error label drifted

That means the next live rerun should be more trustworthy.

## Next step

Immediately re-run the real OpenClawBot live completion gate on the new code and freeze the result as the next evidence boundary.
