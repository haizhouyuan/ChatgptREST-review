# Handoff: Gemini Drive Attachments (ChatgptREST) — 2025-12-30

## Status update (2025-12-31)

P0 is now implemented (Drive URL attach is reliable end-to-end):

- Upload path: `rclone copyto <local> gdrive:chatgptrest_uploads/<jobid>_.._<name>` (no FUSE mount dependency).
- Resolve path: `rclone lsjson ...` to get `ID`, then attach via Drive URL `https://drive.google.com/open?id=<id>` (never rely on filename indexing by default).
- Fail-closed policy:
  - retryable errors (timeouts/transient API issues) -> `status=cooldown` (`DriveUploadNotReady`)
  - permanent errors (rclone misconfig/auth, file too large, missing local file at execution) -> `status=error` (`DriveUploadFailed`)
- Size precheck: `CHATGPTREST_GDRIVE_MAX_FILE_BYTES` (default `209715200` / 200MiB; set to `0` to disable).
- Optional cleanup (disabled by default): `CHATGPTREST_GDRIVE_CLEANUP_MODE` (`never` | `on_success` | `always`).

## Goal (hard requirement from U1)

Make `ChatgptREST` act as the **single server-side** integration point for Gemini Web with Drive-based attachments:

1) Client submits `kind=gemini_web.ask` with:
   - `input.question`
   - `input.file_paths` (server-local file paths)
2) Server uploads files into Google Drive (via `rclone copyto`), then attaches them in Gemini Web via:
   - `+` → `从云端硬盘添加` → Drive picker → `插入`
3) Server waits, saves the answer to artifacts, and serves it via `/answer` chunk API.

Client must not do UI automation; it only polls `/wait` and fetches `/answer`.

## Repo state (so the next maintainer doesn’t get surprised)

- Repo: `/vol1/1000/projects/ChatgptREST`
- Branch: `master` (HEAD currently at `c4837e2`)
- Working tree currently has local modifications (run `git status`).
  - Important: this handoff doc was originally written as an untracked file; commit/push it before starting a fresh worktree.

## Current status (what works vs what’s broken)

### Works (driver-level)

- Gemini Drive picker automation is implemented in the internal driver:
  - Visible picker iframe selection is robust against stale hidden iframes.
  - Attaching via **Drive URL** works reliably (`https://drive.google.com/open?id=<file_id>`).
- Driver direct smoke test succeeded:
  - Tool: `gemini_web_ask_pro`
  - `drive_files=["https://drive.google.com/open?id=<id>"]`
  - Answer retrieval succeeded (then `gemini_web_wait` can also retrieve the final text).

Key code:
- `chatgpt_web_mcp/server.py`:
  - `_gemini_get_visible_drive_picker_frame`
  - `_gemini_attach_drive_file`
  - `gemini_web_ask_*` tools accept `drive_files`

## What Gemini UI actually does (important behavioral notes)

- In Gemini web UI, the reliable attachment flow is:
  - Click `+` → `从云端硬盘添加` → Drive picker → select file → `插入`
- Typing literal text like `@Google 云端硬盘 xxx.md` in the prompt box does **not** reliably attach a file (it can behave like plain text).
- Drive picker “search by filename” is **not reliable** (indexing delays often show “没有匹配的结果” even when the file exists).
- But “paste a Drive URL” is reliably recognized by the picker search box:
  - `https://drive.google.com/open?id=<file_id>`

### Broken / unstable (historical; before the P0 fix)

The **server-side “file_paths → Drive ID/URL resolve” is not stable**.

Observed failure mode:
- The executor copies to `/vol1/1000/gdrive/chatgptrest_uploads/<jobid>_01_<name>`
- It then tries to resolve Drive `ID` via `rclone lsjson gdrive:chatgptrest_uploads/<dest>`
- In the send worker context, `rclone lsjson` sometimes **hangs / times out**, even though:
  - running the same `rclone lsjson ...` manually in a shell returns instantly.

Consequences:
- When we can’t get `drive_url`, Gemini picker name-search is unreliable (indexing delay → “没有匹配的结果”).
- To avoid “send a prompt with missing attachment”, the executor now returns a retryable status:
  - `status=cooldown`
  - `reason_type=DriveUploadNotReady`
  - `retry_after_seconds≈90`

Key evidence jobs / artifacts:
- `artifacts/jobs/9e02fac80b7f425180f551fda3f94cec/run_meta.json` (rclone timeout + picker search empty)
- `artifacts/jobs/31a1ffc018284732b752b158d8dbf53e/run_meta.json` (same)
- `artifacts/jobs/b81b9adbacc342b69adcfe17cce0258b/events.jsonl` (cooldown loop + repeated rclone timeout)
- Example Gemini picker “no matches” screenshot:
  - `artifacts/20251230_200907_gemini_web_ask_pro_error_5810.png`

## What changed recently (important code points)

### Driver (Gemini UI automation)

- File: `chatgpt_web_mcp/server.py`
  - Added `_gemini_get_visible_drive_picker_frame()` to avoid selecting hidden/stale picker iframes.
  - Added a small guard to avoid returning transient “分析/analysis” as a finished answer.
  - Attempted a fallback to open `chatgptrest_uploads/` folder in picker when filename search is not indexed.
    - Current behavior shows this fallback is not reliably reaching a selectable rows view.

### Executor (server-side upload/resolve)

- File: `chatgptrest/executors/gemini_web_mcp.py`
  - Uploads via `rclone copyto <local> gdrive:chatgptrest_uploads/<dest>` (no FUSE mount dependency).
  - Resolves Drive ID via `rclone lsjson --stat ...` and builds Drive URL `https://drive.google.com/open?id=<id>`.
  - Hardens rclone execution:
    - uses per-command subprocess timeouts (`CHATGPTREST_RCLONE_TIMEOUT_SECONDS` / `CHATGPTREST_RCLONE_COPYTO_TIMEOUT_SECONDS`)
    - sets rclone internal timeouts/retries (`CHATGPTREST_RCLONE_CONTIMEOUT_SECONDS`, `CHATGPTREST_RCLONE_IO_TIMEOUT_SECONDS`, `CHATGPTREST_RCLONE_RETRIES`, `CHATGPTREST_RCLONE_LOW_LEVEL_RETRIES`, `CHATGPTREST_RCLONE_RETRIES_SLEEP_SECONDS`)
    - kills the rclone process group on timeout to avoid wedging the worker with stray children
  - Fail-fast to protect the send worker: after the first upload failure, remaining files are marked as skipped (job stays fail-closed).
  - If any upload lacks a `drive_url`, executor returns `cooldown` (DriveUploadNotReady) to prevent “sending without attachment”.
  - Added `_gdrive_extract_existing_id()` to recover the Drive ID when the file already exists in Drive (previous runs).

Environment expectations:
- `rclone config file` is **not** the default path in this host. It is:
  - `/home/yuanhaizhou/.home-codex-official/.config/rclone/rclone.conf`
- The code tries to auto-detect it; can also force via:
  - `CHATGPTREST_RCLONE_CONFIG=/home/yuanhaizhou/.home-codex-official/.config/rclone/rclone.conf`

## Primary root cause hypothesis (to validate)

The current upload strategy (“copy into FUSE mount, then use rclone to query remote”) is fragile:

- The mount may be **eventually consistent** (writes appear locally, but remote metadata/ID may lag).
- `rclone lsjson` sometimes times out **only inside the send worker process**, suggesting:
  - intermittent Google API latency,
  - a token refresh / network stall,
  - or a worker environment mismatch (e.g. config path / HOME / sandbox env / proxy wrappers).

Manual `rclone lsjson` being fast while worker times out strongly suggests an **environment** or **concurrency** issue.
In particular, check **proxy env**: rclone (Go) usually honors `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` (and may ignore `ALL_PROXY`).
ChatgptREST bridges `ALL_PROXY` / `CHROME_PROXY_SERVER` into `HTTP(S)_PROXY` for rclone subprocesses, and also supports `CHATGPTREST_RCLONE_PROXY`
to set the proxy explicitly. The executor records `proxy_env` (booleans) into `run_meta.json` to make this diagnosable.

## To-do for the next Codex (recommended)

### P0: Make Drive ID/URL reliable (so we can attach by URL)

The fastest path to stability is: **always attach by Drive URL**, never rely on filename search.

Recommendations:

1) Stop using the FUSE mount for uploads.
   - Use `rclone copyto <local_file> gdrive:chatgptrest_uploads/<dest_name>` (direct API upload).
   - Then `rclone lsjson gdrive:chatgptrest_uploads/<dest_name>` to get the `ID`.
   - This should remove “mount sync” uncertainty and reduce “can’t find file” errors.

2) If keeping the mount:
   - Always force `RCLONE_CONFIG` to the known config path for subprocess calls.
   - Add logging for rclone timeout diagnostics:
     - include elapsed seconds, remote path, and captured stderr/stdout.
   - Consider increasing timeout (or retry) but keep a hard cap to avoid wedging the worker.

### P0: Fix tests impacted by new cooldown guard

- `tests/test_gemini_drive_attach_urls.py::test_gemini_drive_files_falls_back_to_name`
  currently expects “fallback to name” and `completed`.
- If we keep the guard (“missing drive_url → cooldown”), update the test accordingly.
- Alternatively, introduce an explicit param (e.g. `params.drive_name_fallback=true`) and keep the default conservative.

### P0: Don’t send prompts without attachments (fail-closed behavior)

- When `input.file_paths` is provided, the executor should:
  - either produce `drive_urls` for all files and attach by URL
  - or return `cooldown` / `needs_followup` without sending anything to Gemini (no “partial send”).
- Current implementation already returns `cooldown` when any `drive_url` is missing.
  - Keep that invariant; it’s important for correctness + wind-control.

### P1: Drive picker navigation fallback (optional)

If URL attach is not possible (no ID), improve picker navigation:

- Instead of searching by filename, navigate:
  - `我的云端硬盘` → open folder `chatgptrest_uploads` → select file by visible row → `插入`.
- Ensure the code can detect “we are inside a folder listing view” before waiting for rows.

### P1: Add “Gemini 导入代码” (repo review)

U1 wants Gemini to review code via Gemini UI “导入代码” by providing a repo URL.

Add an optional `input.github_repo` / `params.github_repo` for `gemini_web.ask`, and implement:
- open “导入代码” in Gemini UI
- paste repo URL
- confirm selection

Notes:
- This may require a one-time OAuth/authorization flow in Gemini UI (especially for private repos).
- Gate behind an explicit param (default off) for production safety.

## Safe repro commands (minimal prompts)

### Driver-level “known good” test (URL attach)

```bash
cd /vol1/1000/projects/ChatgptREST

# Resolve a Drive ID (example)
rclone lsjson gdrive:chatgptrest_drive_test.md | head

./.venv/bin/python - <<'PY'
import time
from chatgptrest.integrations.mcp_http_client import McpHttpClient

drive_url = "https://drive.google.com/open?id=<REPLACE_WITH_ID>"
client = McpHttpClient(url="http://127.0.0.1:18701/mcp", client_name="handoff", client_version="0")
key = f"handoff-drive-url-{int(time.time())}"
res = client.call_tool(
    tool_name="gemini_web_ask_pro",
    tool_args={
        "idempotency_key": key,
        "question": "请只回复附件文件的第一行（原文），不要补充任何其它内容。",
        "timeout_seconds": 150,
        "drive_files": [drive_url],
    },
    timeout_sec=200,
)
print(res.get("status"), res.get("ok"))
print(res.get("answer","")[:200])
print(res.get("conversation_url"))
PY
```

### End-to-end (ChatgptREST REST API)

```bash
python3 - <<'PY'
import json, time, urllib.request
idem = f"handoff-rest-{int(time.time())}"
body = {
  "kind": "gemini_web.ask",
  "input": {
    "question": "请只回复附件文件的第一行（原文），不要补充任何其它内容。",
    "file_paths": ["/vol1/1000/projects/ChatgptREST/state/tmp/gemini_drive_attach_smoke.md"],
  },
  "params": {"preset":"pro","timeout_seconds":240,"min_chars":10,"answer_format":"text"},
}
req = urllib.request.Request(
  "http://127.0.0.1:18711/v1/jobs",
  data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
  headers={"Content-Type":"application/json","Idempotency-Key": idem},
  method="POST",
)
with urllib.request.urlopen(req, timeout=30) as resp:
  print(resp.read().decode("utf-8","replace"))
PY
```

Then poll:
- `GET /v1/jobs/<job_id>/wait?timeout_seconds=...&poll_seconds=...`
- if `cooldown`, wait until `not_before`, then poll again.

## Operational notes (tmux)

- Services run under tmux session `chatgptrest`:
  - `driver` pane: internal MCP driver on `127.0.0.1:18701`
  - `api` pane: REST on `127.0.0.1:18711`
  - `send` / `wait` workers
- Restart driver quickly:
  - `tmux respawn-pane -t chatgptrest:6 -k "cd ... && CHATGPT_CDP_URL=http://127.0.0.1:9222 ./ops/start_driver.sh"`

## “Paste prompt” for the next Codex (copy/paste)

You are taking over the Gemini Drive attachment feature in `ChatgptREST`.

1) Read:
   - `/vol1/1000/projects/ChatgptREST/docs/handoff_chatgptrest_history.md`
   - `/vol1/1000/projects/ChatgptREST/docs/handoff_gemini_drive_attachments_20251230.md`
2) Goal: `POST /v1/jobs kind=gemini_web.ask` with `input.file_paths` must result in a Gemini prompt sent with Drive attachments, and `/answer` must return the model answer. Clients should never do UI automation.
3) Current state: attaching by Drive URL works in the driver, but server-side “local file → Drive ID/URL” is unreliable because we copy into `/vol1/1000/gdrive` (FUSE) then run `rclone lsjson`, which sometimes hangs/timeouts in the send-worker context. Executor fails closed as `cooldown` (DriveUploadNotReady) to avoid sending without attachments.
4) Implement P0 fix: upload via `rclone copyto` directly to `gdrive:chatgptrest_uploads/<dest>` then `rclone lsjson` to get the Drive ID, so we can always attach by URL (never depend on filename search). Keep hard timeouts so workers don’t wedge.
5) Update tests accordingly (the “fallback to name” test should likely expect cooldown unless explicitly enabled).
6) Optional P1: implement “导入代码 (Import code)” flow for repo URL review behind an explicit param.
