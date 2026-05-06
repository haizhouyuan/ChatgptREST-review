from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from chatgptrest.kernel.memory_manager import MemoryManager, MemoryRecord, MemorySource, MemoryTier, SourceType
from chatgptrest.kernel.work_memory_manager import WorkMemoryManager, WorkMemoryWriteResult
from chatgptrest.kernel.work_memory_objects import WorkMemoryObject, WorkMemoryValidationError, build_work_memory_object
from chatgptrest.kernel.work_memory_policy import WorkMemoryGovernancePolicy


WORK_MEMORY_IMPORTER_SCHEMA_VERSION = "planning-backfill-import-manifest-v1"
WORK_MEMORY_IMPORTER_SOURCE_IDENTITY = "manual_review"
WORK_MEMORY_IMPORT_REVIEW_CATEGORY = "work_memory_import_review"
_SUPPORTED_OBJECT_TYPES = frozenset({"active_project", "decision_ledger"})
_SUPPORTED_IMPORT_GATES = frozenset({"ready", "manual_review_required"})
_SUPPORTED_REVIEW_STATES = frozenset({"pending", "resolved", "rolled_back", "all"})
_SUPPORTED_REVIEW_ACTIONS = frozenset({"approve", "reject", "promote", "supersede", "rollback"})


class WorkMemoryImportValidationError(ValueError):
    def __init__(self, message: str, *, blocked_by: str = "import_validation") -> None:
        super().__init__(message)
        self.blocked_by = blocked_by


@dataclass(frozen=True)
class WorkMemoryImportEntry:
    seed_id: str
    import_gate: str
    payload: dict[str, Any]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class WorkMemoryImportManifest:
    manifest_id: str
    schema_version: str
    object_type: str
    generated_at: str
    source_repo: str
    contract_basis: list[str]
    normalization_rules_ref: str
    entries: tuple[WorkMemoryImportEntry, ...]
    manifest_path: str

    @property
    def entry_count(self) -> int:
        return len(self.entries)


@dataclass
class WorkMemoryImportEntryResult:
    manifest_id: str
    manifest_path: str
    manifest_schema_version: str
    manifest_generated_at: str
    object_type: str
    seed_id: str
    import_gate: str
    plan_status: str
    status: str
    selected: bool = False
    object_id: str = ""
    message: str = ""
    blocked_by: list[str] = field(default_factory=list)
    duplicate: bool = False
    record_id: str = ""
    queue_record_id: str = ""
    review_status: str = ""
    active: bool = False
    tier: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    import_metadata: dict[str, Any] = field(default_factory=dict)
    governance: dict[str, Any] = field(default_factory=dict)
    audit_trail: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "manifest_path": self.manifest_path,
            "manifest_schema_version": self.manifest_schema_version,
            "manifest_generated_at": self.manifest_generated_at,
            "object_type": self.object_type,
            "seed_id": self.seed_id,
            "import_gate": self.import_gate,
            "plan_status": self.plan_status,
            "status": self.status,
            "selected": self.selected,
            "object_id": self.object_id,
            "message": self.message,
            "blocked_by": list(self.blocked_by),
            "duplicate": self.duplicate,
            "record_id": self.record_id,
            "queue_record_id": self.queue_record_id,
            "review_status": self.review_status,
            "active": self.active,
            "tier": self.tier,
            "payload": dict(self.payload),
            "metadata": dict(self.metadata),
            "import_metadata": dict(self.import_metadata),
            "governance": dict(self.governance),
            "audit_trail": list(self.audit_trail),
        }


@dataclass
class WorkMemoryImportResult:
    ok: bool
    mode: str
    manifests: list[dict[str, Any]]
    entries: list[WorkMemoryImportEntryResult]
    selected_gate: str
    limit: int | None
    identity: dict[str, str]
    source_identity: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "mode": self.mode,
            "manifests": list(self.manifests),
            "summary": self.summary(),
            "entries": [entry.to_dict() for entry in self.entries],
            "selected_gate": self.selected_gate,
            "limit": self.limit,
            "identity": dict(self.identity),
            "source_identity": self.source_identity,
        }

    def summary(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        by_gate: dict[str, int] = {}
        for entry in self.entries:
            by_status[entry.status] = by_status.get(entry.status, 0) + 1
            by_gate[entry.import_gate] = by_gate.get(entry.import_gate, 0) + 1
        return {
            "entry_count": len(self.entries),
            "selected_count": sum(1 for entry in self.entries if entry.selected),
            "written_count": sum(1 for entry in self.entries if entry.status == "written"),
            "duplicate_count": sum(1 for entry in self.entries if entry.duplicate),
            "queued_review_count": sum(1 for entry in self.entries if entry.status == "queued_for_review"),
            "blocked_count": sum(1 for entry in self.entries if entry.status == "blocked"),
            "skipped_count": sum(1 for entry in self.entries if entry.status == "skipped"),
            "by_status": by_status,
            "by_gate": by_gate,
            "manifest_count": len(self.manifests),
        }

    def to_markdown(self) -> str:
        summary = self.summary()
        lines = [
            "# Work Memory Import Report",
            "",
            f"- Mode: `{self.mode}`",
            f"- Selected gate: `{self.selected_gate}`",
            f"- Manifest count: `{summary['manifest_count']}`",
            f"- Entry count: `{summary['entry_count']}`",
            f"- Selected count: `{summary['selected_count']}`",
            f"- Written count: `{summary['written_count']}`",
            f"- Queued review count: `{summary['queued_review_count']}`",
            f"- Blocked count: `{summary['blocked_count']}`",
            f"- Skipped count: `{summary['skipped_count']}`",
            "",
            "## Manifest Summary",
            "",
            "| Manifest | Object Type | Entries | Path |",
            "| --- | --- | ---: | --- |",
        ]
        for manifest in self.manifests:
            lines.append(
                f"| {manifest['manifest_id']} | {manifest['object_type']} | {manifest['entry_count']} | `{manifest['manifest_path']}` |"
            )
        lines.extend(
            [
                "",
                "## Entry Results",
                "",
                "| Seed | Object | Gate | Status | Record | Message |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in self.entries:
            record_ref = entry.record_id or entry.queue_record_id or "-"
            message = (entry.message or "").replace("\n", " ").strip() or "-"
            lines.append(
                f"| {entry.seed_id} | {entry.object_id or entry.object_type} | {entry.import_gate} | {entry.status} | {record_ref} | {message} |"
            )
        return "\n".join(lines) + "\n"


@dataclass
class WorkMemoryReviewQueueItem:
    record_id: str
    manifest_id: str
    manifest_path: str
    seed_id: str
    object_type: str
    review_state: str
    resolution_action: str
    resolution_reason: str
    resolution_actor: str
    resolution_record_id: str
    resolution_superseded_record_id: str
    created_at: str
    updated_at: str
    import_metadata: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    source: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "manifest_id": self.manifest_id,
            "manifest_path": self.manifest_path,
            "seed_id": self.seed_id,
            "object_type": self.object_type,
            "review_state": self.review_state,
            "resolution_action": self.resolution_action,
            "resolution_reason": self.resolution_reason,
            "resolution_actor": self.resolution_actor,
            "resolution_record_id": self.resolution_record_id,
            "resolution_superseded_record_id": self.resolution_superseded_record_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "import_metadata": dict(self.import_metadata),
            "payload": dict(self.payload),
            "source": dict(self.source),
        }


@dataclass
class WorkMemoryReviewQueueResult:
    ok: bool
    state: str
    items: list[WorkMemoryReviewQueueItem]
    limit: int

    def summary(self) -> dict[str, Any]:
        by_state: dict[str, int] = {}
        by_object_type: dict[str, int] = {}
        for item in self.items:
            by_state[item.review_state] = by_state.get(item.review_state, 0) + 1
            by_object_type[item.object_type] = by_object_type.get(item.object_type, 0) + 1
        return {
            "item_count": len(self.items),
            "state": self.state,
            "by_state": by_state,
            "by_object_type": by_object_type,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "summary": self.summary(),
            "items": [item.to_dict() for item in self.items],
            "state": self.state,
            "limit": self.limit,
        }

    def to_markdown(self) -> str:
        summary = self.summary()
        lines = [
            "# Work Memory Review Queue",
            "",
            f"- State filter: `{self.state}`",
            f"- Item count: `{summary['item_count']}`",
            "",
            "| Record | Seed | Object | Review State | Resolution | Durable Record |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for item in self.items:
            lines.append(
                f"| {item.record_id} | {item.seed_id} | {item.object_type} | {item.review_state} | "
                f"{item.resolution_action or '-'} | {item.resolution_record_id or '-'} |"
            )
        return "\n".join(lines) + "\n"


@dataclass
class WorkMemoryReviewResolutionResult:
    ok: bool
    action: str
    record_id: str
    message: str
    review_state: str
    durable_record_id: str = ""
    superseded_record_id: str = ""
    blocked_by: list[str] = field(default_factory=list)
    queue_value: dict[str, Any] = field(default_factory=dict)
    queue_audit_trail: list[dict[str, Any]] = field(default_factory=list)
    durable_audit_trail: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "action": self.action,
            "record_id": self.record_id,
            "message": self.message,
            "review_state": self.review_state,
            "durable_record_id": self.durable_record_id,
            "superseded_record_id": self.superseded_record_id,
            "blocked_by": list(self.blocked_by),
            "queue_value": dict(self.queue_value),
            "queue_audit_trail": list(self.queue_audit_trail),
            "durable_audit_trail": list(self.durable_audit_trail),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Work Memory Review Resolution",
            "",
            f"- Action: `{self.action}`",
            f"- Queue record: `{self.record_id}`",
            f"- Review state: `{self.review_state}`",
            f"- Durable record: `{self.durable_record_id or '-'}`",
            f"- Superseded record: `{self.superseded_record_id or '-'}`",
            f"- Message: {self.message}",
        ]
        if self.blocked_by:
            lines.append(f"- Blocked by: `{', '.join(self.blocked_by)}`")
        return "\n".join(lines) + "\n"


def load_work_memory_import_manifest(path: str | Path) -> WorkMemoryImportManifest:
    manifest_path = Path(path).expanduser().resolve()
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkMemoryImportValidationError(
            f"manifest not found: {manifest_path}",
            blocked_by="manifest_missing",
        ) from exc
    except json.JSONDecodeError as exc:
        raise WorkMemoryImportValidationError(
            f"invalid manifest JSON: {manifest_path}: {exc}",
            blocked_by="manifest_json",
        ) from exc

    if not isinstance(raw, dict):
        raise WorkMemoryImportValidationError("manifest must be a JSON object", blocked_by="manifest_shape")

    manifest_id = _required_text(raw.get("manifest_id"), "manifest_id")
    schema_version = _required_text(raw.get("schema_version"), "schema_version")
    if schema_version != WORK_MEMORY_IMPORTER_SCHEMA_VERSION:
        raise WorkMemoryImportValidationError(
            f"unsupported manifest schema_version: {schema_version}",
            blocked_by="manifest_schema_version",
        )
    object_type = _required_text(raw.get("object_type"), "object_type")
    if object_type not in _SUPPORTED_OBJECT_TYPES:
        raise WorkMemoryImportValidationError(
            f"unsupported object_type: {object_type}",
            blocked_by="object_type",
        )
    generated_at = _required_text(raw.get("generated_at"), "generated_at")
    source_repo = str(raw.get("source_repo") or "").strip()
    normalization_rules_ref = str(raw.get("normalization_rules_ref") or "").strip()
    contract_basis = [
        str(item).strip()
        for item in list(raw.get("contract_basis") or [])
        if str(item).strip()
    ]
    raw_entries = raw.get("entries")
    if not isinstance(raw_entries, list):
        raise WorkMemoryImportValidationError("entries must be a list", blocked_by="entries")
    declared_entry_count = raw.get("entry_count")
    if declared_entry_count is not None and int(declared_entry_count) != len(raw_entries):
        raise WorkMemoryImportValidationError(
            f"entry_count mismatch: declared={declared_entry_count} actual={len(raw_entries)}",
            blocked_by="entry_count",
        )

    entries: list[WorkMemoryImportEntry] = []
    for idx, raw_entry in enumerate(raw_entries):
        if not isinstance(raw_entry, dict):
            raise WorkMemoryImportValidationError(
                f"entry[{idx}] must be an object",
                blocked_by="entry_shape",
            )
        seed_id = _required_text(raw_entry.get("seed_id"), f"entries[{idx}].seed_id")
        import_gate = _required_text(raw_entry.get("import_gate"), f"entries[{idx}].import_gate")
        payload = raw_entry.get("payload")
        metadata = raw_entry.get("metadata") or {}
        if not isinstance(payload, dict):
            raise WorkMemoryImportValidationError(
                f"entry[{idx}] payload must be an object",
                blocked_by="payload_shape",
            )
        if not isinstance(metadata, dict):
            raise WorkMemoryImportValidationError(
                f"entry[{idx}] metadata must be an object",
                blocked_by="metadata_shape",
            )
        entries.append(
            WorkMemoryImportEntry(
                seed_id=seed_id,
                import_gate=import_gate,
                payload=dict(payload),
                metadata=dict(metadata),
            )
        )

    return WorkMemoryImportManifest(
        manifest_id=manifest_id,
        schema_version=schema_version,
        object_type=object_type,
        generated_at=generated_at,
        source_repo=source_repo,
        contract_basis=contract_basis,
        normalization_rules_ref=normalization_rules_ref,
        entries=tuple(entries),
        manifest_path=str(manifest_path),
    )


class WorkMemoryImporter:
    def __init__(
        self,
        memory: MemoryManager,
        *,
        governance_policy: WorkMemoryGovernancePolicy | None = None,
        source_identity: str = WORK_MEMORY_IMPORTER_SOURCE_IDENTITY,
    ) -> None:
        self._memory = memory
        self._manager = WorkMemoryManager(memory, governance_policy=governance_policy)
        self._source_identity = str(source_identity or WORK_MEMORY_IMPORTER_SOURCE_IDENTITY).strip().lower() or WORK_MEMORY_IMPORTER_SOURCE_IDENTITY

    def dry_run(
        self,
        manifest_paths: Iterable[str | Path],
        *,
        only_gate: str = "all",
        limit: int | None = None,
    ) -> WorkMemoryImportResult:
        manifests = [load_work_memory_import_manifest(path) for path in manifest_paths]
        entries = self._plan_entries(manifests, only_gate=only_gate, limit=limit)
        return WorkMemoryImportResult(
            ok=all(entry.status != "blocked" for entry in entries if entry.selected or entry.plan_status == "blocked"),
            mode="dry_run",
            manifests=[_manifest_summary(manifest) for manifest in manifests],
            entries=entries,
            selected_gate=only_gate,
            limit=limit,
            identity={},
            source_identity=self._source_identity,
        )

    def execute(
        self,
        manifest_paths: Iterable[str | Path],
        *,
        account_id: str,
        role_id: str,
        session_id: str = "",
        thread_id: str = "",
        only_gate: str = "ready",
        limit: int | None = None,
    ) -> WorkMemoryImportResult:
        effective_account_id = _required_text(account_id, "account_id")
        effective_role_id = _required_text(role_id, "role_id")
        manifests = [load_work_memory_import_manifest(path) for path in manifest_paths]
        entries = self._plan_entries(manifests, only_gate=only_gate, limit=limit)
        for manifest in manifests:
            stable_session_id = session_id or _default_session_id(
                manifest_id=manifest.manifest_id,
                account_id=effective_account_id,
                role_id=effective_role_id,
            )
            stable_thread_id = thread_id or _default_thread_id(
                manifest_id=manifest.manifest_id,
                object_type=manifest.object_type,
                role_id=effective_role_id,
            )
            for entry in entries:
                if entry.manifest_id != manifest.manifest_id or not entry.selected:
                    continue
                if entry.plan_status == "blocked":
                    entry.status = "blocked"
                    continue
                if entry.import_gate == "manual_review_required":
                    queue_record_id, duplicate, audit_trail = self._queue_review(
                        manifest=manifest,
                        entry=entry,
                        account_id=effective_account_id,
                        role_id=effective_role_id,
                        session_id=stable_session_id,
                        thread_id=stable_thread_id,
                    )
                    entry.status = "queued_for_review"
                    entry.queue_record_id = queue_record_id
                    entry.duplicate = duplicate
                    entry.audit_trail = audit_trail
                    entry.message = "queued for manual review"
                    entry.tier = MemoryTier.META.value
                    continue
                write_result = self._manager.write_from_capture(
                    category=manifest.object_type,
                    title=_entry_title(manifest.object_type, entry.payload),
                    content=_entry_content(manifest.object_type, entry.payload, entry.import_metadata),
                    summary=_entry_summary(manifest.object_type, entry.payload),
                    payload=dict(entry.payload),
                    source_ref=_primary_source_ref(entry.payload),
                    source_system=self._source_identity,
                    source_agent=self._source_identity,
                    role_id=effective_role_id,
                    session_id=stable_session_id,
                    account_id=effective_account_id,
                    thread_id=stable_thread_id,
                    trace_id=_stable_trace_id(manifest.manifest_id, entry.seed_id),
                    confidence=_entry_confidence(manifest.object_type, entry.payload),
                    provenance_quality="complete",
                    identity_gaps=[],
                    import_metadata=dict(entry.import_metadata),
                    import_audit={
                        "mode": "execute",
                        "source_identity": self._source_identity,
                        "session_id": stable_session_id,
                        "thread_id": stable_thread_id,
                        "trace_id": _stable_trace_id(manifest.manifest_id, entry.seed_id),
                    },
                )
                _merge_write_result(entry, write_result)
        return WorkMemoryImportResult(
            ok=all(entry.status not in {"blocked"} for entry in entries if entry.selected),
            mode="execute",
            manifests=[_manifest_summary(manifest) for manifest in manifests],
            entries=entries,
            selected_gate=only_gate,
            limit=limit,
            identity={
                "account_id": effective_account_id,
                "role_id": effective_role_id,
                "session_id": session_id,
                "thread_id": thread_id,
            },
            source_identity=self._source_identity,
        )

    def list_review_queue(
        self,
        *,
        state: str = "pending",
        limit: int = 50,
    ) -> WorkMemoryReviewQueueResult:
        normalized_state = _normalize_review_state(state)
        raw_records = self._memory.get_meta(category=WORK_MEMORY_IMPORT_REVIEW_CATEGORY, limit=max(limit, 1) * 4)
        items: list[WorkMemoryReviewQueueItem] = []
        for record in raw_records:
            item = _review_queue_item(record)
            if normalized_state != "all" and item.review_state != normalized_state:
                continue
            items.append(item)
            if len(items) >= limit:
                break
        return WorkMemoryReviewQueueResult(
            ok=True,
            state=normalized_state,
            items=items,
            limit=limit,
        )

    def resolve_review(
        self,
        record_id: str,
        *,
        action: str,
        reviewer: str,
        reason: str,
        supersedes_decision_id: str = "",
    ) -> WorkMemoryReviewResolutionResult:
        normalized_action = _normalize_review_action(action)
        reviewer_name = _required_text(reviewer, "reviewer")
        review_reason = _required_text(reason, "reason")
        review_record = self._memory.get_by_record_id(_required_text(record_id, "record_id"))
        if review_record is None:
            return WorkMemoryReviewResolutionResult(
                ok=False,
                action=normalized_action,
                record_id=record_id,
                message="review queue record not found",
                review_state="",
                blocked_by=["record_id"],
            )
        if review_record.category != WORK_MEMORY_IMPORT_REVIEW_CATEGORY or not isinstance(review_record.value, dict):
            return WorkMemoryReviewResolutionResult(
                ok=False,
                action=normalized_action,
                record_id=record_id,
                message="record is not a work-memory import review entry",
                review_state="",
                blocked_by=["category"],
            )

        queue_value = dict(review_record.value)
        review_state = str(queue_value.get("review_state") or "pending").strip().lower() or "pending"
        if normalized_action != "rollback" and review_state != "pending":
            return WorkMemoryReviewResolutionResult(
                ok=False,
                action=normalized_action,
                record_id=record_id,
                message=f"review entry already resolved with state={review_state}",
                review_state=review_state,
                blocked_by=["review_state"],
                queue_value=queue_value,
                queue_audit_trail=self._memory.audit_trail(record_id),
            )
        if normalized_action == "rollback" and review_state != "resolved":
            return WorkMemoryReviewResolutionResult(
                ok=False,
                action=normalized_action,
                record_id=record_id,
                message="rollback requires a previously resolved review entry",
                review_state=review_state,
                blocked_by=["review_state"],
                queue_value=queue_value,
                queue_audit_trail=self._memory.audit_trail(record_id),
            )

        if normalized_action == "reject":
            queue_value["review_state"] = "resolved"
            queue_value["resolution_action"] = "reject"
            queue_value["resolution_reason"] = review_reason
            queue_value["resolution_actor"] = reviewer_name
            queue_value["resolution_at"] = _now_iso()
            payload = dict(queue_value.get("payload") or {})
            payload["review_status"] = "rejected"
            queue_value["payload"] = payload
            self._memory.update_record_value(
                record_id,
                queue_value,
                reason=f"work-memory review reject: {review_reason}",
                agent=reviewer_name,
            )
            return WorkMemoryReviewResolutionResult(
                ok=True,
                action=normalized_action,
                record_id=record_id,
                message="review queue entry rejected",
                review_state="resolved",
                queue_value=queue_value,
                queue_audit_trail=self._memory.audit_trail(record_id),
            )

        if normalized_action == "rollback":
            return self._rollback_review_resolution(
                review_record_id=record_id,
                review_record=review_record,
                reviewer=reviewer_name,
                reason=review_reason,
            )

        return self._promote_review_resolution(
            review_record_id=record_id,
            review_record=review_record,
            action=normalized_action,
            reviewer=reviewer_name,
            reason=review_reason,
            supersedes_decision_id=supersedes_decision_id,
        )

    def _plan_entries(
        self,
        manifests: list[WorkMemoryImportManifest],
        *,
        only_gate: str,
        limit: int | None,
    ) -> list[WorkMemoryImportEntryResult]:
        normalized_gate = _normalize_only_gate(only_gate)
        selected = 0
        results: list[WorkMemoryImportEntryResult] = []
        for manifest in manifests:
            for entry in manifest.entries:
                import_metadata = _build_import_metadata(manifest, entry)
                normalized_input = _normalize_import_payload_defaults(
                    manifest=manifest,
                    payload=entry.payload,
                )
                try:
                    work_memory = build_work_memory_object(
                        manifest.object_type,
                        normalized_input,
                        fallback_source_ref=_primary_source_ref(normalized_input),
                    )
                    normalized_payload = work_memory.to_dict()
                    plan_status, message, blocked_by = self._plan_status_for_entry(
                        manifest=manifest,
                        entry=entry,
                        work_memory=work_memory,
                    )
                    object_id = work_memory.object_id
                except WorkMemoryValidationError as exc:
                    plan_status = "blocked"
                    message = str(exc)
                    blocked_by = [exc.blocked_by]
                    object_id = ""
                    normalized_payload = dict(entry.payload)
                should_select = False
                if plan_status in {"ready_to_write", "manual_review_required"}:
                    if normalized_gate == "all" or entry.import_gate == normalized_gate:
                        if limit is None or selected < limit:
                            should_select = True
                            selected += 1
                status = plan_status if should_select or plan_status == "blocked" else "skipped"
                skip_message = message
                if status == "skipped":
                    skip_message = "excluded by only_gate/limit"
                results.append(
                    WorkMemoryImportEntryResult(
                        manifest_id=manifest.manifest_id,
                        manifest_path=manifest.manifest_path,
                        manifest_schema_version=manifest.schema_version,
                        manifest_generated_at=manifest.generated_at,
                        object_type=manifest.object_type,
                        seed_id=entry.seed_id,
                        import_gate=entry.import_gate,
                        plan_status=plan_status,
                        status=status,
                        selected=should_select,
                        object_id=object_id,
                        message=skip_message,
                        blocked_by=blocked_by,
                        payload=normalized_payload,
                        metadata=dict(entry.metadata),
                        import_metadata=import_metadata,
                    )
                )
        return results

    @staticmethod
    def _plan_status_for_entry(
        *,
        manifest: WorkMemoryImportManifest,
        entry: WorkMemoryImportEntry,
        work_memory: WorkMemoryObject,
    ) -> tuple[str, str, list[str]]:
        gate = str(entry.import_gate or "").strip()
        if gate not in _SUPPORTED_IMPORT_GATES:
            return "blocked", f"unsupported import_gate: {gate}", ["import_gate"]
        review_status = str(work_memory.review_status or "").strip().lower()
        if gate == "ready":
            if review_status not in {"approved", "active"}:
                return "blocked", f"ready entry must validate to approved/active, got {review_status}", ["review_status"]
            return "ready_to_write", "validated and ready to write", []
        if review_status not in {"staged", "rejected"}:
            return "blocked", (
                "manual_review_required entry must validate to staged/rejected, "
                f"got {review_status}"
            ), ["review_status"]
        return "manual_review_required", "validated; queued for manual review", []

    def _queue_review(
        self,
        *,
        manifest: WorkMemoryImportManifest,
        entry: WorkMemoryImportEntryResult,
        account_id: str,
        role_id: str,
        session_id: str,
        thread_id: str,
    ) -> tuple[str, bool, list[dict[str, Any]]]:
        trace_id = _stable_trace_id(manifest.manifest_id, entry.seed_id)
        review_note = _entry_content(manifest.object_type, entry.payload, entry.import_metadata)
        existing = self._existing_review_record(manifest_id=manifest.manifest_id, seed_id=entry.seed_id)
        if existing is not None:
            return existing.record_id, True, self._memory.audit_trail(existing.record_id)
        record_id = self._memory.stage_and_promote(
            MemoryRecord(
                category=WORK_MEMORY_IMPORT_REVIEW_CATEGORY,
                key=f"{manifest.manifest_id}:{entry.seed_id}",
                value={
                    "kind": WORK_MEMORY_IMPORT_REVIEW_CATEGORY,
                    "manifest_id": manifest.manifest_id,
                    "manifest_path": manifest.manifest_path,
                    "seed_id": entry.seed_id,
                    "object_type": manifest.object_type,
                    "payload": dict(entry.payload),
                    "import_metadata": dict(entry.import_metadata),
                    "review_note": review_note,
                    "review_state": "pending",
                    "resolution_action": "",
                    "resolution_reason": "",
                    "resolution_actor": "",
                    "resolution_at": "",
                    "resolution_record_id": "",
                    "resolution_superseded_record_id": "",
                    "resolution_restore_snapshots": [],
                },
                confidence=1.0,
                source=MemorySource(
                    type=SourceType.SYSTEM.value,
                    agent=self._source_identity,
                    role=role_id,
                    session_id=session_id,
                    account_id=account_id,
                    thread_id=thread_id,
                    task_id=trace_id,
                ).to_dict(),
                evidence_span=review_note[:500],
            ),
            MemoryTier.META,
            reason="work-memory import review queue",
        )
        audit_trail = self._memory.audit_trail(record_id)
        duplicate = any(item.get("action") == "update" for item in audit_trail)
        return record_id, duplicate, audit_trail

    def _existing_review_record(self, *, manifest_id: str, seed_id: str) -> MemoryRecord | None:
        key = f"{manifest_id}:{seed_id}"
        for record in self._memory.get_meta(key=key, category=WORK_MEMORY_IMPORT_REVIEW_CATEGORY, limit=1):
            return record
        return None

    def _promote_review_resolution(
        self,
        *,
        review_record_id: str,
        review_record: MemoryRecord,
        action: str,
        reviewer: str,
        reason: str,
        supersedes_decision_id: str,
    ) -> WorkMemoryReviewResolutionResult:
        queue_value = dict(review_record.value)
        object_type = str(queue_value.get("object_type") or "").strip()
        payload = dict(queue_value.get("payload") or {})
        import_metadata = dict(queue_value.get("import_metadata") or {})
        source = review_record.source if isinstance(review_record.source, dict) else {}
        account_id = str(source.get("account_id") or "").strip()
        role_id = str(source.get("role_id") or source.get("role") or "").strip()
        session_id = str(source.get("session_id") or "").strip()
        thread_id = str(source.get("thread_id") or "").strip()
        trace_id = str(source.get("task_id") or _stable_trace_id(import_metadata.get("manifest_id", "review"), import_metadata.get("seed_id", review_record_id))).strip()

        restore_snapshots: list[dict[str, Any]] = []
        payload["review_status"] = "approved"
        if action == "supersede":
            if object_type != "decision_ledger":
                return WorkMemoryReviewResolutionResult(
                    ok=False,
                    action=action,
                    record_id=review_record_id,
                    message="supersede is only supported for decision_ledger review entries",
                    review_state=str(queue_value.get("review_state") or "pending"),
                    blocked_by=["object_type"],
                    queue_value=queue_value,
                    queue_audit_trail=self._memory.audit_trail(review_record_id),
                )
            supersede_target = str(supersedes_decision_id or payload.get("supersedes_decision_id") or "").strip()
            if not supersede_target:
                return WorkMemoryReviewResolutionResult(
                    ok=False,
                    action=action,
                    record_id=review_record_id,
                    message="supersede requires --supersedes-decision-id or payload.supersedes_decision_id",
                    review_state=str(queue_value.get("review_state") or "pending"),
                    blocked_by=["supersedes_decision_id"],
                    queue_value=queue_value,
                    queue_audit_trail=self._memory.audit_trail(review_record_id),
                )
            previous = self._memory.get_by_key(supersede_target)
            if previous is None or not isinstance(previous.value, dict):
                return WorkMemoryReviewResolutionResult(
                    ok=False,
                    action=action,
                    record_id=review_record_id,
                    message=f"supersede target not found: {supersede_target}",
                    review_state=str(queue_value.get("review_state") or "pending"),
                    blocked_by=["supersedes_decision_id"],
                    queue_value=queue_value,
                    queue_audit_trail=self._memory.audit_trail(review_record_id),
                )
            payload["supersedes_decision_id"] = supersede_target
            restore_snapshots.append(
                {
                    "record_id": previous.record_id,
                    "value": dict(previous.value),
                }
            )

        write_result = self._manager.write_from_capture(
            category=object_type,
            title=_entry_title(object_type, payload),
            content=_entry_content(object_type, payload, import_metadata),
            summary=_entry_summary(object_type, payload),
            payload=payload,
            source_ref=_primary_source_ref(payload),
            source_system=self._source_identity,
            source_agent=reviewer,
            role_id=role_id,
            session_id=session_id,
            account_id=account_id,
            thread_id=thread_id,
            trace_id=f"{trace_id}:review:{action}",
            confidence=_entry_confidence(object_type, payload),
            provenance_quality="complete",
            identity_gaps=[],
            import_metadata=import_metadata,
            import_audit={
                "mode": "manual_review_resolution",
                "source_identity": self._source_identity,
                "queue_record_id": review_record_id,
                "review_action": action,
                "reviewer": reviewer,
                "review_reason": reason,
                "trace_id": f"{trace_id}:review:{action}",
            },
        )
        if not write_result.ok:
            return WorkMemoryReviewResolutionResult(
                ok=False,
                action=action,
                record_id=review_record_id,
                message=write_result.message,
                review_state=str(queue_value.get("review_state") or "pending"),
                blocked_by=list(write_result.blocked_by),
                queue_value=queue_value,
                queue_audit_trail=self._memory.audit_trail(review_record_id),
                durable_audit_trail=list(write_result.audit_trail),
            )

        queue_value["review_state"] = "resolved"
        queue_value["resolution_action"] = action
        queue_value["resolution_reason"] = reason
        queue_value["resolution_actor"] = reviewer
        queue_value["resolution_at"] = _now_iso()
        queue_value["resolution_record_id"] = write_result.record_id
        queue_value["resolution_superseded_record_id"] = write_result.superseded_record_id
        queue_value["resolution_restore_snapshots"] = restore_snapshots
        queue_value["payload"] = payload
        self._memory.update_record_value(
            review_record_id,
            queue_value,
            reason=f"work-memory review {action}: {reason}",
            agent=reviewer,
        )
        return WorkMemoryReviewResolutionResult(
            ok=True,
            action=action,
            record_id=review_record_id,
            message=write_result.message,
            review_state="resolved",
            durable_record_id=write_result.record_id,
            superseded_record_id=write_result.superseded_record_id,
            queue_value=queue_value,
            queue_audit_trail=self._memory.audit_trail(review_record_id),
            durable_audit_trail=list(write_result.audit_trail),
        )

    def _rollback_review_resolution(
        self,
        *,
        review_record_id: str,
        review_record: MemoryRecord,
        reviewer: str,
        reason: str,
    ) -> WorkMemoryReviewResolutionResult:
        queue_value = dict(review_record.value)
        durable_record_id = str(queue_value.get("resolution_record_id") or "").strip()
        if not durable_record_id:
            return WorkMemoryReviewResolutionResult(
                ok=False,
                action="rollback",
                record_id=review_record_id,
                message="rollback target durable record is missing",
                review_state=str(queue_value.get("review_state") or "resolved"),
                blocked_by=["resolution_record_id"],
                queue_value=queue_value,
                queue_audit_trail=self._memory.audit_trail(review_record_id),
            )
        durable_record = self._memory.get_by_record_id(durable_record_id)
        if durable_record is None or not isinstance(durable_record.value, dict):
            return WorkMemoryReviewResolutionResult(
                ok=False,
                action="rollback",
                record_id=review_record_id,
                message="rollback target durable record not found",
                review_state=str(queue_value.get("review_state") or "resolved"),
                blocked_by=["resolution_record_id"],
                queue_value=queue_value,
                queue_audit_trail=self._memory.audit_trail(review_record_id),
            )
        durable_value = dict(durable_record.value)
        durable_value["review_status"] = "rejected"
        durable_value["rollback"] = {
            "rolled_back_at": _now_iso(),
            "rolled_back_by": reviewer,
            "reason": reason,
            "from_review_record_id": review_record_id,
        }
        self._memory.update_record_value(
            durable_record_id,
            durable_value,
            reason=f"work-memory review rollback: {reason}",
            agent=reviewer,
        )

        for snapshot in list(queue_value.get("resolution_restore_snapshots") or []):
            restore_record_id = str(snapshot.get("record_id") or "").strip()
            restore_value = snapshot.get("value")
            if not restore_record_id or not isinstance(restore_value, dict):
                continue
            self._memory.update_record_value(
                restore_record_id,
                restore_value,
                reason=f"work-memory rollback restore: {reason}",
                agent=reviewer,
            )

        queue_value["review_state"] = "rolled_back"
        queue_value["resolution_action"] = "rollback"
        queue_value["resolution_reason"] = reason
        queue_value["resolution_actor"] = reviewer
        queue_value["resolution_at"] = _now_iso()
        self._memory.update_record_value(
            review_record_id,
            queue_value,
            reason=f"work-memory review rollback: {reason}",
            agent=reviewer,
        )
        return WorkMemoryReviewResolutionResult(
            ok=True,
            action="rollback",
            record_id=review_record_id,
            message="reviewed durable object rolled back",
            review_state="rolled_back",
            durable_record_id=durable_record_id,
            superseded_record_id=str(queue_value.get("resolution_superseded_record_id") or "").strip(),
            queue_value=queue_value,
            queue_audit_trail=self._memory.audit_trail(review_record_id),
            durable_audit_trail=self._memory.audit_trail(durable_record_id),
        )


def _merge_write_result(entry: WorkMemoryImportEntryResult, write_result: WorkMemoryWriteResult) -> None:
    entry.record_id = write_result.record_id
    entry.duplicate = write_result.duplicate
    entry.review_status = write_result.review_status
    entry.active = write_result.active
    entry.tier = write_result.tier
    entry.governance = dict(write_result.governance)
    entry.audit_trail = list(write_result.audit_trail)
    entry.message = write_result.message
    entry.blocked_by = list(write_result.blocked_by)
    if write_result.ok:
        entry.status = "written"
    else:
        entry.status = "blocked"


def _manifest_summary(manifest: WorkMemoryImportManifest) -> dict[str, Any]:
    return {
        "manifest_id": manifest.manifest_id,
        "manifest_path": manifest.manifest_path,
        "schema_version": manifest.schema_version,
        "object_type": manifest.object_type,
        "generated_at": manifest.generated_at,
        "entry_count": manifest.entry_count,
    }


def _build_import_metadata(
    manifest: WorkMemoryImportManifest,
    entry: WorkMemoryImportEntry,
) -> dict[str, Any]:
    metadata = dict(entry.metadata)
    metadata.update(
        {
            "seed_id": entry.seed_id,
            "import_gate": entry.import_gate,
            "manifest_id": manifest.manifest_id,
            "manifest_schema_version": manifest.schema_version,
            "manifest_generated_at": manifest.generated_at,
            "manifest_path": manifest.manifest_path,
            "object_type": manifest.object_type,
            "source_repo": manifest.source_repo,
            "normalization_rules_ref": manifest.normalization_rules_ref,
            "contract_basis": list(manifest.contract_basis),
        }
    )
    return metadata


def _normalize_import_payload_defaults(
    *,
    manifest: WorkMemoryImportManifest,
    payload: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(payload)
    stable_valid_from = str(normalized.get("valid_from") or manifest.generated_at or "").strip()
    if stable_valid_from:
        normalized["valid_from"] = stable_valid_from
    if manifest.object_type == "active_project":
        normalized["last_updated"] = str(
            normalized.get("last_updated") or stable_valid_from
        ).strip()
    elif manifest.object_type == "handoff":
        normalized["created_at"] = str(
            normalized.get("created_at") or stable_valid_from
        ).strip()
    return normalized


def _normalize_only_gate(value: str) -> str:
    normalized = str(value or "").strip() or "all"
    if normalized not in {"ready", "manual_review_required", "all"}:
        raise WorkMemoryImportValidationError(
            f"unsupported only_gate: {normalized}",
            blocked_by="only_gate",
        )
    return normalized


def _normalize_review_state(value: str) -> str:
    normalized = str(value or "").strip().lower() or "pending"
    if normalized not in _SUPPORTED_REVIEW_STATES:
        raise WorkMemoryImportValidationError(
            f"unsupported review state: {normalized}",
            blocked_by="review_state",
        )
    return normalized


def _normalize_review_action(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in _SUPPORTED_REVIEW_ACTIONS:
        raise WorkMemoryImportValidationError(
            f"unsupported review action: {normalized}",
            blocked_by="review_action",
        )
    return normalized


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise WorkMemoryImportValidationError(f"{field_name} is required", blocked_by=field_name)
    return text


def _primary_source_ref(payload: dict[str, Any]) -> str:
    refs = payload.get("source_refs")
    if isinstance(refs, list):
        for item in refs:
            text = str(item or "").strip()
            if text:
                return text
    return ""


def _entry_confidence(object_type: str, payload: dict[str, Any]) -> float:
    if object_type == "decision_ledger":
        try:
            return max(0.0, min(float(payload.get("confidence") or 0.9), 1.0))
        except Exception:
            return 0.9
    return 0.95


def _entry_title(object_type: str, payload: dict[str, Any]) -> str:
    if object_type == "active_project":
        return f"Imported active project: {payload.get('name') or payload.get('project_id') or 'unknown'}"
    return f"Imported decision ledger: {payload.get('decision_id') or 'unknown'}"


def _entry_summary(object_type: str, payload: dict[str, Any]) -> str:
    if object_type == "active_project":
        parts = [
            str(payload.get("name") or "").strip(),
            str(payload.get("phase") or "").strip(),
            str(payload.get("status") or "").strip(),
        ]
        return " | ".join(part for part in parts if part)[:280]
    return str(payload.get("statement") or "").strip()[:280]


def _entry_content(object_type: str, payload: dict[str, Any], import_metadata: dict[str, Any]) -> str:
    lines = [
        "Imported from planning backfill manifest.",
        f"manifest_id: {import_metadata.get('manifest_id')}",
        f"seed_id: {import_metadata.get('seed_id')}",
        f"object_type: {object_type}",
    ]
    if object_type == "active_project":
        lines.extend(
            [
                f"project_id: {payload.get('project_id')}",
                f"name: {payload.get('name')}",
                f"phase: {payload.get('phase')}",
                f"status: {payload.get('status')}",
            ]
        )
    else:
        lines.extend(
            [
                f"decision_id: {payload.get('decision_id')}",
                f"statement: {payload.get('statement')}",
                f"domain: {payload.get('domain')}",
            ]
        )
    conditions = import_metadata.get("conditions")
    if isinstance(conditions, list) and conditions:
        lines.append("conditions:")
        lines.extend(f"- {str(item).strip()}" for item in conditions if str(item).strip())
    do_not_infer = str(import_metadata.get("do_not_infer") or "").strip()
    if do_not_infer:
        lines.append(f"do_not_infer: {do_not_infer}")
    source_seed_doc = str(import_metadata.get("source_seed_doc") or "").strip()
    if source_seed_doc:
        lines.append(f"source_seed_doc: {source_seed_doc}")
    return "\n".join(lines).strip()


def _default_session_id(*, manifest_id: str, account_id: str, role_id: str) -> str:
    return f"wm-import::{account_id}::{role_id}::{manifest_id}"


def _default_thread_id(*, manifest_id: str, object_type: str, role_id: str) -> str:
    return f"wm-import::{role_id}::{object_type}::{manifest_id}"


def _stable_trace_id(manifest_id: str, seed_id: str) -> str:
    raw = f"{manifest_id}:{seed_id}".encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:16]
    return f"wm-import-{digest}"


def _review_queue_item(record: MemoryRecord) -> WorkMemoryReviewQueueItem:
    value = dict(record.value) if isinstance(record.value, dict) else {}
    return WorkMemoryReviewQueueItem(
        record_id=record.record_id,
        manifest_id=str(value.get("manifest_id") or ""),
        manifest_path=str(value.get("manifest_path") or ""),
        seed_id=str(value.get("seed_id") or ""),
        object_type=str(value.get("object_type") or ""),
        review_state=str(value.get("review_state") or "pending").strip().lower() or "pending",
        resolution_action=str(value.get("resolution_action") or "").strip().lower(),
        resolution_reason=str(value.get("resolution_reason") or ""),
        resolution_actor=str(value.get("resolution_actor") or ""),
        resolution_record_id=str(value.get("resolution_record_id") or ""),
        resolution_superseded_record_id=str(value.get("resolution_superseded_record_id") or ""),
        created_at=str(record.created_at or ""),
        updated_at=str(record.updated_at or ""),
        import_metadata=dict(value.get("import_metadata") or {}),
        payload=dict(value.get("payload") or {}),
        source=dict(record.source or {}),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
