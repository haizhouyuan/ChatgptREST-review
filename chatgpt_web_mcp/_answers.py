"""Answer file writing and conversation export helpers.

Extracted from _tools_impl.py — ~285 lines of answer persistence and
conversation export logic.  All public names are re-exported by _tools_impl.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from chatgpt_web_mcp.idempotency import _result_has_full_answer_reference
from chatgpt_web_mcp.runtime.paths import _debug_dir

def _chatgpt_answer_dir() -> Path:
    raw = (os.environ.get("MCP_ANSWER_DIR") or os.environ.get("CHATGPT_ANSWER_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    debug_dir = _debug_dir()
    if debug_dir is not None:
        return debug_dir / "answers"
    return Path("artifacts/answers")


def _chatgpt_conversation_dir() -> Path:
    raw = (os.environ.get("MCP_CONVERSATION_DIR") or os.environ.get("CHATGPT_CONVERSATION_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    debug_dir = _debug_dir()
    if debug_dir is not None:
        return debug_dir / "conversations"
    return Path("artifacts/conversations")


def _chatgpt_max_return_answer_chars() -> int:
    raw = (os.environ.get("CHATGPT_MAX_RETURN_ANSWER_CHARS") or os.environ.get("MCP_MAX_RETURN_ANSWER_CHARS") or "").strip()
    if not raw:
        return 6000
    try:
        return max(0, int(raw))
    except ValueError:
        return 6000



def _chatgpt_write_answer_file(
    *,
    answer: str,
    answer_format: str | None,
    tool: str,
    run_id: str,
    conversation_url: str | None,
) -> dict[str, Any]:
    answer_id = uuid.uuid4().hex
    fmt = str(answer_format or "").strip().lower()
    ext = "md" if fmt == "markdown" else "txt"
    answer_dir = _chatgpt_answer_dir()
    answer_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{answer_id}.{ext}"
    path = answer_dir / file_name
    path.write_text(answer, encoding="utf-8")
    path_resolved = path.resolve()
    sha = hashlib.sha256(answer.encode("utf-8", errors="replace")).hexdigest()
    meta = {
        "answer_id": answer_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tool": str(tool or "").strip(),
        "run_id": str(run_id or "").strip(),
        "conversation_url": str(conversation_url or "").strip(),
        "answer_format": ("markdown" if fmt == "markdown" else "text"),
        "answer_chars": len(answer),
        "answer_sha256": sha,
        "file_name": file_name,
    }
    (answer_dir / f"{answer_id}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "answer_id": answer_id,
        "answer_path": str(path_resolved),
        "answer_sha256": sha,
        "answer_chars": len(answer),
        "answer_format": meta["answer_format"],
    }


def _chatgpt_conversation_id_from_url(conversation_url: str) -> str | None:
    url = str(conversation_url or "").strip()
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    path = str(parsed.path or "")
    m = re.search(r"/c/([A-Za-z0-9-]+)", path)
    if not m:
        return None
    cid = str(m.group(1) or "").strip()
    return cid if len(cid) >= 6 else None


def _chatgpt_write_conversation_export_file(
    *,
    conversation_json: str,
    tool: str,
    run_id: str,
    conversation_url: str | None,
    conversation_id: str | None,
    dst_path: str | None = None,
) -> dict[str, Any]:
    export_id = uuid.uuid4().hex
    if dst_path and str(dst_path).strip():
        path = Path(str(dst_path)).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        file_name = path.name
        path_resolved = path.resolve()
        export_dir = path.parent
    else:
        export_dir = _chatgpt_conversation_dir()
        export_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{export_id}.json"
        path = export_dir / file_name
        path_resolved = path.resolve()

    text = str(conversation_json or "")
    if not text.strip():
        text = "{}"
    if not text.endswith("\n"):
        text += "\n"

    path.write_text(text, encoding="utf-8")
    sha = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()

    meta = {
        "export_id": export_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tool": str(tool or "").strip(),
        "run_id": str(run_id or "").strip(),
        "conversation_url": str(conversation_url or "").strip(),
        "conversation_id": str(conversation_id or "").strip() or None,
        "export_format": "json",
        "export_chars": len(text),
        "export_sha256": sha,
        "file_name": file_name,
    }
    (export_dir / f"{export_id}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "export_id": export_id,
        "export_path": str(path_resolved),
        "export_sha256": sha,
        "export_chars": len(text),
        "export_format": "json",
    }


def _chatgpt_build_export_conversation_object_from_dom_messages(
    *,
    messages: list[dict[str, Any]],
    conversation_url: str,
    conversation_id: str,
    backend_status: int,
    backend_error: str | None,
    title: str | None = None,
) -> dict[str, Any]:
    """
    Convert a DOM-based transcript into a ChatGPT-export-like conversation object.

    This is a compatibility layer so downstream tooling (e.g. chatgptdata) can consume
    exports even when the ChatGPT backend API endpoint is unavailable.
    """
    now = time.time()
    root_id = "client-created-root"
    mapping: dict[str, Any] = {
        root_id: {"id": root_id, "message": None, "parent": None, "children": []},
    }
    parent_id = root_id
    current_node = root_id

    for m in messages:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "").strip().lower()
        text = str(m.get("text") or "")
        if not role and not text.strip():
            continue
        node_id = str(uuid.uuid4())
        msg_obj: dict[str, Any] = {
            "id": node_id,
            "author": {"role": role or "assistant", "name": None, "metadata": {}},
            "create_time": None,
            "update_time": None,
            "content": {"content_type": "text", "parts": [text]},
            "status": "finished_successfully",
            "end_turn": True,
            "weight": 1.0,
            "metadata": {},
            "recipient": "all",
            "channel": None,
        }
        mapping[node_id] = {"id": node_id, "message": msg_obj, "parent": parent_id, "children": []}
        mapping[parent_id]["children"].append(node_id)
        parent_id = node_id
        current_node = node_id

    conv: dict[str, Any] = {
        "title": str(title or "").strip(),
        "create_time": float(now),
        "update_time": float(now),
        "mapping": mapping,
        "moderation_results": [],
        "current_node": current_node,
        "plugin_ids": None,
        "conversation_id": str(conversation_id),
        "id": str(conversation_id),
        # Extra debug context (namespaced to avoid clashing with official exports).
        "chatgptrest_export": {
            "export_kind": "dom_messages",
            "conversation_url": str(conversation_url),
            "backend_status": int(backend_status),
            "backend_error": (str(backend_error) if backend_error else None),
        },
    }
    return conv


def _chatgpt_maybe_offload_answer_result(
    result: dict[str, Any],
    *,
    tool: str,
    run_id: str,
    max_return_chars: int | None = None,
) -> dict[str, Any]:
    if not isinstance(result, dict):
        return result
    answer_raw = result.get("answer")
    answer = str(answer_raw or "")
    if not answer.strip():
        return result

    limit = _chatgpt_max_return_answer_chars() if max_return_chars is None else int(max_return_chars)
    limit = max(0, int(limit))

    result.setdefault("answer_returned_chars", len(answer))
    result.setdefault("answer_chars", len(answer))

    if limit <= 0 or len(answer) <= limit:
        result.setdefault("answer_truncated", False)
        result["answer_returned_chars"] = len(answer)
        result["answer_chars"] = int(result.get("answer_chars") or len(answer))
        return result

    if _result_has_full_answer_reference(result):
        preview = answer[:limit]
        result["answer"] = preview
        result["answer_truncated"] = True
        result.setdefault("answer_saved", True)
        result["answer_chars"] = int(result.get("answer_chars") or len(answer))
        result["answer_returned_chars"] = len(preview)
        return result

    try:
        saved = _chatgpt_write_answer_file(
            answer=answer,
            answer_format=(result.get("answer_format") if isinstance(result.get("answer_format"), str) else None),
            tool=tool,
            run_id=run_id,
            conversation_url=(result.get("conversation_url") if isinstance(result.get("conversation_url"), str) else None),
        )
    except Exception:
        preview = answer[:limit]
        result["answer"] = preview
        result["answer_truncated"] = True
        result["answer_saved"] = False
        result["answer_chars"] = len(answer)
        result["answer_returned_chars"] = len(preview)
        return result

    preview = answer[:limit]
    result["answer"] = preview
    result["answer_truncated"] = True
    result["answer_saved"] = True
    result["answer_id"] = saved.get("answer_id")
    result["answer_path"] = saved.get("answer_path")
    result["answer_sha256"] = saved.get("answer_sha256")
    result["answer_chars"] = int(saved.get("answer_chars") or len(answer))
    result["answer_returned_chars"] = len(preview)
    result.setdefault("answer_format", saved.get("answer_format"))
    return result






