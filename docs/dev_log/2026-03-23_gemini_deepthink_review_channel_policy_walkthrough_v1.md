# 2026-03-23 Gemini DeepThink Review Channel Policy Walkthrough v1

## Problem statement

A recurring failure pattern appeared in review work:

- a user wanted `GeminiDT / DeepThink`
- the execution path drifted into Gemini CLI or another non-web channel
- the failure was then misdiagnosed as OAuth / CLI availability / API-key setup

That diagnosis is wrong for this class of task.

## Correct diagnosis

For these tasks, the real issue is not “Gemini cannot be used”.

The real issue is:

- the task requested a web-only Gemini capability
- but the coding agent routed it to a non-web channel

## What changed

The repo guidance now states the policy explicitly in all of the places that can steer a coding agent:

1. project-level instructions
2. Claude Code instructions
3. Gemini/Codex instructions
4. ChatgptREST wrapper skill
5. code-review upload workflow

This is intentionally repetitive. The mistake came from channel drift at the instruction/workflow layer, so the correction also needs to live there.

## Intended future behavior

When a coding agent sees a DeepThink review request, it should reason like this:

1. The requested capability is web-only Gemini.
2. The valid lane is `gemini_web.ask` or a public surface above it.
3. If the current execution path is Gemini CLI, this is a routing mismatch.
4. The right next step is to stop and report the mismatch, not to keep trying CLI/OAuth fixes.

## Why this is enough for now

The low-level Gemini web runtime already exists in ChatgptREST. The gap was not executor implementation. The gap was that the instructions and review workflow left too much room for a coding agent to drift into the wrong channel.

This package closes that governance gap.

