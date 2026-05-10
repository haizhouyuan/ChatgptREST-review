from __future__ import annotations

import json
import re
import hashlib
from pathlib import Path
from typing import Any


REQUIRED_CLOSEOUT_KEYS = {
    "company",
    "issue_identifier",
    "issue_id",
    "status",
    "runtime_preflight",
    "evidence",
    "validators",
    "memory_closeout",
    "paperclip_readback",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate_closeout(path: Path, *, base: Path | None = None) -> list[str]:
    data = load_json(path)
    errors: list[str] = []
    missing = sorted(REQUIRED_CLOSEOUT_KEYS.difference(data))
    errors.extend(f"missing key: {key}" for key in missing)

    status = data.get("status")
    if status not in {"pass", "fail", "blocked"}:
        errors.append("status must be pass, fail or blocked")

    runtime_preflight = data.get("runtime_preflight")
    if not isinstance(runtime_preflight, dict):
        errors.append("runtime_preflight must be an object")
    elif runtime_preflight.get("status") not in {"pass", "fail", "blocked"}:
        errors.append("runtime_preflight.status must be pass, fail or blocked")

    evidence = data.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("evidence must be a non-empty list")
    else:
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                errors.append(f"evidence[{index}] must be an object")
                continue
            evidence_path = item.get("evidence_path")
            if not evidence_path:
                errors.append(f"evidence[{index}].evidence_path is required")
            else:
                resolved = Path(evidence_path)
                if not resolved.is_absolute() and base is not None:
                    resolved = base / resolved
                if not resolved.exists():
                    errors.append(f"evidence path does not exist: {evidence_path}")

    validators = data.get("validators")
    if not isinstance(validators, list) or not validators:
        errors.append("validators must be a non-empty list")
    else:
        for index, item in enumerate(validators):
            if not isinstance(item, dict):
                errors.append(f"validators[{index}] must be an object")
                continue
            if item.get("status") not in {"pass", "fail", "blocked"}:
                errors.append(f"validators[{index}].status must be pass, fail or blocked")
            if not item.get("command"):
                errors.append(f"validators[{index}].command is required")

    memory = data.get("memory_closeout")
    if not isinstance(memory, dict):
        errors.append("memory_closeout must be an object")
    elif memory.get("disposition") not in {"candidate_memory_delta", "no_write_reason"}:
        errors.append("memory_closeout.disposition must be candidate_memory_delta or no_write_reason")
    elif memory.get("disposition") == "no_write_reason" and not memory.get("no_write_reason"):
        errors.append("memory_closeout.no_write_reason is required for no_write_reason disposition")

    readback = data.get("paperclip_readback")
    if not isinstance(readback, dict):
        errors.append("paperclip_readback must be an object")
    else:
        if not readback.get("issue_id"):
            errors.append("paperclip_readback.issue_id is required")
        if not readback.get("status"):
            errors.append("paperclip_readback.status is required")

    if status == "pass" and data.get("blockers"):
        errors.append("pass closeout cannot contain blockers")

    return errors


def validate_json_tree(root: Path) -> list[str]:
    errors: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in {".json", ".jsonl"}:
            continue
        try:
            if path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
            else:
                for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if line.strip():
                        json.loads(line)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path}:{lineno if path.suffix == '.jsonl' else 1}: {exc}")
    return errors


def _extract_issue_like_ids(text: str, prefix: str) -> set[str]:
    return set(re.findall(rf"\b{re.escape(prefix)}-[A-Z0-9][A-Z0-9-]*\b", text))


def _nested_get(data: dict[str, Any], keys: list[str]) -> Any:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def validate_operator_truth(
    *,
    operator_json: Path,
    current_truth: Path,
    closeout: Path,
    blocker_board: Path,
) -> list[str]:
    """Fail closed when operator surface contradicts master truth docs."""
    return validate_operator_truth_detailed(
        operator_json=operator_json,
        current_truth=current_truth,
        closeout=closeout,
        blocker_board=blocker_board,
    )["errors"]


def validate_operator_truth_detailed(
    *,
    operator_json: Path,
    current_truth: Path,
    closeout: Path,
    blocker_board: Path,
) -> dict[str, Any]:
    """Validate operator truth and return rule-level evidence for dashboards."""
    data = load_json(operator_json)
    current_text = current_truth.read_text(encoding="utf-8")
    closeout_text = closeout.read_text(encoding="utf-8")
    blocker_text = blocker_board.read_text(encoding="utf-8")
    truth_text = "\n".join([current_text, closeout_text, blocker_text])

    errors: list[str] = []
    rules: dict[str, str] = {}
    scoped_provider_quarantine_pass = "user-scoped-passed; provider-quarantine-active" in truth_text
    master_blocked = "production-usable: blocked" in truth_text and not scoped_provider_quarantine_pass
    failures = _nested_get(data, ["sections", "known_blockers", "masterAcceptanceFailures"])
    if failures is None:
        failures = _nested_get(data, ["known_blockers", "masterAcceptanceFailures"])
    if failures is None:
        failures = _nested_get(data, ["masterAcceptanceFailures"])

    if not isinstance(failures, list):
        errors.append("operator masterAcceptanceFailures must be a list")
        failures_set: set[str] = set()
        rules["master_acceptance_failures_list"] = "fail"
    else:
        failures_set = {str(item) for item in failures}
        rules["master_acceptance_failures_list"] = "pass"

    if master_blocked and not failures_set:
        errors.append("closeout/current truth are blocked but operator masterAcceptanceFailures is empty")
        rules["blocked_truth_has_failures"] = "fail"
    else:
        rules["blocked_truth_has_failures"] = "pass"

    required_p0s = _extract_issue_like_ids(blocker_text, "P0")
    required_p1s = _extract_issue_like_ids(blocker_text, "P1")
    reported_p0_p1 = {
        item
        for item in failures_set
        if item.startswith("P0-") or item.startswith("P1-")
    }

    missing_p0s = sorted(required_p0s.difference(failures_set))
    if master_blocked and missing_p0s:
        errors.append("operator masterAcceptanceFailures missing P0 blockers: " + ", ".join(missing_p0s))

    extra_p0s = sorted({item for item in reported_p0_p1 if item.startswith("P0-")}.difference(required_p0s))
    if master_blocked and extra_p0s:
        errors.append("operator masterAcceptanceFailures has extra P0 blockers not in blocker board: " + ", ".join(extra_p0s))

    missing_p1s = sorted(required_p1s.difference(failures_set))
    if master_blocked and missing_p1s:
        errors.append("operator masterAcceptanceFailures missing P1 blockers: " + ", ".join(missing_p1s))

    extra_p1s = sorted({item for item in reported_p0_p1 if item.startswith("P1-")}.difference(required_p1s))
    if master_blocked and extra_p1s:
        errors.append("operator masterAcceptanceFailures has extra P1 blockers not in blocker board: " + ", ".join(extra_p1s))
    rules["exact_p0_p1_set"] = (
        "pass" if not (missing_p0s or extra_p0s or missing_p1s or extra_p1s) else "fail"
    )

    production_ready = _nested_get(data, ["sections", "validator", "productionReady"])
    if production_ready is None:
        production_ready = _nested_get(data, ["validator", "productionReady"])
    if production_ready is None:
        production_ready = data.get("productionReady")
    if master_blocked and production_ready is True:
        errors.append("operator validator.productionReady cannot be true while master closeout is blocked")
        rules["productionReady_false"] = "fail"
    else:
        rules["productionReady_false"] = "pass"

    terminal_label = str(data.get("terminal_label") or _nested_get(data, ["sections", "status", "terminal_label"]) or "")
    hard_external = terminal_label == "HARD_EXTERNAL_BLOCKER"
    hard_external_rows = data.get("hard_external_blockers")
    if not isinstance(hard_external_rows, list):
        hard_external_rows = []
    external_ids = {str(row.get("id")) for row in hard_external_rows if isinstance(row, dict) and row.get("id")}
    local_failures = sorted(
        item
        for item in reported_p0_p1
        if item not in external_ids and item not in required_p0s.union(required_p1s)
    )
    if hard_external:
        non_external = sorted(item for item in reported_p0_p1 if item not in external_ids)
        if non_external:
            errors.append(
                "HARD_EXTERNAL_BLOCKER terminal label cannot keep local P0/P1 failures: "
                + ", ".join(non_external)
            )
            rules["no_local_p0_p1_for_hard_external"] = "fail"
        else:
            rules["no_local_p0_p1_for_hard_external"] = "pass"
    else:
        rules["no_local_p0_p1_for_hard_external"] = "not_applicable"

    if hard_external:
        providers_text = json.dumps(hard_external_rows, ensure_ascii=False)
        required_providers = {"MiniMax", "DeepSeek", "Tavily", "Brave"}
        missing_providers = sorted(provider for provider in required_providers if provider not in providers_text)
        if missing_providers:
            errors.append("hard_external_blockers missing provider rotations: " + ", ".join(missing_providers))
            rules["all_external_key_blockers_enumerated"] = "fail"
        else:
            rules["all_external_key_blockers_enumerated"] = "pass"
    else:
        rules["all_external_key_blockers_enumerated"] = "not_applicable"

    if hard_external:
        companies = data.get("companies")
        if not isinstance(companies, dict):
            companies = {}
        blocked_governance = []
        for key in ("PAPA-21", "PAPA-22"):
            row = companies.get(key)
            if isinstance(row, dict) and row.get("status") != "done":
                blocked_governance.append(key)
        if blocked_governance:
            errors.append(
                "PAPA-21/PAPA-22 must be finalized before HARD_EXTERNAL_BLOCKER terminal label: "
                + ", ".join(blocked_governance)
            )
            rules["papa21_papa22_finalized"] = "fail"
        else:
            rules["papa21_papa22_finalized"] = "pass"
    else:
        rules["papa21_papa22_finalized"] = "not_applicable"

    rules["no_untracked_local_p0_p1"] = "pass" if not local_failures else "fail"

    return {
        "status": "pass" if not errors else "fail",
        "rules": rules,
        "errors": errors,
        "required_p0s": sorted(required_p0s),
        "required_p1s": sorted(required_p1s),
        "reported_p0_p1": sorted(reported_p0_p1),
        "terminal_label": terminal_label,
        "hard_external_blocker_ids": sorted(external_ids),
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


PACKET_PATH_ANCHORS = [
    Path("/vol1/1000/projects/toyresearch"),
    Path(
        "<REDACTED_LOCAL_HOME>/.paperclip/instances/default/projects/"
        "91916737-9533-4d63-9c1e-e04894dabd41/8506d363-3d0a-44f4-b6f6-5bf262d373f1/_default"
    ),
]


def _packet_path_candidates(root: Path, raw_path: str) -> list[Path]:
    path = Path(raw_path)
    candidates: list[Path] = []
    if path.is_absolute():
        for anchor in PACKET_PATH_ANCHORS:
            try:
                candidates.append(root / path.relative_to(anchor))
            except ValueError:
                continue
        candidates.append(root / "_absolute" / path.as_posix().lstrip("/"))
        candidates.append(path)
    else:
        candidates.append(root / path)
        candidates.append(path)
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    return unique


def _resolve_packet_path(root: Path, raw_path: str) -> Path | None:
    for candidate in _packet_path_candidates(root, raw_path):
        if candidate.exists():
            return candidate
    return None


def _manifest_artifact_path(item: dict[str, Any]) -> str | None:
    value = item.get("path") or item.get("relative_path")
    return str(value) if value else None


def _manifest_artifact_sha(item: dict[str, Any]) -> str | None:
    value = item.get("sha256") or item.get("checksum")
    return str(value) if value else None


def verify_recursive_packet_manifests(
    *,
    root: Path,
    manifest: Path,
    nested: list[Path],
) -> dict[str, Any]:
    """Verify packet self-containment for nested evidence manifests.

    The top-level packet recheck proves only the primary manifest artifacts. This
    verifier follows explicitly declared nested manifests and checks that every
    referenced artifact is also present in the packet with its expected hash.
    """
    root = root.resolve()
    missing: list[dict[str, Any]] = []
    bad_hash: list[dict[str, Any]] = []
    uncovered_nested_refs: list[dict[str, Any]] = []
    checked: list[dict[str, Any]] = []
    manifest_errors: list[str] = []

    primary = root / manifest if not manifest.is_absolute() else manifest
    if not primary.exists():
        manifest_errors.append(f"primary manifest missing: {manifest}")

    for nested_path in nested:
        packet_manifest = root / nested_path if not nested_path.is_absolute() else nested_path
        if not packet_manifest.exists():
            missing.append(
                {
                    "nested_manifest": str(nested_path),
                    "path": str(nested_path),
                    "reason": "nested_manifest_missing",
                }
            )
            continue
        try:
            nested_data = load_json(packet_manifest)
        except Exception as exc:  # noqa: BLE001
            manifest_errors.append(f"nested manifest unreadable {nested_path}: {exc}")
            continue
        artifacts = nested_data.get("artifacts")
        if not isinstance(artifacts, list):
            manifest_errors.append(f"nested manifest {nested_path} artifacts must be a list")
            continue
        for index, item in enumerate(artifacts):
            if not isinstance(item, dict):
                manifest_errors.append(f"nested manifest {nested_path} artifacts[{index}] must be an object")
                continue
            raw_path = _manifest_artifact_path(item)
            expected_sha = _manifest_artifact_sha(item)
            if not raw_path:
                manifest_errors.append(f"nested manifest {nested_path} artifacts[{index}] missing path")
                continue
            resolved = _resolve_packet_path(root, raw_path)
            if resolved is None:
                row = {
                    "nested_manifest": str(nested_path),
                    "path": raw_path,
                    "reason": "referenced_artifact_missing_from_packet",
                }
                missing.append(row)
                uncovered_nested_refs.append(row)
                continue
            actual_sha = _file_sha256(resolved)
            ok = expected_sha == actual_sha if expected_sha else False
            row = {
                "nested_manifest": str(nested_path),
                "path": raw_path,
                "packet_path": str(resolved.relative_to(root)) if resolved.is_relative_to(root) else str(resolved),
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
                "ok": ok,
            }
            checked.append(row)
            if not expected_sha:
                bad_hash.append({**row, "reason": "missing_expected_hash"})
            elif not ok:
                bad_hash.append({**row, "reason": "sha256_mismatch"})

    errors = manifest_errors + [
        f"missing nested artifact: {item['nested_manifest']} -> {item['path']}" for item in missing
    ] + [
        f"bad nested hash: {item['nested_manifest']} -> {item['path']}" for item in bad_hash
    ]
    return {
        "status": "pass" if not errors else "fail",
        "root": str(root),
        "manifest": str(manifest),
        "nested_manifests": [str(item) for item in nested],
        "checked_artifacts": checked,
        "checked_count": len(checked),
        "missing": missing,
        "bad_hash": bad_hash,
        "uncovered_nested_refs": uncovered_nested_refs,
        "errors": errors,
    }


def validate_evidence_manifest(path: Path) -> list[str]:
    """Validate a primary evidence manifest by checking paths and sha256s."""
    data = load_json(path)
    errors: list[str] = []
    allowed_master_statuses = {
        "production-usable: blocked",
        "user-scoped-passed; provider-quarantine-active",
    }
    if data.get("master_status") not in allowed_master_statuses:
        errors.append(
            "manifest.master_status must be production-usable: blocked or "
            "user-scoped-passed; provider-quarantine-active"
        )
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("manifest.artifacts must be a non-empty list")
        return errors

    seen_ids: set[str] = set()
    for index, item in enumerate(artifacts):
        if not isinstance(item, dict):
            errors.append(f"artifacts[{index}] must be an object")
            continue
        artifact_id = item.get("id")
        if not artifact_id:
            errors.append(f"artifacts[{index}].id is required")
        elif artifact_id in seen_ids:
            errors.append(f"duplicate artifact id: {artifact_id}")
        else:
            seen_ids.add(str(artifact_id))

        raw_path = item.get("path")
        expected_sha = item.get("sha256")
        if not raw_path:
            errors.append(f"artifacts[{index}].path is required")
            continue
        resolved = Path(raw_path)
        if not resolved.exists():
            errors.append(f"artifact path does not exist: {raw_path}")
            continue
        if not expected_sha:
            errors.append(f"artifacts[{index}].sha256 is required")
            continue
        actual_sha = _file_sha256(resolved)
        if actual_sha != expected_sha:
            errors.append(f"sha256 mismatch for {raw_path}: expected {expected_sha}, got {actual_sha}")

        if not item.get("role"):
            errors.append(f"artifacts[{index}].role is required")

    return errors


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return load_json(path)
    except Exception:
        return None


def _extract_artifact_roots_from_readback(readback: dict[str, Any]) -> list[Path]:
    issue = readback.get("issue_after")
    if not isinstance(issue, dict):
        issue = {}
    comment = issue.get("comment")
    if not isinstance(comment, dict):
        comment = {}
    text = "\n".join(
        str(value or "")
        for value in (
            readback.get("artifact_root"),
            readback.get("evidence_root"),
            issue.get("description"),
            comment.get("body"),
        )
    )
    roots: list[Path] = []
    for raw in re.findall(r"(/vol1/1000/projects/toyresearch/[^ ;\n`]+)", text):
        path = Path(raw.rstrip(".,"))
        if path.suffix:
            path = path.parent
        if path not in roots:
            roots.append(path)
    return roots


def _has_execution_run_or_issue_runs(readback: dict[str, Any], issue_runs: Any) -> bool:
    issue = readback.get("issue_after")
    if not isinstance(issue, dict):
        issue = {}
    if issue.get("executionRunId") or issue.get("checkoutRunId"):
        return True
    if readback.get("executionRunId") or readback.get("execution_run_id"):
        return True
    if isinstance(issue.get("runs"), list) and issue.get("runs"):
        return True
    if isinstance(readback.get("runs"), list) and readback.get("runs"):
        return True
    if isinstance(issue_runs, list) and issue_runs:
        return True
    if isinstance(issue_runs, dict):
        runs = issue_runs.get("runs") or issue_runs.get("issue_runs")
        return isinstance(runs, list) and bool(runs)
    return False


def _is_uuid_like(value: str | None) -> bool:
    if not value:
        return False
    # Accept standard UUIDs and Paperclip run IDs which are UUID-like
    import re
    return bool(re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        str(value),
        re.IGNORECASE,
    ))


def _is_controller_run_id(value: str | None) -> bool:
    if not value:
        return False
    return str(value).startswith("controller-")


def validate_real_agent_loop(root: Path) -> dict[str, Any]:
    """Validate that a company loop was actually agent-owned and run-backed.

    This is intentionally stricter than manifest/readback validation. It fails
    old controller/local-board loops even when local artifacts, manifests and
    Paperclip issue statuses are present.
    """
    errors: list[str] = []
    root = root.resolve()
    readback_path = root / "paperclip_readback.json"
    readback = _read_json_if_exists(readback_path)
    if readback is None:
        errors.append(f"paperclip_readback.json missing or unreadable: {readback_path}")
        readback = {}
    issue = readback.get("issue_after")
    if not isinstance(issue, dict):
        issue = {}
    comment = issue.get("comment")
    if not isinstance(comment, dict):
        comment = {}

    issue_runs = _read_json_if_exists(root / "issue_runs.json")
    execution_evidence = _read_json_if_exists(root / "agent_execution_evidence.json") or {}
    heartbeat = (
        _read_json_if_exists(root / "heartbeat_result.json")
        or _read_json_if_exists(root / "agent_heartbeat.json")
        or execution_evidence.get("heartbeat")
        or {}
    )
    agent_status = (
        _read_json_if_exists(root / "agent_status.json")
        or execution_evidence.get("agent_status")
        or {}
    )

    assignee_agent_id = issue.get("assigneeAgentId") or readback.get("assigneeAgentId") or execution_evidence.get("assigneeAgentId")
    if not assignee_agent_id:
        errors.append("missing assigneeAgentId or equivalent agent assignment evidence")

    if not _has_execution_run_or_issue_runs(readback, issue_runs):
        errors.append("missing executionRunId, checkoutRunId or non-empty issue runs evidence")

    if not (comment.get("authorAgentId") or comment.get("createdByRunId") or execution_evidence.get("commentAuthorAgentId") or execution_evidence.get("commentCreatedByRunId")):
        errors.append("missing comment authorAgentId or createdByRunId evidence")

    heartbeat_status = heartbeat.get("status") if isinstance(heartbeat, dict) else None
    heartbeat_succeeded = heartbeat.get("succeeded") if isinstance(heartbeat, dict) else None
    if not (heartbeat_status in {"pass", "passed", "success", "succeeded"} or heartbeat_succeeded is True):
        errors.append("missing heartbeat run succeeded evidence")

    agent_state = None
    if isinstance(agent_status, dict):
        agent_state = agent_status.get("status") or agent_status.get("state")
    if not agent_state:
        errors.append("missing agent status evidence")
    elif str(agent_state).lower() in {"error", "errored", "paused", "pause", "failed"}:
        errors.append(f"agent status is not acceptable: {agent_state}")

    # --- Meaningful runtime checks (REAL-AGENT-LOOP-006) ---

    origin_kind = issue.get("originKind")

    claimed_status = readback.get("status") or readback.get("paperclip_status")
    actual_issue_status = issue.get("status")
    if claimed_status and actual_issue_status and str(claimed_status).lower() != str(actual_issue_status).lower():
        errors.append(
            f"readback status mismatch: claimed '{claimed_status}' but issue_after status is '{actual_issue_status}'"
        )

    execution_run_id = issue.get("executionRunId") or readback.get("run_id")
    checkout_run_id = issue.get("checkoutRunId")
    if execution_run_id and _is_controller_run_id(execution_run_id):
        errors.append(f"executionRunId '{execution_run_id}' is a controller run, not an agent heartbeat run")
    if checkout_run_id and _is_controller_run_id(checkout_run_id):
        errors.append(f"checkoutRunId '{checkout_run_id}' is a controller run, not an agent heartbeat run")

    comment_author_agent_id = comment.get("authorAgentId")
    if assignee_agent_id and comment_author_agent_id and assignee_agent_id != comment_author_agent_id:
        errors.append(
            f"comment authorAgentId '{comment_author_agent_id}' does not match assigneeAgentId '{assignee_agent_id}'"
        )

    if checkout_run_id and execution_run_id and checkout_run_id != execution_run_id:
        errors.append(
            f"checkoutRunId '{checkout_run_id}' differs from executionRunId '{execution_run_id}'"
        )

    artifact_roots = _extract_artifact_roots_from_readback(readback)
    if root not in artifact_roots:
        artifact_roots.append(root)
    readable_roots = [path for path in artifact_roots if path.exists()]
    closeouts = [
        path
        for artifact_root in readable_roots
        for path in artifact_root.rglob("*")
        if path.is_file() and path.name.endswith("closeout.md")
    ]
    if not readable_roots:
        errors.append("no readable artifact root found from readback or validator root")
    if not closeouts:
        errors.append("no readable closeout artifact found under artifact roots")

    return {
        "status": "pass" if not errors else "fail",
        "root": str(root),
        "readback_path": str(readback_path),
        "issue_identifier": readback.get("issue_identifier") or issue.get("identifier"),
        "issue_id": readback.get("issue_id") or issue.get("id"),
        "checks": {
            "assigneeAgentId": bool(assignee_agent_id),
            "executionRunId_or_issue_runs": _has_execution_run_or_issue_runs(readback, issue_runs),
            "comment_authorAgentId_or_createdByRunId": bool(comment.get("authorAgentId") or comment.get("createdByRunId") or execution_evidence.get("commentAuthorAgentId") or execution_evidence.get("commentCreatedByRunId")),
            "heartbeat_succeeded": bool(heartbeat_status in {"pass", "passed", "success", "succeeded"} or heartbeat_succeeded is True),
            "agent_non_error_non_paused": bool(agent_state and str(agent_state).lower() not in {"error", "errored", "paused", "pause", "failed"}),
            "artifact_path_readable": bool(readable_roots and closeouts),
            "originKind_observed": bool(origin_kind),
            "status_consistent": not (claimed_status and actual_issue_status and str(claimed_status).lower() != str(actual_issue_status).lower()),
            "run_id_not_controller": not (_is_controller_run_id(execution_run_id) or _is_controller_run_id(checkout_run_id)),
            "comment_author_matches_assignee": not (bool(assignee_agent_id) and bool(comment_author_agent_id) and assignee_agent_id != comment_author_agent_id),
        },
        "observed": {
            "createdByUserId": issue.get("createdByUserId"),
            "createdByAgentId": issue.get("createdByAgentId"),
            "originKind": origin_kind,
            "assigneeAgentId": assignee_agent_id,
            "executionRunId": execution_run_id,
            "checkoutRunId": checkout_run_id,
            "commentAuthorUserId": comment.get("authorUserId"),
            "commentAuthorAgentId": comment_author_agent_id,
            "commentCreatedByRunId": comment.get("createdByRunId"),
            "heartbeatStatus": heartbeat_status,
            "agentStatus": agent_state,
            "artifact_roots": [str(path) for path in artifact_roots],
            "readable_artifact_roots": [str(path) for path in readable_roots],
            "closeout_paths": [str(path) for path in closeouts],
        },
        "errors": errors,
    }


def verify_live_readback(
    path: Path,
    client: Any,
) -> dict[str, Any]:
    """Cross-check manifest terminal_issue_readback against live Paperclip API.

    This provides proof that the readback entries reflect actual issue state
    in Paperclip, not just local controller-authored claims.
    """
    errors: list[str] = []
    data = load_json(path)
    readbacks = data.get("terminal_issue_readback")
    if not isinstance(readbacks, list) or not readbacks:
        errors.append("terminal_issue_readback must be a non-empty list")
        readbacks = []

    live_rows: list[dict[str, Any]] = []
    checked = 0
    matched = 0
    mismatched = 0
    unreachable = 0

    for index, item in enumerate(readbacks):
        if not isinstance(item, dict):
            errors.append(f"terminal_issue_readback[{index}] must be an object")
            continue
        issue_key = item.get("issue")
        issue_id = item.get("issue_id")
        if not issue_id:
            errors.append(f"terminal_issue_readback[{index}] {issue_key}: missing issue_id for live check")
            continue

        row: dict[str, Any] = {
            "issue": issue_key,
            "issue_id": issue_id,
            "manifest_status": item.get("status"),
            "manifest_run_id": item.get("run_id") or item.get("run_ids"),
        }

        try:
            live_issue = client.get(f"issues/{issue_id}")
        except Exception as exc:
            row["live_error"] = str(exc)
            row["live_match"] = "unreachable"
            unreachable += 1
            live_rows.append(row)
            errors.append(f"live readback failed for {issue_key} ({issue_id}): {exc}")
            continue

        checked += 1
        live_status = live_issue.get("status")
        live_run_id = live_issue.get("executionRunId") or live_issue.get("checkoutRunId")
        live_assignee = live_issue.get("assigneeAgentId")
        live_completed = live_issue.get("completedAt")
        live_updated = live_issue.get("updatedAt")

        row["live_status"] = live_status
        row["live_run_id"] = live_run_id
        row["live_assignee_agent_id"] = live_assignee
        row["live_completed_at"] = live_completed
        row["live_updated_at"] = live_updated

        status_match = str(item.get("status") or "").lower() == str(live_status or "").lower()
        run_match = bool(
            not item.get("run_id")
            or not live_run_id
            or item.get("run_id") == live_run_id
        )

        if status_match and run_match:
            row["live_match"] = "match"
            matched += 1
        else:
            row["live_match"] = "mismatch"
            mismatched += 1
            if not status_match:
                errors.append(
                    f"live status mismatch for {issue_key}: manifest claims '{item.get('status')}', "
                    f"live API reports '{live_status}'"
                )
            if not run_match:
                errors.append(
                    f"live run mismatch for {issue_key}: manifest run_id '{item.get('run_id')}', "
                    f"live API run_id '{live_run_id}'"
                )

        live_rows.append(row)

    return {
        "status": "pass" if not errors else "fail",
        "manifest_path": str(path),
        "checked_count": checked,
        "matched_count": matched,
        "mismatched_count": mismatched,
        "unreachable_count": unreachable,
        "live_rows": live_rows,
        "errors": errors,
    }


ALLOWED_FULL_MANIFEST_STATUSES = {
    "done",
    "scope_pass_nonproduction",
    "done_as_ledger_only",
    "blocked",
    "fail",
}


def _artifact_matches_issue(item: dict[str, Any], issue: str) -> bool:
    return item.get("issue") == issue


def _artifact_has_marker(item: dict[str, Any], markers: tuple[str, ...]) -> bool:
    searchable = " ".join(
        str(item.get(key, ""))
        for key in ("id", "path", "role")
    ).lower()
    return any(marker in searchable for marker in markers)


def _readback_has_runtime_trace(item: dict[str, Any]) -> bool:
    run_ids = item.get("run_ids")
    return bool(
        item.get("run_id")
        or item.get("paperclip_run_id")
        or (isinstance(run_ids, list) and run_ids)
    )


def _readback_has_issue_id(item: dict[str, Any]) -> bool:
    return bool(item.get("issue_id") or item.get("paperclip_issue_id") or item.get("id"))


def _readback_has_memory_closeout(item: dict[str, Any], artifacts: list[dict[str, Any]]) -> bool:
    if item.get("memory_closeout_id") or item.get("memory_closeout_path") or item.get("no_write_reason"):
        return True
    issue = item.get("issue")
    if not issue:
        return False
    return any(
        _artifact_matches_issue(artifact, issue)
        and _artifact_has_marker(artifact, ("memory", "closeout", "no-write", "no_write"))
        for artifact in artifacts
    )


def _readback_has_validator(item: dict[str, Any], artifacts: list[dict[str, Any]]) -> bool:
    if item.get("validator_artifact_id") or item.get("validator_artifact_path"):
        return True
    issue = item.get("issue")
    if not issue:
        return False
    return any(
        _artifact_matches_issue(artifact, issue)
        and _artifact_has_marker(artifact, ("validator", "validation"))
        for artifact in artifacts
    )


def _artifact_json(item: dict[str, Any]) -> dict[str, Any] | None:
    raw_path = item.get("path")
    if not raw_path:
        return None
    resolved = Path(raw_path)
    if resolved.suffix != ".json" or not resolved.exists():
        return None
    try:
        return load_json(resolved)
    except Exception:
        return None


def verify_full_manifest(path: Path) -> dict[str, Any]:
    """Strictly verify the production evidence manifest and issue closure links.

    This verifier is intentionally stricter than validate_evidence_manifest().
    It is the Stage-B gate for the production master plan and must fail closed
    when a terminal issue lacks issue/run/readback/validator/memory traceability.
    """
    errors = validate_evidence_manifest(path)
    data = load_json(path)
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        artifacts = []

    issue_artifacts: dict[str, list[dict[str, Any]]] = {}
    for index, item in enumerate(artifacts):
        if not isinstance(item, dict):
            continue
        issue = item.get("issue")
        if issue is None:
            continue
        if not isinstance(issue, str) or not issue:
            errors.append(f"artifacts[{index}].issue must be a non-empty string or null")
            continue
        issue_artifacts.setdefault(issue, []).append(item)

    readbacks = data.get("terminal_issue_readback")
    if not isinstance(readbacks, list) or not readbacks:
        errors.append("terminal_issue_readback must be a non-empty list")
        readbacks = []

    readback_issues: set[str] = set()
    for index, item in enumerate(readbacks):
        if not isinstance(item, dict):
            errors.append(f"terminal_issue_readback[{index}] must be an object")
            continue
        issue = item.get("issue")
        if not issue:
            errors.append(f"terminal_issue_readback[{index}].issue is required")
            continue
        if not isinstance(issue, str):
            errors.append(f"terminal_issue_readback[{index}].issue must be a string")
            continue
        readback_issues.add(issue)

        status = item.get("status")
        if status not in ALLOWED_FULL_MANIFEST_STATUSES:
            errors.append(
                f"terminal_issue_readback[{index}] {issue}: status must be one of "
                + ", ".join(sorted(ALLOWED_FULL_MANIFEST_STATUSES))
            )

        if not _readback_has_issue_id(item):
            errors.append(f"terminal_issue_readback[{index}] {issue}: missing Paperclip issue UUID/id")
        if not _readback_has_runtime_trace(item):
            errors.append(f"terminal_issue_readback[{index}] {issue}: missing run_id/run_ids")
        if not item.get("updated_at"):
            errors.append(f"terminal_issue_readback[{index}] {issue}: missing updated_at")
        if not _readback_has_validator(item, artifacts):
            errors.append(f"terminal_issue_readback[{index}] {issue}: missing validator artifact")
        if not _readback_has_memory_closeout(item, artifacts):
            errors.append(f"terminal_issue_readback[{index}] {issue}: missing memory closeout or no_write_reason")

        if issue == "FIN-9":
            plain_done = status == "done" and not item.get("paperclip_status")
            ledger_status = status == "done_as_ledger_only"
            if plain_done:
                errors.append("FIN-9 cannot appear as plain done without paperclip_status")
            if status in {"done", "done_as_ledger_only"}:
                if item.get("paperclip_status") != "done":
                    errors.append("FIN-9 must retain raw Paperclip enum as paperclip_status=done")
                if item.get("corpus_complete") is not False:
                    errors.append("FIN-9 must keep corpus_complete=false until source material is complete")
                if item.get("claim_extraction_allowed") is not False:
                    errors.append("FIN-9 must keep claim_extraction_allowed=false while corpus is incomplete")
                if status == "done" and not ledger_status:
                    errors.append("FIN-9 must use done_as_ledger_only while corpus_complete=false")

    for issue in sorted(issue_artifacts):
        if issue not in readback_issues:
            errors.append(f"issue {issue} has artifacts but no terminal_issue_readback entry")

    open_gaps = data.get("open_manifest_gaps")
    if isinstance(open_gaps, list) and open_gaps:
        errors.append("open_manifest_gaps must be empty for a full manifest verifier pass")
    elif open_gaps is not None and not isinstance(open_gaps, list):
        errors.append("open_manifest_gaps must be a list when present")

    pap13_manifest_items = [
        item
        for item in artifacts
        if isinstance(item, dict)
        and (
            item.get("id") == "PAP13-EVIDENCE-MANIFEST"
            or "pap13_evidence_manifest" in str(item.get("path", "")).lower()
        )
    ]
    if not pap13_manifest_items:
        errors.append("PAP-13 evidence manifest artifact is required")
    for item in pap13_manifest_items:
        manifest = _artifact_json(item)
        if manifest is None:
            errors.append("PAP-13 evidence manifest must be readable JSON")
            continue
        pap13_run = manifest.get("pap13RunId")
        smoke_run = manifest.get("referencedSmokeRunId")
        if not pap13_run:
            errors.append("PAP-13 evidence manifest missing pap13RunId")
        if not smoke_run:
            errors.append("PAP-13 evidence manifest missing referencedSmokeRunId")
        if pap13_run and smoke_run and pap13_run == smoke_run:
            errors.append("PAP-13 pap13RunId must differ from referencedSmokeRunId")

    return {
        "status": "pass" if not errors else "fail",
        "manifest_path": str(path),
        "artifact_count": len(artifacts),
        "terminal_issue_count": len(readbacks),
        "issues_with_artifacts": sorted(issue_artifacts),
        "terminal_issues": sorted(readback_issues),
        "errors": errors,
    }


CONFIG_GATE_REQUIRED_MARKERS = {
    "snapshot": ("snapshot", "manifest"),
    "proposal": ("proposal",),
    "risk_review": ("risk", "review"),
    "bounded_change": ("bounded", "change", "diff"),
    "live_smoke": ("smoke", "probe", "live"),
    "rollback": ("rollback", "restore"),
    "closeout": ("closeout",),
}

APPROVAL_REQUIRED_STATES_BEFORE_APPLY = {
    "snapshot",
    "proposal",
    "risk_review",
    "bounded_change",
}


def validate_config_gate_bundle(root: Path) -> list[str]:
    """Validate a gated config-change bundle with content-level checks.

    In addition to filename markers, this gate:
    - Finds ConfigChangeRecord JSON files and validates their state machine.
    - Checks that evidence files have non-empty content.
    - Rejects bundles where approved changes lack rollback/smoke commands.
    - Requires markers based on the record's current_state (state-aware gate).
    """
    errors: list[str] = []
    if not root.exists():
        return [f"gate bundle root does not exist: {root}"]
    files = [path for path in root.rglob("*") if path.is_file()]
    names = [path.name.lower() for path in files]
    relative = [str(path.relative_to(root)).lower() for path in files]
    searchable = names + relative

    # Determine required markers based on the most advanced record state found
    required_labels = set(CONFIG_GATE_REQUIRED_MARKERS.keys())
    record_states: list[str] = []
    for path in files:
        if path.suffix != ".json":
            continue
        try:
            data = load_json(path)
        except Exception:
            continue
        if "change_id" in data and "current_state" in data:
            record_states.append(data.get("current_state", ""))

    if record_states:
        # Use the most advanced state to determine required markers
        state_order = [
            "snapshot",
            "proposal",
            "risk_review",
            "bounded_change",
            "live_smoke",
            "rollback_proof",
            "paperclip_closeout",
        ]
        most_advanced = max(
            record_states,
            key=lambda s: state_order.index(s) if s in state_order else -1,
        )
        idx = state_order.index(most_advanced)
        # snapshot, proposal, risk_review are always required once reached
        # bounded_change also requires rollback
        # live_smoke and beyond require live_smoke
        # rollback_proof and beyond do not add new markers
        # paperclip_closeout requires closeout
        required_labels = {"snapshot", "proposal", "risk_review"}
        if idx >= state_order.index("bounded_change"):
            required_labels.add("bounded_change")
            required_labels.add("rollback")
        if idx >= state_order.index("live_smoke"):
            required_labels.add("live_smoke")
        if idx >= state_order.index("paperclip_closeout"):
            required_labels.add("closeout")

    for label, markers in CONFIG_GATE_REQUIRED_MARKERS.items():
        if label not in required_labels:
            continue
        if not any(any(marker in value for marker in markers) for value in searchable):
            errors.append(f"missing gated config-change evidence: {label}")

    # Find and validate ConfigChangeRecord files
    for path in files:
        if path.suffix != ".json":
            continue
        try:
            data = load_json(path)
        except Exception:
            continue
        if "change_id" in data and "current_state" in data:
            record_errors = validate_approval_record(data)
            for err in record_errors:
                errors.append(f"{path.name}: {err}")
            # Enforce can_apply() for approved changes
            state = data.get("current_state", "")
            decision = data.get("approval_decision")
            if state == "bounded_change" and decision == "approve":
                if not data.get("rollback_commands"):
                    errors.append(f"{path.name}: approved bounded_change lacks rollback_commands")
                if not data.get("smoke_commands"):
                    errors.append(f"{path.name}: approved bounded_change lacks smoke_commands")
                if not data.get("snapshot_paths"):
                    errors.append(f"{path.name}: approved bounded_change lacks snapshot_paths")
                if not data.get("proposal_paths"):
                    errors.append(f"{path.name}: approved bounded_change lacks proposal_paths")
                for p in data.get("snapshot_paths", []):
                    resolved_path = root / p
                    if not resolved_path.exists():
                        errors.append(f"{path.name}: snapshot path does not exist: {p}")
                for p in data.get("proposal_paths", []):
                    resolved_path = root / p
                    if not resolved_path.exists():
                        errors.append(f"{path.name}: proposal path does not exist: {p}")

    # Evidence files must have non-empty content, not just the right name
    for path in files:
        if path.stat().st_size == 0:
            errors.append(f"empty evidence file: {path.relative_to(root)}")

    json_errors = validate_json_tree(root)
    errors.extend(json_errors)
    return errors


def validate_approval_record(record: dict[str, Any]) -> list[str]:
    """Validate a ConfigChangeRecord dict for approval workflow completeness."""
    errors: list[str] = []
    required_keys = {
        "change_id",
        "kind",
        "title",
        "description",
        "affected_runtimes",
        "proposed_by",
        "current_state",
    }
    missing = sorted(required_keys.difference(record))
    errors.extend(f"missing key: {key}" for key in missing)

    state = record.get("current_state")
    if state not in {
        "snapshot",
        "proposal",
        "risk_review",
        "bounded_change",
        "live_smoke",
        "rollback_proof",
        "paperclip_closeout",
        "blocked",
    }:
        errors.append("current_state must be a valid ConfigChangeState")

    decision = record.get("approval_decision")
    if state in {"bounded_change", "live_smoke", "rollback_proof", "paperclip_closeout"}:
        if decision not in {"approve", "reject", "request_changes", "defer"}:
            errors.append("approval_decision is required once state reaches bounded_change or beyond")
        if not record.get("approved_by"):
            errors.append("approved_by is required once state reaches bounded_change or beyond")
        if not record.get("approved_at"):
            errors.append("approved_at is required once state reaches bounded_change or beyond")

    if decision == "approve":
        if not record.get("rollback_commands"):
            errors.append("approved changes must include rollback_commands")
        if not record.get("smoke_commands"):
            errors.append("approved changes must include smoke_commands")

    if state == "blocked" and not record.get("blockers"):
        errors.append("blocked state must include blockers")

    # can_apply() gate: approved bounded_change must be fully specified
    if decision == "approve" and state == "bounded_change":
        if not record.get("rollback_commands"):
            errors.append("can_apply: approved bounded_change must have rollback_commands")
        if not record.get("smoke_commands"):
            errors.append("can_apply: approved bounded_change must have smoke_commands")

    return errors
