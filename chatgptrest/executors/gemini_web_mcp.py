from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import signal
import subprocess
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

from chatgptrest.core.attachment_contract import (
    attachment_contract_missing_message,
    detect_missing_attachment_contract,
)
from chatgptrest.driver.api import ToolCaller
from chatgptrest.driver.backends.mcp_http import McpHttpToolCaller
from chatgptrest.executors.base import BaseExecutor, ExecutorResult
from chatgpt_web_mcp.runtime.answer_classification import _classify_deep_research_answer
from chatgptrest.executors.config import GeminiExecutorConfig

_cfg = GeminiExecutorConfig()


@dataclass(frozen=True)
class GeminiWebJobParams:
    preset: str
    send_timeout_seconds: int
    wait_timeout_seconds: int
    min_chars: int
    max_wait_seconds: int
    answer_format: str
    phase: str


def _now() -> float:
    return time.time()


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _normalize_phase(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"send", "wait"}:
        return raw
    if raw in {"all", "full", "both"}:
        return "full"
    return "full"


def _normalize_preset(value: Any) -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[\\s\\-]+", "_", raw).strip("_")
    # Policy: disallow Gemini's "Thinking" mode; normalize to Pro.
    if raw in {"pro_thinking", "prothinking", "thinking"}:
        return "pro"
    if raw in {"pro"}:
        return "pro"
    if raw in {"deep_think", "deepthink", "pro_deep_think", "prodeepthink"}:
        # Gemini Ultra feature (Tools drawer): Pro + Deep Think.
        return "deep_think"
    if raw in {"auto", "default", "defaults"}:
        return "pro"
    # Compatibility: treat common ChatGPT preset names as Gemini Pro.
    if raw in {"pro_extended", "thinking_heavy", "thinking_extended", "gemini_pro"}:
        return "pro"
    return raw or "pro"


def _tool_for_preset(preset: str) -> str:
    p = _normalize_preset(preset)
    if p == "deep_think":
        return "gemini_web_ask_pro_deep_think"
    # Default to Pro (never rely on the user's last-selected Gemini mode, which could be Fast/Thinking).
    return "gemini_web_ask_pro"


def _truthy_env(name: str, default: bool) -> bool:
    # Legacy compat — new code should use _cfg properties directly.
    raw = os.environ.get(name)
    if raw is None:
        return default
    val = str(raw).strip().lower()
    if not val:
        return default
    return val in {"1", "true", "yes", "y", "on"}


def _gemini_deep_research_auto_followup_prompt(_last_assistant_text: str) -> str:
    return (
        "OK\n\n"
        "请按我最初的提问直接开始 Deep Research 并输出完整报告。"
        "若存在信息缺口，请做最小合理假设并在报告中明确标注（含不确定性和需我确认清单），不要再反问。"
    )


_GEMINI_TEXT_BUNDLE_ALLOWED_SUFFIXES: frozenset[str] = frozenset(
    {
        ".txt",
        ".md",
        ".markdown",
        ".rst",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".csv",
        ".tsv",
        ".xml",
        ".html",
        ".htm",
        ".css",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".py",
        ".java",
        ".go",
        ".rs",
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".hpp",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
        ".php",
        ".rb",
        ".kt",
        ".swift",
        ".sql",
        ".log",
        ".patch",
        ".diff",
    }
)

_GEMINI_TEXT_BUNDLE_CODE_FENCE_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".ps1": "powershell",
    ".md": "markdown",
    ".markdown": "markdown",
    ".patch": "diff",
    ".diff": "diff",
}

_GEMINI_DEEP_RESEARCH_TOOL_RE = re.compile(
    r"(Deep\s*Research|深入研究|深度研究|深入調研|深度調研|深入调研|深度调研)",
    re.I,
)


def _gemini_max_files_per_prompt() -> int:
    return max(1, min(_cfg.max_files_per_prompt, 50))


def _gemini_attachment_preprocess_enabled() -> bool:
    return _cfg.attachment_preprocess_enabled


def _gemini_deep_research_expand_zip_enabled() -> bool:
    return _cfg.deep_research_expand_zip


def _gemini_expand_zip_always() -> bool:
    """Return True if .zip attachments should be expanded for ALL Gemini
    requests, not just deep_research.  This avoids the Drive-picker failure
    where raw .zip files upload successfully but Gemini UI cannot attach them."""
    return _cfg.expand_zip_always


def _gemini_deep_research_self_check_enabled() -> bool:
    return _cfg.deep_research_self_check


def _gemini_deep_research_self_check_timeout_seconds() -> int:
    return max(10, min(_cfg.deep_research_self_check_timeout_seconds, 180))


def _gemini_send_max_retries() -> int:
    return max(0, min(_cfg.send_max_retries, 30))


def _gemini_send_retry_delay() -> float:
    return max(1.0, min(_cfg.send_retry_delay, 30.0))


_TRANSIENT_DRIVER_ERROR_PATTERNS: list[str] = [
    "targetclosederror",
    "browser has been closed",
    "browser not launched",
    "navigation timeout",
    "connection refused",
    "net::err_",
    "execution context was destroyed",
    "session closed",
    "target closed",
    "page.goto: timeout",
    "frame was detached",
    "context was destroyed",
    "browser.newpage",
    "econnrefused",
    "epipe",
    "econnreset",
]


def _is_transient_driver_error(result: dict) -> bool:
    """Check if a driver result indicates a transient error worth retrying."""
    status = str(result.get("status") or "").strip().lower()
    if status not in {"error", "blocked"}:
        return False
    error = str(result.get("error") or "").lower()
    error_type = str(result.get("error_type") or "").lower()
    combined = f"{error_type} {error}"
    return any(p in combined for p in _TRANSIENT_DRIVER_ERROR_PATTERNS)


def _gemini_zip_expand_max_members() -> int:
    return max(20, min(_cfg.zip_expand_max_members, 2000))


def _gemini_bundle_per_file_max_bytes() -> int:
    return max(8_000, min(_cfg.bundle_per_file_max_bytes, 2_000_000))


def _gemini_bundle_max_bytes() -> int:
    return max(100_000, min(_cfg.bundle_max_bytes, 50_000_000))


def _gemini_attachment_preprocess_dir() -> Path:
    return Path(_cfg.attachment_preprocess_dir).expanduser()


def _safe_zip_member_relpath(name: str) -> str | None:
    raw = str(name or "").replace("\\", "/").strip("/")
    if not raw:
        return None
    parts = [p for p in raw.split("/") if p and p not in {".", ".."}]
    if not parts:
        return None
    return "/".join(parts)


def _looks_binary_blob(data: bytes) -> bool:
    if not data:
        return False
    return b"\x00" in data


def _read_text_snippet_from_file(path: Path, *, max_bytes: int) -> tuple[str | None, str]:
    suffix = path.suffix.lower()
    if suffix not in _GEMINI_TEXT_BUNDLE_ALLOWED_SUFFIXES:
        return None, "unsupported_suffix"
    try:
        payload = path.read_bytes()[: int(max_bytes)]
    except Exception:
        return None, "read_failed"
    if _looks_binary_blob(payload):
        return None, "binary_detected"
    try:
        text = payload.decode("utf-8", errors="replace").strip()
    except Exception:
        return None, "decode_failed"
    if not text:
        return None, "empty_text"
    return text, "ok"


def _render_gemini_bundle_section(*, source_name: str, member_path: str, content: str, suffix: str) -> str:
    lang = _GEMINI_TEXT_BUNDLE_CODE_FENCE_LANG.get(str(suffix or "").lower(), "")
    fence = f"```{lang}".rstrip()
    return (
        f"## {source_name} :: {member_path}\n\n"
        f"{fence}\n"
        f"{content.rstrip()}\n"
        "```\n\n"
    )


def _gemini_has_deep_research_tool_surface(payload: dict[str, Any]) -> bool:
    tools = payload.get("tools")
    if not isinstance(tools, list):
        return False
    for item in tools:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if text and _GEMINI_DEEP_RESEARCH_TOOL_RE.search(text):
            return True
    return False


def _prepare_gemini_file_paths_for_upload(
    *,
    job_id: str,
    file_paths: list[str],
    deep_research: bool,
) -> tuple[list[str], dict[str, Any]]:
    max_files = _gemini_max_files_per_prompt()
    per_file_max_bytes = _gemini_bundle_per_file_max_bytes()
    bundle_max_bytes = _gemini_bundle_max_bytes()
    zip_max_members = _gemini_zip_expand_max_members()
    collapse_multi_text_inputs = len(list(file_paths or [])) > 1
    preprocess_dir = _gemini_attachment_preprocess_dir() / str(job_id or "unknown")
    preprocess_dir.mkdir(parents=True, exist_ok=True)

    uniq: list[str] = []
    seen: set[str] = set()
    for raw in list(file_paths or []):
        s = str(raw or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        uniq.append(s)

    included_sections: list[str] = []
    included_entries: list[dict[str, Any]] = []
    skipped_entries: list[dict[str, Any]] = []
    zip_expanded_names: list[str] = []
    collapsed_text_names: list[str] = []
    passthrough: list[str] = []
    bundle_bytes = 0

    for raw in uniq:
        p = Path(raw)
        should_expand_zip = (
            (deep_research and _gemini_deep_research_expand_zip_enabled())
            or _gemini_expand_zip_always()
        )
        if should_expand_zip and raw.lower().endswith(".zip"):
            if not p.exists():
                passthrough.append(raw)
                skipped_entries.append({"source": p.name, "member": "", "reason": "zip_missing_keep_original"})
                continue
            included_for_zip = 0
            try:
                with zipfile.ZipFile(p, "r") as zf:
                    infos = zf.infolist()
                    for idx, info in enumerate(infos):
                        if idx >= zip_max_members:
                            skipped_entries.append({"source": p.name, "member": "...", "reason": "zip_members_cap"})
                            break
                        if getattr(info, "is_dir", lambda: False)():
                            continue
                        rel = _safe_zip_member_relpath(str(getattr(info, "filename", "") or ""))
                        if not rel:
                            skipped_entries.append({"source": p.name, "member": str(getattr(info, "filename", "") or ""), "reason": "unsafe_path"})
                            continue
                        suffix = Path(rel).suffix.lower()
                        if suffix not in _GEMINI_TEXT_BUNDLE_ALLOWED_SUFFIXES:
                            skipped_entries.append({"source": p.name, "member": rel, "reason": "unsupported_suffix"})
                            continue
                        try:
                            blob = zf.read(info)
                        except Exception:
                            skipped_entries.append({"source": p.name, "member": rel, "reason": "zip_read_failed"})
                            continue
                        if _looks_binary_blob(blob):
                            skipped_entries.append({"source": p.name, "member": rel, "reason": "binary_detected"})
                            continue
                        text = blob[: int(per_file_max_bytes)].decode("utf-8", errors="replace").strip()
                        if not text:
                            skipped_entries.append({"source": p.name, "member": rel, "reason": "empty_text"})
                            continue
                        section = _render_gemini_bundle_section(
                            source_name=p.name,
                            member_path=rel,
                            content=text,
                            suffix=suffix,
                        )
                        section_bytes = len(section.encode("utf-8", errors="replace"))
                        if bundle_bytes + section_bytes > bundle_max_bytes:
                            skipped_entries.append({"source": p.name, "member": rel, "reason": "bundle_size_cap"})
                            continue
                        included_sections.append(section)
                        bundle_bytes += section_bytes
                        included_for_zip += 1
                        included_entries.append({"source": p.name, "member": rel})
            except Exception:
                skipped_entries.append({"source": p.name, "member": "", "reason": "zip_open_failed_keep_original"})
                passthrough.append(raw)
                continue
            if included_for_zip > 0:
                zip_expanded_names.append(p.name)
                continue
            # Keep the original zip as a fallback when no readable text could be extracted.
            passthrough.append(raw)
            skipped_entries.append({"source": p.name, "member": "", "reason": "zip_bundle_empty_keep_original"})
            continue

        if collapse_multi_text_inputs:
            text, reason = _read_text_snippet_from_file(p, max_bytes=per_file_max_bytes)
            if text:
                section = _render_gemini_bundle_section(
                    source_name=p.name,
                    member_path=p.name,
                    content=text,
                    suffix=p.suffix.lower(),
                )
                section_bytes = len(section.encode("utf-8", errors="replace"))
                if bundle_bytes + section_bytes <= bundle_max_bytes:
                    included_sections.append(section)
                    bundle_bytes += section_bytes
                    collapsed_text_names.append(p.name)
                    included_entries.append({"source": p.name, "member": p.name})
                    continue
                skipped_entries.append({"source": p.name, "member": p.name, "reason": "bundle_size_cap_keep_original"})
            elif reason != "unsupported_suffix":
                skipped_entries.append({"source": p.name, "member": p.name, "reason": f"bundle_{reason}_keep_original"})
        passthrough.append(raw)

    dropped_paths: list[str] = []
    overflow_archived: list[str] = []
    generated_files: list[str] = []

    need_bundle = bool(included_sections)
    working = list(passthrough)

    if len(working) > max_files:
        overflow = working[max_files:]
        working = working[:max_files]
        if deep_research:
            need_bundle = True
            for raw in overflow:
                p = Path(raw)
                text, reason = _read_text_snippet_from_file(p, max_bytes=per_file_max_bytes)
                if text:
                    section = _render_gemini_bundle_section(
                        source_name=p.name,
                        member_path=p.name,
                        content=text,
                        suffix=p.suffix.lower(),
                    )
                    section_bytes = len(section.encode("utf-8", errors="replace"))
                    if bundle_bytes + section_bytes <= bundle_max_bytes:
                        included_sections.append(section)
                        bundle_bytes += section_bytes
                        included_entries.append({"source": p.name, "member": p.name})
                        continue
                skipped_entries.append({"source": p.name, "member": p.name, "reason": f"overflow_{reason}"})
                dropped_paths.append(raw)
        else:
            overflow_zip_path = preprocess_dir / "GEMINI_ATTACH_OVERFLOW.zip"
            try:
                with zipfile.ZipFile(overflow_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for idx, raw in enumerate(overflow, start=1):
                        p = Path(raw)
                        if not p.exists() or not p.is_file():
                            dropped_paths.append(raw)
                            continue
                        arcname = f"{idx:03d}_{p.name}"
                        zf.write(p, arcname=arcname)
                        overflow_archived.append(raw)
                if overflow_archived:
                    if len(working) >= max_files:
                        dropped_paths.extend(working[max_files - 1 :])
                        working = working[: max_files - 1]
                    working.append(overflow_zip_path.as_posix())
                    generated_files.append(overflow_zip_path.as_posix())
                else:
                    dropped_paths.extend(overflow)
            except Exception:
                dropped_paths.extend(overflow)

    if need_bundle:
        bundle_path = preprocess_dir / "GEMINI_ATTACH_BUNDLE.md"
        if not included_sections:
            included_sections.append(
                "## Bundle note\n\nNo readable text fragments could be merged. "
                "Refer to `GEMINI_ATTACH_INDEX.md` for file inventory.\n\n"
            )
        header = (
            "# Gemini Attachment Bundle (auto-generated)\n\n"
            "This file is generated by ChatgptREST to reduce attachment count and preserve readable context.\n\n"
        )
        bundle_path.write_text(header + "".join(included_sections), encoding="utf-8", errors="replace")
        if len(working) >= max_files:
            dropped_paths.extend(working[max_files - 1 :])
            working = working[: max_files - 1]
        working.append(bundle_path.as_posix())
        generated_files.append(bundle_path.as_posix())

    need_index = bool(deep_research or len(uniq) > max_files or skipped_entries or dropped_paths or zip_expanded_names)
    if need_index:
        index_path = preprocess_dir / "GEMINI_ATTACH_INDEX.md"
        lines: list[str] = []
        lines.append("# Gemini Attachment Index (auto-generated)")
        lines.append("")
        lines.append(f"- requested_files: `{len(uniq)}`")
        lines.append(f"- upload_limit: `{max_files}`")
        lines.append(f"- deep_research: `{bool(deep_research)}`")
        if zip_expanded_names:
            lines.append(f"- zip_expanded: `{', '.join(zip_expanded_names)}`")
        if overflow_archived:
            lines.append(f"- overflow_archived_count: `{len(overflow_archived)}`")
        lines.append("")
        lines.append("## Requested")
        for raw in uniq:
            lines.append(f"- {Path(raw).name}")
        lines.append("")
        lines.append("## Uploaded")
        preview_uploaded = list(working)
        if len(preview_uploaded) >= max_files:
            preview_uploaded = preview_uploaded[: max_files - 1]
        preview_uploaded.append(index_path.as_posix())
        for raw in preview_uploaded:
            lines.append(f"- {Path(raw).name}")
        if dropped_paths:
            lines.append("")
            lines.append("## Dropped")
            for raw in dropped_paths:
                lines.append(f"- {Path(raw).name}")
        if skipped_entries:
            lines.append("")
            lines.append("## Skipped Details")
            for item in skipped_entries[:200]:
                lines.append(
                    f"- {item.get('source')}"
                    f"{(' :: ' + str(item.get('member') or '')) if item.get('member') else ''}"
                    f" reason={item.get('reason')}"
                )
        index_path.write_text("\n".join(lines) + "\n", encoding="utf-8", errors="replace")
        if len(working) >= max_files:
            dropped_paths.extend(working[max_files - 1 :])
            working = working[: max_files - 1]
        working.append(index_path.as_posix())
        generated_files.append(index_path.as_posix())

    final_paths = list(working[:max_files])
    if len(working) > max_files:
        dropped_paths.extend(working[max_files:])

    info = {
        "enabled": True,
        "deep_research": bool(deep_research),
        "max_files_per_prompt": int(max_files),
        "requested_count": int(len(uniq)),
        "uploaded_count": int(len(final_paths)),
        "zip_expanded_count": int(len(zip_expanded_names)),
        "collapsed_text_count": int(len(collapsed_text_names)),
        "generated_file_count": int(len(generated_files)),
        "dropped_count": int(len(dropped_paths)),
        "zip_expanded": zip_expanded_names[:30],
        "collapsed_text": collapsed_text_names[:30],
        "generated_files": [Path(p).name for p in generated_files[:30]],
        "dropped_files": [Path(p).name for p in dropped_paths[:30]],
    }
    return final_paths, info


_GEMINI_DEEP_THINK_OVERLOADED_RE = re.compile(
    r"("
    r"a lot of people are using deep think right now|"
    r"unselect it from your tools|"
    r"try again in a bit|"
    r"deep think is busy|"
    r"deep think is currently unavailable"
    r")",
    re.I,
)

_GEMINI_DEEP_THINK_UNAVAILABLE_RE = re.compile(
    r"("
    r"gemini tool not found:.*deep\s*think|"
    r"geminideepthinktoolnotfound|"
    r"deep think.*did not apply|"
    r"gemini tool switch did not apply.*deep"
    r")",
    re.I,
)

_GEMINI_UI_NOISE_MARKER_RE = re.compile(
    r"("
    r"設定和幫助|设置和帮助|"
    r"與gemini對話|与gemini对话|"
    r"你说|你說|"
    r"显示思路|顯示思路|"
    r"gemini\s*说|gemini\s*說|"
    r"tools|工具"
    r")",
    re.I,
)

_GEMINI_UI_ANSWER_ANCHOR_RE = re.compile(r"^\s*(?:显示思路|顯示思路|gemini\s*说|gemini\s*說)\s*$", re.I)

_GEMINI_SEMANTIC_NEXT_OWNER_PM_RE = re.compile(
    r"("
    r"owner\s*[:：]\s*reqmgr\s*[-=]>\s*next_owner\s*[:：]\s*pm|"
    r"\"next_owner\"\s*:\s*\"pm(?:[:_a-z0-9-]+)?\""
    r")",
    re.I,
)

_GEMINI_SEMANTIC_NEXT_OWNER_REQMGR_RE = re.compile(
    r"("
    r"\"next_owner\"\s*:\s*\"reqmgr(?:[:_a-z0-9-]+)?\"|"
    r"next_owner\s*[:：]\s*reqmgr"
    r")",
    re.I,
)


def _looks_like_gemini_deep_think_overloaded(text: str) -> bool:
    trimmed = (text or "").strip()
    if not trimmed:
        return False
    if len(trimmed) > 900:
        return False
    if _GEMINI_DEEP_THINK_OVERLOADED_RE.search(trimmed):
        return True
    _RETRY_TOKENS_CJK = ("很多人", "人太多", "拥挤", "稍后", "一会儿", "再试", "重试", "大量")
    # Best-effort CJK variants (exact "深度思考").
    if "深度思考" in trimmed and any(tok in trimmed for tok in _RETRY_TOKENS_CJK):
        return True
    # Mixed CN/EN: Gemini may return "大量用户正在使用 Deep Think ... 请稍后再试"
    if re.search(r"deep\s*think", trimmed, re.I) and any(tok in trimmed for tok in _RETRY_TOKENS_CJK):
        return True
    # Fuzzy CJK: "深度的思考", "深度 思考" etc. (particle insertion)
    if re.search(r"深度.{0,2}思考", trimmed) and any(tok in trimmed for tok in _RETRY_TOKENS_CJK):
        return True
    return False


def _looks_like_gemini_deep_think_unavailable(*, error_type: str, error_text: str) -> bool:
    et = str(error_type or "").strip().lower()
    txt = str(error_text or "").strip()
    if et in {"geminideepthinktoolnotfound", "geminideepthinkdidnotapply"}:
        return True
    if not txt:
        return False
    return bool(_GEMINI_DEEP_THINK_UNAVAILABLE_RE.search(txt))


def _gemini_answer_quality_guard_enabled() -> bool:
    return _cfg.answer_quality_guard


def _gemini_answer_quality_semantic_strict() -> bool:
    return _cfg.semantic_consistency_guard


def _gemini_answer_quality_retry_after_seconds() -> int:
    return max(30, min(int(_cfg.answer_quality_retry_after_seconds), 1800))


def _gemini_strip_ui_noise_prefix(answer: str) -> tuple[str, dict[str, Any]]:
    text = str(answer or "")
    lines = text.splitlines()
    if not lines:
        return text, {"ui_noise_detected": False, "ui_noise_sanitized": False}

    scan_limit = min(len(lines), 220)
    marker_positions: list[int] = []
    for idx in range(scan_limit):
        line = lines[idx].strip()
        if not line:
            continue
        if _GEMINI_UI_NOISE_MARKER_RE.search(line):
            marker_positions.append(idx)

    if not marker_positions:
        return text, {"ui_noise_detected": False, "ui_noise_sanitized": False}

    cut_idx: int | None = None
    ui_anchor_line: int | None = None
    first_marker = marker_positions[0]
    for idx in range(first_marker, scan_limit):
        line = lines[idx].strip()
        if _GEMINI_UI_ANSWER_ANCHOR_RE.search(line):
            cut_idx = idx + 1
            while cut_idx < scan_limit and _GEMINI_UI_ANSWER_ANCHOR_RE.search(lines[cut_idx].strip()):
                cut_idx += 1
            ui_anchor_line = idx + 1
            break

    # Fallback: if we observed Gemini UI markers, cut at a common answer-leading sentence pattern.
    if cut_idx is None:
        for idx in range(first_marker, scan_limit):
            line = lines[idx].strip()
            if re.match(r"^(作为|As\s+an?\b)", line, re.I):
                cut_idx = idx
                ui_anchor_line = idx + 1
                break

    if cut_idx is None:
        return text, {
            "ui_noise_detected": True,
            "ui_noise_sanitized": False,
            "ui_noise_prefix_lines": 0,
            "ui_marker_count": len(marker_positions),
            "ui_anchor_line": None,
        }

    prefix_non_empty = [ln for ln in lines[:cut_idx] if ln.strip()]
    cleaned_lines = lines[cut_idx:]
    while cleaned_lines and (not cleaned_lines[0].strip()):
        cleaned_lines.pop(0)
    cleaned = "\n".join(cleaned_lines).strip()
    if not cleaned:
        return "", {
            "ui_noise_detected": True,
            "ui_noise_sanitized": False,
            "ui_noise_prefix_lines": len(prefix_non_empty),
            "ui_marker_count": len(marker_positions),
            "ui_anchor_line": ui_anchor_line,
            "ui_noise_empty_after_sanitize": True,
        }

    return cleaned, {
        "ui_noise_detected": True,
        "ui_noise_sanitized": True,
        "ui_noise_prefix_lines": len(prefix_non_empty),
        "ui_marker_count": len(marker_positions),
        "ui_anchor_line": ui_anchor_line,
        "ui_noise_prefix_preview": "\n".join(prefix_non_empty[:6])[:300],
    }


def _gemini_semantic_risk_next_owner_mixed(answer: str) -> bool:
    text = str(answer or "")
    if not text:
        return False
    return bool(_GEMINI_SEMANTIC_NEXT_OWNER_PM_RE.search(text) and _GEMINI_SEMANTIC_NEXT_OWNER_REQMGR_RE.search(text))


def _gemini_apply_answer_quality_guard(
    *,
    answer: str,
    preset: str,
    deep_research: bool,
    min_chars: int,
) -> tuple[str, dict[str, Any]]:
    cleaned, strip_info = _gemini_strip_ui_noise_prefix(answer)
    semantic_risk = _gemini_semantic_risk_next_owner_mixed(cleaned)

    guard: dict[str, Any] = {
        "enabled": True,
        "preset": str(preset or ""),
        "deep_research": bool(deep_research),
        "action": ("sanitized" if strip_info.get("ui_noise_sanitized") else ("detected" if strip_info.get("ui_noise_detected") else "none")),
        "ui_noise_detected": bool(strip_info.get("ui_noise_detected")),
        "ui_noise_sanitized": bool(strip_info.get("ui_noise_sanitized")),
        "ui_noise_prefix_lines": int(strip_info.get("ui_noise_prefix_lines") or 0),
        "ui_marker_count": int(strip_info.get("ui_marker_count") or 0),
        "ui_anchor_line": strip_info.get("ui_anchor_line"),
        "semantic_risk_next_owner_mixed": bool(semantic_risk),
        "answer_chars_before": len(str(answer or "").strip()),
        "answer_chars_after": len(str(cleaned or "").strip()),
        "min_chars_requested": max(0, int(min_chars or 0)),
    }
    if strip_info.get("ui_noise_prefix_preview"):
        guard["ui_noise_prefix_preview"] = strip_info.get("ui_noise_prefix_preview")
    if strip_info.get("ui_noise_empty_after_sanitize"):
        guard["ui_noise_empty_after_sanitize"] = True

    status_override = ""
    error_type = ""
    error_text = ""

    if strip_info.get("ui_noise_empty_after_sanitize") or (
        strip_info.get("ui_noise_detected") and (not str(cleaned or "").strip())
    ):
        status_override = "needs_followup"
        error_type = "GeminiAnswerContaminated"
        error_text = "Gemini answer was dominated by UI transcript noise; no usable body after sanitize."

    if semantic_risk:
        guard["semantic_hint"] = (
            "Detected mixed next_owner semantics. Normalize as: pre-freeze next_owner=reqmgr; handoff next_owner=pm."
        )
        if _gemini_answer_quality_semantic_strict():
            status_override = "needs_followup"
            error_type = "GeminiAnswerSemanticConflict"
            error_text = (
                "Gemini answer has mixed next_owner semantics (reqmgr vs pm) without a normalized stage contract."
            )

    if status_override:
        guard["status_override"] = status_override
        guard["error_type"] = error_type or "GeminiAnswerQualityGuard"
        guard["error"] = error_text or "Gemini answer quality guard requested follow-up."

    return cleaned, guard


async def _gemini_try_extract_clean_answer(
    executor: "GeminiWebMcpExecutor",
    *,
    job_id: str,
    conversation_url: str,
    preset: str,
    deep_research: bool,
    min_chars: int,
) -> tuple[str | None, dict[str, Any], dict[str, Any]]:
    extract_res = await executor._run_extract_answer(
        job_id=f"{job_id}:extract_answer",
        input={"conversation_url": conversation_url},
        params={"timeout_seconds": 45},
    )
    recovery: dict[str, Any] = {
        "attempted": True,
        "conversation_url": str(conversation_url),
        "extract_status": str(extract_res.status or ""),
        "extract_error_type": str((extract_res.meta or {}).get("error_type") or ""),
    }
    if extract_res.status != "completed":
        recovery["recovered"] = False
        recovery["error"] = str(extract_res.answer or (extract_res.meta or {}).get("error") or "").strip()
        return None, {}, recovery

    extracted_answer = str(extract_res.answer or "")
    cleaned_answer, guard = _gemini_apply_answer_quality_guard(
        answer=extracted_answer,
        preset=preset,
        deep_research=deep_research,
        min_chars=min_chars,
    )
    recovery["answer_chars_before"] = len(extracted_answer.strip())
    recovery["answer_chars_after"] = len(cleaned_answer.strip())
    status_override = str(guard.get("status_override") or "").strip().lower()
    if status_override in {"in_progress", "needs_followup", "cooldown"} or not cleaned_answer.strip():
        recovery["recovered"] = False
        recovery["guard"] = guard
        return None, guard, recovery

    recovery["recovered"] = True
    return cleaned_answer, guard, recovery


_GEMINI_WAIT_TRANSIENT_ERROR_RE = re.compile(
    r"("
    r"connection refused|"
    r"econnrefused|"
    r"remote disconnected|"
    r"target page, context or browser has been closed|"
    r"closedresourceerror|"
    r"transport send error|"
    r"unexpected content type: none|"
    r"err_connection_closed|"
    r"timed out|"
    r"timeout"
    r")",
    re.I,
)


def _looks_like_wait_transient_error(exc: BaseException | str) -> bool:
    et = ""
    txt = ""
    if isinstance(exc, BaseException):
        et = type(exc).__name__.strip()
        txt = str(exc or "")
    else:
        txt = str(exc or "")
    et_l = et.lower()
    if et_l in {"timeouterror", "connectionerror", "remotedisconnected", "closedresourceerror"}:
        return True
    return bool(_GEMINI_WAIT_TRANSIENT_ERROR_RE.search(txt))


def _gemini_wait_transient_failure_limit() -> int:
    return max(1, min(GeminiExecutorConfig().wait_transient_failure_limit, 8))


def _gemini_wait_transient_retry_after_seconds() -> int:
    return max(5, min(int(GeminiExecutorConfig().wait_transient_retry_after_seconds), 300))


def _gemini_wait_requeue_retry_after_seconds(*, has_thread_url: bool) -> int:
    base = max(30, min(int(_cfg.needs_followup_retry_after_seconds), 1800))
    if has_thread_url:
        return max(180, base)
    return max(30, min(base, 90))


def _gemini_dr_gdoc_fallback_enabled() -> bool:
    return GeminiExecutorConfig().dr_gdoc_fallback_enabled


def _gemini_dr_gdoc_fallback_timeout_seconds() -> int:
    return max(20, min(GeminiExecutorConfig().dr_gdoc_fallback_timeout_seconds, 900))


def _gemini_dr_gdoc_fallback_max_chars() -> int:
    return max(2_000, min(GeminiExecutorConfig().dr_gdoc_fallback_max_chars, 2_000_000))


def _gdrive_mount_dir() -> Path:
    return Path(_cfg.gdrive_mount_dir).expanduser()


def _gdrive_upload_subdir() -> str:
    raw = _cfg.gdrive_upload_subdir
    cleaned = re.sub(r"[^a-zA-Z0-9._/-]+", "_", raw).strip("/")
    return cleaned or "chatgptrest_uploads"


def _gdrive_rclone_remote() -> str:
    raw = _cfg.gdrive_rclone_remote
    if not raw:
        return "gdrive:"
    return raw if raw.endswith(":") else f"{raw}:"


def _rclone_bin() -> str:
    raw = _cfg.rclone_bin
    if raw and raw != "rclone":
        return raw
    # Prefer the common system path to avoid PATH issues in daemonized processes.
    if Path("/usr/bin/rclone").exists():
        return "/usr/bin/rclone"
    return "rclone"


def _drive_url_from_id(file_id: str) -> str:
    fid = str(file_id or "").strip()
    if not fid:
        return ""
    # The Drive picker supports "paste URL" which bypasses name-search indexing delays.
    return f"https://drive.google.com/open?id={fid}"


def _rclone_config_path() -> str | None:
    raw = _cfg.rclone_config
    if raw and Path(raw).expanduser().exists():
        return str(Path(raw).expanduser())

    candidates = [
        Path.home() / ".config" / "rclone" / "rclone.conf",
        Path("/home/yuanhaizhou/.home-codex-official/.config/rclone/rclone.conf"),
    ]
    for p in candidates:
        try:
            if p.exists():
                return str(p)
        except Exception:
            continue
    return None


def _rclone_env() -> dict[str, str]:
    env = dict(os.environ)
    cfg = _rclone_config_path()
    if cfg:
        env.setdefault("RCLONE_CONFIG", cfg)
    # rclone is a Go binary; it typically honors HTTP_PROXY/HTTPS_PROXY/NO_PROXY (not ALL_PROXY).
    # In many setups we only export ALL_PROXY for browsers; bridge it for rclone to avoid Google API timeouts.
    proxy = (env.get("CHATGPTREST_RCLONE_PROXY") or "").strip()
    if proxy:
        # Explicit override: callers expect this to take precedence over inherited proxy vars.
        env["HTTP_PROXY"] = proxy
        env["HTTPS_PROXY"] = proxy
        env["http_proxy"] = proxy
        env["https_proxy"] = proxy
        return env

    all_proxy = (env.get("ALL_PROXY") or env.get("all_proxy") or "").strip()
    if all_proxy:
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            cur = str(env.get(k) or "").strip()
            if not cur:
                env[k] = all_proxy
        return env

    chrome_proxy = (env.get("CHROME_PROXY_SERVER") or "").strip()
    if chrome_proxy:
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            cur = str(env.get(k) or "").strip()
            if not cur:
                env[k] = chrome_proxy
    return env


def _rclone_timeout_seconds() -> float:
    return max(5.0, min(float(_cfg.rclone_timeout_seconds), 120.0))


def _rclone_copyto_timeout_seconds() -> float:
    return max(10.0, min(float(_cfg.rclone_copyto_timeout_seconds), 600.0))


def _rclone_delete_timeout_seconds() -> float:
    return max(5.0, min(float(_cfg.rclone_delete_timeout_seconds), 300.0))


def _rclone_contimeout_seconds() -> float:
    return max(1.0, min(float(_cfg.rclone_contimeout_seconds), 120.0))


def _rclone_io_timeout_seconds() -> float:
    return max(5.0, min(float(_cfg.rclone_io_timeout_seconds), 600.0))


def _rclone_retries() -> int:
    return max(0, min(_cfg.rclone_retries, 10))


def _rclone_low_level_retries() -> int:
    return max(0, min(_cfg.rclone_low_level_retries, 10))


def _rclone_retries_sleep_seconds() -> float:
    return max(0.0, min(_cfg.rclone_retries_sleep_seconds, 30.0))


def _rclone_global_flags() -> list[str]:
    # Keep rclone itself responsive even when upstream networking stalls.
    # Job-level retries are handled by ChatgptREST cooldown/backoff; keep rclone retries low.
    return [
        "--stats",
        "0",
        "--contimeout",
        f"{_rclone_contimeout_seconds()}s",
        "--timeout",
        f"{_rclone_io_timeout_seconds()}s",
        "--retries",
        str(_rclone_retries()),
        "--low-level-retries",
        str(_rclone_low_level_retries()),
        "--retries-sleep",
        f"{_rclone_retries_sleep_seconds()}s",
    ]


def _gdrive_max_file_bytes() -> int:
    val = _cfg.gdrive_max_file_bytes
    return max(0, val) if val else 200 * 1024 * 1024


def _gdrive_cleanup_mode() -> str:
    raw = _cfg.gdrive_cleanup_mode
    if not raw:
        return "never"
    if raw in {"0", "false", "off", "never", "disabled"}:
        return "never"
    if raw in {"on_success", "success", "completed"}:
        return "on_success"
    if raw in {"always", "on_finish", "finish"}:
        return "always"
    return "never"


_RCLONE_RETRYABLE_ERROR_RE = re.compile(
    r"("
    r"\b429\b|too many requests|rate limit|ratelimitexceeded|user rate limit exceeded|"
    r"timeout|timed out|i/o timeout|tls handshake timeout|context deadline exceeded|"
    r"connection reset|connection refused|network is unreachable|no route to host|"
    r"temporary failure|temporarily unavailable|try again|"
    r"\b5\d\d\b|internal error|server error|backend error|"
    r"\b404\b|not found"
    r")",
    re.I,
)
_RCLONE_PERMANENT_ERROR_RE = re.compile(
    r"("
    r"did(n't| not) find section in config file|unknown remote|"
    r"failed to open config file|error reading config file|"
    r"unable to open config file|config file not found|"
    r"invalid credentials|invalid_grant|unauthorized|access denied|"
    r"insufficient permissions|permission denied|forbidden|"
    r"quota exceeded|storage quota|insufficient storage|"
    r"file too large|too large to copy"
    r")",
    re.I,
)


def _classify_rclone_error_kind(*, stdout: str, stderr: str, timed_out: bool) -> str:
    if timed_out:
        return "retryable"
    text = (stderr or stdout or "").strip()
    if not text:
        return "retryable"
    if _RCLONE_PERMANENT_ERROR_RE.search(text):
        # Some "not found" errors are normal during existence checks; treat those as retryable.
        if _RCLONE_RETRYABLE_ERROR_RE.search(text):
            return "retryable"
        return "permanent"
    if _RCLONE_RETRYABLE_ERROR_RE.search(text):
        return "retryable"
    return "retryable"


def _sanitize_drive_filename(name: str) -> str:
    base = str(name or "").strip().replace("/", "_").replace("\\", "_")
    base = re.sub(r"[\u0000-\u001f]+", "_", base)
    base = base.strip("._ ")
    return base or "upload.bin"


def _truncate_log_text(text: str, limit: int = 2000) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    if len(s) <= limit:
        return s
    return f"{s[:limit]}…<truncated {len(s) - limit} chars>"


def _coerce_subprocess_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _rclone_run_raw(args: list[str], *, timeout_seconds: float) -> tuple[dict[str, Any], str, str]:
    env = _rclone_env()
    cmd = [_rclone_bin(), *_rclone_global_flags(), *list(args)]
    started_at = time.time()
    proc: subprocess.Popen[str] | None = None
    proxy_env = {
        "http_proxy": bool((env.get("HTTP_PROXY") or env.get("http_proxy") or "").strip()),
        "https_proxy": bool((env.get("HTTPS_PROXY") or env.get("https_proxy") or "").strip()),
        "all_proxy": bool((env.get("ALL_PROXY") or env.get("all_proxy") or "").strip()),
        "no_proxy": bool((env.get("NO_PROXY") or env.get("no_proxy") or "").strip()),
    }
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=True,
        )
        stdout, stderr = proc.communicate(timeout=float(timeout_seconds))
        ok = proc.returncode == 0
        err = ""
        if not ok:
            err = (stderr or stdout or "").strip() or f"rclone exited {proc.returncode}"
        meta = {
            "cmd": cmd,
            "timeout_seconds": float(timeout_seconds),
            "elapsed_seconds": round(time.time() - started_at, 3),
            "returncode": int(proc.returncode),
            "timed_out": False,
            "ok": bool(ok),
            "error": _truncate_log_text(err) if err else "",
            "stdout": _truncate_log_text(stdout),
            "stderr": _truncate_log_text(stderr),
            "rclone_config": str(env.get("RCLONE_CONFIG") or "").strip(),
            "proxy_env": proxy_env,
        }
        return meta, stdout, stderr
    except subprocess.TimeoutExpired as exc:
        stdout = _coerce_subprocess_text(getattr(exc, "stdout", None))
        stderr = _coerce_subprocess_text(getattr(exc, "stderr", None))
        killed_process_group = False
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
                killed_process_group = True
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                out2, err2 = proc.communicate(timeout=5.0)
                stdout = stdout or (out2 or "")
                stderr = stderr or (err2 or "")
            except Exception:
                pass
        err = (stderr or stdout or "").strip()
        if not err:
            err = f"rclone timed out after {timeout_seconds}s"
        meta = {
            "cmd": cmd,
            "timeout_seconds": float(timeout_seconds),
            "elapsed_seconds": round(time.time() - started_at, 3),
            "returncode": None,
            "timed_out": True,
            "ok": False,
            "error": _truncate_log_text(err),
            "stdout": _truncate_log_text(stdout),
            "stderr": _truncate_log_text(stderr),
            "rclone_config": str(env.get("RCLONE_CONFIG") or "").strip(),
            "killed_process_group": bool(killed_process_group),
            "proxy_env": proxy_env,
        }
        return meta, stdout, stderr
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass
        meta = {
            "cmd": cmd,
            "timeout_seconds": float(timeout_seconds),
            "elapsed_seconds": round(time.time() - started_at, 3),
            "returncode": None,
            "timed_out": False,
            "ok": False,
            "error": _truncate_log_text(err),
            "stdout": "",
            "stderr": "",
            "rclone_config": str(env.get("RCLONE_CONFIG") or "").strip(),
            "proxy_env": proxy_env,
        }
        return meta, "", ""


def _rclone_lsjson_with_meta(remote_path: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    meta, stdout, stderr = _rclone_run_raw(
        ["lsjson", "--stat", "--no-mimetype", "--no-modtime", remote_path],
        timeout_seconds=_rclone_timeout_seconds(),
    )
    meta["remote_path"] = remote_path
    if meta.get("timed_out") or meta.get("returncode") != 0:
        err = (stderr or stdout or "").strip()
        if meta.get("timed_out"):
            meta["error"] = f"rclone lsjson timed out after {meta.get('timeout_seconds')}s"
        else:
            meta["error"] = _truncate_log_text(err or f"rclone lsjson failed (exit={meta.get('returncode')})")
        meta["error_kind"] = _classify_rclone_error_kind(
            stdout=stdout,
            stderr=stderr,
            timed_out=bool(meta.get("timed_out")),
        )
        return [], meta

    try:
        data = json.loads(stdout or "[]")
    except Exception as exc:
        meta["error"] = f"Failed to parse rclone lsjson output ({type(exc).__name__}: {exc})"
        return [], meta

    if isinstance(data, dict):
        return [data], meta
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)], meta
    meta["error"] = "Unexpected rclone lsjson output type"
    return [], meta


def _gdrive_extract_existing_id(*, remote_path: str) -> tuple[str, dict[str, Any]]:
    items, meta = _rclone_lsjson_with_meta(remote_path)
    if not items:
        return "", meta
    item = items[0]
    drive_id = str(item.get("ID") or "").strip()
    if drive_id:
        return drive_id, meta
    for k in ("Id", "id", "fileId", "file_id"):
        v = str(item.get(k) or "").strip()
        if v:
            return v, meta
    return "", meta


def _gdrive_wait_for_id(
    *,
    remote_path: str,
    expected_size_bytes: int | None,  # noqa: ARG001
    timeout_seconds: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, int, str | None]:
    deadline = time.time() + max(1.0, float(timeout_seconds))
    attempts = 0
    last_meta: dict[str, Any] | None = None
    last_error: str | None = None

    while time.time() < deadline:
        attempts += 1
        items, meta = _rclone_lsjson_with_meta(remote_path)
        last_meta = meta
        if items:
            item = items[0]
            drive_id = str(item.get("ID") or "").strip()
            if drive_id:
                return item, meta, attempts, None
        err = str(meta.get("error") or "").strip()
        if err:
            last_error = err
        if bool(meta.get("timed_out")):
            break
        if str(meta.get("error_kind") or "").strip() == "permanent":
            break
        time.sleep(1.0)

    return None, last_meta, attempts, last_error


_RCLONE_NOT_FOUND_RE = re.compile(r"(\b404\b|not found|file not found|object not found)", re.I)


def _gdrive_build_remote_path(*, job_id: str, index: int, src_path: str) -> tuple[str, str]:
    subdir = _gdrive_upload_subdir()
    remote_root = _gdrive_rclone_remote()
    remote_subdir = subdir.strip("/")
    base = _sanitize_drive_filename(Path(src_path).name)
    dest_name = f"{job_id}_{index:02d}_{base}"
    remote_path = f"{remote_root}{remote_subdir}/{dest_name}" if remote_subdir else f"{remote_root}{dest_name}"
    return dest_name, remote_path


def _gdrive_cleanup_uploaded_files(*, job_id: str, file_paths: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for idx, raw in enumerate(list(file_paths)):
        src_path = str(raw)
        drive_name, remote_path = _gdrive_build_remote_path(job_id=job_id, index=idx + 1, src_path=src_path)
        meta, _stdout, _stderr = _rclone_run_raw(["deletefile", remote_path], timeout_seconds=_rclone_delete_timeout_seconds())
        ok = bool(meta.get("ok"))
        not_found = False
        if not ok:
            err = str(meta.get("error") or "")
            if _RCLONE_NOT_FOUND_RE.search(err):
                ok = True
                not_found = True
        meta["ok"] = bool(ok)
        meta["not_found"] = bool(not_found)
        if not ok:
            meta["error_kind"] = _classify_rclone_error_kind(
                stdout=str(meta.get("stdout") or ""),
                stderr=str(meta.get("stderr") or ""),
                timed_out=bool(meta.get("timed_out")),
            )
        results.append({"src_path": src_path, "drive_name": drive_name, "drive_remote_path": remote_path, "rclone_deletefile": meta})
    return results


def _upload_files_to_gdrive(*, job_id: str, file_paths: list[str]) -> list[dict[str, Any]]:
    max_file_bytes = _gdrive_max_file_bytes()
    sync_timeout_seconds = max(5, min(_cfg.gdrive_sync_timeout_seconds, 300))

    uploads: list[dict[str, Any]] = []
    stopped: dict[str, Any] | None = None
    for idx, raw in enumerate(list(file_paths)):
        src = Path(str(raw)).expanduser()
        dest_name, remote_path = _gdrive_build_remote_path(job_id=job_id, index=idx + 1, src_path=str(src))
        if stopped is not None:
            uploads.append(
                {
                    "src_path": str(src),
                    "drive_name": dest_name,
                    "drive_remote_path": remote_path,
                    "drive_id": "",
                    "drive_url": "",
                    "drive_resolve_error": f"SkippedDueToPreviousDriveUploadFailure: {stopped.get('error') or 'unknown'}",
                    "drive_error_kind": str(stopped.get("error_kind") or "retryable"),
                    "upload_completed": False,
                    "size_bytes": None,
                    "expected_size_bytes": None,
                    "rclone_copyto": None,
                    "rclone_lsjson_existing": None,
                    "rclone_lsjson_wait": None,
                    "rclone_lsjson_wait_attempts": None,
                }
            )
            continue
        if not src.exists():
            uploads.append(
                {
                    "src_path": str(src),
                    "drive_name": dest_name,
                    "drive_remote_path": remote_path,
                    "drive_id": "",
                    "drive_url": "",
                    "drive_resolve_error": f"InputFileNotFound: {src}",
                    "drive_error_kind": "permanent",
                    "upload_completed": False,
                    "size_bytes": None,
                    "expected_size_bytes": None,
                    "rclone_copyto": None,
                    "rclone_lsjson_existing": None,
                    "rclone_lsjson_wait": None,
                    "rclone_lsjson_wait_attempts": None,
                }
            )
            continue
        if not src.is_file():
            uploads.append(
                {
                    "src_path": str(src),
                    "drive_name": dest_name,
                    "drive_remote_path": remote_path,
                    "drive_id": "",
                    "drive_url": "",
                    "drive_resolve_error": f"InputPathNotAFile: {src}",
                    "drive_error_kind": "permanent",
                    "upload_completed": False,
                    "size_bytes": None,
                    "expected_size_bytes": None,
                    "rclone_copyto": None,
                    "rclone_lsjson_existing": None,
                    "rclone_lsjson_wait": None,
                    "rclone_lsjson_wait_attempts": None,
                }
            )
            continue

        src_path = str(src)
        try:
            expected_size_bytes = int(src.stat().st_size)
        except Exception:
            expected_size_bytes = None

        drive_id = ""
        drive_url = ""
        drive_resolve_error: str | None = None
        drive_error_kind = ""
        upload_completed = False
        copy_meta: dict[str, Any] | None = None
        lsjson_existing_meta: dict[str, Any] | None = None
        lsjson_wait_meta: dict[str, Any] | None = None
        lsjson_wait_attempts: int | None = None

        try:
            if max_file_bytes > 0 and expected_size_bytes is not None and expected_size_bytes > max_file_bytes:
                raise RuntimeError(
                    f"FileTooLarge: {expected_size_bytes} bytes > CHATGPTREST_GDRIVE_MAX_FILE_BYTES={max_file_bytes} ({src_path})"
                )

            # Retry runs may see the same job_id again; if the file already exists in Drive, reuse
            # the existing ID to avoid redundant uploads.
            existing_id, lsjson_existing_meta = _gdrive_extract_existing_id(remote_path=remote_path)
            if existing_id:
                drive_id = existing_id
                drive_url = _drive_url_from_id(existing_id)
                upload_completed = True
            else:
                copy_meta, copy_stdout, copy_stderr = _rclone_run_raw(
                    ["copyto", src_path, remote_path],
                    timeout_seconds=_rclone_copyto_timeout_seconds(),
                )
                if copy_meta is not None and not bool(copy_meta.get("ok")):
                    copy_meta["error_kind"] = _classify_rclone_error_kind(
                        stdout=str(copy_stdout or ""),
                        stderr=str(copy_stderr or ""),
                        timed_out=bool(copy_meta.get("timed_out")),
                    )
                    # If rclone timed out, the upload might still have succeeded; try a single stat before failing.
                    maybe_id, maybe_meta = _gdrive_extract_existing_id(remote_path=remote_path)
                    if maybe_id:
                        lsjson_wait_meta = maybe_meta
                        lsjson_wait_attempts = 1
                        drive_id = maybe_id
                        drive_url = _drive_url_from_id(maybe_id)
                        upload_completed = True
                        copy_meta["recovered_via_stat"] = True
                    else:
                        stopped = {"error": copy_meta.get("error") or "rclone copyto failed", "error_kind": copy_meta.get("error_kind")}
                        raise RuntimeError(
                            f"rclone copyto failed ({copy_meta.get('error_kind')}): {copy_meta.get('error') or ''}".strip()
                        )
                upload_completed = True
                if not drive_id:
                    item, lsjson_wait_meta, lsjson_wait_attempts, wait_err = _gdrive_wait_for_id(
                        remote_path=remote_path,
                        expected_size_bytes=expected_size_bytes,
                        timeout_seconds=sync_timeout_seconds,
                    )
                    if item:
                        drive_id = str(item.get("ID") or "").strip()
                        drive_url = _drive_url_from_id(drive_id)
                    elif wait_err:
                        raise RuntimeError(f"{wait_err} (attempts={lsjson_wait_attempts})")
        except Exception as exc:
            drive_resolve_error = f"{type(exc).__name__}: {exc}"
            err_kind = ""
            if isinstance(exc, RuntimeError) and str(exc).startswith("FileTooLarge:"):
                err_kind = "permanent"
            if not err_kind and copy_meta is not None:
                err_kind = str(copy_meta.get("error_kind") or "").strip()
            if not err_kind and lsjson_existing_meta is not None:
                err_kind = str(lsjson_existing_meta.get("error_kind") or "").strip()
            if not err_kind and lsjson_wait_meta is not None:
                err_kind = str(lsjson_wait_meta.get("error_kind") or "").strip()
            drive_error_kind = err_kind or "retryable"
            if stopped is None and not upload_completed and drive_error_kind:
                stopped = {"error": drive_resolve_error, "error_kind": drive_error_kind}

        try:
            size_bytes = int(expected_size_bytes) if expected_size_bytes is not None else None
        except Exception:
            size_bytes = None
        uploads.append(
            {
                "src_path": src_path,
                "drive_name": dest_name,
                "drive_remote_path": remote_path,
                "drive_id": drive_id,
                "drive_url": drive_url,
                "drive_resolve_error": drive_resolve_error,
                "drive_error_kind": drive_error_kind,
                "upload_completed": bool(upload_completed),
                "size_bytes": size_bytes,
                "expected_size_bytes": expected_size_bytes,
                "rclone_copyto": copy_meta,
                "rclone_lsjson_existing": lsjson_existing_meta,
                "rclone_lsjson_wait": lsjson_wait_meta,
                "rclone_lsjson_wait_attempts": lsjson_wait_attempts,
            }
        )
    return uploads


class GeminiWebMcpExecutor(BaseExecutor):
    def __init__(
        self,
        *,
        mcp_url: str | None = None,
        tool_caller: ToolCaller | None = None,
        client_name: str = "chatgptrest",
        client_version: str = "0.1.0",
    ) -> None:
        if tool_caller is None:
            if not mcp_url:
                raise ValueError("mcp_url is required when tool_caller is not provided")
            tool_caller = McpHttpToolCaller(url=mcp_url, client_name=client_name, client_version=client_version)
        self._client = tool_caller

    async def run(self, *, job_id: str, kind: str, input: dict[str, Any], params: dict[str, Any]) -> ExecutorResult:  # noqa: A002
        if kind == "gemini_web.ask":
            return await self._run_ask(job_id=job_id, input=input, params=params)
        if kind == "gemini_web.generate_image":
            return await self._run_generate_image(job_id=job_id, input=input, params=params)
        if kind == "gemini_web.extract_answer":
            return await self._run_extract_answer(job_id=job_id, input=input, params=params)
        return ExecutorResult(status="error", answer=f"Unknown kind: {kind}", meta={"error_type": "ValueError"})

    async def _probe_deep_research_surface(self, *, conversation_url: str | None) -> dict[str, Any]:
        timeout_seconds = _gemini_deep_research_self_check_timeout_seconds()
        tool_args: dict[str, Any] = {}
        if conversation_url:
            tool_args["conversation_url"] = str(conversation_url)
        try:
            res = await asyncio.to_thread(
                self._client.call_tool,
                tool_name="gemini_web_self_check",
                tool_args=tool_args,
                timeout_sec=float(timeout_seconds) + 15.0,
            )
        except Exception as exc:
            return {
                "ok": False,
                "status": "error",
                "tool_available": None,
                "error_type": "GeminiDeepResearchSelfCheckError",
                "error": f"{type(exc).__name__}: {exc}",
            }
        if not isinstance(res, dict):
            return {
                "ok": False,
                "status": "error",
                "tool_available": None,
                "error_type": "TypeError",
                "error": "gemini_web_self_check returned non-dict result",
            }

        payload = dict(res)
        tools_btn = payload.get("tools_button")
        tool_button_visible = bool(isinstance(tools_btn, dict) and tools_btn.get("visible"))
        tool_available_detected = _gemini_has_deep_research_tool_surface(payload)
        mode_text = str(payload.get("mode_text") or "").strip()
        if (not tool_available_detected) and mode_text and _GEMINI_DEEP_RESEARCH_TOOL_RE.search(mode_text):
            tool_available_detected = True
        probe_error_type = str(payload.get("error_type") or "").strip()
        probe_error = str(payload.get("error") or "").strip()
        tool_surface_uncertain = False
        if not tool_available_detected:
            if probe_error_type in {"GeminiToolsDrawerError", "GeminiDeepResearchSelfCheckError"}:
                tool_surface_uncertain = True
            elif tool_button_visible and not isinstance(payload.get("tools"), list) and probe_error:
                tool_surface_uncertain = True
            elif tool_button_visible and isinstance(payload.get("tools"), list) and not payload.get("tools") and probe_error:
                tool_surface_uncertain = True

        tool_available: bool | None = None if tool_surface_uncertain else bool(tool_available_detected)
        probe_summary = {
            "ok": bool(payload.get("ok")),
            "status": str(payload.get("status") or ""),
            "tool_button_visible": bool(tool_button_visible),
            "tool_available": tool_available,
            "tool_surface_uncertain": bool(tool_surface_uncertain),
            "tool_count": (len(payload.get("tools")) if isinstance(payload.get("tools"), list) else 0),
            "error_type": (probe_error_type or None),
            "error": (probe_error or None),
            "mode_text": (mode_text or None),
        }
        probe_summary["tools_preview"] = [
            str((item or {}).get("text") or "").strip()
            for item in (payload.get("tools") if isinstance(payload.get("tools"), list) else [])[:12]
            if isinstance(item, dict) and str((item or {}).get("text") or "").strip()
        ]
        return probe_summary

    async def _run_generate_image(self, *, job_id: str, input: dict[str, Any], params: dict[str, Any]) -> ExecutorResult:
        prompt = str(input.get("prompt") or input.get("question") or "").strip()
        if not prompt:
            return ExecutorResult(status="error", answer="Missing input.prompt", meta={"error_type": "ValueError"})

        conversation_url = str(input.get("conversation_url") or "").strip() or None
        file_paths = input.get("file_paths")
        if file_paths is not None and not isinstance(file_paths, list):
            file_paths = None
        timeout_seconds = max(30, _coerce_int(params.get("timeout_seconds"), 600))

        drive_uploads: list[dict[str, Any]] = []
        drive_files: list[str] = []
        allow_drive_name_fallback = bool(params.get("drive_name_fallback") or False)
        if isinstance(file_paths, list) and file_paths:
            try:
                drive_uploads = await asyncio.to_thread(
                    _upload_files_to_gdrive,
                    job_id=job_id,
                    file_paths=[str(p) for p in file_paths],
                )
            except Exception as exc:
                msg = f"Google Drive upload failed: {type(exc).__name__}: {exc}"
                return ExecutorResult(
                    status="error",
                    answer=msg,
                    meta={"error_type": "DriveUploadFailed", "error": msg},
                )
            unusable: list[dict[str, Any]] = []
            for u in drive_uploads:
                url = str(u.get("drive_url") or "").strip()
                name = str(u.get("drive_name") or "").strip()
                upload_ok = bool(u.get("upload_completed")) or bool(str(u.get("drive_id") or "").strip()) or bool(url)
                if url:
                    continue
                if allow_drive_name_fallback and name and upload_ok:
                    continue
                unusable.append(u)

            if unusable:
                permanent = [u for u in unusable if str(u.get("drive_error_kind") or "").strip() == "permanent"]
                if permanent:
                    err_summary = []
                    for u in permanent[:3]:
                        err_summary.append(
                            f"{u.get('drive_remote_path')}: {u.get('drive_resolve_error') or 'missing drive_url'}"
                        )
                    msg = "Google Drive upload failed (permanent error)."
                    if err_summary:
                        msg = f"{msg} ({'; '.join(err_summary)})"
                    return ExecutorResult(
                        status="error",
                        answer=msg,
                        meta={
                            "error_type": "DriveUploadFailed",
                            "error": msg,
                            "drive_uploads": drive_uploads,
                            "drive_name_fallback": bool(allow_drive_name_fallback),
                        },
                    )

                retry_after_seconds = max(30, min(int(_cfg.gdrive_retry_seconds), 900))
                err_summary = []
                for u in unusable[:3]:
                    err_summary.append(
                        f"{u.get('drive_remote_path')}: {u.get('drive_resolve_error') or 'missing drive_url'}"
                    )
                msg = "Google Drive upload not ready; retry later."
                if err_summary:
                    msg = f"{msg} ({'; '.join(err_summary)})"
                return ExecutorResult(
                    status="cooldown",
                    answer=msg,
                    meta={
                        "error_type": "DriveUploadNotReady",
                        "error": msg,
                        "retry_after_seconds": retry_after_seconds,
                        "not_before": _now() + float(retry_after_seconds),
                        "drive_uploads": drive_uploads,
                        "drive_name_fallback": bool(allow_drive_name_fallback),
                    },
                )

            for u in drive_uploads:
                url = str(u.get("drive_url") or "").strip()
                name = str(u.get("drive_name") or "").strip()
                if url:
                    drive_files.append(url)
                    continue
                upload_ok = bool(u.get("upload_completed")) or bool(str(u.get("drive_id") or "").strip())
                if allow_drive_name_fallback and name and upload_ok:
                    drive_files.append(name)

        tool_args: dict[str, Any] = {
            "prompt": prompt,
            "idempotency_key": f"chatgptrest:{job_id}:gemini_web_generate_image",
            "timeout_seconds": int(timeout_seconds),
        }
        if conversation_url:
            tool_args["conversation_url"] = str(conversation_url)
        if drive_files:
            tool_args["drive_files"] = drive_files

        res = await asyncio.to_thread(
            self._client.call_tool,
            tool_name="gemini_web_generate_image",
            tool_args=tool_args,
            timeout_sec=float(timeout_seconds) + 30.0,
        )
        if not isinstance(res, dict):
            return ExecutorResult(
                status="error",
                answer="gemini_web_generate_image returned non-dict",
                meta={"error_type": "TypeError"},
            )

        status = str(res.get("status") or "error").strip().lower()
        meta = dict(res)
        if conversation_url and not str(meta.get("conversation_url") or "").strip():
            meta["conversation_url"] = str(conversation_url)

        images = res.get("images")
        image_paths: list[str] = []
        if isinstance(images, list):
            for item in images:
                if not isinstance(item, dict):
                    continue
                p = str(item.get("path") or "").strip()
                if p:
                    image_paths.append(p)

        answer_lines: list[str] = []
        answer_lines.append("# Gemini image generation")
        answer_lines.append("")
        if meta.get("conversation_url"):
            answer_lines.append(f"- conversation_url: `{meta.get('conversation_url')}`")
        if image_paths:
            answer_lines.append(f"- images: `{len(image_paths)}`")
            for idx, p in enumerate(image_paths, start=1):
                answer_lines.append(f"- image_{idx}: `{p}`")
        answer_lines.append("")

        # The driver tool returns `ok` separately; normalize into ChatgptREST job status.
        if status == "completed":
            return ExecutorResult(status="completed", answer="\n".join(answer_lines), answer_format="markdown", meta=meta)
        if status in {"blocked", "cooldown"}:
            return ExecutorResult(status=status, answer=str(meta.get("error") or ""), meta=meta)
        if status == "in_progress":
            # For image generation, treat "sent but not finalized" as retryable cooldown.
            meta.setdefault("error_type", "InProgress")
            meta.setdefault("error", str(meta.get("error") or "gemini image generation in progress; retry later"))
            meta.setdefault("retry_after_seconds", 30)
            meta.setdefault("not_before", _now() + float(meta.get("retry_after_seconds") or 30))
            return ExecutorResult(status="cooldown", answer=str(meta.get("error") or ""), meta=meta)
        return ExecutorResult(status="error", answer=str(meta.get("error") or ""), meta=meta)

    async def _run_extract_answer(self, *, job_id: str, input: dict[str, Any], params: dict[str, Any]) -> ExecutorResult:
        conversation_url = str(input.get("conversation_url") or "").strip()
        if not conversation_url:
            return ExecutorResult(status="error", answer="Missing input.conversation_url", meta={"error_type": "ValueError"})

        timeout_seconds = max(15, _coerce_int(params.get("timeout_seconds"), 60))

        try:
            result = await asyncio.to_thread(
                self._client.call_tool,
                tool_name="gemini_web_extract_answer",
                tool_args={
                    "conversation_url": conversation_url,
                    "timeout_seconds": timeout_seconds,
                },
                timeout_sec=float(timeout_seconds) + 15.0,
            )
        except Exception as exc:
            return ExecutorResult(
                status="error",
                answer=f"gemini_web_extract_answer tool call failed: {type(exc).__name__}: {exc}",
                meta={"error_type": type(exc).__name__},
            )

        meta = dict(result) if isinstance(result, dict) else {"raw": result}
        answer = str(meta.pop("answer", "") or "").strip()
        ok = bool(meta.pop("ok", False))
        status = str(meta.pop("status", "completed" if ok else "error") or "completed")
        meta["conversation_url"] = str(meta.get("conversation_url") or conversation_url)

        return ExecutorResult(
            status=status,
            answer=answer,
            meta=meta,
        )

    async def _run_ask(self, *, job_id: str, input: dict[str, Any], params: dict[str, Any]) -> ExecutorResult:
        phase = _normalize_phase(params.get("phase") or params.get("execution_phase"))
        question = str(input.get("question") or "").strip()
        if phase != "wait" and not question:
            return ExecutorResult(status="error", answer="Missing input.question", meta={"error_type": "ValueError"})

        conversation_url = str(input.get("conversation_url") or "").strip() or None
        initial_conversation_url = conversation_url
        file_paths = input.get("file_paths")
        if file_paths is not None and not isinstance(file_paths, list):
            file_paths = None
        raw_file_paths_for_hint = list(file_paths) if isinstance(file_paths, list) else []

        deep_research = bool(params.get("deep_research") or False)
        deep_research_effective = bool(deep_research)
        deep_research_probe: dict[str, Any] | None = None
        attachment_preprocess_meta: dict[str, Any] | None = None

        github_repo = str(input.get("github_repo") or "").strip() or None
        enable_import_code = bool(params.get("enable_import_code") or False)
        if github_repo and not enable_import_code:
            return ExecutorResult(
                status="error",
                answer="gemini_web.ask input.github_repo requires params.enable_import_code=true",
                meta={"error_type": "ValueError"},
            )
        if github_repo and deep_research:
            return ExecutorResult(
                status="error",
                answer="gemini_web.ask params.deep_research=true does not support input.github_repo",
                meta={"error_type": "ValueError"},
            )

        preset = _normalize_preset(params.get("preset") or "pro")

        base_timeout = _coerce_int(params.get("timeout_seconds"), 600)
        send_timeout_raw = params.get("send_timeout_seconds")
        send_timeout_seconds = max(30, _coerce_int(send_timeout_raw, base_timeout))
        # Keep the send/ask stage relatively short so we can promptly switch into wait/export recovery
        # without blocking the send queue. Use CHATGPTREST_DEFAULT_SEND_TIMEOUT_SECONDS=0 to disable.
        cap = _cfg.default_send_timeout_seconds
        if not cap:
            cap = 180
        if cap > 0:
            send_timeout_seconds = min(send_timeout_seconds, max(30, cap))

        wait_timeout_seconds = max(30, _coerce_int(params.get("wait_timeout_seconds"), base_timeout))
        # Deep Research should default to a longer wait budget, but explicit caller
        # overrides must still be respected for tests and recovery flows.
        max_wait_default = 3600 if deep_research else 1800
        max_wait_seconds = max(30, _coerce_int(params.get("max_wait_seconds"), max_wait_default))
        min_chars = max(0, _coerce_int(params.get("min_chars"), 200))
        answer_format = str(params.get("answer_format") or "markdown").strip().lower()
        if answer_format not in {"markdown", "text"}:
            answer_format = "markdown"

        job_params = GeminiWebJobParams(
            preset=preset,
            send_timeout_seconds=send_timeout_seconds,
            wait_timeout_seconds=wait_timeout_seconds,
            min_chars=min_chars,
            max_wait_seconds=max_wait_seconds,
            answer_format=answer_format,
            phase=phase,
        )

        contract_signal = detect_missing_attachment_contract(kind="gemini_web.ask", input_obj=input, params_obj=params)
        if phase != "wait" and isinstance(contract_signal, dict) and bool(contract_signal.get("high_risk")):
            message = attachment_contract_missing_message(contract_signal)
            return ExecutorResult(
                status="error",
                answer=message,
                answer_format=answer_format,
                meta={
                    "error_type": "AttachmentContractMissing",
                    "error": message,
                    "family_id": str(contract_signal.get("family_id") or "attachment_contract_missing"),
                    "family_label": str(contract_signal.get("family_label") or "Attachment contract missing"),
                    "attachment_contract": dict(contract_signal),
                },
            )

        if (
            phase != "wait"
            and deep_research_effective
            and _gemini_deep_research_self_check_enabled()
            and isinstance(self._client, McpHttpToolCaller)
        ):
            deep_research_probe = await self._probe_deep_research_surface(conversation_url=conversation_url)
            if (
                isinstance(deep_research_probe, dict)
                and deep_research_probe.get("tool_available") is False
                and str(deep_research_probe.get("status") or "").strip().lower() == "completed"
            ):
                retry_after_seconds = 180
                msg = (
                    "Gemini Deep Research tool is not visible in current UI surface "
                    "(gemini_web_self_check). Retry after refreshing/restarting the driver."
                )
                return ExecutorResult(
                    status="needs_followup",
                    answer=msg,
                    meta={
                        "error_type": "GeminiDeepResearchToolUnavailable",
                        "error": msg,
                        "retry_after_seconds": int(retry_after_seconds),
                        "not_before": _now() + float(retry_after_seconds),
                        "deep_research_probe": deep_research_probe,
                    },
                )

        if phase != "wait" and _gemini_attachment_preprocess_enabled() and isinstance(file_paths, list) and file_paths:
            try:
                prepared_paths, attachment_preprocess_meta = await asyncio.to_thread(
                    _prepare_gemini_file_paths_for_upload,
                    job_id=job_id,
                    file_paths=[str(p) for p in file_paths],
                    deep_research=bool(deep_research_effective),
                )
                file_paths = list(prepared_paths)
            except Exception as exc:
                msg = f"Gemini attachment preprocess failed: {type(exc).__name__}: {exc}"
                return ExecutorResult(
                    status="error",
                    answer=msg,
                    meta={"error_type": "GeminiAttachmentPreprocessFailed", "error": msg},
                )

        hint_parts: list[str] = []
        if question:
            hint_parts.append(question)
        for p in raw_file_paths_for_hint:
            try:
                name = Path(str(p)).name
            except Exception:
                continue
            if name:
                hint_parts.append(name)
        if isinstance(file_paths, list):
            for p in file_paths:
                try:
                    name = Path(str(p)).name
                except Exception:
                    continue
                if name:
                    hint_parts.append(name)
        if github_repo:
            hint_parts.append(github_repo)
        conversation_hint = " ".join(part.strip() for part in hint_parts if str(part).strip())
        conversation_hint = re.sub(r"\s+", " ", conversation_hint).strip()
        # Keep the MCP payload small and stable.
        if len(conversation_hint) > 2000:
            conversation_hint = conversation_hint[:2000]

        primary_key = f"chatgptrest:{job_id}:gemini:{preset}"
        driver_tool_name = "gemini_web_deep_research" if deep_research else _tool_for_preset(preset)

        def _is_gemini_thread_url(value: str) -> bool:
            raw = str(value or "").strip()
            if not raw:
                return False
            base = raw.split("#", 1)[0].split("?", 1)[0].rstrip("/")
            return bool(re.match(r"^https?://gemini\.google\.com/app/[0-9A-Za-z_-]{8,}$", base, re.I))

        def _conversation_url_from_idempotency_record(record: dict[str, Any]) -> str:
            candidates: list[str] = []
            for source in (
                record,
                record.get("result") if isinstance(record.get("result"), dict) else None,
            ):
                if not isinstance(source, dict):
                    continue
                url = str(source.get("conversation_url") or "").strip()
                if url:
                    candidates.append(url)
            for candidate in candidates:
                if _is_gemini_thread_url(candidate):
                    return candidate
            return candidates[0] if candidates else ""

        async def _resolve_conversation_url_from_idempotency(*, tool_name: str, key: str) -> str:
            if not str(tool_name or "").strip():
                return ""
            try:
                res = await asyncio.to_thread(
                    self._client.call_tool,
                    tool_name="gemini_web_idempotency_get",
                    tool_args={
                        "idempotency_key": key,
                        "tool_name": str(tool_name),
                    },
                    timeout_sec=float(_cfg.idempotency_get_timeout_seconds) + 10.0,
                )
            except Exception:
                return ""
            if not isinstance(res, dict):
                return ""
            record = res.get("record") if isinstance(res.get("record"), dict) else {}
            return _conversation_url_from_idempotency_record(record)

        def _merge_idempotency_recovery_meta(result: dict[str, Any], recovered_url: str) -> dict[str, Any]:
            merged = dict(result)
            url = str(recovered_url or "").strip()
            if not url:
                return merged
            merged.setdefault("_idempotency_recovered_conversation_url", url)
            merged.setdefault("conversation_url_recovered_from_idempotency", True)
            return merged

        async def _try_deep_research_gdoc_fallback(*, url: str | None) -> dict[str, Any] | None:
            cur = str(url or "").strip()
            if not deep_research_effective:
                return None
            if not cur or not _is_gemini_thread_url(cur):
                return {
                    "ok": False,
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": cur,
                    "error_type": "WaitingForConversationUrl",
                    "error": "Gemini DR gdoc fallback skipped: conversation_url is not a thread URL.",
                }

            timeout_seconds = _gemini_dr_gdoc_fallback_timeout_seconds()
            tool_args: dict[str, Any] = {
                "conversation_url": cur,
                "timeout_seconds": int(timeout_seconds),
                "fetch_text": True,
                "max_chars": int(_gemini_dr_gdoc_fallback_max_chars()),
            }
            try:
                res = await asyncio.to_thread(
                    self._client.call_tool,
                    tool_name="gemini_web_deep_research_export_gdoc",
                    tool_args=tool_args,
                    timeout_sec=float(timeout_seconds) + 60.0,
                )
            except Exception as exc:
                return {
                    "ok": False,
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": cur,
                    "error_type": "GeminiDeepResearchGDocFallbackError",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            if not isinstance(res, dict):
                return {
                    "ok": False,
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": cur,
                    "error_type": "TypeError",
                    "error": "gemini_web_deep_research_export_gdoc returned non-dict result",
                }
            out = dict(res)
            out.setdefault("conversation_url", cur)
            ans = str(out.get("answer") or "").strip()
            if ans:
                out["classified_status"] = _classify_deep_research_answer(ans)
            return out

        async def _wait_loop(*, url: str | None, allow_auto_followup: bool = True) -> tuple[dict[str, Any], str]:
            transient_failure_limit = _gemini_wait_transient_failure_limit()

            def _on_gemini_wait_result(wait_res: dict[str, Any], cur_url: str) -> tuple[dict[str, Any], str]:
                new_url = str(wait_res.get("conversation_url") or "").strip()
                if new_url and (not _is_gemini_thread_url(cur_url) or _is_gemini_thread_url(new_url)):
                    cur_url = new_url
                wait_res["conversation_url"] = cur_url
                return wait_res, cur_url

            def _on_gemini_transient_error(exc: Exception, failure_count: int) -> tuple[bool, float]:
                if not _looks_like_wait_transient_error(exc):
                    return (False, 0.0)
                retry_after = _gemini_wait_transient_retry_after_seconds()
                if failure_count >= transient_failure_limit:
                    return (False, 0.0)
                return (True, 1.0 + random.random())

            extra_args: dict[str, Any] = {"deep_research": bool(deep_research_effective)}
            if conversation_hint:
                extra_args["conversation_hint"] = conversation_hint

            try:
                result, cur = await self._wait_loop_core(
                    client=self._client,
                    tool_name="gemini_web_wait",
                    conversation_url=url or "",
                    wait_timeout_seconds=job_params.wait_timeout_seconds,
                    max_wait_seconds=job_params.max_wait_seconds,
                    min_chars=job_params.min_chars,
                    extra_tool_args=extra_args,
                    on_wait_result=_on_gemini_wait_result,
                    on_transient_error=_on_gemini_transient_error,
                    now_fn=_now,
                )
            except Exception as exc:
                if _looks_like_wait_transient_error(exc):
                    retry_after = _gemini_wait_transient_retry_after_seconds()
                    cur = str(url or "").strip()
                    return (
                        {
                            "ok": False,
                            "status": "in_progress",
                            "answer": "",
                            "conversation_url": cur,
                            "error_type": "InfraError",
                            "error": f"{type(exc).__name__}: {exc}",
                            "retry_after_seconds": int(retry_after),
                            "not_before": _now() + float(retry_after),
                            "wait_transient_failures": int(transient_failure_limit),
                        },
                        cur,
                    )
                raise

            # Post-loop: GDoc fallback for deep research when wait deadline reached
            status_final = str(result.get("status") or "").strip().lower()
            error_text = str(result.get("error") or "").lower()
            error_type = str(result.get("error_type") or "")
            
            looks_like_crash = status_final in ("error", "blocked") and (
                error_type == "InfraError" or
                "closed" in error_text or
                "timeout" in error_type.lower() or
                "timeout" in error_text
            )
            
            if (status_final == "in_progress" or looks_like_crash) and _gemini_dr_gdoc_fallback_enabled():
                fallback = await _try_deep_research_gdoc_fallback(url=cur)
                if isinstance(fallback, dict):
                    result = dict(result)
                    result["gdoc_export"] = fallback
                    fb_answer = str(fallback.get("answer") or "").strip()
                    fb_status = str(fallback.get("status") or "").strip().lower()
                    fb_classified = str(fallback.get("classified_status") or "").strip().lower()
                    effective_status = fb_classified or fb_status
                    if fb_answer and effective_status in {"completed", "needs_followup"}:
                        result.update(
                            {
                                "ok": True,
                                "status": effective_status,
                                "answer": fb_answer,
                                "conversation_url": str(fallback.get("conversation_url") or cur),
                                "fallback": {
                                    "kind": "gemini_dr_export_gdoc",
                                    "applied": True,
                                    "reason": "wait_deadline_reached",
                                    "gdoc_url": str(fallback.get("gdoc_url") or ""),
                                    "gdoc_id": str(fallback.get("gdoc_id") or ""),
                                },
                            }
                        )
            status_final = str(result.get("status") or "").strip().lower()
            if (
                allow_auto_followup
                and deep_research_effective
                and _cfg.deep_research_auto_followup
                and status_final == "needs_followup"
            ):
                followup = await _try_deep_research_auto_followup(
                    reason="wait_needs_followup",
                    url=cur,
                    prior_answer=str(result.get("answer") or ""),
                )
                if followup is not None:
                    return followup
            if status_final == "in_progress":
                result = dict(result)
                has_thread_url = _is_gemini_thread_url(cur)
                retry_after_seconds = _gemini_wait_requeue_retry_after_seconds(has_thread_url=has_thread_url)
                result["wait_state"] = "stable_thread_wait" if has_thread_url else "waiting_for_thread_url"
                if _coerce_int(result.get("retry_after_seconds"), 0) <= 0:
                    result["retry_after_seconds"] = int(retry_after_seconds)
                if not isinstance(result.get("not_before"), (int, float)):
                    result["not_before"] = _now() + float(result.get("retry_after_seconds") or retry_after_seconds)
            return result, cur

        async def _try_deep_research_auto_followup(
            *,
            reason: str,
            url: str | None,
            prior_answer: str,
        ) -> tuple[dict[str, Any], str] | None:
            cur = str(url or "").strip()
            if not (deep_research_effective and _cfg.deep_research_auto_followup and cur):
                return None

            followup_prompt = _gemini_deep_research_auto_followup_prompt(prior_answer)
            followup_args: Dict[str, Any] = {
                "question": followup_prompt,
                "conversation_url": cur,
                "idempotency_key": f"{primary_key}:auto-followup:{reason}",
                "timeout_seconds": int(min(max(job_params.send_timeout_seconds, 30), 180)),
            }
            try:
                followup_res = await asyncio.to_thread(
                    self._client.call_tool,
                    tool_name="gemini_web_deep_research",
                    tool_args=followup_args,
                    timeout_sec=float(followup_args["timeout_seconds"]) + 30.0,
                )
            except Exception as exc:
                retry_after_seconds = max(30, min(int(_cfg.needs_followup_retry_after_seconds), 3600))
                return (
                    {
                        "ok": False,
                        "status": "needs_followup",
                        "answer": "",
                        "conversation_url": cur,
                        "error_type": "GeminiDeepResearchAutoFollowupError",
                        "error": f"{type(exc).__name__}: {exc}",
                        "retry_after_seconds": int(retry_after_seconds),
                        "not_before": _now() + float(retry_after_seconds),
                        "deep_research_auto_followup": {
                            "enabled": True,
                            "reason": str(reason),
                            "sent": False,
                            "prompt": followup_prompt,
                        },
                    },
                    cur,
                )

            if not isinstance(followup_res, dict):
                return None

            followup_res = dict(followup_res)
            cur = str(followup_res.get("conversation_url") or cur).strip() or cur
            followup_res["conversation_url"] = cur
            auto_meta: Dict[str, Any] = {
                "enabled": True,
                "reason": str(reason),
                "sent": True,
                "prompt": followup_prompt,
            }
            status_follow = str(followup_res.get("status") or "").strip().lower()
            answer_follow = str(followup_res.get("answer") or "")
            if status_follow == "completed":
                status_follow = _classify_deep_research_answer(answer_follow)
                followup_res["status"] = status_follow
            if status_follow == "in_progress":
                waited, cur = await _wait_loop(url=cur, allow_auto_followup=False)
                waited = dict(waited)
                auto_meta["post_status"] = str(waited.get("status") or "").strip().lower() or None
                waited["deep_research_auto_followup"] = auto_meta
                return waited, cur

            auto_meta["post_status"] = status_follow or None
            followup_res["deep_research_auto_followup"] = auto_meta
            return followup_res, cur

        drive_uploads: list[dict[str, Any]] = []
        recovered_wait_url = ""

        if phase == "wait":
            wait_url = str(conversation_url or "").strip()
            if not wait_url:
                wait_url = await _resolve_conversation_url_from_idempotency(
                    tool_name=driver_tool_name,
                    key=primary_key,
                )
                if wait_url:
                    recovered_wait_url = wait_url
                    conversation_url = wait_url if _is_gemini_thread_url(wait_url) else conversation_url
            result, conversation_url = await _wait_loop(url=wait_url or conversation_url)
            result = _merge_idempotency_recovery_meta(result, recovered_wait_url)
        else:
            drive_files: list[str] = []
            allow_drive_name_fallback = bool(params.get("drive_name_fallback") or False)
            if isinstance(file_paths, list) and file_paths:
                # Drive upload + rclone lsjson may take tens of seconds; run it off the event loop so
                # the worker can keep renewing its lease while waiting for Drive to sync.
                try:
                    drive_uploads = await asyncio.to_thread(
                        _upload_files_to_gdrive,
                        job_id=job_id,
                        file_paths=[str(p) for p in file_paths],
                    )
                except Exception as exc:
                    msg = f"Google Drive upload failed: {type(exc).__name__}: {exc}"
                    return ExecutorResult(
                        status="error",
                        answer=msg,
                        meta={"error_type": "DriveUploadFailed", "error": msg},
                    )
                unusable: list[dict[str, Any]] = []
                for u in drive_uploads:
                    url = str(u.get("drive_url") or "").strip()
                    name = str(u.get("drive_name") or "").strip()
                    upload_ok = bool(u.get("upload_completed")) or bool(str(u.get("drive_id") or "").strip()) or bool(url)
                    if url:
                        continue
                    if allow_drive_name_fallback and name and upload_ok:
                        continue
                    unusable.append(u)

                if unusable:
                    permanent = [u for u in unusable if str(u.get("drive_error_kind") or "").strip() == "permanent"]
                    if permanent:
                        err_summary = []
                        for u in permanent[:3]:
                            err_summary.append(
                                f"{u.get('drive_remote_path')}: {u.get('drive_resolve_error') or 'missing drive_url'}"
                            )
                        msg = "Google Drive upload failed (permanent error)."
                        if err_summary:
                            msg = f"{msg} ({'; '.join(err_summary)})"
                        return ExecutorResult(
                            status="error",
                            answer=msg,
                            meta={
                                "error_type": "DriveUploadFailed",
                                "error": msg,
                                "drive_uploads": drive_uploads,
                                "drive_name_fallback": bool(allow_drive_name_fallback),
                            },
                        )
                    retry_after_seconds = max(30, min(int(_cfg.gdrive_retry_seconds), 900))
                    err_summary = []
                    for u in unusable[:3]:
                        err_summary.append(
                            f"{u.get('drive_remote_path')}: {u.get('drive_resolve_error') or 'missing drive_url'}"
                        )
                    msg = "Google Drive upload not ready; retry later."
                    if err_summary:
                        msg = f"{msg} ({'; '.join(err_summary)})"
                    return ExecutorResult(
                        status="cooldown",
                        answer=msg,
                        meta={
                            "error_type": "DriveUploadNotReady",
                            "error": msg,
                            "retry_after_seconds": retry_after_seconds,
                            "not_before": _now() + float(retry_after_seconds),
                            "drive_uploads": drive_uploads,
                            "drive_name_fallback": bool(allow_drive_name_fallback),
                        },
                    )
                for u in drive_uploads:
                    url = str(u.get("drive_url") or "").strip()
                    name = str(u.get("drive_name") or "").strip()
                    if url:
                        drive_files.append(url)
                        continue
                    upload_ok = bool(u.get("upload_completed")) or bool(str(u.get("drive_id") or "").strip())
                    if allow_drive_name_fallback and name and upload_ok:
                        drive_files.append(name)

            tool_args: Dict[str, Any] = {
                "question": question,
                "idempotency_key": primary_key,
                "timeout_seconds": int(job_params.send_timeout_seconds),
            }
            if conversation_url:
                tool_args["conversation_url"] = conversation_url
            if drive_files:
                tool_args["drive_files"] = drive_files
            if github_repo:
                tool_args["github_repo"] = github_repo

            # ── Send with transient-error retry ─────────────────────────
            send_max_retries = _gemini_send_max_retries()
            send_retry_delay = _gemini_send_retry_delay()
            result: Dict[str, Any] = {}
            for send_attempt in range(send_max_retries + 1):
                try:
                    result = await asyncio.to_thread(
                        self._client.call_tool,
                        tool_name=driver_tool_name,
                        tool_args=tool_args,
                        timeout_sec=float(job_params.send_timeout_seconds) + 30.0,
                    )
                except Exception as send_exc:
                    if send_attempt < send_max_retries:
                        logger.warning(
                            "gemini send attempt %d/%d failed (exception): %s — retrying in %.1fs",
                            send_attempt + 1, send_max_retries + 1, send_exc, send_retry_delay,
                        )
                        await asyncio.sleep(send_retry_delay)
                        continue
                    raise
                if not isinstance(result, dict):
                    return ExecutorResult(status="error", answer="driver returned non-dict result", meta={"error_type": "TypeError"})
                if _is_transient_driver_error(result) and send_attempt < send_max_retries:
                    logger.warning(
                        "gemini send attempt %d/%d transient error: %s / %s — retrying in %.1fs",
                        send_attempt + 1, send_max_retries + 1,
                        result.get("error_type"), str(result.get("error") or "")[:200],
                        send_retry_delay,
                    )
                    # Regenerate idempotency key for retry so driver doesn't dedupe
                    tool_args["idempotency_key"] = f"{primary_key}:retry:{send_attempt + 1}"
                    await asyncio.sleep(send_retry_delay)
                    continue
                break  # success or non-transient error

            conversation_url = str(result.get("conversation_url") or conversation_url or "").strip() or None
            status = str(result.get("status") or "").strip().lower()
            answer_text = str(result.get("answer") or "")
            error_type = str(result.get("error_type") or "").strip()
            error_text = str(result.get("error") or "").strip()
            send_without_new_response_start = bool(result.get("send_without_new_response_start"))
            deep_think_retry = result.get("deep_think_retry")
            deep_think_final_overloaded = bool(
                isinstance(deep_think_retry, dict) and deep_think_retry.get("final_overloaded")
            )
            if status == "in_progress" and not conversation_url:
                recovered_wait_url = await _resolve_conversation_url_from_idempotency(
                    tool_name=driver_tool_name,
                    key=primary_key,
                )
                if recovered_wait_url:
                    result = _merge_idempotency_recovery_meta(result, recovered_wait_url)
                    if _is_gemini_thread_url(recovered_wait_url):
                        conversation_url = recovered_wait_url
                        result["conversation_url"] = recovered_wait_url

            async def _try_deep_think_fallback_to_pro(*, reason: str) -> bool:
                nonlocal result, conversation_url, status
                fallback_preset = "pro"
                fallback_tool = _tool_for_preset(fallback_preset)
                fallback_args = dict(tool_args)
                fallback_args["idempotency_key"] = f"chatgptrest:{job_id}:gemini:fallback:{fallback_preset}"
                # The base Gemini app URL is not resumable context. Only carry a
                # stable thread URL into the fallback call; otherwise let Pro start
                # clean instead of inheriting `/app` and re-failing on the wrong page.
                if conversation_url and _is_gemini_thread_url(str(conversation_url)):
                    fallback_args["conversation_url"] = str(conversation_url)
                else:
                    fallback_args.pop("conversation_url", None)
                try:
                    fallback_res = await asyncio.to_thread(
                        self._client.call_tool,
                        tool_name=fallback_tool,
                        tool_args=fallback_args,
                        timeout_sec=float(job_params.send_timeout_seconds) + 30.0,
                    )
                except Exception:
                    return False
                if not isinstance(fallback_res, dict):
                    return False
                fallback_status = str(fallback_res.get("status") or "").strip().lower()
                if not fallback_status:
                    return False
                if fallback_status in {"error", "blocked", "cooldown"}:
                    return False

                fallback_res = dict(fallback_res)
                payload: Dict[str, Any] = {
                    "from_preset": "deep_think",
                    "to_preset": fallback_preset,
                    "reason": str(reason),
                }
                if isinstance(deep_think_retry, dict):
                    payload["deep_think_retry"] = deep_think_retry
                if error_type:
                    payload["source_error_type"] = error_type
                if error_text:
                    payload["source_error"] = error_text[:400]
                fallback_res.setdefault("fallback", payload)
                result = fallback_res
                conversation_url = str(result.get("conversation_url") or conversation_url or "").strip() or None
                status = str(result.get("status") or "").strip().lower()
                return True

            logger.info(
                "deep_think_check: preset=%s deep_research=%s auto_fallback=%s status=%s "
                "overloaded_flag=%s overloaded_regex=%s answer_len=%d answer_head=%s",
                preset, deep_research, _cfg.deep_think_auto_fallback, status,
                deep_think_final_overloaded, _looks_like_gemini_deep_think_overloaded(answer_text),
                len(answer_text), repr(answer_text[:80]),
            )
            if preset == "deep_think" and (not deep_research) and _cfg.deep_think_auto_fallback:
                if status == "completed" and (
                    deep_think_final_overloaded or _looks_like_gemini_deep_think_overloaded(answer_text)
                ):
                    fallback_ok = await _try_deep_think_fallback_to_pro(reason="deep_think_overloaded")
                    if not fallback_ok:
                        # Fallback failed — do NOT return the capacity refusal as "completed".
                        # Mark as cooldown so the worker retries after a delay.
                        status = "cooldown"
                        result["status"] = "cooldown"
                        result.setdefault("error_type", "GeminiDeepThinkOverloaded")
                        result.setdefault("error", "Deep Think capacity exceeded and fallback to Pro failed")
                        _retry = 120
                        result["retry_after_seconds"] = _retry
                        result["not_before"] = _now() + float(_retry)
                        answer_text = ""  # clear garbage answer
                        result["answer"] = ""
                elif status in {"error", "blocked", "cooldown"} and _looks_like_gemini_deep_think_unavailable(
                    error_type=error_type,
                    error_text=error_text,
                ):
                    await _try_deep_think_fallback_to_pro(reason="deep_think_unavailable")
            send_classified_status = ""
            if deep_research_effective and answer_text:
                send_classified_status = _classify_deep_research_answer(answer_text)
            if (
                status == "needs_followup"
                and deep_research_effective
                and _cfg.deep_research_auto_followup
                and conversation_url
                and send_classified_status == "needs_followup"
            ):
                followup = await _try_deep_research_auto_followup(
                    reason="send_needs_followup",
                    url=conversation_url or initial_conversation_url,
                    prior_answer=answer_text,
                )
                if followup is not None:
                    result, conversation_url = followup
                    status = str(result.get("status") or "").strip().lower()
                    answer_text = str(result.get("answer") or "")
            if status == "in_progress" and initial_conversation_url and _is_gemini_thread_url(initial_conversation_url) and send_without_new_response_start:
                if deep_research_effective and _cfg.deep_research_auto_followup:
                    followup = await _try_deep_research_auto_followup(
                        reason="send_without_new_response_start",
                        url=conversation_url or initial_conversation_url,
                        prior_answer=answer_text,
                    )
                    if followup is not None:
                        result, conversation_url = followup
                        status = str(result.get("status") or "").strip().lower()
                        answer_text = str(result.get("answer") or "")
            if status == "in_progress" and initial_conversation_url and _is_gemini_thread_url(initial_conversation_url) and send_without_new_response_start:
                retry_after_seconds = max(30, min(int(_cfg.needs_followup_retry_after_seconds), 3600))
                msg = (
                    "Gemini follow-up send did not start a new response in the existing conversation; "
                    "refusing to wait on the previous answer."
                )
                result = dict(result)
                result["status"] = "needs_followup"
                result["answer"] = ""
                result["error_type"] = "GeminiFollowupSendUnconfirmed"
                result["error"] = msg
                result["retry_after_seconds"] = int(retry_after_seconds)
                result["not_before"] = _now() + float(retry_after_seconds)
                result["followup_wait_guard"] = {
                    "activated": True,
                    "reason": "send_without_new_response_start",
                    "input_conversation_url": str(initial_conversation_url),
                    "response_count_before_send": result.get("response_count_before_send"),
                    "response_count_after_error": result.get("response_count_after_error"),
                }
                status = "needs_followup"
            if phase == "full" and status == "in_progress":
                wait_url = str(conversation_url or recovered_wait_url or "").strip()
                if wait_url:
                    result, conversation_url = await _wait_loop(url=wait_url)
                    result = _merge_idempotency_recovery_meta(result, recovered_wait_url)
                else:
                    retry_after_seconds = max(30, min(int(_cfg.needs_followup_retry_after_seconds), 3600))
                    result = dict(result)
                    result["error_type"] = "WaitingForConversationUrl"
                    result["error"] = "conversation_url not available yet; retry later"
                    result.setdefault("retry_after_seconds", int(retry_after_seconds))
                    result.setdefault("not_before", _now() + float(retry_after_seconds))

        status = str(result.get("status") or "error").strip().lower()
        answer = str(result.get("answer") or "")
        meta = dict(result)
        meta["answer_format"] = job_params.answer_format
        meta["conversation_url"] = str(conversation_url or "")
        meta["preset"] = job_params.preset
        meta["deep_research_requested"] = bool(deep_research)
        meta["deep_research_effective"] = bool(deep_research_effective)
        if isinstance(attachment_preprocess_meta, dict):
            meta["attachment_preprocess"] = dict(attachment_preprocess_meta)
        if isinstance(deep_research_probe, dict):
            meta["deep_research_probe"] = dict(deep_research_probe)

        if status == "completed" and _gemini_answer_quality_guard_enabled():
            cleaned_answer, guard = _gemini_apply_answer_quality_guard(
                answer=answer,
                preset=job_params.preset,
                deep_research=bool(deep_research_effective),
                min_chars=int(job_params.min_chars),
            )
            recovery_meta: dict[str, Any] | None = None
            if (
                str(guard.get("error_type") or "") == "GeminiAnswerContaminated"
                and str(conversation_url or "").strip()
            ):
                recovered_answer, recovered_guard, recovery_meta = await _gemini_try_extract_clean_answer(
                    self,
                    job_id=job_id,
                    conversation_url=str(conversation_url or "").strip(),
                    preset=job_params.preset,
                    deep_research=bool(deep_research_effective),
                    min_chars=int(job_params.min_chars),
                )
                if recovered_answer is not None:
                    cleaned_answer = recovered_answer
                    guard = recovered_guard
            has_quality_signal = bool(
                guard.get("ui_noise_detected")
                or guard.get("semantic_risk_next_owner_mixed")
                or str(guard.get("status_override") or "").strip()
                or (cleaned_answer != answer)
            )
            answer = cleaned_answer
            if has_quality_signal:
                meta["answer_quality_guard"] = guard
            if isinstance(recovery_meta, dict):
                meta["answer_quality_recovery"] = recovery_meta
            status_override = str(guard.get("status_override") or "").strip().lower()
            if status_override in {"in_progress", "needs_followup", "cooldown"}:
                status = status_override
                retry_after = _gemini_answer_quality_retry_after_seconds()
                meta.setdefault("error_type", str(guard.get("error_type") or "GeminiAnswerQualityGuard"))
                meta.setdefault("error", str(guard.get("error") or "gemini answer quality guard requested follow-up"))
                meta.setdefault("retry_after_seconds", int(retry_after))
                meta.setdefault("not_before", _now() + float(retry_after))
            else:
                meta.pop("error_type", None)
                meta.pop("error", None)
                meta.pop("retry_after_seconds", None)
                meta.pop("not_before", None)

        if drive_uploads:
            meta["drive_uploads"] = drive_uploads

        if isinstance(file_paths, list) and file_paths:
            cleanup_mode = _gdrive_cleanup_mode()
            should_cleanup = False
            if cleanup_mode == "on_success" and status == "completed":
                should_cleanup = True
            elif cleanup_mode == "always" and status in {"completed", "error", "canceled"}:
                should_cleanup = True
            if should_cleanup:
                try:
                    cleanup_results = await asyncio.to_thread(
                        _gdrive_cleanup_uploaded_files,
                        job_id=job_id,
                        file_paths=[str(p) for p in file_paths],
                    )
                    meta["drive_cleanup"] = {"mode": cleanup_mode, "results": cleanup_results}
                except Exception as exc:
                    meta["drive_cleanup"] = {"mode": cleanup_mode, "error": f"{type(exc).__name__}: {exc}"}

        # Gemini sometimes fails before sending (no conversation_url) due to auth/region/UI gate.
        # Treat these as needs_followup so callers can fix the browser state and retry the *same* job_id.
        if status in {"error", "blocked", "cooldown"}:
            et = str(meta.get("error_type") or "").strip()
            if et in {"GeminiPromptBoxNotFound", "GeminiNotLoggedIn", "GeminiUnsupportedRegion", "GeminiCaptcha"}:
                hint = (
                    "Open the CDP Chrome profile and ensure you are logged into https://gemini.google.com/app. "
                    "If Gemini says the region is unsupported, route Chrome through a supported-region proxy and restart Chrome."
                )
                msg = str(meta.get("error") or answer or "").strip()
                if hint and hint not in msg:
                    msg = f"{msg}\n\nFollow-up: {hint}" if msg else f"Follow-up: {hint}"
                meta["error"] = msg

                retry_after = max(30, min(int(_cfg.needs_followup_retry_after_seconds), 3600))
                meta.setdefault("retry_after_seconds", int(retry_after))
                meta.setdefault("not_before", _now() + float(retry_after))
                return ExecutorResult(status="needs_followup", answer=msg, answer_format="text", meta=meta)

        return ExecutorResult(status=status, answer=answer, answer_format=job_params.answer_format, meta=meta)
