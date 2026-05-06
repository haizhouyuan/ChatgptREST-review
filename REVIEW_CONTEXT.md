# Code Review Context
## Review Branch: `review-20260506-080806`
Created: 2026-05-06T08:08:09.320917

## Source Commit

- mirrored from source commit `57259f6b075882ae202e375d40a0213ced2c758b`
- source repo: `https://github.com/haizhouyuan/ChatgptREST`

## Project Overview

ChatgptREST is a REST API + worker system that automates interactions with ChatGPT, Gemini, and Qwen web UIs via browser automation (CDP). It includes:

- **MCP Server** — exposes all functionality as MCP tools
- **Advisor** — LangGraph-based intent→route→execute pipeline
- **Worker** — job execution with retry/cooldown/repair
- **EvoMap** — knowledge management with 43K atoms
- **Issue Ledger** — automated issue tracking and resolution
