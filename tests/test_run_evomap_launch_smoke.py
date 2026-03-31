from __future__ import annotations

import argparse
import json
from pathlib import Path

from ops import run_evomap_launch_smoke as module


def test_run_smoke_combines_issue_planning_and_telemetry(monkeypatch) -> None:
    args = argparse.Namespace(
        base_url="http://example.test",
        issue_limit=3,
        planning_query="合同 商务 底线",
        planning_top_k=2,
        db_path="data/evomap_knowledge.db",
        api_key_env="OPENMIND_API_KEY",
        api_token_env="CHATGPTREST_API_TOKEN",
        trace_id="trace-1",
        session_id="session-1",
        event_id="event-1",
        task_ref="telemetry-p0/launch-smoke",
        source="codex",
        agent_name="codex",
        artifact_path="docs/dev_log/2026-03-11_evomap_launch_smoke_v1.md",
        replay_count=2,
        settle_seconds=0.0,
        expect_dedup=False,
        output_dir="",
    )
    calls: list[tuple[str, str, dict[str, str] | None]] = []

    def fake_request_json(*, method: str, url: str, payload=None, headers=None):
        calls.append((method, url, headers))
        if url.endswith("/v1/advisor/recall"):
            return 200, {
                "ok": True,
                "sources": {"planning_review_pack": 2},
                "hits": [
                    {"source": "planning_review_pack", "artifact_id": "at__1"},
                    {"source": "planning_review_pack", "artifact_id": "at__2"},
                ],
                "source_scope": ["planning_review"],
            }
        return 200, {
            "ok": True,
            "summary": {
                "read_plane": "canonical",
                "object_count": 3,
                "canonical_issue_count": 12,
                "coverage_gap_count": 0,
            },
        }

    monkeypatch.setattr(module, "_request_json", fake_request_json)
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "tok-launch-smoke")
    monkeypatch.setattr(
        module,
        "run_telemetry_smoke",
        lambda smoke_args: {
            "ok": True,
            "event_id": smoke_args.event_id,
            "after_match_count": 1,
        },
    )

    report = module.run_smoke(args)

    assert report["ok"] is True
    assert report["issue_domain"]["ok"] is True
    assert report["planning_runtime_pack"]["planning_hit_count"] == 2
    assert report["telemetry_ingest"]["after_match_count"] == 1
    assert calls == [
        (
            "GET",
            "http://example.test/v1/issues/canonical/export?limit=3",
            {"Authorization": "Bearer tok-launch-smoke"},
        ),
        (
            "POST",
            "http://example.test/v1/advisor/recall",
            {"Authorization": "Bearer tok-launch-smoke"},
        ),
    ]


def test_main_writes_launch_smoke_report(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "evomap_launch_smoke"
    args = argparse.Namespace(
        output_dir=str(output_dir),
        base_url="http://127.0.0.1:18711",
        issue_limit=5,
        planning_query="合同 商务 底线",
        planning_top_k=5,
        db_path="data/evomap_knowledge.db",
        api_key_env="OPENMIND_API_KEY",
        api_token_env="CHATGPTREST_API_TOKEN",
        trace_id="trace-2",
        session_id="session-2",
        event_id="event-2",
        task_ref="telemetry-p0/launch-smoke",
        source="codex",
        agent_name="codex",
        artifact_path="docs/dev_log/2026-03-11_evomap_launch_smoke_v1.md",
        replay_count=2,
        settle_seconds=0.0,
        expect_dedup=False,
    )
    monkeypatch.setattr(module, "parse_args", lambda: args)
    monkeypatch.setattr(module, "run_smoke", lambda _: {"ok": True, "base_url": args.base_url})

    assert module.main() == 0

    report_path = output_dir / "launch_smoke.json"
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["output_dir"] == str(output_dir)


def test_main_writes_timeout_failure_report(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "evomap_launch_smoke_timeout"
    args = argparse.Namespace(
        output_dir=str(output_dir),
        base_url="http://127.0.0.1:18711",
        issue_limit=5,
        planning_query="合同 商务 底线",
        planning_top_k=5,
        db_path="data/evomap_knowledge.db",
        api_key_env="OPENMIND_API_KEY",
        api_token_env="CHATGPTREST_API_TOKEN",
        trace_id="trace-timeout",
        session_id="session-timeout",
        event_id="event-timeout",
        task_ref="telemetry-p0/launch-smoke",
        source="codex",
        agent_name="codex",
        artifact_path="docs/dev_log/2026-03-11_evomap_launch_smoke_v1.md",
        replay_count=1,
        settle_seconds=0.0,
        expect_dedup=False,
    )
    monkeypatch.setattr(module, "parse_args", lambda: args)
    monkeypatch.setattr(module, "run_smoke", lambda _: (_ for _ in ()).throw(TimeoutError("telemetry timeout")))

    assert module.main() == 1
    payload = json.loads((output_dir / "launch_smoke.json").read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["error_type"] == "TimeoutError"
