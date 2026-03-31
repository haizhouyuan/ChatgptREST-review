# 2026-03-24 Public Agent Deliberation And Maint Unification Gemini Retry Log v1

## Scope

This log records repeated real Gemini Deep Think review attempts for the `Public Agent deliberation + maintenance unification` blueprint set on 2026-03-24.

Goal:

- obtain an independent GeminiDT review
- distinguish packaging errors from runtime usability errors

## Outcome

No successful GeminiDT review answer was obtained in this round.

What was ruled out:

- wrong API token
- missing `enable_import_code`
- attachment-contract false positives caused by obvious repo-path prompt strings

What remains unresolved:

- `repo import` lane usability
- plain text `deep_think` lane stability

## Attempt Summary

### Attempt `v2b`

- transport: `repo-first`
- mode: `gemini_web.ask + deep_think`
- repo import: enabled
- result: request accepted, but send path repeatedly failed on Gemini Tools interaction

Observed job:

- `16d2032be7f94c1aa207ee0d8b3eeedb`

Observed failure:

- repeated `UiTransientError`
- root symptom: Gemini Tools button remained present but disabled
- conversation never advanced beyond Gemini home/root app state

Evidence:

- [gemini_dt_summary_v2.json](/vol1/1000/projects/ChatgptREST/artifacts/reviews/2026-03-24_deliberation_maint_unification_dual_review/gemini_dt_summary_v2.json)
- `artifacts/jobs/16d2032be7f94c1aa207ee0d8b3eeedb/*`
- repair job `fec973d5926b410c9c843de8ab1d1c99`

### Attempt `v3`

- transport: text-only packet
- mode: `gemini_web.ask + deep_think`
- repo import: disabled
- result: immediate `AttachmentContractMissing`

Observed job:

- `62f43a6159ba4acda2a0fd42c977d328`

Root cause:

- the packet still contained slash-style path strings
- Gemini attachment contract interpreted those as undeclared local file references

Evidence:

- [gemini_dt_summary_v3.json](/vol1/1000/projects/ChatgptREST/artifacts/reviews/2026-03-24_deliberation_maint_unification_dual_review/gemini_dt_summary_v3.json)

### Attempt `v4`

- transport: sanitized text-only packet
- mode: `gemini_web.ask + deep_think`
- repo import: disabled
- result: no attachment-contract error, but repeated generic runtime cooldown with no answer

Observed job:

- `0fb9c61391ae47d788362ef3b626e2bf`

Observed failure:

- no conversation URL
- `RuntimeError` with empty error text
- repeated `cooldown/recovering`
- no answer artifact produced

Evidence:

- [gemini_dt_summary_v4.json](/vol1/1000/projects/ChatgptREST/artifacts/reviews/2026-03-24_deliberation_maint_unification_dual_review/gemini_dt_summary_v4.json)
- `artifacts/jobs/0fb9c61391ae47d788362ef3b626e2bf/*`

### Attempt `v5`

- transport: short sanitized text-only packet
- mode: `gemini_web.ask + deep_think`
- repo import: disabled
- result: still no answer; send phase eventually dropped into generic runtime cooldown

Observed job:

- `92b9f8ec512541d98b4ba8eaf1cce263`

Observed failure:

- no attachment-contract error
- no explicit UI-tools failure
- no conversation URL
- no answer artifact
- generic `RuntimeError` cooldown after long send window

Evidence:

- `artifacts/jobs/92b9f8ec512541d98b4ba8eaf1cce263/*`

## Key Diagnosis

There are at least two distinct GeminiDT usability issues:

1. `repo import` lane can fail before prompt send because the Gemini tools/import interaction remains unavailable at the page state the worker reaches.
2. even when `repo import` is removed and the prompt is reduced to text-only, `deep_think` can still fall into a generic runtime cooldown with no answer and no stable conversation URL.

So the current state is not “bad packing only”.
It is:

- one packaging/contract class of issue
- plus one deeper GeminiDT runtime usability issue

## Practical Conclusion

For this review target:

- `ChatGPT Pro` review is available and recorded
- `GeminiDT` review was genuinely retried several times
- but no successful GeminiDT answer was produced in this round

The missing piece is now runtime usability, not operator diligence.
