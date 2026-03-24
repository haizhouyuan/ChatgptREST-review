#!/usr/bin/env python3
"""Post coordination issue comments with an explicit controller marker."""

from __future__ import annotations

import argparse
import subprocess
import sys

from ops.poll_coordination_issues import CONTROLLER_MARKER


def build_comment_body(body: str, *, controller: bool) -> str:
    text = body.strip()
    if not text:
        raise ValueError("comment body is empty")
    if controller:
        return f"{text}\n\n{CONTROLLER_MARKER}\n"
    return text + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("issue", type=int)
    parser.add_argument("--repo", default="haizhouyuan/ChatgptREST")
    parser.add_argument("--body", help="Comment body. If omitted, stdin is used.")
    parser.add_argument(
        "--origin",
        choices=("controller", "plain"),
        default="controller",
        help="Append the controller marker for comments authored by the controller lane.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    raw_body = args.body if args.body is not None else sys.stdin.read()
    payload = build_comment_body(raw_body, controller=args.origin == "controller")
    cmd = [
        "gh",
        "issue",
        "comment",
        str(args.issue),
        "--repo",
        args.repo,
        "--body-file",
        "-",
    ]
    subprocess.run(cmd, input=payload, text=True, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
