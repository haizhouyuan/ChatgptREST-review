#!/usr/bin/env python3
"""Poll coordination issues and log comment-count changes.

This is intentionally separate from the older watcher scripts. It only polls a
fixed set of issues via GitHub CLI, records deltas to a state file, and emits a
plain log line (plus optional desktop notification) when comment counts change.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ops.watch_github_issue_replies import _build_wake_text, _default_wake_target, _wake_tmux_pane

CONTROLLER_MARKER = "<!-- coordination:controller -->"
_SIDE_LANE_PREFIXES = ("education codex", "evomap-import codex")
_CONTROLLER_RECEIVED_MARKERS = (
    "我已经吸收",
    "已吸收：",
    "你这条更像是",
    "这里先明确",
    "不批准",
    "只批准",
    "我的理解与你这条一致",
)


@dataclass
class IssueSnapshot:
    number: int
    title: str
    url: str
    comments_count: int
    latest_comment_url: str | None
    latest_comment_author: str | None
    latest_comment_created_at: str | None
    latest_comment_body: str | None


def _run_gh(repo: str, issue_number: int) -> dict[str, Any]:
    cmd = [
        "gh",
        "issue",
        "view",
        str(issue_number),
        "--repo",
        repo,
        "--json",
        "number,title,url,comments",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def fetch_snapshot(repo: str, issue_number: int) -> IssueSnapshot:
    payload = _run_gh(repo, issue_number)
    comments = payload.get("comments") or []
    latest = comments[-1] if comments else {}
    author = latest.get("author") or {}
    return IssueSnapshot(
        number=int(payload["number"]),
        title=str(payload.get("title") or ""),
        url=str(payload.get("url") or ""),
        comments_count=len(comments),
        latest_comment_url=str(latest.get("url") or "") or None,
        latest_comment_author=str(author.get("login") or "") or None,
        latest_comment_created_at=str(latest.get("createdAt") or "") or None,
        latest_comment_body=str(latest.get("body") or "") or None,
    )


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def log_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line.rstrip() + "\n")


def maybe_notify(summary: str, body: str) -> None:
    if shutil.which("notify-send") is None:
        return
    subprocess.run(["notify-send", summary, body], check=False)


def trim_body(body: str | None, max_chars: int = 240) -> str:
    text = (body or "").replace("\n", " ").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def parse_wake_pane_map(items: list[str] | None) -> dict[int, str]:
    result: dict[int, str] = {}
    for raw in items or []:
        text = str(raw or "").strip()
        if not text:
            continue
        issue_text, sep, pane_text = text.partition("=")
        if not sep:
            raise ValueError(f"invalid wake pane mapping: {text!r}")
        issue_number = int(issue_text.strip())
        pane_target = pane_text.strip()
        if not pane_target:
            raise ValueError(f"wake pane target is empty for issue {issue_number}")
        result[issue_number] = pane_target
    return result


def _is_mainline_comment(body: str | None) -> bool:
    text = str(body or "")
    if CONTROLLER_MARKER in text:
        return True
    lines = [raw_line.strip() for raw_line in text.splitlines() if raw_line.strip()]
    if not lines:
        return False
    first = lines[0]
    if first.startswith("主线"):
        return True
    if first.startswith(_SIDE_LANE_PREFIXES):
        return False
    if first.startswith("收到"):
        return any(marker in text for marker in _CONTROLLER_RECEIVED_MARKERS)
    return False


def poll_once(
    repo: str,
    issues: list[int],
    state: dict[str, Any],
    log_path: Path,
    notify: bool,
    wake_codex_pane: bool = False,
    wake_pane_target: str = "",
    controller_pane_target: str = "",
    wake_pane_map: dict[int, str] | None = None,
    wake_prefix: str = "",
    wake_submit_delay_seconds: float = 2.0,
) -> dict[str, Any]:
    next_state = dict(state)
    wake_targets = wake_pane_map or {}
    for issue_number in issues:
        snapshot = fetch_snapshot(repo, issue_number)
        key = str(issue_number)
        previous = next_state.get(key) or {}
        previous_count = int(previous.get("comments_count") or 0)
        if snapshot.comments_count != previous_count:
            summary = (
                f"Issue #{issue_number} comments changed: "
                f"{previous_count} -> {snapshot.comments_count} | {snapshot.url}"
            )
            latest = (
                f"latest={snapshot.latest_comment_author} "
                f"{snapshot.latest_comment_created_at} "
                f"{snapshot.latest_comment_url or ''} "
                f"{trim_body(snapshot.latest_comment_body)}"
            ).strip()
            log_line(log_path, summary)
            log_line(log_path, latest)
            if notify and snapshot.comments_count > previous_count:
                maybe_notify(
                    f"ChatgptREST issue #{issue_number} updated",
                    trim_body(snapshot.latest_comment_body, max_chars=120),
                )
            if wake_codex_pane and snapshot.comments_count > previous_count:
                issue_target = str(wake_targets.get(issue_number) or wake_pane_target or "").strip()
                controller_target = str(controller_pane_target or _default_wake_target()).strip()
                payload = {
                    "number": snapshot.number,
                    "url": snapshot.url,
                    "repo": repo,
                    "comments": [
                        {
                            "author": {"login": snapshot.latest_comment_author or ""},
                            "createdAt": snapshot.latest_comment_created_at or "",
                            "url": snapshot.latest_comment_url or "",
                            "body": snapshot.latest_comment_body or "",
                        }
                    ],
                }
                if _is_mainline_comment(snapshot.latest_comment_body):
                    target = issue_target or controller_target
                else:
                    target = controller_target
                if target:
                    wake = _wake_tmux_pane(
                        target,
                        _build_wake_text(payload, previous_count, snapshot.comments_count, prefix=wake_prefix),
                        submit_delay_seconds=wake_submit_delay_seconds,
                    )
                    log_line(log_path, f"wake={json.dumps(wake, ensure_ascii=False)}")
                else:
                    log_line(
                        log_path,
                        f"wake_skipped={json.dumps({'issue': issue_number, 'reason': 'no_target'}, ensure_ascii=False)}",
                    )
        next_state[key] = asdict(snapshot)
    return next_state


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="haizhouyuan/ChatgptREST")
    parser.add_argument("--issues", nargs="+", type=int, required=True)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument(
        "--state-file",
        default="state/coordination_issue_poll.json",
    )
    parser.add_argument(
        "--log-file",
        default="artifacts/monitor/coordination_issue_poll/latest.log",
    )
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("--wake-codex-pane", action="store_true")
    parser.add_argument("--wake-pane-target", default="")
    parser.add_argument("--controller-pane-target", default="")
    parser.add_argument("--wake-pane-map", action="append", default=[])
    parser.add_argument("--wake-prefix", default="")
    parser.add_argument("--wake-submit-delay-seconds", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    state_file = Path(args.state_file)
    log_file = Path(args.log_file)
    state = load_state(state_file)
    wake_pane_map = parse_wake_pane_map(args.wake_pane_map)

    while True:
        try:
            state = poll_once(
                repo=args.repo,
                issues=args.issues,
                state=state,
                log_path=log_file,
                notify=args.notify,
                wake_codex_pane=args.wake_codex_pane,
                wake_pane_target=args.wake_pane_target,
                controller_pane_target=args.controller_pane_target,
                wake_pane_map=wake_pane_map,
                wake_prefix=args.wake_prefix,
                wake_submit_delay_seconds=args.wake_submit_delay_seconds,
            )
            save_state(state_file, state)
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            log_line(log_file, f"poll error rc={exc.returncode}: {stderr}")
        except Exception as exc:  # pragma: no cover - last-resort guard
            log_line(log_file, f"poll error: {type(exc).__name__}: {exc}")
        if args.once:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
