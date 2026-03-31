from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from chatgptrest.core.db import init_db


def _load_module():
    path = Path(__file__).resolve().parents[1] / "ops" / "openclaw_orch_agent.py"
    spec = importlib.util.spec_from_file_location("openclaw_orch_agent", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def orch():
    return _load_module()


def test_parse_json_loose_with_plugin_logs(orch) -> None:
    raw = "\n".join(
        [
            "[plugins] feishu_doc: Registered",
            "[plugins] feishu_wiki: Registered",
            '{"ok":true,"result":{"x":1}}',
        ]
    )
    obj = orch._parse_json_loose(raw)
    assert isinstance(obj, dict)
    assert obj["ok"] is True
    assert obj["result"]["x"] == 1


def test_default_openclaw_cmd_supports_official_home(monkeypatch: pytest.MonkeyPatch, orch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENCLAW_CMD", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(orch.shutil, "which", lambda cmd: None)
    bin_path = tmp_path / ".home-codex-official" / ".local" / "bin" / "openclaw"
    bin_path.parent.mkdir(parents=True, exist_ok=True)
    bin_path.write_text("", encoding="utf-8")
    assert orch._default_openclaw_cmd() == str(bin_path)


def test_reconcile_marks_missing_agent_dir(monkeypatch: pytest.MonkeyPatch, orch) -> None:
    spec = orch.AgentSpec(
        agent_id="chatgptrest-orch",
        workspace="/vol1/1000/projects/ChatgptREST",
        model="openai-codex/gpt-5.3-codex-spark",
        session_id="chatgptrest-orch-main",
    )
    monkeypatch.setattr(
        orch,
        "_list_agents",
        lambda *args, **kwargs: [
            {
                "id": "chatgptrest-orch",
                "workspace": "/vol1/1000/projects/ChatgptREST",
                "model": "openai-codex/gpt-5.3-codex-spark",
                "agentDir": "/tmp/not-exist-dir",
            }
        ],
    )
    out = orch._reconcile(
        openclaw_cmd="openclaw",
        timeout=30,
        specs=[spec],
        do_reconcile=False,
    )
    assert out["ok"] is False
    assert len(out["checks"]) == 1
    c = out["checks"][0]
    assert c["exists"] is True
    assert c["workspace_ok"] is True
    assert c["model_ok"] is True
    assert c["agent_dir_required"] is True
    assert c["agent_dir_ok"] is False
    assert c["agent_dir_effective_ok"] is False
    assert c["needs_reconcile"] is True


def test_reconcile_treats_codex_agent_dir_as_lazy(monkeypatch: pytest.MonkeyPatch, orch) -> None:
    spec = orch.AgentSpec(
        agent_id="chatgptrest-codex-w3",
        workspace="/vol1/1000/projects/ChatgptREST",
        model="codex-cli/gpt-5.3-codex",
        session_id="chatgptrest-codex-w3-main",
    )
    monkeypatch.setattr(
        orch,
        "_list_agents",
        lambda *args, **kwargs: [
            {
                "id": "chatgptrest-codex-w3",
                "workspace": "/vol1/1000/projects/ChatgptREST",
                "model": "codex-cli/gpt-5.3-codex",
                "agentDir": "/tmp/not-exist-dir",
            }
        ],
    )
    out = orch._reconcile(openclaw_cmd="openclaw", timeout=30, specs=[spec], do_reconcile=False)
    assert out["ok"] is True
    c = out["checks"][0]
    assert c["agent_dir_required"] is False
    assert c["agent_dir_ok"] is False
    assert c["agent_dir_effective_ok"] is True
    assert c["needs_reconcile"] is False


def test_reconcile_executes_delete_then_add(monkeypatch: pytest.MonkeyPatch, orch) -> None:
    spec = orch.AgentSpec(
        agent_id="chatgptrest-codex-w2",
        workspace="/vol1/1000/projects/ChatgptREST",
        model="codex-cli/gpt-5.3-codex",
        session_id="chatgptrest-codex-w2-main",
    )
    calls: list[tuple[str, str]] = []
    first = True

    def _fake_list_agents(*args, **kwargs):
        nonlocal first
        if first:
            first = False
            return [
                {
                    "id": "chatgptrest-codex-w2",
                    "workspace": "/vol1/1000/projects/ChatgptREST",
                    "model": "wrong-model",
                    "agentDir": "/tmp/not-exist-dir",
                }
            ]
        return [
            {
                "id": "chatgptrest-codex-w2",
                "workspace": "/vol1/1000/projects/ChatgptREST",
                "model": "codex-cli/gpt-5.3-codex",
                "agentDir": str(Path(__file__).resolve().parents[1]),
            }
        ]

    monkeypatch.setattr(orch, "_list_agents", _fake_list_agents)

    def _fake_delete(openclaw_cmd: str, agent_id: str, timeout: int):  # noqa: ARG001
        calls.append(("delete", agent_id))
        return {"op": "delete", "agent_id": agent_id, "ok": True, "returncode": 0}

    def _fake_add(openclaw_cmd: str, spec, timeout: int):  # noqa: ANN001, ARG001
        calls.append(("add", spec.agent_id))
        return {"op": "add", "agent_id": spec.agent_id, "ok": True, "returncode": 0}

    monkeypatch.setattr(orch, "_delete_agent", _fake_delete)
    monkeypatch.setattr(orch, "_add_agent", _fake_add)

    out = orch._reconcile(
        openclaw_cmd="openclaw",
        timeout=30,
        specs=[spec],
        do_reconcile=True,
    )
    assert out["ok"] is True
    assert calls == [("delete", "chatgptrest-codex-w2"), ("add", "chatgptrest-codex-w2")]
    assert out["checks"][0]["exists"] is True
    assert out["checks"][0]["workspace_ok"] is True
    assert out["checks"][0]["model_ok"] is True
    assert out["checks"][0]["agent_dir_ok"] is True


def test_collect_ui_canary_report_detects_failed_provider(tmp_path: Path, orch) -> None:
    report_path = tmp_path / "ui_canary_latest.json"
    report_path.write_text(
        """
{
  "ts": "2026-02-21T10:00:00Z",
  "providers": [
    {"provider": "chatgpt", "ok": true, "status": "completed", "consecutive_failures": 0},
    {"provider": "gemini", "ok": false, "status": "error", "error_type": "GeminiModeSelectorNotFound", "error": "selector missing", "consecutive_failures": 3}
  ],
  "state": {
    "gemini": {"consecutive_failures": 3}
  }
}
""".strip(),
        encoding="utf-8",
    )
    out = orch._collect_ui_canary_report(  # noqa: SLF001
        report_path=report_path,
        stale_seconds=3600 * 24 * 30,
        fail_threshold=2,
    )
    assert out["ok"] is False
    assert out["stale"] is False
    assert len(out["failed_providers"]) == 1
    assert out["failed_providers"][0]["provider"] == "gemini"


def test_collect_open_incidents_filters_category_and_status(tmp_path: Path, orch) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    init_db(db_path)
    conn = orch.sqlite3.connect(str(db_path))
    try:
        now = 1_800_000_000.0
        conn.execute(
            """
            INSERT INTO incidents(
              incident_id, fingerprint_hash, signature, category, severity, status,
              created_at, updated_at, last_seen_at, count, job_ids_json, evidence_dir
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "inc-ui-1",
                "hash-ui-1",
                "ui_canary:gemini:error:SelectorNotFound",
                "ui_canary",
                "P2",
                "open",
                now,
                now,
                now,
                2,
                "[]",
                str(tmp_path / "inc-ui-1"),
            ),
        )
        conn.execute(
            """
            INSERT INTO incidents(
              incident_id, fingerprint_hash, signature, category, severity, status,
              created_at, updated_at, last_seen_at, count, job_ids_json, evidence_dir
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "inc-job-1",
                "hash-job-1",
                "error:chatgpt_web.ask:TimeoutError",
                "job",
                "P1",
                "open",
                now,
                now,
                now,
                1,
                "[]",
                str(tmp_path / "inc-job-1"),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    out = orch._collect_open_incidents(  # noqa: SLF001
        db_path=db_path,
        categories=["ui_canary"],
        lookback_minutes=60 * 24 * 365,
        limit=20,
    )
    assert out["ok"] is True
    assert out["attention"] is True
    assert len(out["rows"]) == 1
    assert out["rows"][0]["category"] == "ui_canary"
