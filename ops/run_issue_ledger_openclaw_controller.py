#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.ops_shared.issue_dev_controller import (  # noqa: E402
    DEFAULT_ARTIFACT_ROOT,
    DEFAULT_DB,
    DEFAULT_LANE_DB,
    DEFAULT_MANIFEST,
    DEFAULT_PR_BASE,
    DEFAULT_WORKTREE_ROOT,
    ControllerLoopConfig,
    run_controller_loop,
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("issue_id")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--lane-db", type=Path, default=DEFAULT_LANE_DB)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--worktree-root", type=Path, default=DEFAULT_WORKTREE_ROOT)
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--repo", default=str(os.environ.get("CHATGPTREST_GITHUB_ISSUE_SYNC_REPO") or "").strip() or None)
    parser.add_argument("--base-ref", default="origin/master")
    parser.add_argument("--pr-base", default=DEFAULT_PR_BASE)
    parser.add_argument("--implementer-lane", default="worker-1")
    parser.add_argument("--reviewer-lane", default="verifier")
    parser.add_argument("--controller-lane", default="main")
    parser.add_argument(
        "--implementer-command-template",
        default=str(os.environ.get("CHATGPTREST_DEV_LOOP_IMPLEMENTER_CMD_TEMPLATE") or "").strip(),
    )
    parser.add_argument(
        "--reviewer-command-template",
        default=str(os.environ.get("CHATGPTREST_DEV_LOOP_REVIEWER_CMD_TEMPLATE") or "").strip(),
    )
    parser.add_argument(
        "--implementer-hcom-target",
        default=str(os.environ.get("CHATGPTREST_DEV_LOOP_IMPLEMENTER_HCOM_TARGET") or "").strip(),
    )
    parser.add_argument(
        "--reviewer-hcom-target",
        default=str(os.environ.get("CHATGPTREST_DEV_LOOP_REVIEWER_HCOM_TARGET") or "").strip(),
    )
    parser.add_argument(
        "--hcom-dir",
        default=(
            str(os.environ.get("CHATGPTREST_DEV_LOOP_HCOM_DIR") or "").strip()
            or str(os.environ.get("HCOM_DIR") or "").strip()
            or None
        ),
    )
    parser.add_argument(
        "--hcom-sender",
        default=str(os.environ.get("CHATGPTREST_DEV_LOOP_HCOM_SENDER") or "").strip() or "issue-dev-controller",
    )
    parser.add_argument(
        "--hcom-poll-seconds",
        type=float,
        default=float(os.environ.get("CHATGPTREST_DEV_LOOP_HCOM_POLL_SECONDS") or "2.0"),
    )
    parser.add_argument(
        "--implementer-timeout-seconds",
        type=float,
        default=float(os.environ.get("CHATGPTREST_DEV_LOOP_IMPLEMENTER_TIMEOUT_SECONDS") or "1800.0"),
    )
    parser.add_argument(
        "--reviewer-timeout-seconds",
        type=float,
        default=float(os.environ.get("CHATGPTREST_DEV_LOOP_REVIEWER_TIMEOUT_SECONDS") or "1800.0"),
    )
    parser.add_argument("--validation-cmd", action="append", default=[])
    parser.add_argument("--service-start-cmd", action="append", default=[])
    parser.add_argument("--health-url", default=None)
    parser.add_argument("--health-timeout-seconds", type=float, default=10.0)
    parser.add_argument("--skip-github-issue-sync", action="store_true")
    parser.add_argument("--no-worktree", action="store_true")
    parser.add_argument("--no-auto-commit", action="store_true")
    parser.add_argument("--no-push", action="store_true")
    parser.add_argument("--no-pr", action="store_true")
    parser.add_argument("--merge-pr", action="store_true")
    parser.add_argument("--merge-method", choices=("merge", "squash", "rebase"), default="merge")
    parser.add_argument("--close-issue-status", choices=("mitigated", "closed"), default=None)
    parser.add_argument("--role-id", default="devops")
    parser.add_argument("--commit-message", default="")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    cfg = ControllerLoopConfig(
        issue_id=args.issue_id,
        db_path=Path(args.db),
        lane_db_path=Path(args.lane_db),
        repo_root=Path(args.repo_root),
        artifact_root=Path(args.artifact_root),
        worktree_root=Path(args.worktree_root),
        manifest_path=(None if str(args.manifest_path).strip() == "" else Path(args.manifest_path)),
        repo_slug=(str(args.repo or "").strip() or None),
        base_ref=str(args.base_ref),
        pr_base=str(args.pr_base),
        create_worktree=not bool(args.no_worktree),
        skip_github_issue_sync=bool(args.skip_github_issue_sync),
        implementer_lane=str(args.implementer_lane),
        reviewer_lane=str(args.reviewer_lane),
        controller_lane=str(args.controller_lane),
        implementer_command_template=str(args.implementer_command_template),
        reviewer_command_template=str(args.reviewer_command_template),
        implementer_hcom_target=str(args.implementer_hcom_target),
        reviewer_hcom_target=str(args.reviewer_hcom_target),
        hcom_dir=(str(args.hcom_dir).strip() or None) if args.hcom_dir is not None else None,
        hcom_sender=str(args.hcom_sender),
        hcom_poll_seconds=float(args.hcom_poll_seconds),
        implementer_timeout_seconds=float(args.implementer_timeout_seconds),
        reviewer_timeout_seconds=float(args.reviewer_timeout_seconds),
        validation_commands=list(args.validation_cmd or []),
        service_start_commands=list(args.service_start_cmd or []),
        health_url=(str(args.health_url) if args.health_url else None),
        health_timeout_seconds=float(args.health_timeout_seconds),
        auto_commit=not bool(args.no_auto_commit),
        push_branch=not bool(args.no_push),
        create_pr=not bool(args.no_pr),
        merge_pr=bool(args.merge_pr),
        merge_method=str(args.merge_method),
        close_issue_status=(str(args.close_issue_status) if args.close_issue_status else None),
        role_id=str(args.role_id),
        commit_message=str(args.commit_message),
    )
    report = run_controller_loop(cfg)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
