"""Tests for the longest-candidate extraction strategy in conversation exports."""
from __future__ import annotations

from chatgptrest.core.conversation_exports import (
    extract_answer_from_conversation_export_obj,
    conversation_export_has_in_progress,
)


def _make_export(messages: list[dict]) -> dict:
    """Build a minimal conversation export with the flat messages format."""
    return {"messages": messages}


def _make_mapping_export(nodes: list[tuple[str, str, str, str]]) -> dict:
    """Build a minimal mapping export with explicit status values."""
    root = "client-created-root"
    mapping: dict[str, dict] = {root: {"id": root, "message": None, "parent": None, "children": []}}
    parent = root
    current = root
    for idx, (role, text, status, content_type) in enumerate(nodes, start=1):
        node_id = f"node-{idx}"
        if content_type == "text":
            content = {"content_type": "text", "parts": [text]}
        else:
            content = {"content_type": content_type, content_type: []}
        msg = {
            "id": node_id,
            "author": {"role": role, "name": None, "metadata": {}},
            "create_time": None,
            "update_time": None,
            "content": content,
            "status": status,
            "end_turn": True,
            "weight": 1.0,
            "metadata": {},
            "recipient": "all",
            "channel": None,
        }
        mapping[node_id] = {"id": node_id, "message": msg, "parent": parent, "children": []}
        mapping[parent]["children"].append(node_id)
        parent = node_id
        current = node_id
    return {
        "title": "t",
        "create_time": 1.0,
        "update_time": 2.0,
        "mapping": mapping,
        "current_node": current,
        "conversation_id": "conv-1",
        "id": "conv-1",
    }


def test_longest_candidate_wins_over_last() -> None:
    """When multiple assistant messages exist, the longest should be returned."""
    export = _make_export([
        {"role": "user", "text": "Hello world test question"},
        {"role": "assistant", "text": "Short progress update"},  # 21 chars
        {"role": "assistant", "text": "This is the real detailed answer with much more content that should be the one selected by the extraction logic because it is the longest."},  # ~140 chars
        {"role": "assistant", "text": "Brief summary"},  # 13 chars — this was returned by old candidates[-1] logic
    ])
    answer, info = extract_answer_from_conversation_export_obj(
        obj=export,
        question="Hello world test question",
        deep_research=False,
    )
    assert answer is not None
    assert "detailed answer" in answer
    assert info.get("answer_source") == "matched_window_longest"


def test_single_candidate_works() -> None:
    """Single candidate should still work correctly."""
    export = _make_export([
        {"role": "user", "text": "My question here"},
        {"role": "assistant", "text": "The one and only answer"},
    ])
    answer, info = extract_answer_from_conversation_export_obj(
        obj=export,
        question="My question here",
        deep_research=False,
    )
    assert answer == "The one and only answer"
    assert info.get("answer_source") == "matched_window_longest"


def test_longest_final_quality_candidate_beats_longer_meta_commentary() -> None:
    """Prefer a structurally real answer over a longer progress update."""
    export = _make_export([
        {"role": "user", "text": "Review this bundle and tell me what matters."},
        {
            "role": "assistant",
            "text": (
                "I'll start by mapping the code paths, checking the current control boundaries, "
                "and confirming what is already implemented before I give the final recommendation."
            ),
        },
        {
            "role": "assistant",
            "text": (
                "## Findings\n\n"
                "1. The current flow already has issue capture.\n"
                "2. The missing piece is outcome evaluation.\n"
                "3. Promotion needs canary and rollback."
            ),
        },
    ])
    answer, info = extract_answer_from_conversation_export_obj(
        obj=export,
        question="Review this bundle and tell me what matters.",
        deep_research=False,
    )
    assert answer is not None
    assert answer.startswith("## Findings")
    assert info.get("selection_strategy") == "longest_final_quality"
    assert info.get("answer_quality") == "final"


def test_in_progress_partial_meta_commentary_returns_none() -> None:
    """Do not return preamble-like export text while the conversation is still in progress."""
    export = _make_mapping_export([
        ("user", "Please review the attached code bundle.", "finished_successfully", "text"),
        (
            "assistant",
            (
                "I’m unpacking the bundle and mapping the code paths for iteration, tool use, "
                "and control boundaries before I provide the final answer."
            ),
            "finished_successfully",
            "text",
        ),
        ("assistant", "", "in_progress", "thoughts"),
    ])
    answer, info = extract_answer_from_conversation_export_obj(
        obj=export,
        question="Please review the attached code bundle.",
        deep_research=False,
        allow_fallback_last_assistant=False,
    )
    assert answer is None
    assert info.get("export_has_in_progress") is True
    assert info.get("answer_source") == "matched_in_progress_partial"
    assert info.get("answer_quality") in {"suspect_meta_commentary", "suspect_short_answer"}


def test_empty_candidates_filtered() -> None:
    """Empty assistant messages should be filtered, not returned."""
    export = _make_export([
        {"role": "user", "text": "Question with thinking"},
        {"role": "assistant", "text": ""},  # empty thinking message
        {"role": "assistant", "text": ""},  # empty thinking message
        {"role": "assistant", "text": "Final answer here"},
    ])
    answer, info = extract_answer_from_conversation_export_obj(
        obj=export,
        question="Question with thinking",
        deep_research=False,
    )
    assert answer == "Final answer here"


def test_in_progress_detection() -> None:
    """Detect in_progress messages in conversation export mapping."""
    export_with = {
        "mapping": {
            "a": {"message": {"status": "finished_successfully"}},
            "b": {"message": {"status": "in_progress"}},
            "c": {"message": {"status": "in_progress"}},
        }
    }
    has, count = conversation_export_has_in_progress(export_with)
    assert has is True
    assert count == 2

    export_without = {
        "mapping": {
            "a": {"message": {"status": "finished_successfully"}},
            "b": {"message": {"status": "finished_successfully"}},
        }
    }
    has, count = conversation_export_has_in_progress(export_without)
    assert has is False
    assert count == 0


def test_in_progress_detection_empty() -> None:
    """Empty exports should report no in_progress."""
    has, count = conversation_export_has_in_progress({})
    assert has is False
    assert count == 0


# ── Tests for classify_answer_quality ─────────────────────────────────


from chatgptrest.core.conversation_exports import classify_answer_quality


def test_meta_commentary_detected() -> None:
    """Real meta-commentary from ChatGPT Pro job should be flagged."""
    meta = (
        "I'll start by aligning the review material with the actual diff "
        "and key implementation paths, checking both whether the validation "
        "evidence holds up and whether the code truly fixes production "
        "realities rather than just making the full-flow harness pass."
    )
    assert classify_answer_quality(meta) == "suspect_meta_commentary"


def test_meta_commentary_let_me() -> None:
    """'Let me' opener with enough length should be detected."""
    meta = (
        "Let me check the conversation export and extract the relevant "
        "information from the previous discussion thread before responding."
    )
    assert classify_answer_quality(meta) == "suspect_meta_commentary"


def test_meta_commentary_im_now() -> None:
    """'I'm now at...' opener should be detected."""
    meta = (
        "I'm now at the point where the signal is clearer: the webhook "
        "header case-sensitivity fix looks production-relevant."
    )
    assert classify_answer_quality(meta) == "suspect_meta_commentary"


def test_real_review_passes() -> None:
    """A real review with structure should be classified as final."""
    review = (
        "## Findings\n\n"
        "### Critical\n"
        "- `_connect()` returns None due to indentation bug\n"
        "- Tests failing: 17 failures across 2 test files\n\n"
        "### High\n"
        "- sdnotify missing from dependencies\n\n"
        "## Recommendation\n"
        "Fix the indentation, expand the compat shim."
    )
    assert classify_answer_quality(review) == "final"


def test_meta_commentary_with_structure_passes() -> None:
    """Meta-commentary opener WITH structural markers should pass."""
    mixed = (
        "I'll start by reviewing the changes:\n\n"
        "## Summary\n"
        "- Fix 1: _connect() restored\n"
        "- Fix 2: __getattr__ expanded\n\n"
        "### Details\n"
        "The changes look correct."
    )
    assert classify_answer_quality(mixed) == "final"


def test_short_no_structure_is_suspect() -> None:
    """Short answer without any structured content is suspect."""
    short = "The changes look fine to me."
    assert classify_answer_quality(short) == "suspect_short_answer"


def test_very_short_is_always_suspect() -> None:
    """Very short answers are always suspect."""
    assert classify_answer_quality("ok") == "suspect_short_answer"
    assert classify_answer_quality("") == "suspect_short_answer"


def test_all_candidates_short_meta() -> None:
    """When all candidates are short meta-commentary, flag it."""
    meta = (
        "I'll start by checking the diff for correctness and comparing "
        "against the known test baseline to identify any deviations."
    )
    assert classify_answer_quality(
        meta,
        all_candidate_lengths=[525, 436, 351],
    ) == "suspect_meta_commentary"


def test_normal_length_passes() -> None:
    """A 1000+ char plain text answer should pass as final."""
    long_text = "This is a detailed analysis. " * 50  # ~1450 chars
    assert classify_answer_quality(long_text) == "final"
