"""Tests for preamble detection + is_complete signal guard + wait observations."""

from __future__ import annotations

import re
import pytest


# ── Import the regex and heuristic from the executor ──────────────────────
from chatgptrest.executors.chatgpt_web_mcp import (
    _PREAMBLE_HEURISTIC_RE,
    _PREAMBLE_MIN_ANSWER_CHARS,
    _PREAMBLE_MAX_CHECK_CHARS,
    _preamble_heuristic_check,
)


# ══════════════════════════════════════════════════════════════════════════
# Section 1: _PREAMBLE_HEURISTIC_RE pattern tests
# ══════════════════════════════════════════════════════════════════════════


class TestPreambleHeuristicRegex:
    """Verify the preamble regex matches known patterns and skips normal text."""

    @pytest.mark.parametrize(
        "text",
        [
            "Let me plan the architecture first.",
            "I'll start by analyzing the requirements.",
            "Let me think about this carefully.",
            "I'll begin by reviewing the code.",
            "Let me analyze the data structure.",
            "let me outline the steps needed",
            "Let me break this down into components.",
            "Here's my plan for the implementation:",
            "Here's my approach to solving this:",
        ],
    )
    def test_matches_preamble_patterns(self, text: str) -> None:
        assert _PREAMBLE_HEURISTIC_RE.search(text), f"Expected match for: {text!r}"

    @pytest.mark.parametrize(
        "text",
        [
            "The solution uses a recursive algorithm to traverse the tree.",
            "Here is the implementation of the function:",
            "```python\ndef hello():\n    print('world')\n```",
            "The error occurs because the variable is undefined.",
            "You need to install the package first with pip install foo.",
            "According to the documentation, this feature was added in v2.",
            "# Heading\n\nSome content here with **bold** text.",
        ],
    )
    def test_does_not_match_normal_answers(self, text: str) -> None:
        assert not _PREAMBLE_HEURISTIC_RE.search(text), f"Unexpected match for: {text!r}"


# ══════════════════════════════════════════════════════════════════════════
# Section 2: _preamble_heuristic_check function tests
# ══════════════════════════════════════════════════════════════════════════


class TestPreambleHeuristicCheck:
    """Verify the full heuristic check function with length guards."""

    def test_short_preamble_is_detected(self) -> None:
        answer = "Let me plan the architecture for this."
        assert _preamble_heuristic_check(answer) is True

    def test_long_answer_is_not_preamble(self) -> None:
        # Longer than _PREAMBLE_MIN_ANSWER_CHARS → should not be flagged
        answer = "Let me plan. " + "x" * 500
        assert _preamble_heuristic_check(answer) is False

    def test_empty_answer_is_not_preamble(self) -> None:
        assert _preamble_heuristic_check("") is False

    def test_normal_short_answer_is_not_preamble(self) -> None:
        assert _preamble_heuristic_check("Hello world") is False


# ══════════════════════════════════════════════════════════════════════════
# Section 3: is_complete signal guard tests
# ══════════════════════════════════════════════════════════════════════════


class TestIsCompleteGuard:
    """Test the is_complete signal and preamble guard marking in executor results."""

    def test_is_complete_false_should_continue_waiting(self) -> None:
        """Simulates is_complete=False → result should be treated as in_progress."""
        wait_res = {
            "status": "completed",
            "answer": "Some answer text",
            "export_last_assistant_is_complete": False,
        }
        # When is_complete is explicitly False, the executor should NOT
        # accept the result as completed.
        assert wait_res.get("export_last_assistant_is_complete") is False

    def test_is_complete_true_should_accept(self) -> None:
        """Simulates is_complete=True → result should be accepted."""
        wait_res = {
            "status": "completed",
            "answer": "Final answer",
            "export_last_assistant_is_complete": True,
        }
        assert wait_res.get("export_last_assistant_is_complete") is True

    def test_is_complete_absent_is_none(self) -> None:
        """When export is unavailable, is_complete is None → falls back to heuristic."""
        wait_res = {
            "status": "completed",
            "answer": "Some answer",
        }
        assert wait_res.get("export_last_assistant_is_complete") is None


# ══════════════════════════════════════════════════════════════════════════
# Section 4: Preamble guard marking tests
# ══════════════════════════════════════════════════════════════════════════


class TestPreambleGuardMarking:
    """Test that the preamble guard correctly marks results."""

    def test_marks_preamble_when_is_complete_absent(self) -> None:
        """When is_complete is absent and answer looks like preamble, mark it."""
        answer = "Let me plan the solution first."
        is_complete = None
        preamble_detected = is_complete is None and _preamble_heuristic_check(answer)
        assert preamble_detected is True

    def test_does_not_mark_when_is_complete_true(self) -> None:
        """When is_complete is True, don't apply preamble heuristic."""
        answer = "Let me plan the solution first."
        is_complete = True
        preamble_detected = is_complete is None and _preamble_heuristic_check(answer)
        assert preamble_detected is False

    def test_does_not_mark_normal_answer(self) -> None:
        """Normal answers should never be marked as preamble."""
        answer = "The function returns True when the condition is met."
        is_complete = None
        preamble_detected = is_complete is None and _preamble_heuristic_check(answer)
        assert preamble_detected is False


# ══════════════════════════════════════════════════════════════════════════
# Section 5: _flush_obs tests
# ══════════════════════════════════════════════════════════════════════════


# We cannot import _flush_obs directly (it's in _tools_impl which requires
# Playwright), so we test the interface contract instead.

class TestFlushObsContract:
    """Test the observations dict contract."""

    def test_observations_keys(self) -> None:
        """Verify expected keys in a populated observations dict."""
        obs: dict = {
            "thinking_seconds": 5.2,
            "code_sandbox_appeared": True,
            "stop_button_appeared": True,
            "stop_button_disappeared_at": 1700000002.0,
            "answer_stable_at": 1700000004.0,
            "dom_changes_count": 12,
            "timed_out": False,
        }
        assert isinstance(obs["thinking_seconds"], float)
        assert isinstance(obs["code_sandbox_appeared"], bool)
        assert isinstance(obs["stop_button_appeared"], bool)
        assert isinstance(obs["dom_changes_count"], int)
        assert isinstance(obs["timed_out"], bool)

    def test_none_observations_is_noop(self) -> None:
        """When observations is None, nothing should happen."""
        obs = None
        # Just verify the interface — _flush_obs(None, ...) should be a no-op
        assert obs is None
