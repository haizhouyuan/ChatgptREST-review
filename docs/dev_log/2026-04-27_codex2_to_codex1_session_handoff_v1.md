# Codex2 to Codex1 Session Handoff v1

Date: 2026-04-27 12:49 CST

## Purpose

Hand off the active Codex2 session `019dc3f6-9059-7732-8efe-36a6d9123194` so Codex1 can resume from the same conversation history.

## Session Snapshot

- Source home: `/vol1/1000/home-yuanhaizhou/.codex2`
- Destination home: `/vol1/1000/home-yuanhaizhou/.codex1`
- Source session file:
  `/vol1/1000/home-yuanhaizhou/.codex2/sessions/2026/04/25/rollout-2026-04-25T17-26-49-019dc3f6-9059-7732-8efe-36a6d9123194.jsonl`
- Codex1 copied session file:
  `/vol1/1000/home-yuanhaizhou/.codex1/sessions/2026/04/25/rollout-2026-04-25T17-26-49-019dc3f6-9059-7732-8efe-36a6d9123194.jsonl`
- Copied snapshot SHA256:
  `2fb6492c21f5fe74c562fa1cabe2bd1d87479986b904cb557cd7fd3b19b12f74`
- Copied snapshot size: `21347322` bytes
- Copied snapshot lines: `8735`
- JSONL validation: passed
- Prefix validation: the Codex1 file matches the Codex2 source prefix at the copied snapshot size.

The Codex2 source session is still a live append file while this handoff is being written, so the full source file hash is expected to diverge after the snapshot. Treat the copied Codex1 file as the resume checkpoint, and this document as the handoff delta for actions performed after the copy.

## Resume Command

Use the Codex1 wrapper, which resolves to official Codex with `CODEX_HOME=/vol1/1000/home-yuanhaizhou/.codex1`.

```bash
cd /vol1/1000/projects/ChatgptREST
/vol1/1000/home-yuanhaizhou/_root_home/.local/bin/codex1 resume 019dc3f6-9059-7732-8efe-36a6d9123194
```

If launched through tmux, attach with:

```bash
tmux attach -t codex1-resume-019dc3f6
```

## Current Repository State

- Repository: `/vol1/1000/projects/ChatgptREST`
- Current HEAD before this handoff commit: `d22beab4`
- Recent relevant commits:
  - `d22beab4 Block public ingress by default`
  - `cd035c60 Harden admission observability and worker lock retry`
  - `cb676b9b Move ask fingerprinting outside DB lock`

Existing unrelated dirty worktree entries were present before this handoff and were not modified by this handoff:

- `.gitignore`
- `.omx/plans/2026-04-17_chatgptrest_execution-layer-governance_plan_v1.md`
- `ops/chrome_stop.sh`
- `ops/systemd/chatgptrest.env.example`
- `archives/`
- `ops/chrome_profile_state.py`
- `tmp/`

## Runtime Notes

- ChatgptREST API health: `http://127.0.0.1:18711/health` returned OK.
- Public MCP health: `http://127.0.0.1:18712/health` returned OK.
- User services were active at handoff time:
  - `chatgptrest-api.service`
  - `chatgptrest-mcp.service`
  - `chatgptrest-worker-send.service`
  - `chatgptrest-worker-wait.service`
  - `chatgptrest-driver.service`
- Tailscale address:
  - IPv4: `100.124.54.52`
  - IPv6: `fd7a:115c:a1e0::bb01:3634`
  - MagicDNS/funnel: `https://yogas2.tail594315.ts.net`

## Operational Context for Codex1

1. The most recent system-level ChatgptREST changes were about preventing client harm:
   - public ingress is blocked by default unless local or Tailscale-trusted;
   - missing attachments are rejected at job creation for high-risk jobs;
   - API job creation writes rejection audits;
   - worker claim retries tolerate transient SQLite lock contention.
2. Do not treat previous 429 handling as solved only by monitoring. The intended direction is systemic admission control, queue visibility, and user-safe failure semantics.
3. Avoid submitting new ChatGPT Pro / Deep Research work unless the user explicitly asks or the job is already justified. Preserve client usability first.
4. When changing ChatgptREST code, follow AGENTS.md:
   - run bootstrap first when starting cold;
   - use GitNexus impact before editing symbols;
   - run tests targeted to the changed surface;
   - run `scripts/check_doc_obligations.py --diff HEAD`;
   - commit meaningful changes;
   - run `python scripts/chatgptrest_closeout.py --agent codex --status completed --summary "..."`

## Handoff Status

- Codex2 session copied to Codex1 path: complete.
- Copied session snapshot validated: complete.
- This handoff document created for Codex1 resume context: complete.
