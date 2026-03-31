## Summary

Fixed a false positive in attachment-contract preflight that treated Chinese slash phrases such as `/二手来源`, `/中/弱/推测`, and `/行为/访谈/...` as undeclared local file references.

## Root Cause

- `chatgptrest/core/attachment_contract.py` used `_LOCAL_FILE_REF_RE` to collect slash-prefixed tokens.
- The regex matched Markdown-like Chinese slash headings and rubric fragments inside long research prompts.
- A second token scan also stripped leading `.` from relative paths, so `./review_bundle_v1.zip` could be duplicated as `/review_bundle_v1.zip`.
- Public agent requests using `goal_hint=research` were then fail-closed with `AttachmentContractMissing`, which surfaced as `blocking`.

## Fix

- Added `_looks_like_local_file_ref()` to filter regex matches before treating them as real local file refs.
- Kept true positives for:
  - explicit attachment suffixes like `.md`, `.zip`, `.pdf`
  - Windows drive paths
  - multi-segment relative/absolute paths with path-like ASCII segments
- Ignored slash-prefixed Chinese prose fragments that do not look like actual filesystem paths.
- Preserved leading `.` for relative-path token scanning so `./review_bundle_v1.zip` stays intact.
- Skipped nested `/...` regex matches inside `./...` and `~/...`.

## Tests

Ran:

```bash
./.venv/bin/pytest -q tests/test_attachment_contract_preflight.py
```

Added regression coverage for:

- Leopold-style Chinese slash headings not triggering attachment preflight
- relative bundle paths still fail-closing correctly

## Impact

- Narrow fix only in attachment-contract detection
- No worker/executor calling semantics changed
- Real undeclared attachment paths such as `/vol1/work/review_bundle_v1.md` and `./review_bundle_v1.zip` still trigger fail-closed behavior
