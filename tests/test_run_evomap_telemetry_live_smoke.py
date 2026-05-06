from __future__ import annotations

import argparse

from ops import run_evomap_telemetry_live_smoke as module


def _args(**overrides):
    data = {
        "base_url": "http://127.0.0.1:18711",
        "db_path": "data/evomap_knowledge.db",
        "api_key_env": "OPENMIND_API_KEY",
        "trace_id": "trace-1",
        "session_id": "session-1",
        "event_id": "event-1",
        "task_ref": "telemetry-p0/live-smoke",
        "source": "codex",
        "agent_name": "codex",
        "artifact_path": "docs/dev_log/2026-03-11_evomap_live_smoke_results.md",
        "replay_count": 1,
        "settle_seconds": 0.0,
        "http_timeout_seconds": 60.0,
        "visibility_timeout_seconds": 1.0,
        "poll_interval_seconds": 0.1,
        "max_attempts": 2,
        "retry_sleep_seconds": 0.0,
        "expect_dedup": False,
    }
    data.update(overrides)
    return argparse.Namespace(**data)


def test_run_smoke_polls_until_activity_atom_is_visible(monkeypatch) -> None:
    args = _args()
    sleeps: list[float] = []
    calls = {"post": 0, "match": 0}

    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setattr(
        module,
        "post_telemetry",
        lambda **kwargs: calls.__setitem__("post", calls["post"] + 1) or {"ok": True, "recorded": 1},
    )

    def fake_matches(db_path: str, *, event_id: str):
        calls["match"] += 1
        if calls["match"] < 3:
            return []
        return [{"atom_id": "at_act_1", "event_id": event_id, "upstream_event_id": ""}]

    monkeypatch.setattr(module, "matching_activity_atoms", fake_matches)
    monkeypatch.setattr("ops.run_evomap_telemetry_live_smoke.time.sleep", sleeps.append)

    report = module.run_smoke(args)

    assert report["ok"] is True
    assert report["after_match_count"] == 1
    assert calls["post"] == 1
    assert sleeps == [0.0, 0.1]


def test_run_smoke_returns_failed_report_when_visibility_times_out(monkeypatch) -> None:
    args = _args(visibility_timeout_seconds=0.0)
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setattr(module, "post_telemetry", lambda **kwargs: {"ok": True, "recorded": 1})
    monkeypatch.setattr(module, "matching_activity_atoms", lambda db_path, *, event_id: [])
    monkeypatch.setattr("ops.run_evomap_telemetry_live_smoke.time.sleep", lambda seconds: None)

    report = module.run_smoke(args)

    assert report["ok"] is False
    assert report["after_match_count"] == 0
    assert report["dedup_ok"] is False


def test_post_telemetry_retries_once_on_transient_timeout(monkeypatch) -> None:
    attempts = {"count": 0}

    class _Response:
        status = 200

        def read(self):
            return b'{"ok": true, "recorded": 1}'

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(req, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TimeoutError("transient timeout")
        return _Response()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("ops.run_evomap_telemetry_live_smoke.time.sleep", lambda seconds: None)

    result = module.post_telemetry(
        base_url="http://127.0.0.1:18711",
        api_key="test-key",
        payload={"trace_id": "trace-1"},
        timeout_seconds=1.0,
        max_attempts=2,
        retry_sleep_seconds=0.0,
    )

    assert result["ok"] is True
    assert attempts["count"] == 2
