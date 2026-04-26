# Runtime Duel MCP / Policy / Secret Ledger

## MCP Policy

This demo does not grant model lanes arbitrary MCP access.

Allowed:

- Paperclip local API for assigned issue context and closeout.
- Local filesystem reads for the mandatory evidence files in `shared_target_brief.md`.
- Local filesystem writes only under `/vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs`.

Denied:

- External account mutation.
- Real customer data access.
- Secret export or token printing.
- Production publishing, paid ads, real store changes, or real CAD/manufacturing claims.
- Unbounded web browsing. The comparison is local-context only.

## Runtime Ledger

| Lane | Paperclip adapter | Local runtime | Purpose |
| --- | --- | --- | --- |
| Claude Code | `claude_local` | `/home/yuanhaizhou/local/node/bin/claude` with `HOME=/home/yuanhaizhou` | Official Claude Code comparison lane |
| Kimi | `kimi_cli` external local adapter | `/home/yuanhaizhou/.local/bin/kimi-direct` with model `kimi-for-coding` | Native Kimi Code CLI comparison lane |

## Secret Policy

- No secrets are copied into this package.
- Kimi uses the existing local Kimi config path; the package only records the config file path, not its contents.
- Claude uses existing local Claude auth state through `HOME=/home/yuanhaizhou`.
- Paperclip run JWT is short-lived and injected by Paperclip at runtime; it is not written to disk.

## Evidence Requirements

Each lane must produce:

- A Paperclip heartbeat run record.
- A terminal run status.
- A non-empty artifact file.
- A Paperclip issue status of `done`.
- A local evidence JSON file under `outputs/evidence`.
