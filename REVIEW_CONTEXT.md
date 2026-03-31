# Code Review Context
## Review Branch: `review-20260331-harness-round2`
Created: 2026-03-31T22:14:07.215053

## Source Commit

- mirrored from source commit `dfb8877c9651b61eab3e76ec4b02eb83f0d7dc73`
- source repo: `https://github.com/haizhouyuan/ChatgptREST`

## Review Instructions

High-standard re-review of current Task Harness implementation and opencli integration. Read docs/reviews/agent_harness_round2_20260331/ first.

## Project Overview

ChatgptREST is a REST API + worker system that automates interactions with ChatGPT, Gemini, and Qwen web UIs via browser automation (CDP). It includes:

- **MCP Server** — exposes all functionality as MCP tools
- **Advisor** — LangGraph-based intent→route→execute pipeline
- **Worker** — job execution with retry/cooldown/repair
- **EvoMap** — knowledge management with 43K atoms
- **Issue Ledger** — automated issue tracking and resolution
