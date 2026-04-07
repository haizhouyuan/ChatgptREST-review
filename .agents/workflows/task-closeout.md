---
description: ChatgptREST-specific closeout workflow. Use together with gitnexus-review.md when a task ends.
---

# ChatgptREST Task Closeout Workflow

This repo has heavy multi-agent parallel work. Silent dirty state is treated as a defect.

## Before you stop

1. Run:

```bash
git status --short --branch
```

2. If the current change is a meaningful isolated unit, commit it now.
3. Run the repo wrapper first so doc obligations are checked against the task scope.
4. The wrapper then emits the shared closeout event.

## Completed task

```bash
python scripts/chatgptrest_closeout.py \
  --repo /vol1/1000/projects/ChatgptREST \
  --agent <antigravity|codex|codex2|claude-code|gemini-cli> \
  --status completed \
  --summary "one-line delivery summary"
```

Notes:
- By default, a clean completed task checks `HEAD~1..HEAD`.
- If the task spans multiple commits, pass `--diff <range>` explicitly.
- The wrapper blocks closeout when required doc updates are missing.

## Dirty worktree you are intentionally leaving

```bash
python scripts/chatgptrest_closeout.py \
  --repo /vol1/1000/projects/ChatgptREST \
  --agent <antigravity|codex|codex2|claude-code|gemini-cli> \
  --status partial \
  --summary "paused with pending edits" \
  --pending-reason "mixed worktree / waiting for review / generated artifact / blocked" \
  --pending-scope "file1 file2 ..."
```

## What happens automatically

On this repo, once hooks are installed:
- commits auto-enqueue HomePC GitNexus analyze
- commit/head changes are written to OpenMind export JSONL
- stale timer later re-enqueues analyze if HEAD changed without a direct post-commit trigger

## Use with GitNexus review

If the task changed shared code or refactor objects, read first:
- `/vol1/1000/projects/ChatgptREST/.agents/workflows/gitnexus-review.md`
