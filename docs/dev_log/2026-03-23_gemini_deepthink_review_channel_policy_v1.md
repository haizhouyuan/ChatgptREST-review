# 2026-03-23 Gemini DeepThink Review Channel Policy v1

## Summary

This package closes a recurring execution-path mistake for coding agents:

- `Gemini DeepThink / GeminiDT / web-only Gemini review` must be treated as a web-automation capability
- it must not be silently reinterpreted as a Gemini CLI task
- OAuth/API key fixes are not the right remediation when the task was routed to the wrong channel

## Correct Channel Model

### Allowed

- `gemini_web.ask`
- a higher-level public advisor-agent surface that compiles to `gemini_web.ask`

### Not allowed as substitutes

- `gemini cli -p`
- generic MCP text-model calls
- API-key LLM calls

## Why

The DeepThink / GeminiDT behavior being discussed here is a consumer-web capability. Coding agents should not “repair” a wrong channel selection by falling back to CLI, because that changes the model surface and invalidates the review intent.

## Policy Changes

- [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md) now states that coding agents must keep GeminiDT on `gemini_web.ask` or a public northbound surface above it.
- [CLAUDE.md](/vol1/1000/projects/ChatgptREST/CLAUDE.md) documents the same rule for Claude Code usage.
- [GEMINI.md](/vol1/1000/projects/ChatgptREST/GEMINI.md) documents the same rule for Codex / Claude Code / Antigravity.
- [SKILL.md](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/SKILL.md) now has an explicit `Gemini DeepThink / GeminiDT rule` section.
- [.agents/workflows/code-review-upload.md](/vol1/1000/projects/ChatgptREST/.agents/workflows/code-review-upload.md) now separates:
  - Gemini consumer/web review
  - Gemini CLI
  - DeepThink review channel policy

## Operational Rule

If a coding agent requests:

- `GeminiDT`
- `Gemini DeepThink`
- `web-only Gemini review`

and the current executor is not `gemini_web.ask` (or a higher-level surface that resolves to it), the correct behavior is:

- fail fast
- report channel mismatch
- do not silently downgrade to Gemini CLI

## Scope Boundary

This package is a policy and workflow correction. It does not modify the low-level Gemini web executor itself.

