from __future__ import annotations

import http.server
import json
import os
import socketserver
import subprocess
import sys
import time
import threading
from pathlib import Path

import pytest

from chatgptrest.core import client_issues
from chatgptrest.core.db import connect
from chatgptrest.ops_shared import issue_dev_controller as controller
from ops import controller_lane_continuity as continuity


class _HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = b'{"ok":true,"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A003,ANN001
        return


class _FakeGitHubClient:
    def __init__(self) -> None:
        self.prs: dict[int, dict[str, object]] = {}
        self.next_number = 901

    def ensure_pull_request(
        self,
        *,
        repo: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body_path: Path,
        cwd: Path,
    ) -> dict[str, object]:
        for pr in self.prs.values():
            if pr["head"] == head_branch and pr["base"] == base_branch:
                return dict(pr)
        number = self.next_number
        self.next_number += 1
        pr = {
            "ok": True,
            "created": True,
            "number": number,
            "url": f"https://github.com/{repo}/pull/{number}",
            "state": "OPEN",
            "title": title,
            "head": head_branch,
            "base": base_branch,
            "body": body_path.read_text(encoding="utf-8"),
            "cwd": str(cwd),
        }
        self.prs[number] = pr
        return dict(pr)

    def merge_pull_request(
        self,
        *,
        repo: str,
        number: int,
        method: str,
        cwd: Path,
    ) -> dict[str, object]:
        pr = self.prs[int(number)]
        pr["state"] = "MERGED"
        return {
            "ok": True,
            "number": int(number),
            "method": method,
            "repo": repo,
            "cwd": str(cwd),
        }


def _git(args: list[str], *, cwd: Path) -> None:
    proc = subprocess.run(["git", *args], cwd=str(cwd), text=True, capture_output=True, check=False)
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"


def _init_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    remote_root = tmp_path / "remote.git"
    repo_root.mkdir(parents=True, exist_ok=True)
    _git(["init", "-b", "master"], cwd=repo_root)
    _git(["config", "user.email", "pytest@example.com"], cwd=repo_root)
    _git(["config", "user.name", "pytest"], cwd=repo_root)
    (repo_root / "README.md").write_text("base\n", encoding="utf-8")
    _git(["add", "README.md"], cwd=repo_root)
    _git(["commit", "-m", "base"], cwd=repo_root)
    subprocess.run(["git", "init", "--bare", str(remote_root)], text=True, capture_output=True, check=True)
    _git(["remote", "add", "origin", str(remote_root)], cwd=repo_root)
    _git(["push", "-u", "origin", "master"], cwd=repo_root)
    return repo_root, remote_root


def _manifest(tmp_path: Path, repo_root: Path) -> Path:
    manifest = tmp_path / "controller_lanes.json"
    manifest.write_text(
        json.dumps(
            {
                "lanes": [
                    {
                        "lane_id": "main",
                        "purpose": "controller",
                        "lane_kind": "codex",
                        "cwd": str(repo_root),
                        "desired_state": "observed",
                        "run_state": "idle",
                    },
                    {
                        "lane_id": "worker-1",
                        "purpose": "implementer",
                        "lane_kind": "codex",
                        "cwd": str(repo_root),
                        "desired_state": "observed",
                        "run_state": "idle",
                    },
                    {
                        "lane_id": "verifier",
                        "purpose": "reviewer",
                        "lane_kind": "codex",
                        "cwd": str(repo_root),
                        "desired_state": "observed",
                        "run_state": "idle",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return manifest


def _report_issue(db_path: Path, *, title: str) -> client_issues.ClientIssueRecord:
    with connect(db_path) as conn:
        issue, _created, _info = client_issues.report_issue(
            conn,
            project="ChatgptREST",
            title=title,
            severity="P1",
            kind="openclaw.dev_controller",
            symptom="Need implementer + reviewer + PR + health verification",
            raw_error="pytest synthetic controller issue",
            source="worker_auto",
        )
        conn.commit()
        return issue


def _install_fake_hcom(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    log_path = tmp_path / "hcom_log.jsonl"
    script = bin_dir / "hcom"
    script.write_text(
        """#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _append_log(payload: dict[str, object]) -> None:
    path_text = os.environ.get("FAKE_HCOM_LOG", "").strip()
    if not path_text:
        return
    path = Path(path_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\\n")


def _parse_message(message: str) -> dict[str, str]:
    payload = json.loads(message)
    return {str(key): str(value) for key, value in payload.items() if value is not None}


def _atomic_write_json(path_text: str, tmp_text: str | None, payload: dict[str, object]) -> None:
    path = Path(path_text)
    tmp_path = Path(tmp_text) if tmp_text else path.with_name(f".{path.name}.tmp")
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp_path, path)


def main(argv: list[str]) -> int:
    _append_log({"argv": argv, "hcom_dir": os.environ.get("HCOM_DIR", "")})
    if argv[:2] == ["list", "--names"]:
        if os.environ.get("FAKE_HCOM_LIST_FAIL", "").strip() == "1":
            sys.stderr.write("fake hcom list failure\\n")
            return 7
        sys.stdout.write(os.environ.get("FAKE_HCOM_NAMES", "impl-1\\nreview-1\\n"))
        return 0
    if argv and argv[0] == "send":
        target = next((arg for arg in argv if arg.startswith("@")), "")
        if target in {item.strip() for item in os.environ.get("FAKE_HCOM_SEND_FAIL_TARGETS", "").split(",") if item.strip()}:
            sys.stderr.write(f"fake hcom send failure for {target}\\n")
            return 9
        message = argv[argv.index("--") + 1] if "--" in argv else ""
        parsed = _parse_message(message)
        output_path = Path(parsed["output_path"])
        output_tmp_path = parsed.get("output_tmp_path", "")
        if target in {item.strip() for item in os.environ.get("FAKE_HCOM_SKIP_OUTPUT_TARGETS", "").split(",") if item.strip()}:
            sys.stdout.write("sent-without-output\\n")
            return 0
        if target == "@impl-1":
            worktree = Path(parsed["worktree_path"])
            (worktree / "hcom_feature.txt").write_text("implemented via hcom\\n", encoding="utf-8")
            payload = {
                "ok": True,
                "summary": "patched via hcom",
                "changed_files": ["hcom_feature.txt"],
                "tests_ran": ["hcom-smoke"],
            }
        elif target == "@review-1":
            payload = {
                "ok": True,
                "decision": "approve",
                "summary": "ready via hcom",
                "findings": [],
            }
        else:
            sys.stderr.write(f"Unknown target: {target}\\n")
            return 2
        _atomic_write_json(str(output_path), output_tmp_path or None, payload)
        sys.stdout.write("sent\\n")
        return 0
    sys.stderr.write(f"unsupported fake hcom argv: {argv}\\n")
    return 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return bin_dir, log_path


def test_controller_loop_runs_full_lane_to_pr_flow(tmp_path: Path) -> None:
    repo_root, _remote_root = _init_repo(tmp_path)
    manifest_path = _manifest(tmp_path, repo_root)
    db_path = tmp_path / "jobdb.sqlite3"
    lane_db_path = tmp_path / "controller_lanes.sqlite3"
    worktree_root = tmp_path / "worktrees"
    artifact_root = tmp_path / "artifacts"
    issue = _report_issue(db_path, title="Automate controller dev loop")
    gh = _FakeGitHubClient()

    service_marker = tmp_path / "service_started.txt"
    server = socketserver.TCPServer(("127.0.0.1", 0), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    health_url = f"http://127.0.0.1:{server.server_address[1]}/healthz"

    implementer_template = (
        "{python_executable_q} -c \"from pathlib import Path; import json; "
        "worktree = Path({worktree_path_py}); "
        "(worktree / 'feature.txt').write_text('implemented\\n', encoding='utf-8'); "
        "Path({implementer_output_py}).write_text(json.dumps({{'ok': True, 'summary': 'patched', "
        "'changed_files': ['feature.txt'], 'tests_ran': ['unit-smoke']}}), encoding='utf-8')\""
    )
    reviewer_template = (
        "{python_executable_q} -c \"from pathlib import Path; import json; "
        "Path({reviewer_output_py}).write_text(json.dumps({{'ok': True, 'decision': 'approve', "
        "'summary': 'ready', 'findings': []}}), encoding='utf-8')\""
    )

    try:
        report = controller.run_controller_loop(
            controller.ControllerLoopConfig(
                issue_id=issue.issue_id,
                db_path=db_path,
                lane_db_path=lane_db_path,
                repo_root=repo_root,
                artifact_root=artifact_root,
                worktree_root=worktree_root,
                manifest_path=manifest_path,
                repo_slug="haizhouyuan/ChatgptREST",
                base_ref="origin/master",
                pr_base="master",
                create_worktree=True,
                skip_github_issue_sync=True,
                implementer_command_template=implementer_template,
                reviewer_command_template=reviewer_template,
                validation_commands=[f"{sys.executable} -c \"print('tests-ok')\""],
                service_start_commands=[
                    f"{sys.executable} -c \"from pathlib import Path; Path({repr(str(service_marker))}).write_text('ok', encoding='utf-8')\""
                ],
                health_url=health_url,
                auto_commit=True,
                push_branch=True,
                create_pr=True,
                merge_pr=True,
                close_issue_status="mitigated",
            ),
            github_client=gh,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert report["ok"] is True
    assert report["implementer"]["result"]["ok"] is True
    assert report["reviewer"]["result"]["decision"] == "approve"
    assert report["pull_request"]["url"] == "https://github.com/haizhouyuan/ChatgptREST/pull/901"
    assert report["merge"]["ok"] is True
    assert report["health"]["ok"] is True
    assert service_marker.exists()
    assert report["git"]["commit"]["ok"] is True
    assert "feature.txt" in report["git"]["head_files"]
    assert continuity.lane_status(db_path=lane_db_path, lane_id="worker-1")["run_state"] == "completed"
    assert continuity.lane_status(db_path=lane_db_path, lane_id="verifier")["run_state"] == "completed"

    with connect(db_path) as conn:
        updated = client_issues.get_issue(conn, issue_id=issue.issue_id)
        assert updated is not None
        assert updated.status == "mitigated"
        assert isinstance(updated.metadata, dict)
        assert updated.metadata["dev_loop"]["pull_request"]["number"] == 901
        assert str(updated.latest_artifacts_path or "").endswith("report.json")


def test_controller_loop_rejects_merge_without_review_approval(tmp_path: Path) -> None:
    repo_root, _remote_root = _init_repo(tmp_path)
    manifest_path = _manifest(tmp_path, repo_root)
    db_path = tmp_path / "jobdb.sqlite3"
    lane_db_path = tmp_path / "controller_lanes.sqlite3"
    worktree_root = tmp_path / "worktrees"
    artifact_root = tmp_path / "artifacts"
    issue = _report_issue(db_path, title="Merge gate requires reviewer approval")
    gh = _FakeGitHubClient()

    implementer_template = (
        "{python_executable_q} -c \"from pathlib import Path; import json; "
        "(Path({worktree_path_py}) / 'change.txt').write_text('x', encoding='utf-8'); "
        "Path({implementer_output_py}).write_text(json.dumps({{'ok': True, 'summary': 'patched', "
        "'changed_files': ['change.txt'], 'tests_ran': []}}), encoding='utf-8')\""
    )
    reviewer_template = (
        "{python_executable_q} -c \"from pathlib import Path; import json; "
        "Path({reviewer_output_py}).write_text(json.dumps({{'ok': True, 'decision': 'request_changes', "
        "'summary': 'not ready', 'findings': ['missing tests']}}), encoding='utf-8')\""
    )

    with pytest.raises(RuntimeError, match="reviewer approval"):
        controller.run_controller_loop(
            controller.ControllerLoopConfig(
                issue_id=issue.issue_id,
                db_path=db_path,
                lane_db_path=lane_db_path,
                repo_root=repo_root,
                artifact_root=artifact_root,
                worktree_root=worktree_root,
                manifest_path=manifest_path,
                repo_slug="haizhouyuan/ChatgptREST",
                base_ref="origin/master",
                skip_github_issue_sync=True,
                implementer_command_template=implementer_template,
                reviewer_command_template=reviewer_template,
                auto_commit=True,
                push_branch=True,
                create_pr=True,
                merge_pr=True,
            ),
            github_client=gh,
        )


def test_controller_loop_runs_full_hcom_lane_to_pr_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, _remote_root = _init_repo(tmp_path)
    manifest_path = _manifest(tmp_path, repo_root)
    db_path = tmp_path / "jobdb.sqlite3"
    lane_db_path = tmp_path / "controller_lanes.sqlite3"
    worktree_root = tmp_path / "worktrees"
    artifact_root = tmp_path / "artifacts"
    issue = _report_issue(db_path, title="Automate controller dev loop with hcom")
    gh = _FakeGitHubClient()
    bin_dir, log_path = _install_fake_hcom(tmp_path)
    hcom_dir = tmp_path / "hcom"
    hcom_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_HCOM_LOG", str(log_path))

    service_marker = tmp_path / "service_started.txt"
    server = socketserver.TCPServer(("127.0.0.1", 0), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    health_url = f"http://127.0.0.1:{server.server_address[1]}/healthz"

    try:
        report = controller.run_controller_loop(
            controller.ControllerLoopConfig(
                issue_id=issue.issue_id,
                db_path=db_path,
                lane_db_path=lane_db_path,
                repo_root=repo_root,
                artifact_root=artifact_root,
                worktree_root=worktree_root,
                manifest_path=manifest_path,
                repo_slug="haizhouyuan/ChatgptREST",
                base_ref="origin/master",
                pr_base="master",
                create_worktree=True,
                skip_github_issue_sync=True,
                implementer_hcom_target="@impl-1",
                reviewer_hcom_target="@review-1",
                hcom_dir=str(hcom_dir),
                hcom_sender="controller-test",
                hcom_poll_seconds=0.1,
                implementer_timeout_seconds=5.0,
                reviewer_timeout_seconds=5.0,
                validation_commands=[f"{sys.executable} -c \"print('tests-ok')\""],
                service_start_commands=[
                    f"{sys.executable} -c \"from pathlib import Path; Path({repr(str(service_marker))}).write_text('ok', encoding='utf-8')\""
                ],
                health_url=health_url,
                auto_commit=True,
                push_branch=True,
                create_pr=True,
                merge_pr=True,
                close_issue_status="mitigated",
            ),
            github_client=gh,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert report["ok"] is True
    assert report["implementer"]["execution"]["mode"] == "hcom"
    assert report["implementer"]["result"]["changed_files"] == ["hcom_feature.txt"]
    assert report["reviewer"]["execution"]["mode"] == "hcom"
    assert report["reviewer"]["result"]["decision"] == "approve"
    assert report["pull_request"]["url"] == "https://github.com/haizhouyuan/ChatgptREST/pull/901"
    assert report["merge"]["ok"] is True
    assert report["health"]["ok"] is True
    assert report["git"]["commit"]["ok"] is True
    assert "hcom_feature.txt" in report["git"]["head_files"]
    assert service_marker.exists()
    assert continuity.lane_status(db_path=lane_db_path, lane_id="worker-1")["run_state"] == "completed"
    assert continuity.lane_status(db_path=lane_db_path, lane_id="verifier")["run_state"] == "completed"
    log_lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(line["argv"][:2] == ["list", "--names"] for line in log_lines)
    send_calls = [line for line in log_lines if line["argv"] and line["argv"][0] == "send"]
    assert len(send_calls) == 2
    assert all(line["hcom_dir"] == str(hcom_dir) for line in send_calls)


def test_controller_loop_reports_missing_hcom_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, _remote_root = _init_repo(tmp_path)
    manifest_path = _manifest(tmp_path, repo_root)
    db_path = tmp_path / "jobdb.sqlite3"
    lane_db_path = tmp_path / "controller_lanes.sqlite3"
    worktree_root = tmp_path / "worktrees"
    artifact_root = tmp_path / "artifacts"
    issue = _report_issue(db_path, title="Missing hcom target fails controller lane")
    bin_dir, _log_path = _install_fake_hcom(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_HCOM_NAMES", "review-1\n")

    report = controller.run_controller_loop(
        controller.ControllerLoopConfig(
            issue_id=issue.issue_id,
            db_path=db_path,
            lane_db_path=lane_db_path,
            repo_root=repo_root,
            artifact_root=artifact_root,
            worktree_root=worktree_root,
            manifest_path=manifest_path,
            base_ref="origin/master",
            skip_github_issue_sync=True,
            implementer_hcom_target="@impl-1",
            create_pr=False,
            push_branch=False,
            auto_commit=False,
        )
    )

    assert report["ok"] is False
    assert "target not found" in str(report["implementer"]["execution"]["error"])
    assert continuity.lane_status(db_path=lane_db_path, lane_id="worker-1")["run_state"] == "failed"


def test_hcom_target_matching_is_exact_unless_wildcard() -> None:
    assert controller._hcom_target_available("@impl-1", ["impl-1", "impl-2"]) is True
    assert controller._hcom_target_available("@impl", ["impl-1", "impl-2"]) is False
    assert controller._hcom_target_available("@impl-*", ["impl-1", "impl-2"]) is True


def test_hcom_task_message_is_json_with_atomic_output_hint(tmp_path: Path) -> None:
    output_path = tmp_path / "result.json"
    message = controller._build_hcom_task_message(
        role="implementer",
        issue_id="issue_123",
        branch="codex/test",
        worktree_path=tmp_path,
        prompt_path=tmp_path / "prompt.md",
        output_path=output_path,
        schema_path=tmp_path / "schema.json",
        task_readme=tmp_path / "README.md",
        pr_url=None,
    )
    payload = json.loads(message)
    assert payload["message_type"] == "issue_dev_controller_task"
    assert payload["schema_version"] == controller.HCOM_MESSAGE_SCHEMA_VERSION
    assert payload["output_path"] == str(output_path)
    assert payload["output_tmp_path"].endswith(".result.json.tmp")
    assert any("Atomically rename" in item for item in payload["instructions"])


def test_wait_for_json_output_accepts_atomic_result_after_partial_file(tmp_path: Path) -> None:
    output_path = tmp_path / "result.json"

    def _writer() -> None:
        output_path.write_text('{"ok":', encoding="utf-8")
        time.sleep(0.2)
        tmp_path = controller._hcom_output_tmp_path(output_path)
        tmp_path.write_text(json.dumps({"ok": True, "summary": "done"}), encoding="utf-8")
        os.replace(tmp_path, output_path)

    thread = threading.Thread(target=_writer, daemon=True)
    thread.start()
    result = controller._wait_for_json_output(output_path, timeout_seconds=2.0, poll_seconds=0.05)
    thread.join(timeout=1)
    assert result["ok"] is True
    assert result["parsed"] == {"ok": True, "summary": "done"}


def test_controller_loop_reports_hcom_list_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, _remote_root = _init_repo(tmp_path)
    manifest_path = _manifest(tmp_path, repo_root)
    db_path = tmp_path / "jobdb.sqlite3"
    lane_db_path = tmp_path / "controller_lanes.sqlite3"
    worktree_root = tmp_path / "worktrees"
    artifact_root = tmp_path / "artifacts"
    issue = _report_issue(db_path, title="hcom list failure fails controller lane")
    bin_dir, _log_path = _install_fake_hcom(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_HCOM_LIST_FAIL", "1")

    report = controller.run_controller_loop(
        controller.ControllerLoopConfig(
            issue_id=issue.issue_id,
            db_path=db_path,
            lane_db_path=lane_db_path,
            repo_root=repo_root,
            artifact_root=artifact_root,
            worktree_root=worktree_root,
            manifest_path=manifest_path,
            base_ref="origin/master",
            skip_github_issue_sync=True,
            implementer_hcom_target="@impl-1",
            create_pr=False,
            push_branch=False,
            auto_commit=False,
        )
    )

    assert report["ok"] is False
    assert "fake hcom list failure" in str(report["implementer"]["execution"]["error"])
    assert continuity.lane_status(db_path=lane_db_path, lane_id="worker-1")["run_state"] == "failed"


def test_controller_loop_reports_hcom_send_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, _remote_root = _init_repo(tmp_path)
    manifest_path = _manifest(tmp_path, repo_root)
    db_path = tmp_path / "jobdb.sqlite3"
    lane_db_path = tmp_path / "controller_lanes.sqlite3"
    worktree_root = tmp_path / "worktrees"
    artifact_root = tmp_path / "artifacts"
    issue = _report_issue(db_path, title="hcom send failure fails controller lane")
    bin_dir, _log_path = _install_fake_hcom(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_HCOM_SEND_FAIL_TARGETS", "@impl-1")

    report = controller.run_controller_loop(
        controller.ControllerLoopConfig(
            issue_id=issue.issue_id,
            db_path=db_path,
            lane_db_path=lane_db_path,
            repo_root=repo_root,
            artifact_root=artifact_root,
            worktree_root=worktree_root,
            manifest_path=manifest_path,
            base_ref="origin/master",
            skip_github_issue_sync=True,
            implementer_hcom_target="@impl-1",
            create_pr=False,
            push_branch=False,
            auto_commit=False,
        )
    )

    assert report["ok"] is False
    assert report["implementer"]["execution"]["send"]["returncode"] == 9
    assert continuity.lane_status(db_path=lane_db_path, lane_id="worker-1")["run_state"] == "failed"


def test_controller_loop_reports_hcom_output_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, _remote_root = _init_repo(tmp_path)
    manifest_path = _manifest(tmp_path, repo_root)
    db_path = tmp_path / "jobdb.sqlite3"
    lane_db_path = tmp_path / "controller_lanes.sqlite3"
    worktree_root = tmp_path / "worktrees"
    artifact_root = tmp_path / "artifacts"
    issue = _report_issue(db_path, title="hcom output timeout fails controller lane")
    bin_dir, _log_path = _install_fake_hcom(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_HCOM_SKIP_OUTPUT_TARGETS", "@impl-1")

    report = controller.run_controller_loop(
        controller.ControllerLoopConfig(
            issue_id=issue.issue_id,
            db_path=db_path,
            lane_db_path=lane_db_path,
            repo_root=repo_root,
            artifact_root=artifact_root,
            worktree_root=worktree_root,
            manifest_path=manifest_path,
            base_ref="origin/master",
            skip_github_issue_sync=True,
            implementer_hcom_target="@impl-1",
            hcom_poll_seconds=0.1,
            implementer_timeout_seconds=1.0,
            create_pr=False,
            push_branch=False,
            auto_commit=False,
        )
    )

    assert report["ok"] is False
    assert report["implementer"]["execution"]["wait"]["timeout_seconds"] == 1.0
    assert report["implementer"]["execution"]["wait"]["last_state"]["exists"] is False
    assert continuity.lane_status(db_path=lane_db_path, lane_id="worker-1")["run_state"] == "failed"
