from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_RESPONSE_ENVELOPE_SENTINEL_KEYS = {
    "task_violates_safety_guidelines",
    "user_def_doesnt_want_research",
    "response",
    "title",
    "prompt",
}

_DOM_COPY_CODE_BLOCK_RE = re.compile(r"^([A-Za-z0-9_+-]{1,32})\nCopy code\n([\s\S]+)$")
_DOM_COPY_CODE_GENERIC_RE = re.compile(r"^Copy code\n([\s\S]+)$")
_CONTEXT_ACQUISITION_FAILURE_RE = re.compile(
    r"(?:"
    r"(?:difficult(?:y|ies)|issue|problem|trouble|unable|failed)\s+(?:retrieving|accessing|opening|reading|extracting|locating)|"
    r"(?:could|can't|cannot|unable to)\s+(?:access|retrieve|open|read|extract|locate)|"
    r"(?:would you be able to|please)\s+(?:upload|provide)\s+(?:the|relevant)?\s*(?:files?|bundle|context)|"
    r"additional context|"
    r"not present in the extracted contents|"
    r"based on the information so far|"
    r"(?:i will|i'll)\s+proceed to analyze(?:\s+this|\s+further)?|"
    r"unable to analyze (?:it|this) directly"
    r")",
    re.IGNORECASE,
)
_FILE_CONTEXT_HINT_RE = re.compile(
    r"(?:\bzip\b|\bbundle\b|\bupload(?:ed)?\b|\battached?\b|\bfile\b)",
    re.IGNORECASE,
)
_PARTIAL_ANALYSIS_CONTINUATION_RE = re.compile(
    r"(?:"
    r"based on the initial analysis|"
    r"(?:i will|i'll)\s+(?:now|continue to|proceed to)\s+(?:review|analy[sz]e|check|dig into)|"
    r"let me\s+(?:continue|proceed|dig into|check)|"
    r"given this,\s*i will\s+proceed|"
    r"let'?s proceed with the deeper review"
    r")",
    re.IGNORECASE,
)
_REVIEW_REQUIREMENT_RE = re.compile(
    r"(?:"
    r"findings first|"
    r"be critical rather than compliant|"
    r"required reading|"
    r"review scope|"
    r"cite the problematic path|"
    r"problematic path|"
    r"formal(?:ly)? review|"
    r"正式评审|"
    r"批判性评审|"
    r"必须阅读|"
    r"引用.*路径|"
    r"给出.*路径"
    r")",
    re.IGNORECASE,
)
_REVIEW_PATH_REQUIREMENT_RE = re.compile(
    r"(?:cite the problematic path|problematic path|引用.*路径|具体路径|路径)",
    re.IGNORECASE,
)
_REVIEW_PATH_LABEL_RE = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?(?:path|路径)(?:\*\*)?\s*:",
)
_REVIEW_FILELIKE_RE = re.compile(
    r"(?:"
    r"/[A-Za-z0-9_./-]+\.(?:py|md|json|ya?ml|ts|tsx|js|jsx|sh|txt|toml)|"
    r"\b[A-Za-z0-9_.-]+\.(?:py|md|json|ya?ml|ts|tsx|js|jsx|sh|txt|toml)\b"
    r")",
    re.IGNORECASE,
)
_REVIEW_COMMIT_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
_REVIEW_REPO_RE = re.compile(r"\b[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\b")
_REVIEW_GENERIC_APPROVAL_RE = re.compile(
    r"(?:"
    r"\bsound decision\b|"
    r"\bfundamentally solid\b|"
    r"\bwell-justified\b|"
    r"\bwell-considered\b|"
    r"\bcoherent and implementable\b|"
    r"\bthis is a sound\b|"
    r"\bthis is solid\b|"
    r"\bthe phased approach is sound\b|"
    r"\brealistic\b|"
    r"\bcoherent\b|"
    r"\bimplementable\b|"
    r"\bvalid\b|"
    r"\bsolid\b"
    r")",
    re.IGNORECASE,
)


def normalize_text(value: str) -> str:
    return (value or "").replace("\r\n", "\n").strip()


def unwrap_response_envelope_text(text: str) -> str:
    """
    Unwrap the Deep Research JSON response envelope when it is confidently detected.
    """
    trimmed = (text or "").strip()
    if not trimmed:
        return ""

    candidate = trimmed
    if candidate.startswith("```") and candidate.rstrip().endswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3 and lines[0].lstrip().startswith("```") and lines[-1].strip() == "```":
            inner = "\n".join(lines[1:-1]).strip()
            if inner.startswith("{") and inner.endswith("}"):
                candidate = inner

    if not (candidate.startswith("{") and candidate.endswith("}")):
        return trimmed

    try:
        obj = json.loads(candidate)
    except Exception:
        return trimmed

    if not isinstance(obj, dict):
        return trimmed
    if "response" not in obj or not isinstance(obj.get("response"), str):
        return trimmed

    keys = set(str(k) for k in obj.keys())
    if not (
        _RESPONSE_ENVELOPE_SENTINEL_KEYS.issubset(keys)
        or {"task_violates_safety_guidelines", "response"}.issubset(keys)
    ):
        return trimmed

    response = str(obj.get("response") or "")
    return response.strip() if response.strip() else trimmed


def message_text_from_export_mapping(message: dict[str, Any] | None) -> str:
    content = (message or {}).get("content") or {}
    parts = content.get("parts")
    if isinstance(parts, list):
        return "".join(str(p) for p in parts)
    text = content.get("text")
    if isinstance(text, str):
        return text
    return ""


def _deep_research_widget_export_text(obj: dict[str, Any]) -> str:
    raw = obj.get("deep_research_widget_export")
    text = ""
    if isinstance(raw, dict):
        for key in ("markdown", "text", "report_markdown"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                text = value
                break
    elif isinstance(raw, str):
        text = raw
    return normalize_text(text)


def conversation_export_messages(
    obj: dict[str, Any],
    *,
    include_roles: set[str] | None = None,
    include_hidden: bool = False,
) -> list[dict[str, str]]:
    """
    Normalize conversation export JSON into an ordered list of {role, text} messages.
    """
    messages = obj.get("messages")
    if isinstance(messages, list) and messages:
        out: list[dict[str, str]] = []
        for item in messages:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip().lower()
            if include_roles and role not in include_roles:
                continue
            text = str(item.get("text") or "")
            out.append({"role": role, "text": text})
        widget_text = _deep_research_widget_export_text(obj)
        if widget_text and (not include_roles or "assistant" in include_roles):
            normalized_existing = {
                normalize_text(normalize_dom_export_text(str(item.get("text") or "")))
                for item in out
                if str(item.get("role") or "").strip().lower() == "assistant"
            }
            normalized_widget = normalize_text(normalize_dom_export_text(widget_text))
            if normalized_widget and normalized_widget not in normalized_existing:
                out.append({"role": "assistant", "text": widget_text})
        if out:
            return out

    mapping = obj.get("mapping")
    if not isinstance(mapping, dict) or not mapping:
        return []

    current = obj.get("current_node")
    node_id = str(current).strip() if isinstance(current, str) and current.strip() else None
    if not node_id:
        for key, node in mapping.items():
            if not isinstance(key, str) or not key:
                continue
            if not isinstance(node, dict):
                continue
            if node.get("children"):
                continue
            if isinstance(node.get("message"), dict):
                node_id = key
                break
    if not node_id:
        return []

    path: list[dict[str, Any]] = []
    seen: set[str] = set()
    while node_id and node_id not in seen:
        seen.add(node_id)
        node = mapping.get(node_id)
        if not isinstance(node, dict):
            break
        path.append(node)
        parent = node.get("parent")
        node_id = str(parent).strip() if isinstance(parent, str) and parent.strip() else ""
    path.reverse()

    out: list[dict[str, str]] = []
    for node in path:
        message = node.get("message")
        if not isinstance(message, dict):
            continue
        author = message.get("author") or {}
        role = str((author.get("role") if isinstance(author, dict) else "") or "").strip().lower()
        if include_roles and role not in include_roles:
            continue
        recipient = str(message.get("recipient") or "").strip().lower()
        if role == "assistant" and recipient and recipient != "all":
            continue
        metadata = message.get("metadata")
        if (not include_hidden) and isinstance(metadata, dict) and metadata.get("is_visually_hidden_from_conversation"):
            continue
        text = message_text_from_export_mapping(message)
        out.append({"role": role, "text": text})
    widget_text = _deep_research_widget_export_text(obj)
    if widget_text and (not include_roles or "assistant" in include_roles):
        normalized_existing = {
            normalize_text(normalize_dom_export_text(str(item.get("text") or "")))
            for item in out
            if str(item.get("role") or "").strip().lower() == "assistant"
        }
        normalized_widget = normalize_text(normalize_dom_export_text(widget_text))
        if normalized_widget and normalized_widget not in normalized_existing:
            out.append({"role": "assistant", "text": widget_text})
    return out


def conversation_export_is_dom_fallback(obj: dict[str, Any]) -> bool:
    meta = obj.get("chatgptrest_export")
    if not isinstance(meta, dict):
        return False
    kind = str(meta.get("export_kind") or "").strip().lower()
    return kind == "dom_messages"


def normalize_dom_export_text(text: str) -> str:
    """
    Normalize DOM-based exports into stable plain text/markdown.
    """
    normalized = normalize_text(text)
    if not normalized:
        return ""

    match = _DOM_COPY_CODE_BLOCK_RE.match(normalized)
    if match:
        lang = match.group(1).strip().lower()
        code = normalize_text(match.group(2))
        return f"```{lang}\n{code}\n```" if code else f"```{lang}\n```"

    match = _DOM_COPY_CODE_GENERIC_RE.match(normalized)
    if match:
        code = normalize_text(match.group(1))
        return f"```\n{code}\n```" if code else "```"

    return normalized


def _looks_like_context_acquisition_failure(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    if not _CONTEXT_ACQUISITION_FAILURE_RE.search(normalized):
        # Also catch "partial bundle walk" stubs that summarize one uploaded
        # file and then promise to continue reviewing later.
        if not (_FILE_CONTEXT_HINT_RE.search(normalized) and _PARTIAL_ANALYSIS_CONTINUATION_RE.search(normalized)):
            return False
    # Keep the heuristic narrow: only flag when the answer is explicitly
    # talking about uploaded files / bundles / extraction context.
    return bool(_FILE_CONTEXT_HINT_RE.search(normalized))


def _extract_review_prompt_anchors(question_text: str) -> set[str]:
    normalized = normalize_text(question_text).lower()
    if not normalized:
        return set()

    anchors: set[str] = set()
    for regex in (_REVIEW_FILELIKE_RE, _REVIEW_COMMIT_RE, _REVIEW_REPO_RE):
        for match in regex.finditer(normalized):
            token = str(match.group(0) or "").strip().lower()
            if not token:
                continue
            anchors.add(token)
            if "/" in token:
                tail = token.rsplit("/", 1)[-1].strip().lower()
                if tail:
                    anchors.add(tail)
    return anchors


def _looks_like_review_shallow_verdict(answer_text: str, question_text: str) -> bool:
    question = normalize_text(question_text)
    if not question or not _REVIEW_REQUIREMENT_RE.search(question):
        return False

    answer = normalize_text(answer_text)

    lower_answer = answer.lower()
    prompt_anchors = _extract_review_prompt_anchors(question)
    anchor_hits = sum(1 for token in prompt_anchors if token and token in lower_answer)
    filelike_hits = len(_REVIEW_FILELIKE_RE.findall(answer))
    path_label_hits = len(_REVIEW_PATH_LABEL_RE.findall(answer))
    approval_hits = len(_REVIEW_GENERIC_APPROVAL_RE.findall(answer))
    has_review_sections = bool(
        re.search(r"(?im)^\s*(?:#{1,4}\s+)?(?:findings|open questions|assumptions|verdict|结论)\b", answer)
    )

    if (
        _REVIEW_PATH_REQUIREMENT_RE.search(question)
        and path_label_hits >= 1
        and filelike_hits == 0
    ):
        return True

    if len(answer) < 600:
        return False

    if (
        has_review_sections
        and approval_hits >= 2
        and filelike_hits == 0
        and anchor_hits == 0
        and ("required reading" in question.lower() or len(prompt_anchors) >= 2)
    ):
        return True

    return False


def render_conversation_export_markdown(
    *,
    export_obj: dict[str, Any],
    conversation_id: str | None = None,
    conversation_url: str | None = None,
) -> str:
    title = str(export_obj.get("title") or "").strip()
    cid = str(export_obj.get("conversation_id") or export_obj.get("id") or conversation_id or "").strip()
    url = str(conversation_url or export_obj.get("conversation_url") or "").strip()
    if not url and cid:
        url = f"https://chatgpt.com/c/{cid}"

    header = title or (cid if cid else "ChatGPT Conversation")
    lines: list[str] = [f"# {header}\n"]
    if url:
        lines.append(f"- 会话：{url}\n")
    lines.append("\n---\n\n")

    messages = conversation_export_messages(
        export_obj,
        include_roles={"user", "assistant"},
        include_hidden=False,
    )
    for message in messages:
        role = str(message.get("role") or "").strip().lower()
        text = str(message.get("text") or "")
        if not text.strip() or role not in {"user", "assistant"}:
            continue
        rendered = normalize_dom_export_text(text)
        lines.append(f"## {role}\n\n")
        lines.append(rendered.rstrip() + "\n")
        lines.append("\n---\n\n")

    return "".join(lines).rstrip() + "\n"


def _common_prefix_len(a: str, b: str, limit: int) -> int:
    size = min(len(a), len(b), max(0, int(limit)))
    idx = 0
    while idx < size and a[idx] == b[idx]:
        idx += 1
    return idx


def _best_matching_user_message_index(
    messages: list[dict[str, str]],
    *,
    question: str,
) -> tuple[int | None, dict[str, Any]]:
    normalized_question = normalize_text(str(question or ""))
    prefix = normalized_question[:200]

    best_idx: int | None = None
    best_score: tuple[int, int] | None = None
    best_meta: dict[str, Any] = {}

    for idx, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        if str(message.get("role") or "").strip().lower() != "user":
            continue
        text = normalize_text(str(message.get("text") or ""))
        if not text:
            continue

        kind = None
        strength = 0
        common_prefix = 0

        if normalized_question and text == normalized_question:
            kind = "exact"
            strength = 10_000
        elif normalized_question and len(normalized_question) >= 40 and normalized_question in text:
            kind = "question_in_text"
            strength = 9_999
        elif normalized_question and len(text) >= 40 and text in normalized_question:
            kind = "text_in_question"
            strength = 9_998
        elif prefix and text.startswith(prefix):
            kind = "prefix"
            strength = 9_997
        else:
            common_prefix = _common_prefix_len(text, normalized_question, 400) if normalized_question else 0
            if common_prefix < 40:
                continue
            kind = "common_prefix"
            strength = int(common_prefix)

        score = (int(strength), int(idx))
        if best_score is None or score > best_score:
            best_score = score
            best_idx = idx
            best_meta = {
                "match_kind": kind,
                "match_strength": int(strength),
                "match_common_prefix_len": int(common_prefix),
                "matched_user_text_preview": text[:200],
            }

    return best_idx, best_meta


def extract_answer_from_conversation_export_obj(
    *,
    obj: dict[str, Any],
    question: str,
    deep_research: bool = False,
    allow_fallback_last_assistant: bool = True,
) -> tuple[str | None, dict[str, Any]]:
    info: dict[str, Any] = {}
    messages = conversation_export_messages(obj, include_roles={"user", "assistant"}, include_hidden=False)
    info["export_messages_len"] = len(messages)
    info["export_last_role"] = str(messages[-1].get("role") or "").strip().lower() if messages else None
    has_in_progress, in_progress_count = conversation_export_has_in_progress(obj)
    info["export_has_in_progress"] = bool(has_in_progress)
    info["export_in_progress_count"] = int(in_progress_count)

    if not messages:
        info["matched"] = False
        info["matched_user_index"] = None
        info["has_assistant_reply_after_match"] = False
        info["answer_source"] = "missing"
        return None, info

    best_idx, match_meta = _best_matching_user_message_index(messages, question=question)
    info.update(match_meta)
    info["matched"] = best_idx is not None
    info["matched_user_index"] = best_idx

    if best_idx is not None:
        candidates: list[str] = []
        candidate_qualities: list[str] = []
        for idx in range(int(best_idx) + 1, len(messages)):
            message = messages[idx]
            if not isinstance(message, dict):
                continue
            role = str(message.get("role") or "").strip().lower()
            if role == "user":
                break
            if role != "assistant":
                continue
            answer = normalize_dom_export_text(str(message.get("text") or ""))
            answer = unwrap_response_envelope_text(answer)
            if not answer.strip():
                continue
            candidates.append(answer)
            candidate_qualities.append(
                classify_answer_quality(
                    answer,
                    answer_chars=len(answer),
                    question_text=question,
                )
            )

        info["has_assistant_reply_after_match"] = bool(candidates)
        if not candidates:
            info["answer_source"] = "matched_but_missing_assistant"
            return None, info
        info["all_candidate_lengths"] = [len(item) for item in candidates]
        info["all_candidate_qualities"] = list(candidate_qualities)

        # Prefer the longest candidate that already looks like a real answer. Extended-thinking
        # models can emit progress updates before the final content, and those updates can be
        # longer than the real answer.
        final_candidates = [
            (idx, answer)
            for idx, (answer, quality) in enumerate(zip(candidates, candidate_qualities))
            if quality == "final"
        ]
        if final_candidates:
            best = max(final_candidates, key=lambda item: (len(item[1]), item[0]))
            info["selection_strategy"] = "longest_final_quality"
        else:
            # Fallback to the historic behavior when every candidate still looks partial.
            best = max(enumerate(candidates), key=lambda item: (len(item[1]), item[0]))
            info["selection_strategy"] = "longest_overall"
        chosen_quality = candidate_qualities[int(best[0])]
        info["answer_quality"] = chosen_quality
        if has_in_progress and chosen_quality != "final":
            info["answer_source"] = "matched_in_progress_partial"
            return None, info
        info["answer_source"] = "matched_window_longest"
        return best[1], info

    info["has_assistant_reply_after_match"] = False
    if not allow_fallback_last_assistant:
        info["answer_source"] = "no_match"
        return None, info

    answer = extract_last_assistant_text(obj=obj)
    if answer:
        info["answer_source"] = "fallback_last_assistant"
        return answer, info

    info["answer_source"] = "missing"
    return None, info


def extract_answer_from_conversation_export(
    *,
    export_path: Path,
    question: str,
    deep_research: bool = False,
    allow_fallback_last_assistant: bool = True,
) -> str | None:
    try:
        obj = json.loads(export_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None

    answer, _ = extract_answer_from_conversation_export_obj(
        obj=obj if isinstance(obj, dict) else {},
        question=question,
        deep_research=deep_research,
        allow_fallback_last_assistant=allow_fallback_last_assistant,
    )
    return answer


def extract_last_assistant_text(*, obj: dict[str, Any]) -> str | None:
    messages = conversation_export_messages(obj, include_roles={"assistant"}, include_hidden=False)
    for message in reversed(messages):
        answer = normalize_dom_export_text(str(message.get("text") or ""))
        answer = unwrap_response_envelope_text(answer)
        if answer.strip():
            return answer
    return None


def conversation_export_has_in_progress(obj: dict[str, Any]) -> tuple[bool, int]:
    """Check if the conversation export has any in_progress messages.

    Extended-thinking models (GPT-5.4 Pro) produce multi-turn 'thoughts' messages
    that remain ``in_progress`` while the model is actively generating. This signal
    can be used by the wait phase to avoid premature stall detection.
    """
    mapping = obj.get("mapping")
    if not isinstance(mapping, dict) or not mapping:
        return False, 0
    count = 0
    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        msg = node.get("message")
        if isinstance(msg, dict) and str(msg.get("status") or "").strip().lower() == "in_progress":
            count += 1
    return count > 0, count


def classify_answer_quality(
    answer_text: str,
    *,
    answer_chars: int | None = None,
    all_candidate_lengths: list[int] | None = None,
    question_text: str | None = None,
) -> str:
    """Classify the quality of an extracted answer.

    Returns one of:
      - ``"final"``: answer appears to be a substantive response.
      - ``"suspect_meta_commentary"``: answer looks like self-referential
        process description ("I'll start by...", "I'm now at the point...")
        rather than actual findings.
      - ``"suspect_context_acquisition_failure"``: answer explains that the
        model could not retrieve/open the provided files or asks for the same
        uploads/context again instead of answering.
      - ``"suspect_short_answer"``: answer is suspiciously short with no
        structural content.
      - ``"suspect_review_shallow_verdict"``: answer looks like a generic
        review verdict that failed to cite the concrete material the prompt
        explicitly required.

    The heuristic is deliberately conservative — it only flags when multiple
    signals align (short + no structure + meta-commentary opener).
    """
    text = str(answer_text or "").strip()
    chars = answer_chars if isinstance(answer_chars, int) else len(text)

    # Very short answers are suspect regardless
    if chars < 100:
        return "suspect_short_answer"

    # Uploaded-file / bundle retrieval failures are not final answers even
    # when the model phrases them politely in several sentences.
    if _looks_like_context_acquisition_failure(text):
        return "suspect_context_acquisition_failure"

    if question_text and _looks_like_review_shallow_verdict(text, question_text):
        return "suspect_review_shallow_verdict"

    # ── Meta-commentary detection ────────────────────────────────────
    # GPT-5.4 Pro extended thinking emits self-referential process
    # descriptions as visible text while the real reasoning happens in
    # invisible ``thoughts`` content.  Typical patterns:
    _META_OPENERS = re.compile(
        r"^(?:"
        r"I'll (?:start|begin|first|now) (?:by|with)|"
        r"I'm (?:now |currently |going to |separating |looking |at the point )|"
        r"Let me (?:start|begin|first|now|check|review|look|read|analyze|examine)|"
        r"I need to |"
        r"I want to (?:start|begin|first)|"
        r"(?:The|My) (?:main |first |next )?(?:blocker|step|task|approach|goal|plan) (?:is|here)|"
        r"I (?:should|will|can) (?:start|begin|first)"
        r")",
        re.IGNORECASE,
    )

    # Structural markers that indicate real content (not meta-commentary)
    has_headers = bool(re.search(r"^#{1,4}\s", text, re.MULTILINE))
    has_bullets = bool(re.search(r"^[\s]*[-*•]\s", text, re.MULTILINE))
    has_numbered = bool(re.search(r"^[\s]*\d+[.)]\s", text, re.MULTILINE))
    has_code_block = "```" in text
    has_table = bool(re.search(r"\|.*\|.*\|", text))
    structural_markers = sum([has_headers, has_bullets, has_numbered, has_code_block, has_table])
    sentence_like_chunks = [
        chunk.strip()
        for chunk in re.split(r"(?:[。！？!?]+|\.\s+)", text)
        if chunk.strip()
    ]
    sentence_like_count = len(sentence_like_chunks)

    is_meta_opener = bool(_META_OPENERS.match(text))

    # Multi-signal gating: flag only when short + no structure + meta opener
    if chars < 800 and is_meta_opener and structural_markers == 0:
        return "suspect_meta_commentary"

    # Even longer text can be suspect if ALL candidates are short meta-comments
    if all_candidate_lengths and all(c < 600 for c in all_candidate_lengths) and is_meta_opener:
        return "suspect_meta_commentary"

    # Concise but complete answers are common on the hot path. If the text has
    # several sentence-like chunks and no meta opener, treat it as final even
    # when it lacks markdown structure.
    if structural_markers == 0 and not is_meta_opener:
        if chars >= 140 and sentence_like_count >= 3:
            return "final"

    # Short without any structure is still suspect
    if chars < 400 and structural_markers == 0 and sentence_like_count < 3:
        return "suspect_short_answer"

    return "final"


__all__ = [
    "classify_answer_quality",
    "conversation_export_has_in_progress",
    "conversation_export_is_dom_fallback",
    "conversation_export_messages",
    "extract_answer_from_conversation_export",
    "extract_answer_from_conversation_export_obj",
    "extract_last_assistant_text",
    "message_text_from_export_mapping",
    "normalize_dom_export_text",
    "normalize_text",
    "render_conversation_export_markdown",
    "unwrap_response_envelope_text",
]
