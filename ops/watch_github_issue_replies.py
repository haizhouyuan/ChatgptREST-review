#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import textwrap
import time
from pathlib import Path
from typing import Any
from urllib import error, request


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = REPO_ROOT / "state" / "github_issue_watch"
DEFAULT_WAKE_SUBMIT_DELAY_SECONDS = 2.0


def _repo_slug(repo: str) -> str:
    return repo.replace("/", "__").strip("_") or "default"


def _default_state_file(repo: str, issue_number: int, state_dir: Path) -> Path:
    return state_dir / _repo_slug(repo) / f"issue_{int(issue_number)}.json"


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _run_gh_issue_view(repo: str, issue_number: int) -> dict[str, Any]:
    proc = subprocess.run(
        [
            "gh",
            "issue",
            "view",
            str(int(issue_number)),
            "--repo",
            repo,
            "--json",
            "number,title,url,comments",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    return payload if isinstance(payload, dict) else {}


def _comment_count(payload: dict[str, Any]) -> int:
    comments = payload.get("comments")
    return len(comments) if isinstance(comments, list) else 0


def _latest_comment(payload: dict[str, Any]) -> dict[str, Any] | None:
    comments = payload.get("comments")
    if not isinstance(comments, list) or not comments:
        return None
    latest = comments[-1]
    return latest if isinstance(latest, dict) else None


def _summarize_comment(comment: dict[str, Any] | None) -> str:
    if not comment:
        return "No comments"
    author = comment.get("author") or {}
    author_name = str(author.get("login") or author.get("name") or "unknown") if isinstance(author, dict) else "unknown"
    created_at = str(comment.get("createdAt") or "").strip()
    url = str(comment.get("url") or "").strip()
    body = " ".join(str(comment.get("body") or "").split())
    if len(body) > 280:
        body = body[:277] + "..."
    parts = [f"author={author_name}"]
    if created_at:
        parts.append(f"created_at={created_at}")
    if url:
        parts.append(f"url={url}")
    if body:
        parts.append(f"body={body}")
    return " | ".join(parts)


def _notify_webhook(webhook_url: str, text: str, timeout_seconds: float) -> dict[str, Any]:
    req = request.Request(
        webhook_url,
        data=json.dumps({"msg_type": "text", "content": {"text": text}}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with request.urlopen(req, timeout=float(timeout_seconds)) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = getattr(resp, "status", 200)
        return {"ok": True, "status": status, "body": body}
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "status": exc.code, "body": body}
    except Exception as exc:  # pragma: no cover - transport/env failure
        return {"ok": False, "error": repr(exc)}


def _notify_desktop(title: str, text: str) -> dict[str, Any]:
    if not shutil.which("notify-send"):
        return {"ok": False, "error": "notify-send not found"}
    proc = subprocess.run(["notify-send", title, text], capture_output=True, text=True)
    return {"ok": proc.returncode == 0, "returncode": proc.returncode, "stderr": proc.stderr.strip()}


def _default_wake_target() -> str:
    return str(os.environ.get("CODEX_CONTROLLER_PANE") or "").strip()


def _build_wake_text(payload: dict[str, Any], old_count: int, new_count: int, prefix: str = "") -> str:
    latest = _summarize_comment(_latest_comment(payload))
    prefix_text = str(prefix or "").strip()
    parts = []
    if prefix_text:
        parts.append(prefix_text)
    parts.append(
        f"GitHub issue #{payload.get('number')} has a new reply in {payload.get('repo') or 'the tracked repo'}"
    )
    parts.append(f"comments {old_count}->{new_count}")
    parts.append(f"url={payload.get('url')}")
    parts.append(f"latest={latest}")
    parts.append("Read the latest comment, summarize the delta, and continue the workstream immediately.")
    return " | ".join(part for part in parts if part).strip()


def _wake_tmux_pane(target: str, text: str, submit_delay_seconds: float = DEFAULT_WAKE_SUBMIT_DELAY_SECONDS) -> dict[str, Any]:
    target_text = str(target or "").strip()
    if not target_text:
        return {"ok": False, "error": "wake target pane is empty"}
    if not shutil.which("tmux"):
        return {"ok": False, "error": "tmux not found"}
    try:
        send = subprocess.run(
            ["tmux", "send-keys", "-t", target_text, "-l", text],
            capture_output=True,
            text=True,
            check=False,
        )
        if send.returncode != 0:
            return {
                "ok": False,
                "error": "tmux send-keys text failed",
                "returncode": send.returncode,
                "stderr": send.stderr.strip(),
            }
        time.sleep(max(0.0, float(submit_delay_seconds)))
        enter = subprocess.run(
            ["tmux", "send-keys", "-t", target_text, "C-m"],
            capture_output=True,
            text=True,
            check=False,
        )
        return {
            "ok": enter.returncode == 0,
            "target": target_text,
            "submit_delay_seconds": max(0.0, float(submit_delay_seconds)),
            "returncode": enter.returncode,
            "stderr": enter.stderr.strip(),
        }
    except Exception as exc:  # pragma: no cover - transport/env failure
        return {"ok": False, "error": repr(exc), "target": target_text}


def _build_alert_text(payload: dict[str, Any], old_count: int, new_count: int) -> str:
    latest = _summarize_comment(_latest_comment(payload))
    return textwrap.dedent(
        f"""\
        GitHub issue reply detected
        issue=#{payload.get("number")} title={payload.get("title")}
        comments: {old_count} -> {new_count}
        url={payload.get("url")}
        latest={latest}
        """
    ).strip()


def _write_baseline(state_file: Path, repo: str, issue_number: int, payload: dict[str, Any]) -> dict[str, Any]:
    latest = _latest_comment(payload) or {}
    data = {
        "repo": repo,
        "issue_number": int(issue_number),
        "baseline_comment_count": _comment_count(payload),
        "updated_at": time.time(),
        "latest_comment_url": str(latest.get("url") or ""),
    }
    _save_state(state_file, data)
    return data


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Watch GitHub issue replies and notify when a new comment arrives.")
    p.add_argument("issue_number", type=int)
    p.add_argument("--repo", default="haizhouyuan/ChatgptREST")
    p.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    p.add_argument("--interval-seconds", type=float, default=60.0)
    p.add_argument("--timeout-seconds", type=float, default=8.0)
    p.add_argument("--webhook-url", default="")
    p.add_argument("--desktop-notify", action="store_true")
    p.add_argument("--wake-codex-pane", action="store_true")
    p.add_argument("--wake-pane-target", default="")
    p.add_argument("--wake-prefix", default="")
    p.add_argument("--wake-submit-delay-seconds", type=float, default=DEFAULT_WAKE_SUBMIT_DELAY_SECONDS)
    p.add_argument("--wait", action="store_true")
    p.add_argument("--arm-only", action="store_true")
    p.add_argument("--wake-current-if-unseen", action="store_true")
    p.add_argument("--print-latest", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    state_dir = Path(args.state_dir).expanduser()
    state_file = _default_state_file(args.repo, args.issue_number, state_dir)
    webhook_url = str(args.webhook_url or os.environ.get("FEISHU_BOT_WEBHOOK_URL") or "").strip()
    wake_target = str(args.wake_pane_target or _default_wake_target()).strip()

    payload = _run_gh_issue_view(args.repo, args.issue_number)
    if isinstance(payload, dict):
        payload.setdefault("repo", args.repo)
    if args.print_latest:
        print(_summarize_comment(_latest_comment(payload)))

    if args.arm_only:
        state = _write_baseline(state_file, args.repo, args.issue_number, payload)
        print(json.dumps({"armed": True, "state_file": str(state_file), **state}, ensure_ascii=False))
        return 0

    state = _load_state(state_file)
    if not state:
        current_count = _comment_count(payload)
        latest = _latest_comment(payload)
        if args.wake_current_if_unseen and latest:
            alert_text = _build_alert_text(payload, 0, current_count)
            if webhook_url:
                notify = _notify_webhook(webhook_url, alert_text, timeout_seconds=args.timeout_seconds)
            elif args.desktop_notify:
                notify = _notify_desktop(f"GitHub issue #{args.issue_number} replied", alert_text)
            else:
                notify = {"ok": False, "error": "no notify target configured"}
            wake = None
            if args.wake_codex_pane:
                wake_text = _build_wake_text(payload, 0, current_count, prefix=args.wake_prefix)
                wake = _wake_tmux_pane(
                    wake_target,
                    wake_text,
                    submit_delay_seconds=args.wake_submit_delay_seconds,
                )
            state = _write_baseline(state_file, args.repo, args.issue_number, payload)
            event = {
                "detected": True,
                "initial_wake": True,
                "issue_number": args.issue_number,
                "repo": args.repo,
                "old_count": 0,
                "new_count": current_count,
                "state_file": str(state_file),
                "latest_comment": _summarize_comment(latest),
                "notify": notify,
                "wake": wake,
                "state": state,
            }
            print(json.dumps(event, ensure_ascii=False))
            if not args.wait:
                return 0
        else:
            state = _write_baseline(state_file, args.repo, args.issue_number, payload)
    baseline_count = int(state.get("baseline_comment_count") or 0)

    if not args.wait:
        print(
            json.dumps(
                {
                    "issue_number": args.issue_number,
                    "repo": args.repo,
                    "baseline_comment_count": baseline_count,
                    "current_comment_count": _comment_count(payload),
                    "state_file": str(state_file),
                    "latest_comment": _summarize_comment(_latest_comment(payload)),
                },
                ensure_ascii=False,
            )
        )
        return 0

    while True:
        payload = _run_gh_issue_view(args.repo, args.issue_number)
        current_count = _comment_count(payload)
        if args.print_latest:
            print(_summarize_comment(_latest_comment(payload)))
        if current_count > baseline_count:
            alert_text = _build_alert_text(payload, baseline_count, current_count)
            if webhook_url:
                notify = _notify_webhook(webhook_url, alert_text, timeout_seconds=args.timeout_seconds)
            elif args.desktop_notify:
                notify = _notify_desktop(f"GitHub issue #{args.issue_number} replied", alert_text)
            else:
                notify = {"ok": False, "error": "no notify target configured"}
            wake = None
            if args.wake_codex_pane:
                wake_text = _build_wake_text(payload, baseline_count, current_count, prefix=args.wake_prefix)
                wake = _wake_tmux_pane(
                    wake_target,
                    wake_text,
                    submit_delay_seconds=args.wake_submit_delay_seconds,
                )
            state = _write_baseline(state_file, args.repo, args.issue_number, payload)
            print(
                json.dumps(
                    {
                        "detected": True,
                        "issue_number": args.issue_number,
                        "repo": args.repo,
                        "old_count": baseline_count,
                        "new_count": current_count,
                        "state_file": str(state_file),
                        "latest_comment": _summarize_comment(_latest_comment(payload)),
                        "notify": notify,
                        "wake": wake,
                        "state": state,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        time.sleep(max(1.0, float(args.interval_seconds)))


if __name__ == "__main__":
    raise SystemExit(main())
