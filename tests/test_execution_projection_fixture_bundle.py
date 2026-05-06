from __future__ import annotations

import json
from pathlib import Path


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_projection_fixture_bundle_20260311")


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_runner_adapter_projection_fixture_bundle_is_self_consistent() -> None:
    adapter = _load("runner_adapter_result_codex_batch_v1.json")
    projected = _load("telemetry_ingest_execution_run_completed_v1.json")
    split = _load("runner_adapter_projection_split_v1.json")

    identity = adapter["identity"]
    data = adapter["data"]

    assert split["root_canonical"]["trace_id"] == identity["trace_id"] == projected["trace_id"]
    assert split["root_canonical"]["session_id"] == identity["session_id"] == projected["session_id"]
    assert split["root_canonical"]["run_id"] == identity["run_id"] == projected["run_id"]
    assert split["root_canonical"]["task_ref"] == identity["task_ref"] == projected["task_ref"]
    assert split["root_canonical"]["source"] == identity["source"] == projected["source"]
    assert split["root_canonical"]["repo_name"] == identity["repo_name"] == projected["repo_name"]
    assert split["root_canonical"]["repo_path"] == identity["repo_path"] == projected["repo_path"]
    assert split["root_canonical"]["agent_name"] == identity["agent_name"] == projected["agent_name"]
    assert split["root_canonical"]["agent_source"] == identity["agent_source"] == projected["agent_source"]

    assert split["execution_extensions"]["lane_id"] == adapter["lane_id"] == projected["lane_id"]
    assert split["execution_extensions"]["adapter_id"] == adapter["adapter_id"] == projected["adapter_id"]
    assert split["execution_extensions"]["profile_id"] == data["effective_profile"] == projected["profile_id"]
    assert split["execution_extensions"]["executor_kind"] == data["executor_kind"] == projected["executor_kind"]

    assert split["event_payload_metadata"]["adapter_ticket_id"] == data["ticket_id"] == projected["adapter_ticket_id"]
    assert split["event_payload_metadata"]["fallback_used"] == data["fallback_used"] == projected["fallback_used"]
    assert split["event_payload_metadata"]["approval_mode_effective"] == data["approval_mode_effective"] == projected["approval_mode_effective"]
    assert split["event_payload_metadata"]["result_type"] == data["result_type"] == projected["result_type"]
    assert split["event_payload_metadata"]["output_ref"] == data["output_ref"] == projected["output_ref"]
    assert split["event_payload_metadata"]["state"] == data["state"] == projected["state"]
    assert split["event_payload_metadata"]["cost"] == data["cost"] == projected["cost"]


def test_live_archive_mapping_fixture_bundle_is_self_consistent() -> None:
    live = _load("live_bus_team_run_completed_v1.json")
    archive = _load("archive_envelope_agent_task_closeout_v1.json")
    split = _load("live_archive_mapping_split_v1.json")

    shared_root = split["shared_root_correlation_fields"]
    assert shared_root["trace_id"] == live["trace_id"] == archive["trace_id"]
    assert shared_root["session_id"] == live["session_id"] == archive["session_id"]
    assert shared_root["run_id"] == live["run_id"] == archive["run_id"]
    assert shared_root["task_ref"] == live["task_ref"] == archive["task_ref"]
    assert shared_root["repo_name"] == live["repo_name"] == archive["repo"]["name"]
    assert shared_root["repo_path"] == live["repo_path"] == archive["repo"]["path"]
    assert shared_root["agent_name"] == live["agent_name"] == archive["agent"]["name"]
    assert shared_root["agent_source"] == live["agent_source"] == archive["agent"]["source"]

    shared_ext = split["shared_execution_extensions"]
    assert shared_ext["lane_id"] == live["lane_id"] == archive["lane_id"]
    assert shared_ext["role_id"] == live["role_id"] == archive["role_id"]
    assert shared_ext["executor_kind"] == live["executor_kind"] == archive["executor_kind"]

    assert split["live_bus_only_fields"]["event_type"] == live["event_type"]
    assert split["live_bus_only_fields"]["event_id"] == live["event_id"]
    assert split["live_bus_only_fields"]["upstream_event_id"] == live["upstream_event_id"]
    assert split["live_bus_only_fields"]["provider"] == live["provider"]
    assert split["live_bus_only_fields"]["model"] == live["model"]

    archive_only = split["archive_envelope_only_fields"]
    assert archive_only["event_type"] == archive["event_type"]
    assert archive_only["schema_version"] == archive["schema_version"]
    assert archive_only["ts"] == archive["ts"]
    assert archive_only["adapter_id"] == archive["adapter_id"]
    assert archive_only["profile_id"] == archive["profile_id"]
    assert archive_only["closeout"] == archive["closeout"]
