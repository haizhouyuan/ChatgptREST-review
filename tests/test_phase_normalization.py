"""Tests for chatgptrest.core.phase — two-tier phase normalization."""
from __future__ import annotations

from chatgptrest.core.phase import normalize_db_phase, normalize_execution_phase


class TestNormalizeDbPhase:
    def test_send(self) -> None:
        assert normalize_db_phase("send") == "send"

    def test_wait(self) -> None:
        assert normalize_db_phase("wait") == "wait"

    def test_full_becomes_send(self) -> None:
        """DB layer does NOT support 'full' — defaults to 'send'."""
        assert normalize_db_phase("full") == "send"

    def test_none(self) -> None:
        assert normalize_db_phase(None) == "send"

    def test_empty(self) -> None:
        assert normalize_db_phase("") == "send"

    def test_case_insensitive(self) -> None:
        assert normalize_db_phase("WAIT") == "wait"
        assert normalize_db_phase("Send") == "send"


class TestNormalizeExecutionPhase:
    def test_send(self) -> None:
        assert normalize_execution_phase("send") == "send"

    def test_wait(self) -> None:
        assert normalize_execution_phase("wait") == "wait"

    def test_full(self) -> None:
        assert normalize_execution_phase("full") == "full"

    def test_all_alias(self) -> None:
        assert normalize_execution_phase("all") == "full"

    def test_both_alias(self) -> None:
        assert normalize_execution_phase("both") == "full"

    def test_none_defaults_full(self) -> None:
        assert normalize_execution_phase(None) == "full"

    def test_empty_defaults_full(self) -> None:
        assert normalize_execution_phase("") == "full"

    def test_case_insensitive(self) -> None:
        assert normalize_execution_phase("FULL") == "full"
        assert normalize_execution_phase("All") == "full"
