# 2026-04-28 MCP Attachment Auto-Staging Root Cause Fix v1

## Investigation

Recent runtime checks showed no new ChatGPT backend `429`, Cloudflare cooldown, or active shared cooldown. The recent client-visible failures were different classes:

- Public internet probes were rejected by `PublicIngressBlocked`; this is expected tunnel-first behavior.
- Pro answers that lacked the required finality / thinking trace were degraded to `needs_followup`; this is expected fail-closed behavior for external-review evidence.
- Several client submissions failed before job creation with `FilePathOutsideAllowedDirectory`, especially from project-local review packets under `/vol1/1000/projects/toyresearch/...`.

## Root Cause

The low-level `/v1/jobs` attachment contract was intentionally strict: local attachments must be under the ChatgptREST repo, `ChatgptREST/tmp/`, `/tmp/chatgptrest_uploads/`, or an explicit `CHATGPTREST_EXTRA_ALLOWED_FILE_ROOTS` entry.

That API rule is correct, but the public MCP automation layer exposed the same raw `file_paths` field without a matching staging step. Client agents therefore had to discover the policy by receiving a 403, manually copy files into `/tmp/chatgptrest_uploads`, then resubmit. This kept the provider safe, but made the northbound automation contract incomplete and caused repeated avoidable client friction.

## Fix

`chatgptrest/mcp/server.py` now stages explicit MCP job attachments before signing and submitting the `/v1/jobs` request:

- If `input.file_paths[]` points to an existing local file outside API-accepted roots, MCP copies it to `/tmp/chatgptrest_uploads/mcp_staged/<date>/<idempotency-key>/`.
- Already accepted paths are preserved.
- Missing paths and non-files are left for the API to reject with its existing precise errors.
- The staged job client metadata records `mcp_attachment_staging.files[]` with original path, staged path, SHA-256, and byte count.
- Staged jobs emit a `mcp_attachment_staged` event after job creation, so `automation_job_events` and artifacts expose that MCP converted a would-be outside-root rejection into a sanctioned upload-root submission.
- Direct REST `/v1/jobs` remains strict and still rejects outside roots.

This is enabled by default with `CHATGPTREST_MCP_STAGE_OUTSIDE_ALLOWED_FILE_PATHS=1`. If `CHATGPTREST_MCP_ATTACHMENT_STAGING_ROOT` is set outside an API-accepted root, MCP falls back to `/tmp/chatgptrest_uploads/mcp_staged`.

## Why This Is Systemic

The fix sits in `chatgptrest_job_create`, the shared MCP create path. It covers `automation_ask`, legacy MCP submit helpers, consult submissions, repair jobs, and image submissions without weakening the API allowlist.

The security model remains fail-closed at the REST boundary; only the trusted local MCP process performs a deliberate, auditable staging copy for files the caller explicitly referenced.

## Validation

Added regression coverage in `tests/test_mcp_trace_headers.py`:

- outside local file paths are staged before submit;
- staged submissions emit `mcp_attachment_staged`;
- already accepted `/tmp/chatgptrest_uploads` paths are preserved.
