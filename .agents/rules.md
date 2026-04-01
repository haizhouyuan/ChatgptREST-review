# Antigravity Terminal Rules — Avoid Stuck Commands

## NEVER do
- **No long `sleep` in commands** — use `WaitMsBeforeAsync` or `command_status` polling instead
- **No multi-line `&&` chains** — split into separate `run_command` calls
- **No `for` loops with `git log` inside** — git may hold locks from CC activity, one stuck = all stuck
- **No `hcom` commands piped through `head/tail/grep`** — hcom may block waiting for TTY
- **No `export VAR=...` then use** — each `run_command` is a fresh shell; use `VAR=val cmd` inline
- **No `gh` / `git` large output piped** — `gh pr diff`, `git log`, `git diff` use a pager by default; piping to `head`/`tail` hangs indefinitely when the pager waits for interactive input

## DO
- **One simple command per `run_command`** — e.g. `git log feat/L-items --oneline -3`
- **Inline env vars** — `VAR=val cmd`
- **Short `WaitMsBeforeAsync`** — 3000ms for fast commands, background for slow ones
- **Check git lock first** — `test -f .git/index.lock && echo LOCKED || echo OK`
- **Redirect large `gh`/`git` output to file** — `gh pr diff 70 > /tmp/pr70.txt && wc -l /tmp/pr70.txt`, then `view_file` to read it; NEVER pipe `gh pr diff | tail`

## hcom correct usage
- **HCOM_DIR** must be `/home/yuanhaizhou/.hcom` (not default)
- **Send as external**: `HCOM_DIR=/home/yuanhaizhou/.hcom hcom send --from antigravity @target --intent request -- message`
- **Join as participant**: `hcom start --as antigravity` (not `--name`)
- **Inject keypress**: `HCOM_DIR=/home/yuanhaizhou/.hcom hcom term inject <name> --enter`
- **Never use** `tmux send-keys` for hcom-managed CC instances

## CDP Driver Observation
- **Port mapping**: `9222`=user browser, `9226`=ChatGPT driver, `9335`=Qwen driver — NEVER mix up
- **chrome-devtools MCP connects to 9222** — to observe driver browsers, use direct CDP via Python `websockets`
- **Screenshot method**: `curl http://127.0.0.1:9226/json/list` → find page id → connect `ws://127.0.0.1:9226/devtools/page/{id}` → `Page.captureScreenshot`
- **When to observe**: driver errors, new UI behavior, answer extraction issues — take timestamped screenshots to build evidence chain
- **Use `/observe-driver` workflow** for step-by-step instructions

## Deployment Safety
- **Always restart driver after code changes**: `systemctl --user restart chatgptrest-driver.service`
- **Deployment gap = silent errors**: code committed but old driver still running → `UnboundLocalError` / `NameError` on new symbols
- **Verify**: `systemctl --user show chatgptrest-driver.service --property=ExecMainStartTimestamp` — compare with last git commit time
- **Error timeline analysis**: get error job timestamps from API → compare with driver restart time → errors before restart = deployment gap, not code bug

## ChatGPT Pro Extended Behavior
- **Thinking UI**: for complex questions, Pro Extended outputs a "thinking plan" first, then a dynamic thinking status line, then the final answer
- **Stop button stays visible** during entire thinking phase — driver's `_wait_for_answer` correctly waits
- **`_wait_for_answer` three-tier protection**: (1) `stable_seconds >= 2.0`, (2) `not stop_visible`, (3) `len >= min_chars` — all must be true to exit
- **Monitor for UI changes**: if ChatGPT changes stop button behavior during thinking, add a thinking-indicator guard to `_wait_for_answer`

## Issue Ledger Usage
- **Before investigating errors**: `chatgptrest_issue_list(status="open")` — check if the problem already has an open issue
- **Get overview**: `chatgptrest_issue_digest()` — compact summary of open issues by severity/kind with top issues list
- **Report new issues**: `chatgptrest_issue_report(project="ChatgptREST", title="...", kind="...", raw_error="...", source="agent")` — creates or merges with existing
- **Close resolved issues**: `chatgptrest_issue_update_status(issue_id="...", status="closed", note="root cause + fix description")` — always include root cause; this auto-sinks to EvoMap
- **Link evidence**: `chatgptrest_issue_link_evidence(issue_id="...", job_id="...", note="...")` — connect investigation artifacts
- **Bridge repair.check**: `chatgptrest_issue_auto_link_repair(repair_job_id="...")` — auto-links repair.check results to matching open issues
- **Auto-reported issues**: Failed jobs automatically create/merge issues with `source=executor_auto` — these can be closed once investigated
- **Don't duplicate work**: if `chatgptrest_issue_list` shows an existing issue for the same error pattern, add evidence instead of creating a new one

## Code Review Upload
- **Gemini review** (10-file limit): `python ops/code_review_pack.py --mode gemini --output-dir /tmp/review_gemini` → upload 10 `.md` files
- **ChatGPT review** (zip): `python ops/code_review_pack.py --mode chatgpt --output-dir /tmp/review_chatgpt` → upload single zip
- **PR review** (changed files only): `python ops/code_review_pack.py --mode pr --base master --output-dir /tmp/review_pr`
- **Public repo sync**: `python ops/sync_review_repo.py --sync --push` → Gemini code import + ChatGPT Pro connector
- **ChatGPT Pro GitHub connector**: only reads **public** repos; use the public review mirror repo
- **Always verify uploads**: confirm all file chips appear in chat input before sending the question
