# Code Review Context
## Review Branch: `review-20260407-next-stage-dual-model`
Created: 2026-04-07T22:20:12.929037

## Source Commit

- mirrored from source commit `41869dc9ac077d77b650e37ebbf847fda992fd5b`
- source repo: `https://github.com/haizhouyuan/ChatgptREST`

## Review Instructions

Review the next-stage full platform realignment after A-F. Use attached review packets for architecture intent, authority/priority rules, and cross-system context.

## Project Overview

ChatgptREST is a REST API + worker system that automates interactions with ChatGPT, Gemini, and Qwen web UIs via browser automation (CDP). It includes:

- **MCP Server** — exposes all functionality as MCP tools
- **Advisor** — LangGraph-based intent→route→execute pipeline
- **Worker** — job execution with retry/cooldown/repair
- **EvoMap** — knowledge management with 43K atoms
- **Issue Ledger** — automated issue tracking and resolution
