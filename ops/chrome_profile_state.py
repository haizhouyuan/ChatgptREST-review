#!/usr/bin/env python3
"""Normalize persistent Chrome profile state for the Xvfb/CDP lane."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _store_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = 0o600
    try:
        mode = path.stat().st_mode & 0o777
    except FileNotFoundError:
        pass

    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        handle.flush()
        os.fsync(handle.fileno())
        tmp_path = Path(handle.name)

    os.chmod(tmp_path, mode)
    os.replace(tmp_path, path)


def _set_nested(payload: dict, dotted_path: str, value) -> bool:
    cursor = payload
    parts = dotted_path.split(".")
    for key in parts[:-1]:
        child = cursor.get(key)
        if not isinstance(child, dict):
            child = {}
            cursor[key] = child
        cursor = child
    leaf = parts[-1]
    if cursor.get(leaf) == value:
        return False
    cursor[leaf] = value
    return True


def mark_clean(user_data_dir: Path, profile_dir: str) -> int:
    changed = False

    local_state = user_data_dir / "Local State"
    if local_state.exists():
        payload = _load_json(local_state)
        changed_local = False
        changed_local |= _set_nested(
            payload,
            "user_experience_metrics.stability.exited_cleanly",
            True,
        )
        changed_local |= _set_nested(payload, "was.restarted", False)
        if changed_local:
            _store_json(local_state, payload)
            changed = True

    preferences = user_data_dir / profile_dir / "Preferences"
    if preferences.exists():
        payload = _load_json(preferences)
        changed_prefs = False
        changed_prefs |= _set_nested(payload, "profile.exit_type", "Normal")
        changed_prefs |= _set_nested(payload, "profile.exited_cleanly", True)
        if changed_prefs:
            _store_json(preferences, payload)
            changed = True

    return 0 if changed else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    mark_clean_parser = subparsers.add_parser("mark-clean")
    mark_clean_parser.add_argument("--user-data-dir", required=True)
    mark_clean_parser.add_argument("--profile-dir", default="Default")

    args = parser.parse_args()

    if args.command == "mark-clean":
        return mark_clean(Path(args.user_data_dir), args.profile_dir)

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
