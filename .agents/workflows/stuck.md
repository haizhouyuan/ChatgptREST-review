---
description: Record a stuck/hanging command to global rules so it won't repeat
---

# /stuck — Record Stuck Command

When the user runs `/stuck`, do the following:

1. **Identify the stuck command** — check `Running terminal commands` in the user's metadata for any that have been running unusually long (>30s for simple commands, >2min for builds)

2. **Diagnose the root cause** — common patterns:
   - `&&` chains where one command blocks all subsequent ones
   - `sleep N` inside a command (use `WaitMsBeforeAsync` instead)
   - `for` loops with `git` operations (git lock contention from CC)
   - `hcom` commands that block on TTY (pipe through `head`/`tail`)
   - `export VAR=X` then using it (each `run_command` is a fresh shell)
   - `cd /path` inside command (use `Cwd` parameter instead)

3. **Append to rules** — add a new entry to `/vol1/1000/projects/ChatgptREST/.agents/rules.md` under the appropriate section:
   ```
   - **Don't**: `<the stuck command pattern>`
   - **Do instead**: `<the correct alternative>`
   - **Why**: `<root cause>`
   ```

4. **Kill the stuck command** if possible — use `send_command_input` with `Terminate: true`

5. **Also record as EvoMap capsule** if the pattern is novel — append to `docs/evomap_capsules/skill_terminal_antipatterns.json` (create if missing)

// turbo-all
