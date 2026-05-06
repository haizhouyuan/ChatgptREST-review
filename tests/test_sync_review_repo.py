import importlib.util
import subprocess
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parent.parent / "ops" / "sync_review_repo.py"
_SPEC = importlib.util.spec_from_file_location("sync_review_repo", _MODULE_PATH)
assert _SPEC and _SPEC.loader
sync_review_repo = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sync_review_repo)


def test_default_sync_includes_scripts() -> None:
    assert "scripts" in sync_review_repo.SOURCE_DIRS


def test_allowlisted_sensitive_marker_file_is_not_filtered() -> None:
    allowed = sync_review_repo.REPO_ROOT / "ops" / "sync_review_repo.py"

    assert sync_review_repo.has_sensitive_content(allowed, "ops/sync_review_repo.py") is False


def test_sync_source_files_copies_referenced_script(tmp_path: Path) -> None:
    stats = sync_review_repo.sync_source_files(tmp_path, include_dirs=["scripts"])

    copied = tmp_path / "scripts" / "rebuild_openclaw_openmind_stack.py"
    assert copied.exists()
    assert copied.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3")
    assert stats["files"] >= 1


def test_default_sync_includes_openclaw_extensions() -> None:
    assert "openclaw_extensions" in sync_review_repo.SOURCE_DIRS


def test_default_sync_includes_config() -> None:
    assert "config" in sync_review_repo.SOURCE_DIRS


def test_default_sync_includes_skills_src() -> None:
    assert "skills-src" in sync_review_repo.SOURCE_DIRS


def test_sync_source_files_copies_openmind_plugin_sources(tmp_path: Path) -> None:
    stats = sync_review_repo.sync_source_files(tmp_path, include_dirs=["openclaw_extensions"])

    plugin_json = tmp_path / "openclaw_extensions" / "openmind-memory" / "openclaw.plugin.json"
    entrypoint = tmp_path / "openclaw_extensions" / "openmind-memory" / "index.ts"
    assert plugin_json.exists()
    assert entrypoint.exists()
    assert '"id": "openmind-memory"' in plugin_json.read_text(encoding="utf-8")
    assert stats["files"] >= 2


def test_sync_source_files_copies_ops_sync_script(tmp_path: Path) -> None:
    stats = sync_review_repo.sync_source_files(tmp_path, include_dirs=["ops"])

    copied = tmp_path / "ops" / "sync_review_repo.py"
    assert copied.exists()
    assert "SOURCE_DIRS" in copied.read_text(encoding="utf-8")
    assert stats["files"] >= 1


def test_sync_source_files_copies_chatgptrest_skill_sources(tmp_path: Path) -> None:
    stats = sync_review_repo.sync_source_files(tmp_path, include_dirs=["skills-src"])

    skill = tmp_path / "skills-src" / "chatgptrest-call" / "SKILL.md"
    wrapper = tmp_path / "skills-src" / "chatgptrest-call" / "scripts" / "chatgptrest_call.py"
    assert skill.exists()
    assert wrapper.exists()
    assert "ChatgptREST" in skill.read_text(encoding="utf-8")
    assert stats["files"] >= 2


def test_sync_source_files_copies_role_config(tmp_path: Path) -> None:
    stats = sync_review_repo.sync_source_files(tmp_path, include_dirs=["config"])

    roles = tmp_path / "config" / "agent_roles.yaml"
    assert roles.exists()
    content = roles.read_text(encoding="utf-8")
    assert "devops:" in content
    assert "research:" in content
    assert stats["files"] >= 1


def test_sync_source_files_copies_review_safe_verifier_docs(tmp_path: Path) -> None:
    stats = sync_review_repo.sync_source_files(tmp_path, include_dirs=["docs"])

    lean = tmp_path / "docs" / "reviews" / "openclaw_openmind_verifier_lean_20260309.md"
    ops = tmp_path / "docs" / "reviews" / "openclaw_openmind_verifier_ops_20260309.md"
    lean_json = tmp_path / "docs" / "reviews" / "openclaw_openmind_verifier_lean_20260309.json"
    ops_json = tmp_path / "docs" / "reviews" / "openclaw_openmind_verifier_ops_20260309.json"
    auth_evidence = tmp_path / "docs" / "reviews" / "evidence" / "openclaw_openmind" / "B2" / "openmind_advisor_auth_ops_20260309.json"
    assert lean.exists()
    assert ops.exists()
    assert lean_json.exists()
    assert ops_json.exists()
    assert auth_evidence.exists()
    assert "# OpenClaw + OpenMind Verification Report" in lean.read_text(encoding="utf-8")
    assert "# OpenClaw + OpenMind Verification Report" in ops.read_text(encoding="utf-8")
    assert stats["files"] >= 2


def test_generate_review_context_includes_source_commit_metadata(tmp_path: Path) -> None:
    sync_review_repo.generate_review_context(
        tmp_path,
        branch_name="review-branch",
        pr_branch="feature/test",
        review_instructions="check this",
        source_commit="deadbeef",
    )

    context = (tmp_path / "REVIEW_CONTEXT.md").read_text(encoding="utf-8")
    source = (tmp_path / "REVIEW_SOURCE.json").read_text(encoding="utf-8")

    assert "mirrored from source commit `deadbeef`" in context
    assert '"source_repo": "https://github.com/haizhouyuan/ChatgptREST"' in source
    assert '"source_commit": "deadbeef"' in source
    assert '"source_commit_url": "https://github.com/haizhouyuan/ChatgptREST/commit/deadbeef"' in source


def test_sync_and_push_updates_stable_import_branch(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    calls: list[list[str]] = []

    def _fake_sync_source_files(dst_dir: Path, *, include_dirs=None):  # noqa: ANN001
        (dst_dir / "README.md").write_text("review repo\n", encoding="utf-8")
        return {"files": 1, "skipped": 0, "bytes": 11}

    def _fake_generate_review_context(*args, **kwargs):  # noqa: ANN002, ANN003
        dst_dir = args[0]
        (dst_dir / "REVIEW_CONTEXT.md").write_text("# context\n", encoding="utf-8")
        (dst_dir / "REVIEW_SOURCE.json").write_text('{"source_commit":"deadbeef"}\n', encoding="utf-8")

    def _fake_run(cmd, **kwargs):  # noqa: ANN001
        calls.append([str(part) for part in cmd])
        if cmd[:3] == ["gh", "api", "user"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="haizhouyuan\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(sync_review_repo, "sync_source_files", _fake_sync_source_files)
    monkeypatch.setattr(sync_review_repo, "generate_review_context", _fake_generate_review_context)
    monkeypatch.setattr(sync_review_repo, "_ensure_review_remote", lambda dst, repo_name: "remote-url")  # noqa: ARG005
    monkeypatch.setattr(sync_review_repo.subprocess, "run", _fake_run)

    result = sync_review_repo.sync_and_push(
        repo_name="ChatgptREST-review",
        repo_dir=str(tmp_path),
        branch_name="review-20260309-test",
        push=True,
    )

    assert result["pushed"] is True
    assert result["import_branch"] == "main"
    assert result["import_branch_pushed"] is True
    assert result["repo_url"] == "https://github.com/haizhouyuan/ChatgptREST-review"
    assert result["import_branch_url"] == "https://github.com/haizhouyuan/ChatgptREST-review/tree/main"
    assert ["git", "push", "-f", sync_review_repo.DEFAULT_REVIEW_REMOTE, "review-20260309-test"] in calls
    assert [
        "git",
        "push",
        "-f",
        sync_review_repo.DEFAULT_REVIEW_REMOTE,
        "HEAD:refs/heads/main",
    ] in calls
    assert [
        "gh",
        "api",
        "repos/haizhouyuan/ChatgptREST-review",
        "-X",
        "PATCH",
        "-f",
        "default_branch=main",
    ] in calls


def test_finalize_review_bundle_clears_import_branch_and_deletes_review_branch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir()
    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):  # noqa: ANN001
        cmd_list = [str(part) for part in cmd]
        calls.append(cmd_list)
        if cmd[:3] == ["gh", "api", "user"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="haizhouyuan\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(sync_review_repo.subprocess, "run", _fake_run)
    monkeypatch.setattr(sync_review_repo, "_ensure_review_remote", lambda dst, repo_name: "remote-url")  # noqa: ARG005

    result = sync_review_repo.finalize_review_bundle(
        repo_name="ChatgptREST-review",
        repo_dir=str(tmp_path),
        branch_name="review-20260317-test",
        import_branch="main",
        clear_import=True,
    )

    assert result["finalized"] is True
    assert result["import_branch_cleared"] is True
    assert result["branch_deleted"] is True
    assert (tmp_path / "README.md").exists()
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "cleared after review finalization" in readme
    assert "finalized_review_branch" in readme
    assert [
        "git",
        "push",
        "-f",
        sync_review_repo.DEFAULT_REVIEW_REMOTE,
        "HEAD:refs/heads/main",
    ] in calls
    assert [
        "git",
        "push",
        sync_review_repo.DEFAULT_REVIEW_REMOTE,
        "--delete",
        "review-20260317-test",
    ] in calls


def test_cleanup_remote_branches_can_clear_import_branch_when_last_branch_is_deleted(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir()
    calls: list[list[str]] = []
    branch_list_calls = {"count": 0}

    def _fake_run(cmd, **kwargs):  # noqa: ANN001
        cmd_list = [str(part) for part in cmd]
        calls.append(cmd_list)
        if cmd[:4] == ["git", "branch", "-r", "--list"]:
            branch_list_calls["count"] += 1
            if branch_list_calls["count"] == 1:
                return subprocess.CompletedProcess(cmd, 0, stdout="  review/review-20260317-old\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:4] == ["git", "log", "-1", "--format=%ct"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="1000\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(sync_review_repo.subprocess, "run", _fake_run)
    monkeypatch.setattr(sync_review_repo, "_ensure_review_remote", lambda dst, repo_name: "remote-url")  # noqa: ARG005

    result = sync_review_repo.cleanup_remote_branches(
        repo_name="ChatgptREST-review",
        repo_dir=str(tmp_path),
        max_age_hours=0.01,
        import_branch="main",
        clear_import_when_empty=True,
    )

    assert result["deleted"] == 1
    assert result["import_branch_cleared"] is True
    assert [
        "git",
        "push",
        sync_review_repo.DEFAULT_REVIEW_REMOTE,
        "--delete",
        "review-20260317-old",
    ] in calls
    assert [
        "git",
        "push",
        "-f",
        sync_review_repo.DEFAULT_REVIEW_REMOTE,
        "HEAD:refs/heads/main",
    ] in calls


def test_finalize_review_bundle_infers_branch_from_review_source(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "REVIEW_SOURCE.json").write_text(
        '{"review_branch":"review-20260317-auto"}\n',
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):  # noqa: ANN001
        cmd_list = [str(part) for part in cmd]
        calls.append(cmd_list)
        if cmd[:4] == ["git", "branch", "-r", "--list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="  review/review-20260317-auto\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(sync_review_repo.subprocess, "run", _fake_run)
    monkeypatch.setattr(sync_review_repo, "_ensure_review_remote", lambda dst, repo_name: "remote-url")  # noqa: ARG005

    result = sync_review_repo.finalize_review_bundle(
        repo_name="ChatgptREST-review",
        repo_dir=str(tmp_path),
        branch_name="",
        import_branch="main",
        clear_import=False,
    )

    assert result["branch"] == "review-20260317-auto"
    assert result["branch_deleted"] is True
    assert [
        "git",
        "push",
        sync_review_repo.DEFAULT_REVIEW_REMOTE,
        "--delete",
        "review-20260317-auto",
    ] in calls


def test_purge_review_repo_deletes_all_review_branches_and_clears_import(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir()
    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):  # noqa: ANN001
        cmd_list = [str(part) for part in cmd]
        calls.append(cmd_list)
        if cmd[:4] == ["git", "branch", "-r", "--list"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="  review/review-20260317-a\n  review/review-20260317-b\n",
                stderr="",
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(sync_review_repo.subprocess, "run", _fake_run)
    monkeypatch.setattr(sync_review_repo, "_ensure_review_remote", lambda dst, repo_name: "remote-url")  # noqa: ARG005

    result = sync_review_repo.purge_review_repo(
        repo_name="ChatgptREST-review",
        repo_dir=str(tmp_path),
        import_branch="main",
    )

    assert result["purged"] is True
    assert result["deleted"] == 2
    assert result["import_branch_cleared"] is True
    assert [
        "git",
        "push",
        sync_review_repo.DEFAULT_REVIEW_REMOTE,
        "--delete",
        "review-20260317-a",
    ] in calls
    assert [
        "git",
        "push",
        sync_review_repo.DEFAULT_REVIEW_REMOTE,
        "--delete",
        "review-20260317-b",
    ] in calls
    assert [
        "git",
        "push",
        "-f",
        sync_review_repo.DEFAULT_REVIEW_REMOTE,
        "HEAD:refs/heads/main",
    ] in calls
