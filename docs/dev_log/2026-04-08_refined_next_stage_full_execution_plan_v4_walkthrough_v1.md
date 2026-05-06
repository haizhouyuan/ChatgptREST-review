# Refined Next-Stage Full Execution Plan V4 Walkthrough V1

Date: 2026-04-08

## Why V4 was needed

V3 and the red-team follow-on wave closed the immediate problems, but they did not yet turn the platform into a fully coherent runtime.

The clearest signal was the `jobs answer 401` issue:

- external coding-agent behavior was green
- internal jobs-answer primary path was still broken
- fallback hid the mismatch well enough for clients, but not well enough for long-term platform coherence

That means the next plan has to be a root-fix plan, not just another corrective patch list.

## What V4 adds

V4 adds one systemic frame:

- public surface
- auth domain
- live gate
- project-truth governance
- promotion maintenance

are now treated as one connected runtime problem instead of five separate follow-up topics.

## Main practical change

The biggest change in V4 is that it no longer treats `jobs answer 401` as an isolated auth bug.

It treats it as evidence that:

- the platform still has mixed auth domains
- fallback is currently compensating for that mismatch
- release gates need to distinguish primary-path green from degraded-path green

## Result

V4 is now the main plan for the next system-level hardening wave.
