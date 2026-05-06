# ChatgptREST Call Skill Decision Map v1

Date: 2026-04-30

## Problem

The `chatgptrest-call` skill had accumulated many correct but flat "hard rules." Agents had to read a long list and infer the correct path for each task. This made several historical mistakes more likely:

- treating URL conversation retrieval as a new model ask;
- over-constraining tool-selection/research tasks with attachment-only phrasing;
- using foreground waits for long Pro tasks;
- retrying with new idempotency keys during 429/concurrency/cooldown;
- failing to report finality fields and artifact paths clearly.

## Change

Added a `First classify the request` section near the top of the skill. It maps common user intents to the correct surface and explicitly lists what not to do.

Added an `Evidence boundary policy` section with three modes:

- `attachment_first`
- `current_research_allowed`
- `deep_research_requested`

Added `Conversation URL recovery` guidance so agents know that a user-provided ChatGPT conversation URL should use the read-only conversation export lane, not a prompt send.

Added a response contract for agent handoffs:

- job id;
- conversation URL;
- phase/status;
- canonical answer readiness;
- authoritative answer path;
- finality state;
- output artifact paths.

## Intended Behavior

The skill should now act more like a routing guide:

1. classify the task;
2. choose the evidence boundary;
3. choose the public MCP/tool surface;
4. submit or retrieve without creating duplicate jobs;
5. report finality and artifacts precisely.

This is a documentation-level optimization only. It does not change runtime code.
