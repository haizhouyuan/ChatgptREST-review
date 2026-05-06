"""Tests for chatgptrest.api.routes_metrics — Prometheus /metrics endpoint."""
from __future__ import annotations

from chatgptrest.api.routes_metrics import _escape_label


class TestEscapeLabel:
    def test_plain(self) -> None:
        assert _escape_label("hello") == "hello"

    def test_backslash(self) -> None:
        assert _escape_label("a\\b") == "a\\\\b"

    def test_newline(self) -> None:
        assert _escape_label("a\nb") == "a\\nb"

    def test_double_quote(self) -> None:
        assert _escape_label('a"b') == 'a\\"b'

    def test_combined(self) -> None:
        assert _escape_label('a\\b\n"c') == 'a\\\\b\\n\\"c'
