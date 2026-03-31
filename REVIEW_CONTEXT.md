# Code Review Context
## Review Branch: `review-20260331-1318-harness`
Created: 2026-03-31T13:19:30.067556

## Source Commit

- mirrored from source commit `cb0d6d5bb9d862c3f56653ece1883eaa36964827`
- source repo: `https://github.com/haizhouyuan/ChatgptREST`

## Review Instructions

Dual external review for Agent Harness v4 and opencli/CLI-Anything integration v2. Review strict architecture, implementation sequencing, risk boundaries, and acceptance criteria.

## Project Overview

ChatgptREST is a REST API + worker system that automates interactions with ChatGPT, Gemini, and Qwen web UIs via browser automation (CDP). It includes:

- **MCP Server** — exposes all functionality as MCP tools
- **Advisor** — LangGraph-based intent→route→execute pipeline
- **Worker** — job execution with retry/cooldown/repair
- **EvoMap** — knowledge management with 43K atoms
- **Issue Ledger** — automated issue tracking and resolution

## Current External Review Packet

This review bundle also includes a focused packet under:

- `docs/reviews/agent_harness_20260331/`

Key files:

- `00_INDEX.md`
- `CODE_CONTEXT_MAP.md`
- `REVIEW_REQUEST_task_harness_v4.md`
- `REVIEW_REQUEST_opencli_cli_anything_v2.md`
- `2026-03-31_Agent_Harness工程调研_最终综合结论_v4.md`
- `2026-03-31_ChatgptREST_opencli_CLI-Anything_集成详细实施方案_v2.md`

The intent is to get two strict external reviews:

1. the `Task Harness / Agent Harness v4` architecture
2. the `opencli / CLI-Anything integration v2` implementation plan
