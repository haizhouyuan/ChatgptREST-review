# Public Agent Same-Session Contract Patch Walkthrough v1

## Why this slice matters

The public agent already had:

- `session_id`
- status polling
- streaming
- background watch

What it did not have was a formal way to say:

\"keep the same session, patch the contract, and continue execution.\"

This slice adds that missing semantic.

## Implementation notes

- Session persistence was extended to keep canonical intake/contract state, not just delivery state.
- Clarify responses now return machine-readable patch guidance, so coding agents can resubmit without guessing.
- Session/status responses now expose the stored control-plane objects so clients can inspect what the server believes the task contract is.

## Deliberate boundaries

- This slice does not yet change clarify policy itself.
- This slice does not yet add message parsing.
- This slice only establishes the patch protocol and the minimum diagnostics needed to use it.
