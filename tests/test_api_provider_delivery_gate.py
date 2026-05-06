from __future__ import annotations

from pathlib import Path

import chatgptrest.eval.api_provider_delivery_gate as mod


def test_run_api_provider_delivery_gate_passes_with_monkeypatched_live_calls(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "_post_advise",
        lambda **kwargs: {
            "status_code": 200,
            "body": {
                "status": "completed",
                "selected_route": "hybrid",
                "controller_status": "DELIVERED",
                "answer": "done",
                "route_result": {"route": "quick_ask"},
            },
        },
    )
    monkeypatch.setattr(
        mod,
        "_get_trace_snapshot",
        lambda **kwargs: {
            "status": "completed",
            "selected_route": "hybrid",
            "answer": "done",
            "route_result": {"route": "quick_ask"},
        },
    )
    monkeypatch.setattr(
        mod,
        "_read_llm_events",
        lambda **kwargs: [
            {
                "source": "llm_connector",
                "event_type": "llm.call_completed",
                "trace_id": kwargs["trace_id"],
                "data": {"model": "coding_plan/MiniMax-M2.5", "preset": "default"},
            }
        ],
    )
    monkeypatch.setattr(mod, "_load_tokens", lambda env_file: {"OPENMIND_API_KEY": "token", "CHATGPTREST_API_TOKEN": ""})
    monkeypatch.setattr(mod, "_build_auth_header", lambda tokens: {"X-Api-Key": "token"})

    report = mod.run_api_provider_delivery_gate(base_url="http://127.0.0.1:18711")

    assert report.num_checks == 3
    assert report.num_failed == 0


def test_eventbus_llm_trace_correlation_fails_without_event() -> None:
    check = mod._build_llm_event_correlation_check(llm_events=[], trace_id="phase21-empty")

    assert not check.passed
    assert "event_count" in check.mismatches


def test_api_provider_delivery_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = mod.ApiProviderDeliveryGateReport(
        base_url="http://127.0.0.1:18711",
        trace_id="phase21-sample",
        num_checks=1,
        num_passed=1,
        num_failed=0,
        checks=[mod.ApiProviderDeliveryCheck(name="live_advise_delivery", passed=True, details={"http_status": 200})],
        scope_boundary=["scoped api-provider delivery"],
    )

    json_path, md_path = mod.write_api_provider_delivery_gate_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    assert "API Provider Delivery Gate Report" in md_path.read_text(encoding="utf-8")
