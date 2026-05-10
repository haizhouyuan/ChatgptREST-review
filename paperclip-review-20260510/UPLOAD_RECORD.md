# Upload Record

Published: `2026-05-10T16:17:57+08:00`

Package root in review repo: `paperclip-review-20260510/`

Public GitHub URL: `https://github.com/haizhouyuan/ChatgptREST-review/tree/review-20260506-085232/paperclip-review-20260510`

Target repo local path: `$REVIEW_REPO`

Target repo remote verified before copy:

```text
review	git@github.com:haizhouyuan/ChatgptREST-review.git (fetch)
review	git@github.com:haizhouyuan/ChatgptREST-review.git (push)
```

Baseline local package: `$PACKAGE_ROOT`

Baseline package commit: `263efe1ee15e2df3fc3c8519fd55325575b3a9bc`

Copy rule: `rsync -a --delete --exclude='.git/' $PACKAGE_ROOT/ $REVIEW_REPO/paperclip-review-20260510/`, followed by explicit removal of any package-local `.git` directory.

Safety result: no push was attempted until after remote verification and package audit regeneration.
