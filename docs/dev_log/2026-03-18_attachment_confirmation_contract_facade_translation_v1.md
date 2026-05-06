# 2026-03-18 Attachment Confirmation Contract Facade Translation v1

## What Changed

- Kept the low-level attachment detector fail-closed for real local file references.
- Translated `AttachmentContractMissing` into a public agent facade `needs_input` response instead of surfacing it as a generic failure.
- Added structured attachment confirmation payloads on both:
  - `POST /v3/agent/turn`
  - `GET /v3/agent/session/{session_id}`

## Why

- The detector should remain strict for real local paths such as `/vol1/...` or `./bundle.zip`.
- Public agent clients should not need to reverse-engineer worker/job errors.
- The facade now returns a client-actionable contract:
  - detected attachment candidates
  - confidence
  - explicit next action

## Behavior

- When a controller-backed request fails because attachments were referenced but not provided:
  - facade status becomes `needs_input`
  - `next_action.type` becomes `attachment_confirmation_required`
  - `attachment_confirmation` is included in the response body
- Session refresh keeps the same `needs_input` state and confirmation payload.

## Scope Boundary

- No controller or worker fail-closed semantics were relaxed.
- No low-level attachment detector behavior was widened here.
- This change is only a facade-level translation and response-shaping improvement.

## Validation

- `./.venv/bin/pytest -q tests/test_attachment_contract_preflight.py tests/test_routes_agent_v3.py tests/test_agent_v3_routes.py`

