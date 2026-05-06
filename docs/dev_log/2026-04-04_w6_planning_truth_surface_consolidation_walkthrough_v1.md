# W6 Walkthrough v1

## What I Did

Adjusted the OpenClaw planning query surface so callers no longer have to guess which planning field is authoritative.

Implemented in `openmind-advisor`:

- added `read_semantics` summarization
- added authority-first `planning_query`
- made snapshot reads point to `planning_query.snapshot`
- made list reads point to `planning_query.items`
- updated human-readable tool text to print authority/read-mode/canonical-field

Then updated:

- `openclaw_extensions/openmind-advisor/README.md`
- `AGENTS.md`
- plugin-facing tests

## Why

Before this batch, the plugin returned useful summarized fields, but the contract still left room for consumer drift:

- some callers could read `planning_task`
- others could read session-projected `planning_task`
- others could inspect `read_semantics`
- and none of that clearly declared a single plugin-level authority field

`planning_query` now fixes that without breaking compatibility.

## Validation

- `./.venv/bin/python -m py_compile tests/test_openmind_advisor_truth_surface.py tests/test_openclaw_cognitive_plugins.py`
- `./.venv/bin/pytest -q tests/test_openmind_advisor_truth_surface.py tests/test_openclaw_cognitive_plugins.py`

## Outcome

The public OpenClaw planning query surface now has a single plugin-level rule:

- use `planning_query.snapshot` for single-task/session reads
- use `planning_query.items` for list reads
- use `read_semantics` plus the printed authority/read-mode lines to understand how fresh the read is
