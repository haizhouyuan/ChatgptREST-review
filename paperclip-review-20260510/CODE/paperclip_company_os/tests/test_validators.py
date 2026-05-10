"""Tests for paperclip_company_os validators."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from paperclip_company_os.validators import (
    validate_evidence_manifest,
    validate_approval_record,
    validate_closeout,
    validate_config_gate_bundle,
    validate_real_agent_loop,
    validate_operator_truth,
    verify_full_manifest,
    verify_recursive_packet_manifests,
)


class TestValidateCloseout:
    def test_pass_closeout_with_blockers_fails(self, tmp_path: Path):
        path = tmp_path / "closeout.json"
        path.write_text(
            json.dumps(
                {
                    "company": "test",
                    "issue_identifier": "TEST-1",
                    "issue_id": "1",
                    "status": "pass",
                    "runtime_preflight": {"status": "pass"},
                    "evidence": [{"evidence_path": "/tmp/fake"}],
                    "validators": [{"status": "pass", "command": "echo ok"}],
                    "memory_closeout": {
                        "disposition": "no_write_reason",
                        "no_write_reason": "none",
                    },
                    "paperclip_readback": {"issue_id": "1", "status": "done"},
                    "blockers": ["something"],
                }
            )
        )
        errors = validate_closeout(path)
        assert any("pass closeout cannot contain blockers" in e for e in errors)

    def test_valid_closeout_passes(self, tmp_path: Path):
        path = tmp_path / "closeout.json"
        path.write_text(
            json.dumps(
                {
                    "company": "test",
                    "issue_identifier": "TEST-1",
                    "issue_id": "1",
                    "status": "pass",
                    "runtime_preflight": {"status": "pass"},
                    "evidence": [{"evidence_path": str(path)}],
                    "validators": [{"status": "pass", "command": "echo ok"}],
                    "memory_closeout": {
                        "disposition": "no_write_reason",
                        "no_write_reason": "none",
                    },
                    "paperclip_readback": {"issue_id": "1", "status": "done"},
                }
            )
        )
        errors = validate_closeout(path, base=tmp_path)
        assert errors == []


class TestValidateApprovalRecord:
    def test_missing_keys(self):
        errors = validate_approval_record({})
        assert any("missing key" in e for e in errors)

    def test_approved_without_rollback(self):
        record = {
            "change_id": "c1",
            "kind": "runtime",
            "title": "t",
            "description": "d",
            "affected_runtimes": ["r1"],
            "proposed_by": "alice",
            "current_state": "bounded_change",
            "approval_decision": "approve",
            "approved_by": "bob",
            "approved_at": "2024-01-01T00:00:00Z",
        }
        errors = validate_approval_record(record)
        assert any("rollback_commands" in e for e in errors)
        assert any("smoke_commands" in e for e in errors)

    def test_approved_with_rollback_and_smoke_passes(self):
        record = {
            "change_id": "c1",
            "kind": "runtime",
            "title": "t",
            "description": "d",
            "affected_runtimes": ["r1"],
            "proposed_by": "alice",
            "current_state": "bounded_change",
            "approval_decision": "approve",
            "approved_by": "bob",
            "approved_at": "2024-01-01T00:00:00Z",
            "rollback_commands": ["git checkout -- file"],
            "smoke_commands": ["pytest"],
        }
        errors = validate_approval_record(record)
        assert errors == []

    def test_blocked_without_blockers(self):
        record = {
            "change_id": "c1",
            "kind": "runtime",
            "title": "t",
            "description": "d",
            "affected_runtimes": ["r1"],
            "proposed_by": "alice",
            "current_state": "blocked",
        }
        errors = validate_approval_record(record)
        assert any("blockers" in e for e in errors)


class TestValidateConfigGateBundle:
    def test_missing_markers(self, tmp_path: Path):
        errors = validate_config_gate_bundle(tmp_path)
        assert any("missing gated config-change evidence" in e for e in errors)

    def test_empty_evidence_file_rejected(self, tmp_path: Path):
        (tmp_path / "snapshot_manifest.json").write_text("{}")
        (tmp_path / "proposal.md").write_text("")
        (tmp_path / "risk_review.md").write_text("reviewed")
        (tmp_path / "bounded_change.diff").write_text("diff")
        (tmp_path / "smoke_probe.log").write_text("ok")
        (tmp_path / "rollback.sh").write_text("rollback")
        (tmp_path / "closeout.json").write_text("{}")
        errors = validate_config_gate_bundle(tmp_path)
        assert any("empty evidence file" in e for e in errors)

    def test_invalid_config_change_record_rejected(self, tmp_path: Path):
        (tmp_path / "snapshot_manifest.json").write_text("{}")
        (tmp_path / "proposal.md").write_text("proposal")
        (tmp_path / "risk_review.md").write_text("reviewed")
        (tmp_path / "bounded_change.diff").write_text("diff")
        (tmp_path / "smoke_probe.log").write_text("ok")
        (tmp_path / "rollback.sh").write_text("rollback")
        (tmp_path / "closeout.json").write_text("{}")

        bad_record = {
            "change_id": "c1",
            "kind": "runtime",
            "title": "t",
            "description": "d",
            "affected_runtimes": ["r1"],
            "proposed_by": "alice",
            "current_state": "bounded_change",
            "approval_decision": "approve",
            "approved_by": "bob",
            "approved_at": "2024-01-01T00:00:00Z",
            # missing rollback_commands and smoke_commands
        }
        (tmp_path / "change_record.json").write_text(json.dumps(bad_record))
        errors = validate_config_gate_bundle(tmp_path)
        assert any("rollback_commands" in e for e in errors)
        assert any("smoke_commands" in e for e in errors)


    def test_approved_bounded_change_missing_paths(self, tmp_path: Path):
        # Setup: Create a minimal bundle structure and a ConfigChangeRecord
        record_path = tmp_path / "change_record.json"
        record = {
            "change_id": "c1",
            "kind": "runtime",
            "title": "t",
            "description": "d",
            "affected_runtimes": ["r1"],
            "proposed_by": "alice",
            "current_state": "bounded_change",
            "approval_decision": "approve",
            "approved_by": "bob",
            "approved_at": "2024-01-01T00:00:00Z",
            "rollback_commands": ["git checkout -- file"],
            "smoke_commands": ["pytest"],
            "snapshot_paths": ["non_existent_snap.json"],
            "proposal_paths": ["non_existent_prop.md"],
        }
        record_path.write_text(json.dumps(record))

        # Add other required marker files (empty for now)
        (tmp_path / "snapshot_manifest.json").write_text("{}")
        (tmp_path / "proposal.md").write_text("proposal")
        (tmp_path / "risk_review.md").write_text("reviewed")
        (tmp_path / "bounded_change.diff").write_text("diff")
        (tmp_path / "smoke_probe.log").write_text("ok")
        (tmp_path / "rollback.sh").write_text("rollback")
        (tmp_path / "closeout.json").write_text("{}")

        # 1. Test when paths do not exist
        errors = validate_config_gate_bundle(tmp_path)
        assert any("snapshot path does not exist: non_existent_snap.json" in e for e in errors)
        assert any("proposal path does not exist: non_existent_prop.md" in e for e in errors)

        # 2. Create the missing files
        (tmp_path / "non_existent_snap.json").write_text("{}")
        (tmp_path / "non_existent_prop.md").write_text("content")

        # 3. Re-run validation, expect no errors related to path existence
        errors = validate_config_gate_bundle(tmp_path)
        assert not any("snapshot path does not exist" in e for e in errors)
        assert not any("proposal path does not exist" in e for e in errors)
        # Ensure other errors are still caught if applicable
        assert errors == []

    def test_valid_bundle_passes(self, tmp_path: Path):
        (tmp_path / "snapshot_manifest.json").write_text("{}")
        (tmp_path / "proposal.md").write_text("proposal")
        (tmp_path / "risk_review.md").write_text("reviewed")
        (tmp_path / "bounded_change.diff").write_text("diff")
        (tmp_path / "smoke_probe.log").write_text("ok")
        (tmp_path / "rollback.sh").write_text("rollback")
        (tmp_path / "closeout.json").write_text("{}")

        good_record = {
            "change_id": "c1",
            "kind": "runtime",
            "title": "t",
            "description": "d",
            "affected_runtimes": ["r1"],
            "proposed_by": "alice",
            "current_state": "bounded_change",
            "approval_decision": "approve",
            "approved_by": "bob",
            "approved_at": "2024-01-01T00:00:00Z",
            "rollback_commands": ["git checkout -- file"],
            "smoke_commands": ["pytest"],
            "snapshot_paths": ["snap.json"],
            "proposal_paths": ["prop.md"],
        }
        (tmp_path / "change_record.json").write_text(json.dumps(good_record))
        # Create the files referenced in snapshot_paths and proposal_paths
        (tmp_path / "snap.json").write_text("{}")
        (tmp_path / "prop.md").write_text("content")
        errors = validate_config_gate_bundle(tmp_path)
        assert errors == []


class TestOperatorTruth:
    def test_blocked_truth_requires_master_failures(self, tmp_path: Path):
        operator = tmp_path / "operator.json"
        current = tmp_path / "current.md"
        closeout = tmp_path / "closeout.md"
        blockers = tmp_path / "blockers.md"
        operator.write_text(json.dumps({"sections": {"known_blockers": {"masterAcceptanceFailures": []}}}))
        current.write_text("status `production-usable: blocked`")
        closeout.write_text("production-usable: blocked")
        blockers.write_text("| P0-RUNTIME-001 | Runtime |")

        errors = validate_operator_truth(
            operator_json=operator,
            current_truth=current,
            closeout=closeout,
            blocker_board=blockers,
        )

        assert any("masterAcceptanceFailures is empty" in e for e in errors)
        assert any("P0-RUNTIME-001" in e for e in errors)

    def test_blocked_truth_with_p0s_passes(self, tmp_path: Path):
        operator = tmp_path / "operator.json"
        current = tmp_path / "current.md"
        closeout = tmp_path / "closeout.md"
        blockers = tmp_path / "blockers.md"
        operator.write_text(
            json.dumps(
                {
                    "sections": {
                        "known_blockers": {"masterAcceptanceFailures": ["P0-RUNTIME-001"]},
                        "validator": {"productionReady": False},
                    }
                }
            )
        )
        current.write_text("production-usable: blocked")
        closeout.write_text("production-usable: blocked")
        blockers.write_text("| P0-RUNTIME-001 | Runtime |")

        errors = validate_operator_truth(
            operator_json=operator,
            current_truth=current,
            closeout=closeout,
            blocker_board=blockers,
        )

        assert errors == []

    def test_blocked_truth_requires_exact_p0_p1_set(self, tmp_path: Path):
        operator = tmp_path / "operator.json"
        current = tmp_path / "current.md"
        closeout = tmp_path / "closeout.md"
        blockers = tmp_path / "blockers.md"
        operator.write_text(
            json.dumps(
                {
                    "sections": {
                        "known_blockers": {
                            "masterAcceptanceFailures": [
                                "P0-RUNTIME-001",
                                "P0-STALE-001",
                                "P1-PLANNING-001",
                                "P1-STALE-001",
                            ]
                        },
                        "validator": {"productionReady": False},
                    }
                }
            )
        )
        current.write_text("production-usable: blocked")
        closeout.write_text("production-usable: blocked")
        blockers.write_text("| P0-RUNTIME-001 | Runtime |\n| P1-PLANNING-001 | Planning |\n| P1-MEMORY-001 | Memory |")

        errors = validate_operator_truth(
            operator_json=operator,
            current_truth=current,
            closeout=closeout,
            blocker_board=blockers,
        )

        assert any("extra P0" in e and "P0-STALE-001" in e for e in errors)
        assert any("missing P1" in e and "P1-MEMORY-001" in e for e in errors)
        assert any("extra P1" in e and "P1-STALE-001" in e for e in errors)

    def test_operator_cli_live_parent_check_flags_blocked_parent(self, tmp_path: Path):
        # The live API check is wired in cli.py because it depends on PaperclipClient.
        # Keep this contract visible here so parent issue drift is covered by CLI tests.
        from paperclip_company_os.cli import cmd_validate_operator_truth

        operator = tmp_path / "operator.json"
        current = tmp_path / "current.md"
        closeout = tmp_path / "closeout.md"
        blockers = tmp_path / "blockers.md"
        parent_closeout = tmp_path / "parent_closeout.md"
        operator.write_text(
            json.dumps(
                {
                    "terminal_label": "HARD_EXTERNAL_BLOCKER",
                    "masterAcceptanceFailures": ["P0-KEY-ROTATION-MINIMAX"],
                    "hard_external_blockers": [{"id": "P0-KEY-ROTATION-MINIMAX", "provider": "MiniMax"}],
                    "validator": {"productionReady": False},
                }
            )
        )
        current.write_text("production-usable: blocked")
        closeout.write_text("production-usable: blocked")
        blockers.write_text("| P0-KEY-ROTATION-MINIMAX | P0 |")
        parent_closeout.write_text("parent closeout")

        class FakeClient:
            def __init__(self, _: str, api_key: str | None = None):
                pass

            def get(self, path: str):
                assert path == "issues/PAP-10"
                return {
                    "id": "parent-id",
                    "status": "blocked",
                    "updatedAt": "2026-05-07T00:00:00Z",
                    "completedAt": None,
                }

        import paperclip_company_os.cli as cli

        original = cli.PaperclipClient
        cli.PaperclipClient = FakeClient
        try:
            args = type(
                "Args",
                (),
                {
                    "operator_json": str(operator),
                    "current_truth": str(current),
                    "closeout": str(closeout),
                    "blocker_board": str(blockers),
                    "paperclip_base_url": "http://paperclip.test/api",
                    "paperclip_api_key": None,
                    "parent_issues": "PAP-10",
                    "parent_allowed_statuses": "done",
                    "parent_closeout": str(parent_closeout),
                    "output": str(tmp_path / "result.json"),
                },
            )()
            assert cmd_validate_operator_truth(args) == 1
            result = json.loads((tmp_path / "result.json").read_text())
            assert result["rules"]["no_unexplained_blocked_parent_issue_live_api"] == "fail"
            assert any("PAP-10" in error and "blocked" in error for error in result["errors"])
        finally:
            cli.PaperclipClient = original


class TestEvidenceManifest:
    def test_manifest_checks_sha(self, tmp_path: Path):
        artifact = tmp_path / "artifact.md"
        artifact.write_text("hello")
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "master_status": "production-usable: blocked",
                    "artifacts": [
                        {
                            "id": "A",
                            "path": str(artifact),
                            "sha256": "bad",
                            "role": "test",
                        }
                    ],
                }
            )
        )
        errors = validate_evidence_manifest(manifest)
        assert any("sha256 mismatch" in e for e in errors)

    def test_manifest_accepts_user_scoped_provider_quarantine_status(self, tmp_path: Path):
        artifact = tmp_path / "artifact.md"
        artifact.write_text("hello")
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "master_status": "user-scoped-passed; provider-quarantine-active",
                    "artifacts": [
                        {
                            "id": "A",
                            "path": str(artifact),
                            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                            "role": "test",
                        }
                    ],
                }
            )
        )

        assert validate_evidence_manifest(manifest) == []

    def test_local_board_readback_fails_real_agent_loop_gate(self, tmp_path: Path):
        closeout = tmp_path / "09_closeout.md"
        closeout.write_text("closeout")
        readback = {
            "issue_identifier": "FIN-26",
            "issue_id": "issue-id",
            "paperclip_status": "done",
            "issue_after": {
                "identifier": "FIN-26",
                "id": "issue-id",
                "status": "done",
                "originKind": "manual",
                "createdByUserId": "local-board",
                "assigneeAgentId": None,
                "executionRunId": None,
                "checkoutRunId": None,
                "description": f"Evidence root: {tmp_path}",
                "comment": {
                    "authorUserId": "local-board",
                    "authorAgentId": None,
                    "createdByRunId": None,
                    "body": f"closeout: {closeout}",
                },
            },
        }
        (tmp_path / "paperclip_readback.json").write_text(json.dumps(readback))

        result = validate_real_agent_loop(tmp_path)

        assert result["status"] == "fail"
        assert any("assigneeAgentId" in error for error in result["errors"])
        assert any("executionRunId" in error for error in result["errors"])
        assert any("comment authorAgentId" in error for error in result["errors"])
        assert result["checks"]["artifact_path_readable"] is True

    def test_agent_run_evidence_passes_real_agent_loop_gate(self, tmp_path: Path):
        closeout = tmp_path / "09_closeout.md"
        closeout.write_text("closeout")
        readback = {
            "issue_identifier": "FIN-100",
            "issue_id": "issue-id",
            "paperclip_status": "done",
            "issue_after": {
                "identifier": "FIN-100",
                "id": "issue-id",
                "status": "done",
                "originKind": "agent",
                "createdByAgentId": "agent-create",
                "assigneeAgentId": "agent-runner",
                "executionRunId": "run-1",
                "description": f"Evidence root: {tmp_path}",
                "comment": {
                    "authorAgentId": "agent-runner",
                    "createdByRunId": "run-1",
                    "body": f"closeout: {closeout}",
                },
            },
        }
        (tmp_path / "paperclip_readback.json").write_text(json.dumps(readback))
        (tmp_path / "heartbeat_result.json").write_text(json.dumps({"status": "success", "run_id": "run-1"}))
        (tmp_path / "agent_status.json").write_text(json.dumps({"status": "active", "agent_id": "agent-runner"}))

        result = validate_real_agent_loop(tmp_path)

        assert result["status"] == "pass"
        assert result["errors"] == []

    def test_full_manifest_requires_terminal_issue_traceability(self, tmp_path: Path):
        artifact = tmp_path / "validator.json"
        artifact.write_text(json.dumps({"ok": True}))
        pap13 = tmp_path / "PAP13_evidence_manifest.json"
        pap13.write_text(json.dumps({"pap13RunId": "run-a", "referencedSmokeRunId": "run-b"}))
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "master_status": "production-usable: blocked",
                    "artifacts": [
                        {
                            "id": "TEST-VALIDATOR",
                            "path": str(artifact),
                            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                            "issue": "TEST-1",
                            "role": "validator",
                        },
                        {
                            "id": "PAP13-EVIDENCE-MANIFEST",
                            "path": str(pap13),
                            "sha256": hashlib.sha256(pap13.read_bytes()).hexdigest(),
                            "issue": "PAP-13",
                            "role": "evidence manifest",
                        },
                    ],
                    "terminal_issue_readback": [
                        {"issue": "TEST-1", "status": "done", "updated_at": "now"},
                        {
                            "issue": "PAP-13",
                            "status": "blocked",
                            "issue_id": "uuid",
                            "run_id": "run-a",
                            "updated_at": "now",
                            "validator_artifact_id": "TEST-VALIDATOR",
                            "no_write_reason": "validator-only test",
                        },
                    ],
                    "open_manifest_gaps": [],
                }
            )
        )

        result = verify_full_manifest(manifest)

        assert result["status"] == "fail"
        assert any("TEST-1: missing Paperclip issue UUID/id" in e for e in result["errors"])
        assert any("TEST-1: missing run_id/run_ids" in e for e in result["errors"])
        assert any("TEST-1: missing memory closeout" in e for e in result["errors"])

    def test_full_manifest_passes_traceable_blocked_manifest(self, tmp_path: Path):
        validator = tmp_path / "validator.json"
        validator.write_text(json.dumps({"ok": True}))
        memory = tmp_path / "memory_closeout.json"
        memory.write_text(json.dumps({"disposition": "no_write_reason"}))
        pap13 = tmp_path / "PAP13_evidence_manifest.json"
        pap13.write_text(json.dumps({"pap13RunId": "run-a", "referencedSmokeRunId": "run-b"}))
        artifacts = [
            {
                "id": "TEST-VALIDATOR",
                "path": str(validator),
                "issue": "TEST-1",
                "role": "validator",
            },
            {
                "id": "TEST-MEMORY",
                "path": str(memory),
                "issue": "TEST-1",
                "role": "memory closeout",
            },
            {
                "id": "PAP13-EVIDENCE-MANIFEST",
                "path": str(pap13),
                "issue": "PAP-13",
                "role": "evidence manifest",
            },
            {
                "id": "PAP13-VALIDATOR",
                "path": str(validator),
                "issue": "PAP-13",
                "role": "validator",
            },
            {
                "id": "PAP13-MEMORY",
                "path": str(memory),
                "issue": "PAP-13",
                "role": "memory closeout",
            },
        ]
        for item in artifacts:
            item["sha256"] = hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest()
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "master_status": "production-usable: blocked",
                    "artifacts": artifacts,
                    "terminal_issue_readback": [
                        {
                            "issue": "TEST-1",
                            "status": "done",
                            "issue_id": "uuid-1",
                            "run_id": "run-1",
                            "updated_at": "now",
                        },
                        {
                            "issue": "PAP-13",
                            "status": "blocked",
                            "issue_id": "uuid-2",
                            "run_id": "run-a",
                            "updated_at": "now",
                        },
                    ],
                    "open_manifest_gaps": [],
                }
            )
        )

        result = verify_full_manifest(manifest)

        assert result["status"] == "pass"
        assert result["errors"] == []


class TestRealAgentLoopMeaningful:
    def test_manual_origin_with_agent_execution_passes(self, tmp_path: Path):
        closeout = tmp_path / "09_closeout.md"
        closeout.write_text("closeout")
        readback = {
            "issue_identifier": "FIN-100",
            "issue_id": "issue-id",
            "paperclip_status": "done",
            "issue_after": {
                "identifier": "FIN-100",
                "id": "issue-id",
                "status": "done",
                "originKind": "manual",
                "createdByAgentId": "agent-create",
                "assigneeAgentId": "agent-runner",
                "executionRunId": "run-1",
                "checkoutRunId": "run-1",
                "description": f"Evidence root: {tmp_path}",
                "comment": {
                    "authorAgentId": "agent-runner",
                    "createdByRunId": "run-1",
                    "body": f"closeout: {closeout}",
                },
            },
        }
        (tmp_path / "paperclip_readback.json").write_text(json.dumps(readback))
        (tmp_path / "heartbeat_result.json").write_text(json.dumps({"status": "success", "run_id": "run-1"}))
        (tmp_path / "agent_status.json").write_text(json.dumps({"status": "active", "agent_id": "agent-runner"}))

        result = validate_real_agent_loop(tmp_path)

        assert result["status"] == "pass"
        assert result["errors"] == []
        assert result["checks"]["originKind_observed"] is True

    def test_controller_run_id_fails(self, tmp_path: Path):
        closeout = tmp_path / "09_closeout.md"
        closeout.write_text("closeout")
        readback = {
            "issue_identifier": "FIN-100",
            "issue_id": "issue-id",
            "paperclip_status": "done",
            "issue_after": {
                "identifier": "FIN-100",
                "id": "issue-id",
                "status": "done",
                "originKind": "agent",
                "createdByAgentId": "agent-create",
                "assigneeAgentId": "agent-runner",
                "executionRunId": "controller-pap22",
                "description": f"Evidence root: {tmp_path}",
                "comment": {
                    "authorAgentId": "agent-runner",
                    "createdByRunId": "controller-pap22",
                    "body": f"closeout: {closeout}",
                },
            },
        }
        (tmp_path / "paperclip_readback.json").write_text(json.dumps(readback))
        (tmp_path / "heartbeat_result.json").write_text(json.dumps({"status": "success", "run_id": "controller-pap22"}))
        (tmp_path / "agent_status.json").write_text(json.dumps({"status": "active", "agent_id": "agent-runner"}))

        result = validate_real_agent_loop(tmp_path)

        assert result["status"] == "fail"
        assert any("controller run" in error for error in result["errors"])
        assert result["checks"]["run_id_not_controller"] is False

    def test_status_mismatch_fails(self, tmp_path: Path):
        closeout = tmp_path / "09_closeout.md"
        closeout.write_text("closeout")
        readback = {
            "issue_identifier": "FIN-100",
            "issue_id": "issue-id",
            "status": "blocked",
            "paperclip_status": "blocked",
            "issue_after": {
                "identifier": "FIN-100",
                "id": "issue-id",
                "status": "done",
                "originKind": "agent",
                "createdByAgentId": "agent-create",
                "assigneeAgentId": "agent-runner",
                "executionRunId": "run-1",
                "description": f"Evidence root: {tmp_path}",
                "comment": {
                    "authorAgentId": "agent-runner",
                    "createdByRunId": "run-1",
                    "body": f"closeout: {closeout}",
                },
            },
        }
        (tmp_path / "paperclip_readback.json").write_text(json.dumps(readback))
        (tmp_path / "heartbeat_result.json").write_text(json.dumps({"status": "success", "run_id": "run-1"}))
        (tmp_path / "agent_status.json").write_text(json.dumps({"status": "active", "agent_id": "agent-runner"}))

        result = validate_real_agent_loop(tmp_path)

        assert result["status"] == "fail"
        assert any("status mismatch" in error for error in result["errors"])
        assert result["checks"]["status_consistent"] is False

    def test_comment_author_mismatch_fails(self, tmp_path: Path):
        closeout = tmp_path / "09_closeout.md"
        closeout.write_text("closeout")
        readback = {
            "issue_identifier": "FIN-100",
            "issue_id": "issue-id",
            "paperclip_status": "done",
            "issue_after": {
                "identifier": "FIN-100",
                "id": "issue-id",
                "status": "done",
                "originKind": "agent",
                "createdByAgentId": "agent-create",
                "assigneeAgentId": "agent-runner",
                "executionRunId": "run-1",
                "description": f"Evidence root: {tmp_path}",
                "comment": {
                    "authorAgentId": "other-agent",
                    "createdByRunId": "run-2",
                    "body": f"closeout: {closeout}",
                },
            },
        }
        (tmp_path / "paperclip_readback.json").write_text(json.dumps(readback))
        (tmp_path / "heartbeat_result.json").write_text(json.dumps({"status": "success", "run_id": "run-1"}))
        (tmp_path / "agent_status.json").write_text(json.dumps({"status": "active", "agent_id": "agent-runner"}))

        result = validate_real_agent_loop(tmp_path)

        assert result["status"] == "fail"
        assert any("comment authorAgentId" in error and "other-agent" in error for error in result["errors"])
        assert result["checks"]["comment_author_matches_assignee"] is False

    def test_checkout_run_id_differs_fails(self, tmp_path: Path):
        closeout = tmp_path / "09_closeout.md"
        closeout.write_text("closeout")
        readback = {
            "issue_identifier": "FIN-100",
            "issue_id": "issue-id",
            "paperclip_status": "done",
            "issue_after": {
                "identifier": "FIN-100",
                "id": "issue-id",
                "status": "done",
                "originKind": "agent",
                "createdByAgentId": "agent-create",
                "assigneeAgentId": "agent-runner",
                "executionRunId": "run-1",
                "checkoutRunId": "run-2",
                "description": f"Evidence root: {tmp_path}",
                "comment": {
                    "authorAgentId": "agent-runner",
                    "createdByRunId": "run-1",
                    "body": f"closeout: {closeout}",
                },
            },
        }
        (tmp_path / "paperclip_readback.json").write_text(json.dumps(readback))
        (tmp_path / "heartbeat_result.json").write_text(json.dumps({"status": "success", "run_id": "run-1"}))
        (tmp_path / "agent_status.json").write_text(json.dumps({"status": "active", "agent_id": "agent-runner"}))

        result = validate_real_agent_loop(tmp_path)

        assert result["status"] == "fail"
        assert any("checkoutRunId" in error and "differs" in error for error in result["errors"])


class TestVerifyLiveReadback:
    def test_live_readback_match(self, tmp_path: Path):
        from paperclip_company_os.validators import verify_live_readback

        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "terminal_issue_readback": [
                        {
                            "issue": "TEST-1",
                            "status": "done",
                            "issue_id": "uuid-1",
                            "run_id": "run-1",
                            "updated_at": "now",
                        }
                    ]
                }
            )
        )

        class FakeClient:
            def get(self, path: str):
                return {
                    "id": "uuid-1",
                    "status": "done",
                    "executionRunId": "run-1",
                    "assigneeAgentId": "agent-1",
                    "updatedAt": "now",
                    "completedAt": "now",
                }

        result = verify_live_readback(manifest, FakeClient())
        assert result["status"] == "pass"
        assert result["matched_count"] == 1
        assert result["mismatched_count"] == 0

    def test_live_readback_status_mismatch(self, tmp_path: Path):
        from paperclip_company_os.validators import verify_live_readback

        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "terminal_issue_readback": [
                        {
                            "issue": "TEST-1",
                            "status": "done",
                            "issue_id": "uuid-1",
                            "run_id": "run-1",
                            "updated_at": "now",
                        }
                    ]
                }
            )
        )

        class FakeClient:
            def get(self, path: str):
                return {
                    "id": "uuid-1",
                    "status": "blocked",
                    "executionRunId": "run-1",
                    "assigneeAgentId": "agent-1",
                    "updatedAt": "now",
                }

        result = verify_live_readback(manifest, FakeClient())
        assert result["status"] == "fail"
        assert result["mismatched_count"] == 1
        assert any("status mismatch" in e for e in result["errors"])

    def test_live_readback_unreachable(self, tmp_path: Path):
        from paperclip_company_os.validators import verify_live_readback

        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "terminal_issue_readback": [
                        {
                            "issue": "TEST-1",
                            "status": "done",
                            "issue_id": "uuid-1",
                            "run_id": "run-1",
                            "updated_at": "now",
                        }
                    ]
                }
            )
        )

        class FakeClient:
            def get(self, path: str):
                raise RuntimeError("connection refused")

        result = verify_live_readback(manifest, FakeClient())
        assert result["status"] == "fail"
        assert result["unreachable_count"] == 1
        assert any("live readback failed" in e for e in result["errors"])

    def test_live_readback_missing_issue_id(self, tmp_path: Path):
        from paperclip_company_os.validators import verify_live_readback

        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "terminal_issue_readback": [
                        {
                            "issue": "TEST-1",
                            "status": "done",
                            "updated_at": "now",
                        }
                    ]
                }
            )
        )

        class FakeClient:
            pass

        result = verify_live_readback(manifest, FakeClient())
        assert result["status"] == "fail"
        assert any("missing issue_id" in e for e in result["errors"])


class TestRecursivePacketManifests:
    def test_missing_nested_artifact_fails(self, tmp_path: Path):
        root = tmp_path / "packet"
        (root / "docs").mkdir(parents=True)
        (root / "docs/primary.json").write_text(json.dumps({"artifacts": []}))
        (root / "docs/nested.json").write_text(
            json.dumps({"artifacts": [{"path": "docs/missing.md", "sha256": "x"}]})
        )

        result = verify_recursive_packet_manifests(
            root=root,
            manifest=Path("docs/primary.json"),
            nested=[Path("docs/nested.json")],
        )

        assert result["status"] == "fail"
        assert result["missing"]
        assert result["uncovered_nested_refs"]

    def test_nested_artifact_hash_passes(self, tmp_path: Path):
        root = tmp_path / "packet"
        (root / "docs").mkdir(parents=True)
        artifact = root / "docs/artifact.md"
        artifact.write_text("ok", encoding="utf-8")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        (root / "docs/primary.json").write_text(json.dumps({"artifacts": []}))
        (root / "docs/nested.json").write_text(
            json.dumps({"artifacts": [{"path": "docs/artifact.md", "sha256": digest}]})
        )

        result = verify_recursive_packet_manifests(
            root=root,
            manifest=Path("docs/primary.json"),
            nested=[Path("docs/nested.json")],
        )

        assert result["status"] == "pass"
        assert result["missing"] == []
        assert result["bad_hash"] == []
        assert result["uncovered_nested_refs"] == []
