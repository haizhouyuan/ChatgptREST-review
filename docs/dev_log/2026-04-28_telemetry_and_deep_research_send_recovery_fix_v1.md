# 2026-04-28 Telemetry and Deep Research Send Recovery Fix v1

## Context

Two operational gaps surfaced together:

- Repo closeout wrote local activity events, but the telemetry mirror to `/v2/telemetry/ingest` returned HTTP 401 in Codex sessions whose `HOME` does not resolve to the normal user config directory.
- A ChatGPT Deep Research job with staged attachments reached `MaxAttemptsExceeded` before `prompt_sent_at`. The job repeatedly failed in `send` with `SSE stream timeout (deadline exceeded)`, `Target crashed`, and `Page.goto: Page crashed`.

## Root Cause

The closeout mirror script can authenticate with `X-Api-Key`, but the shared script expands `~/.config/chatgptrest/chatgptrest.env` under the current agent HOME. In Codex sessions this can differ from `/home/yuanhaizhou`, so no `OPENMIND_API_KEY` is found and the mirror receives 401.

The Deep Research failure was not a 429 and not an attachment-root 403. MCP attachment auto-staging worked and emitted `mcp_attachment_staged`. The first failure mode was that live config has `CHATGPTREST_DEFAULT_SEND_TIMEOUT_SECONDS=60`, while ChatGPT Deep Research send can need longer to upload attachments and activate the Deep Research tool before returning a prompt-sent receipt.

A second related failure mode appeared after retrying with fewer attachments: ChatGPT Web could crash the page while the send worker was still before `prompt_sent_at`. `TargetClosedError` was already classified as recoverable, but the plain Playwright `Page.goto: Page crashed` form was not, so it terminalized as a generic error and did not emit the send-exhaustion telemetry the operator needs.

## Fix

- `scripts/chatgptrest_closeout.py` now builds an explicit closeout environment and loads the telemetry mirror key from known ChatgptREST config files when the current process env does not contain it.
- ChatGPT Deep Research now has a dedicated send timeout floor via `CHATGPTREST_CHATGPT_DEEP_RESEARCH_SEND_TIMEOUT_SECONDS` with default 240 seconds. This floor only applies to `deep_research=true` and only when callers did not explicitly set `send_timeout_seconds`.
- `store_retryable_result` now emits `web_send_retry_exhausted` before terminalizing an unsent web send transport failure. The event gives a safe next action, recommended retry params, and attachment counts/bytes.
- Send-stage `Page crashed` errors are now classified as recoverable browser infra failures, and `web_send_retry_exhausted` recognizes the same text if the job exhausts attempts before any thread URL exists.

## Validation

Targeted tests cover:

- closeout mirror env injection from process env and config files;
- ChatGPT Deep Research send timeout floor under a 60 second global send cap;
- retry-exhausted web send telemetry;
- send-stage `Page.goto: Page crashed` classification and terminal telemetry.

## Operational Note

For an already-terminal job such as `98ee93d068764b8eb0af74255d81bdfc`, this code does not retroactively submit a duplicate Pro/Deep Research request. The safe recovery is to retry the same task once with either `send_timeout_seconds >= 240` or a slimmer attachment set, preferably when no other ChatGPT Web jobs are active.
