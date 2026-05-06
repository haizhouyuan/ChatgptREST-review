from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from chatgptrest.core.file_path_inputs import _looks_like_pathish_token

_LOCAL_FILE_REF_RE = re.compile(
    r"(?P<path>(?:/|~?/|\.{1,2}/)[^\s'\"`()\[\]{}<>]+|[A-Za-z]:[\\/][^\s'\"`()\[\]{}<>]+)"
)
_PATHY_SEGMENT_RE = re.compile(r"[A-Za-z0-9_.-]")
_FILESYSTEM_ROOT_HINTS: frozenset[str] = frozenset(
    {
        "bin",
        "data",
        "etc",
        "home",
        "mnt",
        "opt",
        "private",
        "root",
        "srv",
        "tmp",
        "users",
        "usr",
        "var",
        "vol1",
        "vol2",
        "workspace",
    }
)
_ATTACHMENT_SUFFIXES: frozenset[str] = frozenset(
    {
        ".md",
        ".markdown",
        ".txt",
        ".pdf",
        ".doc",
        ".docx",
        ".csv",
        ".tsv",
        ".json",
        ".jsonl",
        ".yaml",
        ".yml",
        ".zip",
        ".patch",
        ".diff",
        ".log",
        ".html",
    }
)
_HIGH_RISK_VERB_RE = re.compile(
    r"\b(read|review|audit|analy[sz]e|inspect|check|summari[sz]e|use|compare|diff|examine)\b|"
    r"(阅读|读取|审阅|审查|检查|分析|对比|比较|使用)",
    re.I,
)
_HIGH_RISK_OBJECT_RE = re.compile(
    r"\b(attached|attachment|attachments|bundle|package|packages|document|documents|file|files|artifact|artifacts)\b|"
    r"(附件|材料包|文件|文档|压缩包|bundle|包)",
    re.I,
)
_HIGH_RISK_LOCAL_RE = re.compile(
    r"\b(local|repo|repository|review bundle|audit bundle|material bundle)\b|"
    r"(本地|仓库|repo|bundle)",
    re.I,
)
_PURPOSE_HIGH_RISK: frozenset[str] = frozenset({"review", "audit", "report", "check"})


def _compact_preview(value: Any, *, limit: int = 240) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _looks_like_local_file_ref(candidate: str) -> bool:
    raw = str(candidate or "").strip()
    if not raw:
        return False
    if "://" in raw:
        return False
    suffix = Path(raw).suffix.lower()
    if suffix and suffix in _ATTACHMENT_SUFFIXES:
        return True
    if re.match(r"^[A-Za-z]:[\\/]", raw):
        return True

    normalized = raw.replace("\\", "/")
    if not normalized.startswith(("/", "~/", "./", "../")):
        return False

    parts = [part for part in normalized.split("/") if part and part not in {".", "..", "~"}]
    if len(parts) < 2:
        return False
    if suffix:
        return any(_PATHY_SEGMENT_RE.search(part) for part in parts)
    if normalized.startswith(("~/", "./", "../")):
        return True
    if parts and parts[0].strip().lower() in _FILESYSTEM_ROOT_HINTS:
        return True
    return False


def _local_file_refs(text: str) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    raw = str(text or "")
    for match in _LOCAL_FILE_REF_RE.finditer(raw):
        start = match.start("path")
        if start > 0 and raw[start] == "/" and raw[start - 1] in {".", "~", ":"}:
            continue
        if start > 0 and raw[start] == "/" and _PATHY_SEGMENT_RE.search(raw[start - 1]):
            continue
        candidate = str(match.group("path") or "").strip().rstrip(".,;:)]}>")
        if candidate and candidate not in seen and _looks_like_local_file_ref(candidate):
            seen.add(candidate)
            refs.append(candidate)
    for token in re.split(r"\s+", raw):
        candidate = str(token or "").strip().strip("'\"`()[]{}<>").rstrip(".,;:")
        if not candidate or candidate in seen:
            continue
        if not _looks_like_pathish_token(candidate):
            continue
        suffix = Path(candidate).suffix.lower()
        if suffix and suffix in _ATTACHMENT_SUFFIXES:
            seen.add(candidate)
            refs.append(candidate)
    return refs


def _purpose(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    raw = value.get("purpose")
    if not isinstance(raw, str):
        return ""
    return raw.strip().lower()


def detect_missing_attachment_contract(
    *,
    kind: str,
    input_obj: dict[str, Any] | None,
    params_obj: dict[str, Any] | None,
) -> dict[str, Any] | None:
    input_dict = dict(input_obj or {})
    params_dict = dict(params_obj or {})
    file_paths = input_dict.get("file_paths")
    if isinstance(file_paths, list) and any(str(item).strip() for item in file_paths):
        return None

    text_parts: list[str] = []
    for key in ("question", "prompt"):
        value = input_dict.get(key)
        if isinstance(value, str) and value.strip():
            text_parts.append(value)
    if not text_parts:
        return None

    text = "\n".join(text_parts)
    refs = _local_file_refs(text)
    if not refs:
        return None

    reasons = ["local_file_reference_without_file_paths"]
    purpose = _purpose(params_dict)
    high_risk = bool(_HIGH_RISK_VERB_RE.search(text) and (_HIGH_RISK_OBJECT_RE.search(text) or _HIGH_RISK_LOCAL_RE.search(text)))
    if purpose in _PURPOSE_HIGH_RISK:
        reasons.append(f"purpose:{purpose}")
        high_risk = True

    return {
        "family_id": "attachment_contract_missing",
        "family_label": "Attachment contract missing",
        "kind": str(kind or "").strip(),
        "high_risk": bool(high_risk),
        "reasons": reasons,
        "purpose": purpose or None,
        "local_file_refs": refs[:8],
        "question_preview": _compact_preview(input_dict.get("question")),
        "prompt_preview": _compact_preview(input_dict.get("prompt")),
    }


def attachment_contract_missing_message(signal: dict[str, Any]) -> str:
    refs = [str(item) for item in list(signal.get("local_file_refs") or []) if str(item).strip()]
    ref_preview = ", ".join(refs[:3])
    reason = "request references local files but does not declare input.file_paths"
    if ref_preview:
        reason = f"{reason}: {ref_preview}"
    return (
        "Attachment contract missing: "
        f"{reason}. Pass the files explicitly via input.file_paths instead of relying on prompt text alone."
    )
