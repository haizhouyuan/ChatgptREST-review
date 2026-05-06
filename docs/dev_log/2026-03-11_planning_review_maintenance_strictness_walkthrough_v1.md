# 2026-03-11 Planning Review Maintenance Strictness Walkthrough v1

## What changed

The earlier hardening added `consistency_audit.json`, but the cycle still behaved as an observational tool only.

This round keeps the same boundary and adds one more maintenance-only control:

- operators can now run the planning priority cycle in strict mode
- strict mode fails immediately if reviewed slice / allowlist / backlog / live bootstrap state drift apart

I also locked the deterministic parts of the maintenance surface:

- the priority queue returns the same ordered rows on the same DB snapshot
- the review scaffold renders the same TSV on the same DB snapshot

## Why this matters

Within the current `#114` boundary, the remaining useful hardening work is not runtime work. It is maintenance reliability work:

- make drift visible
- make drift optionally fatal
- make queue/scaffold outputs stable enough for repeated review passes

This patch does exactly that and does not move the workstream into retrieval, runtime, or promotion changes.
