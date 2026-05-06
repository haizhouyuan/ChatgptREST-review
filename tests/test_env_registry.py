"""Tests for chatgptrest.core.env — centralized env var registry."""
from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

from chatgptrest.core.env import (
    EnvType,
    EnvVar,
    _effective_sensitive,
    _is_sensitive_name,
    coerce_int,
    dump_all,
    get_bool,
    get_float,
    get_int,
    get_str,
    REGISTRY,
    _BY_NAME,
)


# ---------------------------------------------------------------------------
# Registry integrity
# ---------------------------------------------------------------------------

class TestRegistryIntegrity:
    def test_no_duplicate_names(self) -> None:
        names = [v.name for v in REGISTRY]
        assert len(names) == len(set(names)), f"duplicate names: {[n for n in names if names.count(n) > 1]}"

    def test_all_names_start_with_prefix(self) -> None:
        allowed_prefixes = ("CHATGPTREST_", "OPENMIND_")
        for v in REGISTRY:
            assert v.name.startswith(allowed_prefixes), f"{v.name} missing allowed prefix"

    def test_by_name_matches_registry(self) -> None:
        assert len(_BY_NAME) == len(REGISTRY)


# ---------------------------------------------------------------------------
# get_bool
# ---------------------------------------------------------------------------

class TestGetBool:
    def test_missing_env_returns_default_true(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHATGPTREST_BLOCK_PRO_SMOKE_TEST", None)
            assert get_bool("CHATGPTREST_BLOCK_PRO_SMOKE_TEST") is True

    def test_truthy_values(self) -> None:
        for val in ("1", "true", "True", "TRUE", "yes", "y", "on"):
            with mock.patch.dict(os.environ, {"CHATGPTREST_BLOCK_PRO_SMOKE_TEST": val}):
                assert get_bool("CHATGPTREST_BLOCK_PRO_SMOKE_TEST") is True, f"failed for {val!r}"

    def test_falsy_values(self) -> None:
        for val in ("0", "false", "False", "no", "n", "off"):
            with mock.patch.dict(os.environ, {"CHATGPTREST_BLOCK_PRO_SMOKE_TEST": val}):
                assert get_bool("CHATGPTREST_BLOCK_PRO_SMOKE_TEST") is False, f"failed for {val!r}"

    def test_unrecognised_returns_default_not_false(self) -> None:
        """Critical: Finding-3 — unrecognised values must return spec.default, not False."""
        with mock.patch.dict(os.environ, {"CHATGPTREST_BLOCK_PRO_SMOKE_TEST": "garbage"}):
            # spec.default is True for this var
            assert get_bool("CHATGPTREST_BLOCK_PRO_SMOKE_TEST") is True

    def test_empty_string_returns_default(self) -> None:
        with mock.patch.dict(os.environ, {"CHATGPTREST_BLOCK_PRO_SMOKE_TEST": "  "}):
            assert get_bool("CHATGPTREST_BLOCK_PRO_SMOKE_TEST") is True

    def test_unknown_var_defaults_false(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHATGPTREST_UNKNOWN_BOOL_VAR_XYZ", None)
            assert get_bool("CHATGPTREST_UNKNOWN_BOOL_VAR_XYZ") is False


# ---------------------------------------------------------------------------
# get_int
# ---------------------------------------------------------------------------

class TestGetInt:
    def test_missing_returns_default(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS", None)
            assert get_int("CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS") == 61

    def test_valid_int(self) -> None:
        with mock.patch.dict(os.environ, {"CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS": "120"}):
            assert get_int("CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS") == 120

    def test_invalid_returns_default(self) -> None:
        with mock.patch.dict(os.environ, {"CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS": "abc"}):
            assert get_int("CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS") == 61

    def test_min_clamp(self) -> None:
        with mock.patch.dict(os.environ, {"CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS": "-5"}):
            assert get_int("CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS") == 0  # min_value=0


# ---------------------------------------------------------------------------
# get_float
# ---------------------------------------------------------------------------

class TestGetFloat:
    def test_missing_returns_default(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHATGPTREST_RCLONE_TIMEOUT_SECONDS", None)
            assert get_float("CHATGPTREST_RCLONE_TIMEOUT_SECONDS") == 20.0

    def test_clamped(self) -> None:
        with mock.patch.dict(os.environ, {"CHATGPTREST_RCLONE_TIMEOUT_SECONDS": "1.0"}):
            assert get_float("CHATGPTREST_RCLONE_TIMEOUT_SECONDS") == 5.0  # min_value=5.0


# ---------------------------------------------------------------------------
# get_str
# ---------------------------------------------------------------------------

class TestGetStr:
    def test_missing_returns_default(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHATGPTREST_DB_PATH", None)
            assert get_str("CHATGPTREST_DB_PATH") == "state/jobdb.sqlite3"

    def test_present(self) -> None:
        with mock.patch.dict(os.environ, {"CHATGPTREST_DB_PATH": " /tmp/test.db "}):
            assert get_str("CHATGPTREST_DB_PATH") == "/tmp/test.db"


# ---------------------------------------------------------------------------
# coerce_int
# ---------------------------------------------------------------------------

class TestCoerceInt:
    def test_valid(self) -> None:
        assert coerce_int("42", 0) == 42

    def test_invalid(self) -> None:
        assert coerce_int("abc", 99) == 99

    def test_none(self) -> None:
        assert coerce_int(None, 7) == 7


# ---------------------------------------------------------------------------
# Sensitivity detection
# ---------------------------------------------------------------------------

class TestSensitivity:
    def test_explicit_sensitive(self) -> None:
        spec = _BY_NAME["CHATGPTREST_API_TOKEN"]
        assert _effective_sensitive(spec) is True

    def test_auto_detect_by_name(self) -> None:
        assert _is_sensitive_name("CHATGPTREST_API_TOKEN") is True
        assert _is_sensitive_name("CHATGPTREST_DB_PATH") is False
        assert _is_sensitive_name("CHATGPTREST_RCLONE_PROXY") is True  # PROXY keyword

    def test_non_sensitive_var(self) -> None:
        spec = _BY_NAME["CHATGPTREST_DB_PATH"]
        assert _effective_sensitive(spec) is False


# ---------------------------------------------------------------------------
# dump_all
# ---------------------------------------------------------------------------

class TestDumpAll:
    def test_sensitive_redacted(self) -> None:
        with mock.patch.dict(os.environ, {"CHATGPTREST_API_TOKEN": "super-secret-123"}):
            result = dump_all()
        entry = result["CHATGPTREST_API_TOKEN"]
        assert entry["current"] == "***"
        assert entry["effective"] == "***"
        assert entry["default"] == "***"
        assert entry["sensitive"] is True

    def test_non_sensitive_shown(self) -> None:
        with mock.patch.dict(os.environ, {"CHATGPTREST_DB_PATH": "/tmp/test.db"}):
            result = dump_all()
        entry = result["CHATGPTREST_DB_PATH"]
        assert entry["current"] == "/tmp/test.db"
        assert entry["effective"] == "/tmp/test.db"
        assert entry["sensitive"] is False

    def test_all_registry_entries_present(self) -> None:
        result = dump_all()
        for spec in REGISTRY:
            assert spec.name in result, f"missing from dump_all: {spec.name}"

    def test_float_type_works(self) -> None:
        """Finding-4: dump_all must correctly handle FLOAT type."""
        with mock.patch.dict(os.environ, {"CHATGPTREST_RCLONE_TIMEOUT_SECONDS": "15.5"}):
            result = dump_all()
        entry = result["CHATGPTREST_RCLONE_TIMEOUT_SECONDS"]
        assert entry["type"] == "float"
        assert entry["effective"] == 15.5


class TestWorkerDefaultParity:
    """Codex Review Finding #3: assert env.py defaults match worker.py callsites."""

    def test_all_worker_env_vars_in_registry(self) -> None:
        """Every _truthy_env / _env_int call in worker.py must be registered."""
        import re
        worker_path = Path(__file__).resolve().parents[1] / "chatgptrest" / "worker" / "worker.py"
        content = worker_path.read_text(encoding="utf-8")
        truthy = re.findall(r'_truthy_env\(\s*"(CHATGPTREST_\w+)"', content)
        env_int = re.findall(r'_env_int\(\s*"(CHATGPTREST_\w+)"', content)
        all_vars = set(truthy + env_int)
        registry_names = {v.name for v in REGISTRY}
        missing = all_vars - registry_names
        assert not missing, f"worker.py vars missing from REGISTRY: {missing}"

    def test_critical_bool_defaults_match_worker(self) -> None:
        """Previously-drifted defaults must now match runtime."""
        by_name = {v.name: v for v in REGISTRY}
        # These 4 were False in env.py but True in worker.py — now fixed
        assert by_name["CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_APPLY_ACTIONS"].default is True
        assert by_name["CHATGPTREST_WAIT_NO_PROGRESS_GUARD"].default is True
        assert by_name["CHATGPTREST_RESCUE_FOLLOWUP_GUARD"].default is True
        assert by_name["CHATGPTREST_ISSUE_AUTOREPORT_ENABLED"].default is True
