from __future__ import annotations

import re
from typing import Iterable

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _looks_like_pathish_token(value: str) -> bool:
    s = str(value or "").strip()
    if not s:
        return False
    if s.startswith(("/", "~/", "./", "../")):
        return True
    if _WINDOWS_DRIVE_RE.match(s):
        return True
    return ("/" in s) or ("\\" in s)


def _split_joined_file_path_entry(raw: str) -> list[str]:
    s = str(raw or "").strip()
    if not s:
        return []
    if "\\n" in s and "\n" not in s:
        s = s.replace("\\n", "\n")
    if "\r" in s or "\n" in s:
        return [part.strip() for part in re.split(r"[\r\n]+", s) if part.strip()]
    if "," in s:
        parts = [part.strip() for part in s.split(",") if part.strip()]
        if len(parts) > 1 and all(_looks_like_pathish_token(part) for part in parts):
            return parts
    return [s]


def normalize_file_path_entries(entries: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in entries:
        for part in _split_joined_file_path_entry(str(raw or "")):
            if not part or part in seen:
                continue
            seen.add(part)
            out.append(part)
    return out


def coerce_file_path_input(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        out = normalize_file_path_entries([value])
        return out or None
    if isinstance(value, list):
        out = normalize_file_path_entries(str(item) for item in value if str(item).strip())
        return out or None
    return None
