# 2026-04-07 Dual-Model Related System Context Sanitized v1

## Purpose

This note provides the minimum cross-repo / cross-system context needed for an external architectural review.

It is intentionally sanitized:

- no secrets
- no tokens
- no private business-planning source materials
- no local absolute filesystem paths
- no personally sensitive data beyond already-public system roles

## 1. OpenClaw Main Workspace Principles

The current `OpenClaw main` workspace is intentionally lean.

Its key principles are:

1. treat the shell as the primary human-facing agent
2. use `OpenMind` tools first when memory/context/graph awareness matters
3. prefer direct execution and explicit skills/workflows over rebuilding a large persistent role-agent topology
4. do not assume old experimental orchestrator roles still exist
5. keep the shell close to upstream `OpenClaw`

The user-level operating principle is:

> keep the shell lean; do not re-grow the old half-finished role-agent topology

This matters because the next-stage platform plan must not solve complexity by bloating the `OpenClaw` shell.

## 2. Authority Anchor Pattern

The current project truth approach uses an explicit per-project authority anchor document.

Its role is to preserve human-governed items such as:

- frozen facts
- style rules
- pinned authority inputs
- current human stage framing

The important architectural point is:

- this anchor is not meant to become a giant dynamic cache
- it is meant to remain the top human-governed truth layer
- dynamic recall and project-scoped retrieval must not silently override it

## 3. Review/Upload Workflow Constraints

Current review channels use two complementary mechanisms:

### Public review repo

Used when:

- a private main repo cannot be read directly by external web review tools
- a curated subset is preferable to the full private codebase
- import-size control matters

Current tooling supports:

- syncing selected directories into a public review mirror
- creating branch-scoped review bundles
- maintaining a stable import branch for Gemini code import
- finalizing/cleanup after review

### Review packet attachments

Used when:

- architecture intent must be made explicit
- cross-repo context is needed
- code alone would not convey the intended product boundary
- a curated subset of related-system context must be attached without publishing more source code

## 4. Privacy And Scope Rules For This Review

For this external review, the intended safe boundary is:

### Publicly mirrored code

Only the curated ChatgptREST trunk subset that is directly relevant to:

- coding-agent surface
- public agent MCP / wrapper
- OpenMind plugin bridge
- project-scoped substrate
- promotion/maintenance harness

### Attached sanitized context

Only distilled architectural context about:

- OpenClaw entry-layer role
- authority-anchor role
- review-channel constraints
- next-stage target shape

### Explicitly excluded

- business strategy documents
- customer/project-sensitive planning details
- secrets/credentials/tokens
- env files
- runtime artifacts
- large unrelated historical source trees

## 5. Why Cross-Repo Context Is Still Needed

Even though the code under direct review is centered on `ChatgptREST`, the target architecture spans:

1. `ChatgptREST` as web-first execution and cognition substrate
2. `OpenMind plugins` as the bridge layer
3. `OpenClaw` as the human-facing entry/orchestration layer
4. project authority anchors as the human-governed truth layer

So the review must not pretend `ChatgptREST` is an isolated product.

At the same time, it must not over-share unrelated source or sensitive business material.

## 6. Practical Reading Heuristic For Reviewers

When reading the curated public repo and attachments, reviewers should interpret the platform in this order:

1. coding-agent northbound surface
2. OpenClaw/OpenMind handoff boundary
3. project truth layering
4. promotion/maintenance operations

This order reflects the current mainline risk:

- first restore the correct user/product surface
- then ensure the entry layer behaves correctly
- then lock down truth governance
- then scale substrate digestion and evolution safely
