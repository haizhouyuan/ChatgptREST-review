# Code Review Context
## Review Branch: `review-20260324-131635`
Created: 2026-03-24T13:16:38.098955

## Source Commit

- mirrored from source commit `d84fe718e1478c59324e753a3637ed87b304d1fc`
- source repo: `https://github.com/haizhouyuan/ChatgptREST`

## Review Instructions

Review the current ChatgptREST branch with special focus on the newly added deliberation/maint unification blueprint, development plan, and whether the architecture cleanly unifies Public Agent, Maint Controller, maintagent, and guardian removal without creating duplicate controller surfaces.

## Project Overview

ChatgptREST is a REST API + worker system that automates interactions with ChatGPT, Gemini, and Qwen web UIs via browser automation (CDP). It includes:

- **MCP Server** — exposes all functionality as MCP tools
- **Advisor** — LangGraph-based intent→route→execute pipeline
- **Worker** — job execution with retry/cooldown/repair
- **EvoMap** — knowledge management with 43K atoms
- **Issue Ledger** — automated issue tracking and resolution
