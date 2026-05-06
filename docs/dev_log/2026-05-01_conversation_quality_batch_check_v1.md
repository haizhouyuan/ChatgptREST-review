# Conversation Quality Batch Check v1

Date: 2026-05-01

## Scope

Fetched and quality-checked the ChatGPT conversation URL batch requested by the user.

- input URLs: 11
- unique conversations: 10
- duplicate input collapsed: `https://chatgpt.com/c/69f2dd9e-bfec-83e8-acab-77a18360a739`
- lane: public MCP conversation recovery tools
- fetch mode: read-only `chatgpt_web.conversation_export`
- backend mode: `dom_only`

## Artifacts

- v1 report: `artifacts/conversation_quality_checks/20260501_104509_batch/report.md`
- v1 manifest: `artifacts/conversation_quality_checks/20260501_104509_batch/manifest.json`
- v2 report: `artifacts/conversation_quality_checks/20260501_105050_batch_v2/report.md`
- v2 manifest: `artifacts/conversation_quality_checks/20260501_105050_batch_v2/manifest.json`

The v1 pass initially reused some completed `chatgpt_web.ask` jobs found by conversation URL. Those jobs had valid raw `conversation.json` exports, but their `answer.md` files represented the ask answer rather than a full rendered conversation. The v2 pass corrected this by forcing dedicated `chatgpt_web.conversation_export` jobs for those conversations.

## Final Result

The final v2 quality result is:

```json
{"PASS": 10}
```

All 10 unique conversations have:

- completed export job
- canonical answer ready
- readable full-conversation Markdown
- readable raw `conversation.json`
- conversation id matching the supplied URL
- at least one user turn and one assistant turn
- substantive last assistant answer
- no detected progress stub
- working `automation_conversation_get` raw chunk endpoint

## Final Export Jobs

| Conversation | Export job | Answer chars | Export chars |
|---|---|---:|---:|
| `69f31386-03e0-83e8-a93a-57846b97e760` | `3072fe32114b454589af38afbe82a1bc` | 117298 | 1537079 |
| `69f30acc-c994-83e8-9763-4b19610fac55` | `451201cd2c1641199b60ad1555f372bc` | 46333 | 1371453 |
| `69f2dd9e-bfec-83e8-acab-77a18360a739` | `5f5092314d3143c58c11a24ea53c3ab3` | 38820 | 605889 |
| `69f2dd9e-dc84-83e8-aef2-e621bb4642ec` | `41132052888444299d5382fd8773c985` | 28055 | 145285 |
| `69f2da65-f6c8-83e8-bd91-6c70e924ec91` | `24fe4a3e02044d77b4eb152b3c42c3f9` | 26558 | 400898 |
| `69f2d992-22f0-83e8-930d-a0150e32cc6d` | `f3de1776a4f5488f845c68d493dcbc9d` | 27016 | 59623 |
| `69f1e423-f958-83e8-88f3-e0d487e3cc7f` | `39615b0ce2ea4713906f511133853937` | 102246 | 1539886 |
| `69f20cd0-9ab4-83e8-9827-ac9c94728bfe` | `626d13ef5bc047b1ae7911c471c3398b` | 38038 | 323233 |
| `69f17ad5-f254-83e8-a63b-4a43c6a064d7` | `60f270fdb5174079812f9d70b1f79337` | 117352 | 1280721 |
| `69f05784-b010-83e8-92ca-bc4e45a20666` | `1c4c5199167a442e9805853233053f2d` | 108997 | 322329 |

## Operational Note

This batch exposed a useful production rule for future URL recovery: when the user asks for a full conversation, `automation_conversation_find` may find historical ask jobs associated with the URL, but the agent should prefer a dedicated `chatgpt_web.conversation_export` job unless the found job is already a conversation-export job with full rendered turn markers.

