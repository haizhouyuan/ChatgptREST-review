from __future__ import annotations

import http.server
import importlib.util
import json
import socketserver
import sys
import threading
from pathlib import Path

import pytest

from chatgptrest.core import client_issues
from chatgptrest.core.db import connect


class _HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A003,ANN001
        return


def _load_dev_loop_module():
    path = Path(__file__).resolve().parents[1] / "ops" / "run_issue_ledger_dev_loop.py"
    spec = importlib.util.spec_from_file_location("run_issue_ledger_dev_loop", str(path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    return {"db_path": db_path, "tmp_path": tmp_path}


def test_run_loop_generates_task_pack_and_checks_health(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    mod = _load_dev_loop_module()
    with connect(env["db_path"]) as conn:
        issue, _created, _info = client_issues.report_issue(
            conn,
            project="chatgptrest",
            title="Automate issue ledger dev loop",
            severity="P1",
            kind="openclaw.dev_loop",
            symptom="Need branch + tests + service health",
            raw_error="manual request",
            source="worker_auto",
        )
        conn.commit()

    server = socketserver.TCPServer(("127.0.0.1", 0), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    health_url = f"http://127.0.0.1:{server.server_address[1]}/healthz"

    try:
        monkeypatch.setattr(
            mod,
            "sync_issue_to_github",
            lambda conn, issue, repo, dry_run: {
                "issue_id": issue.issue_id,
                "action": "created",
                "github_url": "https://github.com/haizhouyuan/ChatgptREST/issues/900",
                "github_number": 900,
                "repo": repo,
                "dry_run": dry_run,
            },
        )
        args = mod._parse_args(  # noqa: SLF001
            [
                issue.issue_id,
                "--db",
                str(env["db_path"]),
                "--repo",
                "haizhouyuan/ChatgptREST",
                "--artifact-root",
                str(env["tmp_path"] / "artifacts"),
                "--run-test-cmd",
                f"{sys.executable} -c \"print('tests-ok')\"",
                "--service-start-cmd",
                f"{sys.executable} -c \"from pathlib import Path; Path('service_started.txt').write_text('ok')\"",
                "--health-url",
                health_url,
            ]
        )
        report = mod.run_loop(args)
    finally:
        server.shutdown()
        server.server_close()

    assert report["ok"] is True
    artifact_dir = Path(report["artifact_dir"])
    assert (artifact_dir / "task.json").exists()
    assert (artifact_dir / "README.md").exists()
    assert (artifact_dir / "report.json").exists()
    task = json.loads((artifact_dir / "task.json").read_text(encoding="utf-8"))
    assert task["roles"]["implementer"]["lane"] == "codex_auth_only"
    assert task["roles"]["reviewer"]["lane"] == "claudeminmax"
    assert report["health"]["ok"] is True
    assert (mod.REPO_ROOT / "service_started.txt").exists()
    (mod.REPO_ROOT / "service_started.txt").unlink()
