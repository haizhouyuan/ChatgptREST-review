"""D6: Security tests — filename sanitizer, path traversal, env allowlist."""

from __future__ import annotations

import pytest

from paperclip_labebe.labebe_orchestrator import safe_slug
from paperclip_planning.planning_orchestrator import safe_slug as planning_safe_slug
from paperclip_memory.memory_orchestrator import _safe_slug as memory_safe_slug


class TestFilenameSanitizer:
    @pytest.mark.parametrize(
        "input_val,expected",
        [
            ("hello-world", "hello-world"),
            ("hello world", "hello_world"),
            ("../etc/passwd", "etc_passwd"),
            ("a..b", "a__b"),
            ("test_", "test"),
            ("_test", "test"),
            ("very_long_string_that_exceeds_limit", "very_long_string_that_exceeds_li"),
        ],
    )
    def test_safe_slug(self, input_val, expected):
        assert safe_slug(input_val, max_len=32) == expected

    def test_path_traversal_blocked(self):
        malicious = "../../../etc/shadow"
        result = safe_slug(malicious)
        assert ".." not in result
        assert "/" not in result
        # Should not be able to traverse upward
        assert not result.startswith(".")

    def test_unicode_kept_or_underscored(self):
        # Python \w includes unicode word chars, so 世界 may be kept
        result = safe_slug("hello世界")
        assert "hello" in result
        assert ".." not in result
        assert "/" not in result


class TestModelDownloadSecurity:
    def test_delete_rejects_unknown_model_id(self):
        from runtime_allocator.model_download import ModelDownloader
        dl = ModelDownloader()
        # model_id not in registry → should not delete
        assert dl.delete("../../../etc") is False

    def test_delete_path_containment(self):
        from runtime_allocator.model_download import ModelDownloader
        import tempfile
        from pathlib import Path

        tmpdir = tempfile.mkdtemp()
        dl = ModelDownloader(model_dir=Path(tmpdir))
        # Even if model_id tries traversal, resolve() check blocks it
        assert dl.delete("mimo-7b/../../../etc") is False


class TestEnvResolution:
    def test_resolve_env_basic(self):
        from runtime_allocator.runtime_probe import _resolve_env
        import os
        os.environ["TEST_VAR"] = "hello"
        assert _resolve_env("${TEST_VAR}") == "hello"
        del os.environ["TEST_VAR"]

    def test_resolve_env_with_default(self):
        from runtime_allocator.runtime_probe import _resolve_env
        assert _resolve_env("${NONEXISTENT_VAR:default_val}") == "default_val"

    def test_resolve_env_no_substitution(self):
        from runtime_allocator.runtime_probe import _resolve_env
        assert _resolve_env("http://localhost:8000") == "http://localhost:8000"
