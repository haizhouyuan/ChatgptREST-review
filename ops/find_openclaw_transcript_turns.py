#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_DEFAULT_OPENCLAW_STATE_DIR = Path("/home/yuanhaizhou/.home-codex-official/.openclaw")
_MESSAGE_ID_RE = re.compile(r"\[message_id:\s*([^\]]+)\]")
_SENDER_ID_RE = re.compile(r'"sender_id"\s*:\s*"([^"]+)"')
_FILE_NAME_RE = re.compile(r'"file_name"\s*:\s*"([^"]+)"')
_MEDIA_PATH_RE = re.compile(r"(/[^\s\]]*?/media/inbound/[^\s\]]+)")


def _string(value: Any) -> str:
    return str(value or "").strip()


def _default_openclaw_state_dir() -> Path:
    raw = _string(os.environ.get("OPENCLAW_STATE_DIR"))
    if raw:
        return Path(raw).expanduser().resolve()

    candidates = [
        _DEFAULT_OPENCLAW_STATE_DIR,
        Path.home() / ".home-codex-official" / ".openclaw",
        Path.home() / ".openclaw",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.expanduser().resolve()
    return candidates[0].expanduser().resolve()


def _collapse_text(text: str, *, limit: int = 300) -> str:
    collapsed = " ".join(_string(text).split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[:limit].rstrip()}..."


def _extract_message_id(text: str) -> str:
    match = _MESSAGE_ID_RE.search(text)
    return _string(match.group(1) if match else "")


def _extract_sender_id(text: str) -> str:
    match = _SENDER_ID_RE.search(text)
    return _string(match.group(1) if match else "")


def _extract_file_names(text: str) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for match in _FILE_NAME_RE.findall(text):
        file_name = _string(match)
        if not file_name or file_name in seen:
            continue
        seen.add(file_name)
        results.append(file_name)
    return results


def _extract_media_paths(text: str) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for match in _MEDIA_PATH_RE.findall(text):
        media_path = _string(match)
        if not media_path or media_path in seen:
            continue
        seen.add(media_path)
        results.append(media_path)
    return results


def _content_items(message: dict[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [dict(item) for item in content if isinstance(item, dict)]


def _extract_text_items(message: dict[str, Any]) -> list[str]:
    results: list[str] = []
    for item in _content_items(message):
        if _string(item.get("type")) != "text":
            continue
        text = _string(item.get("text"))
        if text:
            results.append(text)
    return results


def _extract_tool_read_paths(message: dict[str, Any]) -> list[str]:
    results: list[str] = []
    for item in _content_items(message):
        if _string(item.get("type")) != "toolCall":
            continue
        if _string(item.get("name")) != "read":
            continue
        arguments = item.get("arguments")
        if isinstance(arguments, dict):
            path = _string(arguments.get("path"))
            if path:
                results.append(path)
    return results


def _user_excerpt(raw_text: str, file_names: Iterable[str]) -> str:
    names = [name for name in file_names if _string(name)]
    if names:
        return f"[image] {', '.join(names[:3])}"
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return ""
    return _collapse_text(lines[-1])


def _assistant_excerpt(texts: Iterable[str]) -> str:
    merged = "\n".join(_string(text) for text in texts if _string(text))
    return _collapse_text(merged)


def _iter_transcript_paths(state_dir: Path, *, agent: str = "", limit: int = 20) -> list[Path]:
    agents_dir = state_dir / "agents"
    if not agents_dir.exists():
        return []
    pattern = f"{agent}/sessions/*.jsonl" if agent else "*/sessions/*.jsonl"
    paths = sorted(agents_dir.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    return paths[: max(limit, 0)]


def _build_turns(transcript_path: Path, *, agent_name: str) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    session_id = transcript_path.stem

    with transcript_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                payload = json.loads(raw_line)
            except Exception:
                continue
            if _string(payload.get("type")) != "message":
                continue
            message = dict(payload.get("message") or {})
            role = _string(message.get("role"))
            timestamp = _string(payload.get("timestamp"))
            if role == "user":
                if current is not None:
                    turns.append(current)
                texts = _extract_text_items(message)
                raw_text = "\n".join(texts)
                file_names = _extract_file_names(raw_text)
                current = {
                    "agent": agent_name,
                    "session_id": session_id,
                    "transcript_path": str(transcript_path),
                    "timestamp": timestamp,
                    "message_id": _extract_message_id(raw_text),
                    "sender_id": _extract_sender_id(raw_text),
                    "user_text": raw_text,
                    "user_excerpt": _user_excerpt(raw_text, file_names),
                    "file_names": file_names,
                    "media_paths": _extract_media_paths(raw_text),
                    "assistant_texts": [],
                }
                continue
            if current is None:
                continue
            if role == "assistant":
                current["assistant_texts"].extend(_extract_text_items(message))
                current["media_paths"].extend(_extract_tool_read_paths(message))

    if current is not None:
        turns.append(current)

    results: list[dict[str, Any]] = []
    for turn in turns:
        seen_paths: set[str] = set()
        media_paths: list[str] = []
        for path in turn.get("media_paths") or []:
            text = _string(path)
            if not text or text in seen_paths:
                continue
            seen_paths.add(text)
            media_paths.append(text)
        results.append(
            {
                "agent": turn["agent"],
                "session_id": turn["session_id"],
                "transcript_path": turn["transcript_path"],
                "timestamp": turn["timestamp"],
                "message_id": turn["message_id"],
                "sender_id": turn["sender_id"],
                "user_excerpt": turn["user_excerpt"],
                "user_text": turn["user_text"],
                "file_names": turn["file_names"],
                "media_paths": media_paths,
                "assistant_excerpt": _assistant_excerpt(turn.get("assistant_texts") or []),
                "assistant_text": "\n".join(turn.get("assistant_texts") or []),
            }
        )
    return results


def _search_text(turn: dict[str, Any]) -> str:
    values = [
        turn.get("agent"),
        turn.get("session_id"),
        turn.get("message_id"),
        turn.get("sender_id"),
        turn.get("user_excerpt"),
        turn.get("user_text"),
        turn.get("assistant_excerpt"),
        turn.get("assistant_text"),
    ]
    values.extend(list(turn.get("file_names") or []))
    values.extend(list(turn.get("media_paths") or []))
    return "\n".join(_string(value) for value in values if _string(value))


def _format_turn(turn: dict[str, Any]) -> str:
    when = _string(turn.get("timestamp"))
    return (
        f"[{when}] agent={turn.get('agent') or '-'} "
        f"message_id={turn.get('message_id') or '-'} sender={turn.get('sender_id') or '-'}\n"
        f"  user: {_string(turn.get('user_excerpt'))}\n"
        f"  reply: {_string(turn.get('assistant_excerpt'))}\n"
        f"  media: {list(turn.get('media_paths') or [])}\n"
        f"  transcript: {_string(turn.get('transcript_path'))}"
    )


def _timestamp_to_epoch(value: str) -> float:
    text = _string(value)
    if not text:
        return 0.0
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except Exception:
        return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect recent OpenClaw transcript turns and assistant replies.")
    parser.add_argument("--keyword", default="", help="Substring filter across user text, reply, filenames, and media paths.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum turns to print.")
    parser.add_argument("--since-hours", type=float, default=24.0, help="Only include turns newer than this many hours.")
    parser.add_argument("--agent", default="", help="Optional exact agent name, e.g. main.")
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of human-readable lines.")
    parser.add_argument("--scan-sessions", type=int, default=20, help="Maximum transcript session files to scan.")
    args = parser.parse_args()

    state_dir = _default_openclaw_state_dir()
    cutoff = time.time() - max(float(args.since_hours), 0.0) * 3600.0
    keyword = _string(args.keyword).lower()

    matches: list[dict[str, Any]] = []
    transcript_paths = _iter_transcript_paths(state_dir, agent=_string(args.agent), limit=max(int(args.scan_sessions), 0))
    for transcript_path in transcript_paths:
        agent_name = transcript_path.parent.parent.name
        for turn in _build_turns(transcript_path, agent_name=agent_name):
            updated_at = _timestamp_to_epoch(_string(turn.get("timestamp")))
            if updated_at and updated_at < cutoff:
                continue
            if keyword and keyword not in _search_text(turn).lower():
                continue
            matches.append(turn)
            if len(matches) >= max(int(args.limit), 0):
                break
        if len(matches) >= max(int(args.limit), 0):
            break

    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "state_dir": str(state_dir),
                    "matches": matches,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not matches:
        print("No transcript turns matched.")
        return 0

    for turn in matches:
        print(_format_turn(turn))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
