from __future__ import annotations

import asyncio

from chatgptrest.mcp import server


def test_mcp_sre_fix_request_submit_uses_shared_payload_contract(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return {"job_id": "sre-fix-1", "status": "queued"}

    async def fake_notify(job, *, notify_done):
        return None

    monkeypatch.setattr(server, "chatgptrest_job_create", fake_create)
    monkeypatch.setattr(server, "_maybe_notify_done", fake_notify)

    result = asyncio.run(
        server.chatgptrest_sre_fix_request_submit(
            idempotency_key="idem-sre",
            issue_id="iss_1",
            incident_id="inc_1",
            job_id="target_1",
            symptom="answer only contains json",
            instructions="Prefer a p0 patch proposal.",
            lane_id="lane-1",
            context={"source": "pytest"},
            context_pack={"recent_failures": [{"job_id": "job-1"}], "system_state": {"driver": "degraded"}},
            timeout_seconds=300,
            model="gpt-5-codex",
            resume_lane=False,
            route_mode="plan_only",
            runtime_apply_actions=False,
            runtime_max_risk="medium",
            runtime_allow_actions=["restart_driver"],
            open_pr_mode="p1",
            open_pr_run_tests=True,
            gitnexus_limit=7,
            notify_controller=False,
            notify_done=False,
        )
    )

    assert result["job_id"] == "sre-fix-1"
    assert captured["kind"] == "sre.fix_request"
    assert captured["input"] == {
        "issue_id": "iss_1",
        "incident_id": "inc_1",
        "job_id": "target_1",
        "symptom": "answer only contains json",
        "instructions": "Prefer a p0 patch proposal.",
        "lane_id": "lane-1",
        "context": {"source": "pytest"},
        "context_pack": {"recent_failures": [{"job_id": "job-1"}], "system_state": {"driver": "degraded"}},
    }
    assert captured["params"] == {
        "timeout_seconds": 300,
        "model": "gpt-5-codex",
        "resume_lane": False,
        "route_mode": "plan_only",
        "runtime_apply_actions": False,
        "runtime_max_risk": "medium",
        "runtime_allow_actions": ["restart_driver"],
        "open_pr_mode": "p1",
        "open_pr_run_tests": True,
        "gitnexus_limit": 7,
    }
