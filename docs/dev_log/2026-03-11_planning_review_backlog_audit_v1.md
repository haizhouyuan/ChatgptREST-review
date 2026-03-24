# 2026-03-11 Planning Review Backlog Audit v1

## Scope

Add a maintenance audit for the unreviewed planning backlog outside the current reviewed slice.

Added:

- [report_planning_review_backlog.py](/vol1/1000/projects/ChatgptREST/ops/report_planning_review_backlog.py)
- [test_report_planning_review_backlog.py](/vol1/1000/projects/ChatgptREST/tests/test_report_planning_review_backlog.py)

## Question

This script answers a narrower question than the earlier reviewed-slice audit:

`What remains outside the current planning reviewed baseline, and where is that backlog concentrated?`

It reports:

- total / role-tagged / reviewed / backlog doc counts
- reviewed docs by final bucket
- backlog by:
  - `review_domain`
  - `source_bucket`
  - `document_role`
- `latest_output_backlog_docs`
- top backlog families
- sample backlog docs from the latest-output slice

## Live Result

Command:

```bash
./.venv/bin/python ops/report_planning_review_backlog.py
```

Result:

- `total_docs = 3350`
- `role_tagged_docs = 3350`
- `reviewed_docs = 156`
- `backlog_docs = 3194`

Reviewed by bucket:

- `service_candidate = 103`
- `review_only = 25`
- `procedure = 12`
- `archive_only = 7`
- `controlled = 7`
- `correction = 1`
- `reject_noise = 1`

Backlog by domain:

- `misc = 1300`
- `business_104 = 1076`
- `reducer = 451`
- `governance = 169`
- `business_60 = 126`

Backlog by source bucket:

- `planning_misc = 1761`
- `planning_review_pack = 1071`
- `planning_latest_output = 82`
- `planning_outputs = 78`
- `planning_aios = 68`

Backlog by document role:

- `archive_only = 1694`
- `review_plane = 1483`
- `controlled = 17`

Latest-output backlog:

- `latest_output_backlog_docs = 160`

Top backlog families include:

- empty-family `planning_misc` / `misc`: `1200`
- `b104_exec_report` / `planning_review_pack`: `340`
- `peek_reviewpack_sim_code` / `planning_review_pack`: `196`
- `b104_customer_comm` / `planning_review_pack`: `104`
- `b104_latest_outputs` / `planning_latest_output`: `73`

## Interpretation

This audit makes two things clearer than the raw reviewed-slice counts:

1. The backlog is not evenly distributed.
   The dominant backlog is still:
   - generic `planning_misc`
   - `_review_pack` / review-plane material

2. The latest-output backlog still contains mixed value.
   The sample latest-output backlog includes obviously non-service-ready items like:
   - `README`
   - `runlog`
   - `问 Pro`

That means the next maintenance step should not be “review more latest outputs indiscriminately”.

It should be:

- build a tighter priority queue inside the latest-output backlog
- keep `_review_pack` mostly in review/archive planes
- avoid interpreting `latest_output` as automatically service-worthy

## Validation

```bash
./.venv/bin/python -m py_compile \
  ops/report_planning_review_backlog.py \
  tests/test_report_planning_review_backlog.py

./.venv/bin/pytest -q \
  tests/test_report_planning_review_backlog.py \
  tests/test_report_planning_review_state.py \
  tests/test_run_planning_review_cycle.py
```

## Boundary

This round did **not**:

- expand the reviewed baseline
- change live bootstrap state
- alter runtime retrieval or promotion rules

It only adds deterministic visibility into the remaining planning review backlog.
