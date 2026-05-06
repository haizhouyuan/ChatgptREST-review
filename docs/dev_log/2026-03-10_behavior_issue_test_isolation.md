## Summary

`tests/test_behavior_issue_detection.py` could hang inside `maint_daemon.main()` when run after other tests, even though the behavior-issue logic itself was fine.

## Root cause

The test objective is behavior-issue promotion from human-authored prompts, but `maint_daemon.main()` still inherited the default `ui_canary` path. In the test environment that path can reach live MCP HTTP/SSE self-checks, which makes the test depend on an external runtime instead of only its temporary SQLite fixtures.

This showed up as a hang in:

- `tests/test_behavior_issue_detection.py::test_maint_daemon_main_promotes_behavior_issue_from_human_questions`

and was reproducible outside pytest once the prior behavior-issue subsystem test had already run.

## Change

- Added `--disable-ui-canary` to the two `maint_daemon.main()` tests in `tests/test_behavior_issue_detection.py`.

## Why this is the right fix

- The tests are validating behavior-issue promotion and job-scan incident creation.
- They do not need live UI health checks.
- Disabling `ui_canary` keeps the test aligned with its real contract and removes an unrelated external dependency from the suite.

## Validation

- `./.venv/bin/pytest -q tests/test_behavior_issue_detection.py -vv`
