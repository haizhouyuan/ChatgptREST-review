from __future__ import annotations

import asyncio
import zipfile
from pathlib import Path
from typing import Any

import pytest

from chatgptrest.executors import gemini_web_mcp
from chatgptrest.executors.gemini_web_mcp import GeminiWebMcpExecutor
from chatgptrest.executors.config import GeminiExecutorConfig


def test_gemini_deep_research_uses_deep_research_tool() -> None:
    calls: list[dict[str, Any]] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            return {"status": "in_progress", "answer": "", "conversation_url": "https://gemini.google.com/app/88b014d5748a30d0"}

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job",
            kind="gemini_web.ask",
            input={"question": "research"},
            params={"preset": "pro", "phase": "send", "deep_research": True, "timeout_seconds": 60, "max_wait_seconds": 60, "min_chars": 0},
        )
    )
    assert res.status == "in_progress"
    assert calls
    assert calls[0]["tool_name"] == "gemini_web_deep_research"


def test_gemini_drive_files_prefers_url(monkeypatch: pytest.MonkeyPatch) -> None:
    uploaded = [
        {
            "src_path": "/tmp/a.md",
            "drive_name": "job_01_a.md",
            "drive_id": "abc123",
            "drive_url": "https://drive.google.com/open?id=abc123",
        }
    ]

    def _fake_upload(*, job_id: str, file_paths: list[str]) -> list[dict[str, Any]]:  # noqa: ARG001
        return list(uploaded)

    monkeypatch.setattr(gemini_web_mcp, "_upload_files_to_gdrive", _fake_upload)

    calls: list[dict[str, Any]] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            return {"status": "completed", "answer": "ok", "conversation_url": "https://gemini.google.com/app"}

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]

    res = asyncio.run(
        executor.run(
            job_id="job",
            kind="gemini_web.ask",
            input={"question": "read", "file_paths": ["/tmp/a.md"]},
            params={"preset": "pro", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0},
        )
    )
    assert res.status == "completed"
    assert calls
    assert calls[0]["tool_name"] == "gemini_web_ask_pro"
    assert calls[0]["tool_args"]["drive_files"] == ["https://drive.google.com/open?id=abc123"]


def test_gemini_drive_files_missing_url_is_cooldown_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    uploaded = [
        {
            "src_path": "/tmp/a.md",
            "drive_name": "job_01_a.md",
            "drive_id": "",
            "drive_url": "",
        }
    ]

    def _fake_upload(*, job_id: str, file_paths: list[str]) -> list[dict[str, Any]]:  # noqa: ARG001
        return list(uploaded)

    monkeypatch.setattr(gemini_web_mcp, "_upload_files_to_gdrive", _fake_upload)

    calls: list[dict[str, Any]] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            return {"status": "completed", "answer": "ok", "conversation_url": "https://gemini.google.com/app"}

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]

    res = asyncio.run(
        executor.run(
            job_id="job",
            kind="gemini_web.ask",
            input={"question": "read", "file_paths": ["/tmp/a.md"]},
            params={"preset": "pro", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0},
        )
    )
    assert res.status == "cooldown"
    assert not calls


def test_gemini_drive_files_falls_back_to_name_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    uploaded = [
        {
            "src_path": "/tmp/a.md",
            "drive_name": "job_01_a.md",
            "drive_id": "",
            "drive_url": "",
            "upload_completed": True,
        }
    ]

    def _fake_upload(*, job_id: str, file_paths: list[str]) -> list[dict[str, Any]]:  # noqa: ARG001
        return list(uploaded)

    monkeypatch.setattr(gemini_web_mcp, "_upload_files_to_gdrive", _fake_upload)

    calls: list[dict[str, Any]] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            return {"status": "completed", "answer": "ok", "conversation_url": "https://gemini.google.com/app"}

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]

    res = asyncio.run(
        executor.run(
            job_id="job",
            kind="gemini_web.ask",
            input={"question": "read", "file_paths": ["/tmp/a.md"]},
            params={"preset": "pro", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0, "drive_name_fallback": True},
        )
    )
    assert res.status == "completed"
    assert calls
    assert calls[0]["tool_name"] == "gemini_web_ask_pro"
    assert calls[0]["tool_args"]["drive_files"] == ["job_01_a.md"]


def test_gemini_multiple_text_attachments_collapse_into_bundle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    preprocess_dir = tmp_path / "preprocess"
    monkeypatch.setenv("CHATGPTREST_GEMINI_ATTACHMENT_PREPROCESS_DIR", str(preprocess_dir))
    monkeypatch.setattr(gemini_web_mcp, "_cfg", GeminiExecutorConfig())

    a = tmp_path / "audit_review_package_v2.py"
    b = tmp_path / "audit_code_diff.patch"
    c = tmp_path / "feishu_10_replay_v2_results.json"
    a.write_text("print('hello')\n", encoding="utf-8")
    b.write_text("--- a/x\n+++ b/x\n@@\n-old\n+new\n", encoding="utf-8")
    c.write_text('{"ok": true}\n', encoding="utf-8")

    uploaded_batches: list[list[str]] = []

    def _fake_upload(*, job_id: str, file_paths: list[str]) -> list[dict[str, Any]]:  # noqa: ARG001
        uploaded_batches.append(list(file_paths))
        return [
            {
                "src_path": path,
                "drive_name": Path(path).name,
                "drive_id": f"id-{idx}",
                "drive_url": f"https://drive.google.com/open?id=id-{idx}",
                "upload_completed": True,
            }
            for idx, path in enumerate(file_paths, start=1)
        ]

    monkeypatch.setattr(gemini_web_mcp, "_upload_files_to_gdrive", _fake_upload)

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            assert tool_name == "gemini_web_ask_pro"
            return {"status": "completed", "answer": "ok", "conversation_url": "https://gemini.google.com/app"}

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job",
            kind="gemini_web.ask",
            input={"question": "read", "file_paths": [str(a), str(b), str(c)]},
            params={"preset": "pro", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0},
        )
    )
    assert res.status == "completed"
    assert uploaded_batches == [[str(preprocess_dir / "job" / "GEMINI_ATTACH_BUNDLE.md")]]
    bundle_path = Path(uploaded_batches[0][0])
    content = bundle_path.read_text(encoding="utf-8")
    assert "audit_review_package_v2.py" in content
    assert "audit_code_diff.patch" in content
    assert "feishu_10_replay_v2_results.json" in content


def test_gemini_drive_missing_url_permanent_error_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    uploaded = [
        {
            "src_path": "/tmp/a.md",
            "drive_name": "job_01_a.md",
            "drive_id": "",
            "drive_url": "",
            "drive_error_kind": "permanent",
            "drive_resolve_error": "ConfigMissing: rclone config file not found",
        }
    ]

    def _fake_upload(*, job_id: str, file_paths: list[str]) -> list[dict[str, Any]]:  # noqa: ARG001
        return list(uploaded)

    monkeypatch.setattr(gemini_web_mcp, "_upload_files_to_gdrive", _fake_upload)

    calls: list[dict[str, Any]] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            return {"status": "completed", "answer": "ok", "conversation_url": "https://gemini.google.com/app"}

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]

    res = asyncio.run(
        executor.run(
            job_id="job",
            kind="gemini_web.ask",
            input={"question": "read", "file_paths": ["/tmp/a.md"]},
            params={"preset": "pro", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0},
        )
    )
    assert res.status == "error"
    assert not calls


def test_upload_files_to_gdrive_rejects_large_files(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("hi", encoding="utf-8")
    monkeypatch.setenv("CHATGPTREST_GDRIVE_MAX_FILE_BYTES", "1")
    uploads = gemini_web_mcp._upload_files_to_gdrive(job_id="job", file_paths=[str(p)])  # noqa: SLF001
    assert uploads
    assert uploads[0]["drive_url"] == ""
    assert uploads[0]["drive_error_kind"] == "permanent"
    assert "FileTooLarge" in str(uploads[0]["drive_resolve_error"] or "")


def test_gemini_drive_cleanup_runs_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_GDRIVE_CLEANUP_MODE", "on_success")
    monkeypatch.setattr(gemini_web_mcp, "_cfg", GeminiExecutorConfig())

    uploaded = [
        {
            "src_path": "/tmp/a.md",
            "drive_name": "job_01_a.md",
            "drive_id": "abc123",
            "drive_url": "https://drive.google.com/open?id=abc123",
        }
    ]

    def _fake_upload(*, job_id: str, file_paths: list[str]) -> list[dict[str, Any]]:  # noqa: ARG001
        return list(uploaded)

    monkeypatch.setattr(gemini_web_mcp, "_upload_files_to_gdrive", _fake_upload)

    cleaned: list[dict[str, Any]] = []

    def _fake_cleanup(*, job_id: str, file_paths: list[str]) -> list[dict[str, Any]]:  # noqa: ARG001
        cleaned.append({"job_id": job_id, "file_paths": list(file_paths)})
        return [{"drive_remote_path": "gdrive:chatgptrest_uploads/x", "rclone_deletefile": {"ok": True}}]

    monkeypatch.setattr(gemini_web_mcp, "_gdrive_cleanup_uploaded_files", _fake_cleanup)

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            return {"status": "completed", "answer": "ok", "conversation_url": "https://gemini.google.com/app"}

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job",
            kind="gemini_web.ask",
            input={"question": "read", "file_paths": ["/tmp/a.md"]},
            params={"preset": "pro", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0},
        )
    )
    assert res.status == "completed"
    assert cleaned
    assert isinstance(res.meta, dict)
    assert "drive_cleanup" in res.meta


def test_gemini_github_repo_is_passed_without_import_code() -> None:
    calls: list[dict[str, Any]] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            return {"status": "completed", "answer": "ok", "conversation_url": "https://gemini.google.com/app"}

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job",
            kind="gemini_web.ask",
            input={"question": "read", "github_repo": "https://github.com/org/repo"},
            params={"preset": "pro", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0},
        )
    )
    assert res.status == "completed"
    assert calls
    assert calls[0]["tool_name"] == "gemini_web_ask_pro"
    assert calls[0]["tool_args"]["repo_context_hint"] == "https://github.com/org/repo"
    assert "github_repo" not in calls[0]["tool_args"]
    assert "enable_import_code" not in calls[0]["tool_args"]


def test_gemini_github_repo_is_passed_when_enabled() -> None:
    calls: list[dict[str, Any]] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            return {"status": "completed", "answer": "ok", "conversation_url": "https://gemini.google.com/app"}

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job",
            kind="gemini_web.ask",
            input={"question": "read", "github_repo": "https://github.com/org/repo"},
            params={"preset": "pro", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0, "enable_import_code": True},
        )
    )
    assert res.status == "completed"
    assert calls
    assert calls[0]["tool_name"] == "gemini_web_ask_pro"
    assert calls[0]["tool_args"]["github_repo"] == "https://github.com/org/repo"
    assert calls[0]["tool_args"]["enable_import_code"] is True


def test_gemini_github_repo_still_blocked_for_deep_research() -> None:
    calls: list[dict[str, Any]] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            return {"status": "completed", "answer": "ok", "conversation_url": "https://gemini.google.com/app"}

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job",
            kind="gemini_web.ask",
            input={"question": "read", "github_repo": "https://github.com/org/repo"},
            params={"preset": "pro", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0, "deep_research": True},
        )
    )
    assert res.status == "error"
    assert not calls


def test_gemini_deep_research_attachment_count_is_capped_to_ten(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    files: list[str] = []
    for i in range(12):
        p = tmp_path / f"f{i:02d}.md"
        p.write_text(f"# file {i}\n\nhello {i}\n", encoding="utf-8")
        files.append(p.as_posix())

    captured_upload_paths: list[str] = []

    def _fake_upload(*, job_id: str, file_paths: list[str]) -> list[dict[str, Any]]:  # noqa: ARG001
        captured_upload_paths[:] = list(file_paths)
        out: list[dict[str, Any]] = []
        for idx, raw in enumerate(file_paths):
            out.append(
                {
                    "src_path": raw,
                    "drive_name": Path(raw).name,
                    "drive_id": f"id{idx:02d}",
                    "drive_url": f"https://drive.google.com/open?id=id{idx:02d}",
                    "upload_completed": True,
                }
            )
        return out

    monkeypatch.setattr(gemini_web_mcp, "_upload_files_to_gdrive", _fake_upload)

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            if tool_name == "gemini_web_deep_research":
                return {"status": "in_progress", "answer": "", "conversation_url": "https://gemini.google.com/app/88b014d5748a30d0"}
            return {"status": "completed", "answer": "ok", "conversation_url": "https://gemini.google.com/app/88b014d5748a30d0"}

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job_cap10",
            kind="gemini_web.ask",
            input={"question": "research", "file_paths": files},
            params={"preset": "pro", "deep_research": True, "phase": "send", "timeout_seconds": 60, "max_wait_seconds": 60, "min_chars": 0},
        )
    )
    assert res.status == "in_progress"
    assert 1 <= len(captured_upload_paths) <= 10
    uploaded_names = {Path(p).name for p in captured_upload_paths}
    assert "GEMINI_ATTACH_INDEX.md" in uploaded_names


def test_gemini_deep_research_expands_zip_into_bundle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    zip_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.md", "# Readme\n\nhello zip\n")
        zf.writestr("src/main.py", "print('ok')\n")

    captured_upload_paths: list[str] = []

    def _fake_upload(*, job_id: str, file_paths: list[str]) -> list[dict[str, Any]]:  # noqa: ARG001
        captured_upload_paths[:] = list(file_paths)
        out: list[dict[str, Any]] = []
        for idx, raw in enumerate(file_paths):
            out.append(
                {
                    "src_path": raw,
                    "drive_name": Path(raw).name,
                    "drive_id": f"id{idx:02d}",
                    "drive_url": f"https://drive.google.com/open?id=id{idx:02d}",
                    "upload_completed": True,
                }
            )
        return out

    monkeypatch.setattr(gemini_web_mcp, "_upload_files_to_gdrive", _fake_upload)

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            if tool_name == "gemini_web_deep_research":
                return {"status": "in_progress", "answer": "", "conversation_url": "https://gemini.google.com/app/88b014d5748a30d0"}
            return {"status": "completed", "answer": "ok", "conversation_url": "https://gemini.google.com/app/88b014d5748a30d0"}

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job_zip_expand",
            kind="gemini_web.ask",
            input={"question": "research", "file_paths": [zip_path.as_posix()]},
            params={"preset": "pro", "deep_research": True, "phase": "send", "timeout_seconds": 60, "max_wait_seconds": 60, "min_chars": 0},
        )
    )
    assert res.status == "in_progress"
    names = {Path(p).name for p in captured_upload_paths}
    assert "bundle.zip" not in names
    assert "GEMINI_ATTACH_BUNDLE.md" in names
    assert "GEMINI_ATTACH_INDEX.md" in names


def test_gemini_deep_research_self_check_blocks_when_tool_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append(tool_name)
            if tool_name == "gemini_web_self_check":
                return {
                    "ok": True,
                    "status": "completed",
                    "tools_button": {"visible": True},
                    "tools": [{"text": "Canvas", "checked": False}],
                }
            return {"status": "in_progress", "answer": "", "conversation_url": "https://gemini.google.com/app/88b014d5748a30d0"}

    monkeypatch.setattr(gemini_web_mcp, "McpHttpToolCaller", _DummyToolCaller)

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job_probe_block",
            kind="gemini_web.ask",
            input={"question": "research"},
            params={"preset": "pro", "deep_research": True, "phase": "send", "timeout_seconds": 60, "max_wait_seconds": 60, "min_chars": 0},
        )
    )
    assert res.status == "needs_followup"
    assert calls and calls[0] == "gemini_web_self_check"
    assert "gemini_web_deep_research" not in calls
    assert isinstance(res.meta, dict)
    assert res.meta.get("error_type") == "GeminiDeepResearchToolUnavailable"


def test_gemini_deep_research_self_check_drawer_error_does_not_block(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append(tool_name)
            if tool_name == "gemini_web_self_check":
                return {
                    "ok": True,
                    "status": "completed",
                    "mode_text": "快速",
                    "tools_button": {"visible": True},
                    "tools": [],
                    "error_type": "GeminiToolsDrawerError",
                    "error": "TargetClosedError: ... subtree intercepts pointer events",
                }
            if tool_name == "gemini_web_deep_research":
                return {
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": "https://gemini.google.com/app/88b014d5748a30d0",
                }
            raise AssertionError(f"unexpected tool call: {tool_name}")

    monkeypatch.setattr(gemini_web_mcp, "McpHttpToolCaller", _DummyToolCaller)

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job_probe_uncertain",
            kind="gemini_web.ask",
            input={"question": "research"},
            params={"preset": "pro", "deep_research": True, "phase": "send", "timeout_seconds": 60, "max_wait_seconds": 60, "min_chars": 0},
        )
    )
    assert res.status == "in_progress"
    assert calls and calls[0] == "gemini_web_self_check"
    assert "gemini_web_deep_research" in calls
