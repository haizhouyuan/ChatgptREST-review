# Manual ChatGPT Conversation Harvest v1

## Problem

Human-created ChatGPT Web conversations were outside the ChatgptREST evidence
chain. If a user manually asked Pro in the shared browser, agents could only
reason from screenshots, pasted URLs, or partial Obsidian clips. That failed in
multi-turn cases and after Web Clipper stopped capturing answer DOM reliably.

The missing product capability was not another Pro retry loop. It was a
read-only URL-to-conversation-export surface plus a conservative scanner that
can notice open `chatgpt.com/c/<id>` tabs and enqueue exports without sending
prompts.

## Root Cause

- Public MCP had `automation_result(job_id)` and low-level raw job creation, but
  no canonical `automation_*` tool that accepts a ChatGPT conversation URL and
  returns a complete exported conversation.
- Existing `chatgpt_web.conversation_export` could reuse a matching CDP page,
  but its cleanup path closed the page unconditionally. That is unsafe for
  human-owned browser tabs.
- CDP open logic brought reused pages to the foreground. For a background
  harvester this is user-visible interference.
- There was no lightweight scanner for human-created conversation tabs. Existing
  monitors focused on worker/API health or Pro lane protection, not harvesting
  manual answers.

## Changes

- Added public MCP tools:
  - `automation_conversation_fetch(conversation_url=...)`
  - `automation_conversation_get(job_id=...)`
  - `automation_conversation_find(conversation_url=... | conversation_id=...)`
- `automation_conversation_fetch` creates a read-only
  `chatgpt_web.conversation_export` job and starts background waiting. It
  defaults to `backend_mode=dom_only` to avoid probing the ChatGPT conversation
  backend during periods that already showed 429 sensitivity.
- The ChatGPT driver now marks whether a CDP page was reused. Conversation
  export preserves reused conversation tabs instead of closing them.
- Reused CDP tabs are no longer brought to the foreground by default. Set
  `CHATGPTREST_CDP_BRING_EXISTING_PAGE_TO_FRONT=1` only when debugging.
- Added `ops/manual_chatgpt_conversation_harvest.py`:
  - discovers open ChatGPT conversation tabs through Chrome CDP `/json/list`;
  - optionally submits read-only export jobs;
  - records state under `artifacts/monitor/manual_chatgpt_conversation_harvest/`;
  - never sends prompts.
- Added opt-in user systemd units:
  - `ops/systemd/chatgptrest-manual-conversation-harvest.service`
  - `ops/systemd/chatgptrest-manual-conversation-harvest.timer`

## Operating Contract

For an explicit URL:

```bash
# Agent-facing MCP:
automation_conversation_fetch(conversation_url="https://chatgpt.com/c/<id>")
automation_result(job_id="<returned job_id>")
automation_conversation_get(job_id="<returned job_id>")
```

For local discovery:

```bash
PYTHONPATH=. ./.venv/bin/python ops/manual_chatgpt_conversation_harvest.py --once
PYTHONPATH=. ./.venv/bin/python ops/manual_chatgpt_conversation_harvest.py --once --submit
```

To enable the conservative 5-minute scanner:

```bash
ln -sf /vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-manual-conversation-harvest.service ~/.config/systemd/user/chatgptrest-manual-conversation-harvest.service
ln -sf /vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-manual-conversation-harvest.timer ~/.config/systemd/user/chatgptrest-manual-conversation-harvest.timer
systemctl --user daemon-reload
systemctl --user enable --now chatgptrest-manual-conversation-harvest.timer
```

## Safety Boundaries

- The scanner only discovers tabs and creates export jobs; it never submits a
  user prompt.
- Manual Pro holds and frontend 429 holds still block `chatgpt_web.*` job
  creation. The scanner records the failure instead of clearing holds.
- DOM-only export is the default because backend conversation API access has
  previously amplified 429 incidents.
- Reused human tabs are not closed after export and are not brought to the
  foreground by default.

## Verification

Targeted tests cover:

- URL normalization and MCP job creation for `automation_conversation_fetch`.
- Conversation export chunk delegation through `automation_conversation_get`.
- Driver cleanup preserving reused ChatGPT conversation tabs.
