from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.cognitive.wakeup_packet import WakeUpPacket, WakeUpPacketLayer
from ops.run_wakeup_packet_harness import run_harness


def test_run_wakeup_packet_harness_writes_packet_artifacts(tmp_path: Path, monkeypatch) -> None:
    packet = WakeUpPacket(
        schema_version="openmind-wakeup-packet-v1",
        packet_id="pkt-1",
        generated_at="2026-04-09T00:00:00+00:00",
        trace_id="trace-1",
        query="继续推进 beta rollout",
        project_id="prj-beta",
        source_precedence="authority anchor > project memory > EvoMap knowledge > runtime heuristics",
        degraded=False,
        degraded_sources=[],
        identity={"session_id": "sess-1", "account_id": "acct-1", "agent_id": "advisor", "role_id": "planning", "thread_id": "thread-1"},
        token_summary={"context_used_tokens": 120, "requested_token_budget": 4500, "layer_count": 2},
        provenance_summary={},
        quality_receipt={"comparison_digest": "digest-1", "layer_order": ["L0", "L3"], "coverage_ratio": 0.5},
        layers=[
            WakeUpPacketLayer(
                layer_id="L0",
                title="Authority anchor",
                summary="Pilot stays in controlled rollout.",
                provenance=[{"type": "authority_anchor", "path": "/tmp/prj-beta/_project_context.md"}],
                signals={},
            ),
            WakeUpPacketLayer(
                layer_id="L3",
                title="Runtime handoff / recommended next step",
                summary="Recommended next step: confirm finance sign-off",
                provenance=[],
                signals={},
            ),
        ],
    )
    monkeypatch.setattr(
        "ops.run_wakeup_packet_harness.build_wakeup_packet",
        lambda **kwargs: packet,  # noqa: ARG005
    )

    summary = run_harness(
        runtime=object(),
        output_root=tmp_path / "artifacts",
        query="继续推进 beta rollout",
        project_id="prj-beta",
        trace_id="trace-1",
    )

    assert summary["ok"] is True
    packet_json = Path(summary["artifacts"]["packet_json"])
    packet_md = Path(summary["artifacts"]["packet_md"])
    assert packet_json.exists()
    assert packet_md.exists()
    payload = json.loads(packet_json.read_text(encoding="utf-8"))
    assert payload["packet_id"] == "pkt-1"
    assert "Wake-up packet" in packet_md.read_text(encoding="utf-8")
    assert "Packet quality receipt" in packet_md.read_text(encoding="utf-8")
