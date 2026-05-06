# Conversation Fetch Live Smoke v1

Date: 2026-05-01

## Scope

Validated the public MCP URL-to-conversation recovery path against a real multi-turn human-created conversation:

```text
https://chatgpt.com/c/69f31386-03e0-83e8-a93a-57846b97e760
```

## Result

The public MCP conversation tools are discoverable and operational after restarting `chatgptrest-mcp.service`.

`automation_conversation_find` returned no existing local jobs and correctly advised `automation_conversation_fetch`.

`automation_conversation_fetch` created a read-only `chatgpt_web.conversation_export` job without sending a prompt:

- job_id: `f4205290caeb437db1970e4e764a382d`
- status: `completed`
- authoritative answer path: `jobs/f4205290caeb437db1970e4e764a382d/answer.md`
- answer chars: `117298`
- conversation export path: `jobs/f4205290caeb437db1970e4e764a382d/conversation.json`
- conversation export chars: `1537079`
- conversation export sha256: `2e8e295989371f5f16bd63a5d9dc20552305089c6930375c1f1e459568e596d4`

`automation_conversation_get` successfully returned raw export chunks from the same job.

## Production Interpretation

Claude/Codex/other MCP clients can now use the dedicated public tools directly:

- discover: `automation_conversation_find`
- fetch missing conversation: `automation_conversation_fetch`
- read raw export chunks: `automation_conversation_get`
- read rendered markdown answer: `automation_result`

The fallback low-level `automation_job_create(kind="chatgpt_web.conversation_export")` path remains compatible, but agents should prefer the dedicated conversation tools.

