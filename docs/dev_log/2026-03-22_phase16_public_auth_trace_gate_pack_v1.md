# Phase 16 Public Auth Trace Gate Pack v1

## Goal

Freeze the live write-path guards for the public `/v3/agent/turn` ingress:

- auth
- client allowlist
- required trace headers

## Live Checks

1. `no_auth_rejected`
   - no auth headers
   - expected: `401 Invalid or missing API key`
2. `auth_without_allowlisted_client_rejected`
   - valid auth
   - missing `X-Client-Name`
   - expected: `403 client_not_allowed`
3. `auth_allowlisted_without_trace_rejected`
   - valid auth
   - `X-Client-Name=chatgptrestctl`
   - missing `X-Client-Instance` and `X-Request-ID`
   - expected: `400 missing_trace_headers`
4. `auth_allowlisted_traced_request_accepted`
   - valid auth
   - allowlisted client
   - required trace headers present
   - expected: `200`, `status=needs_followup`, `route=clarify`

## Implementation

- Validation module:
  - [chatgptrest/eval/public_auth_trace_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/public_auth_trace_gate.py)
- Runner:
  - [ops/run_public_auth_trace_gate.py](/vol1/1000/projects/ChatgptREST/ops/run_public_auth_trace_gate.py)
- Tests:
  - [tests/test_public_auth_trace_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_public_auth_trace_gate.py)

## Acceptance

- runner exits `0`
- report shows `4/4` checks passed
- live `/v3/agent/turn` write guards are proven in the current runtime
