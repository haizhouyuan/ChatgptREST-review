from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from chatgptrest.kernel.memory_manager import MemoryManager, MemoryRecord, MemorySource, MemoryTier, SourceType
from chatgptrest.kernel.work_memory_objects import (
    DecisionLedgerObject,
    WORK_MEMORY_ACTIVE_REVIEW_STATUSES,
    WorkMemoryObject,
    WorkMemoryValidationError,
    build_work_memory_object,
    work_memory_is_active,
)
from chatgptrest.kernel.work_memory_policy import (
    WorkMemoryGovernancePolicy,
    load_work_memory_governance,
)


@dataclass
class WorkMemoryWriteResult:
    ok: bool
    message: str
    record_id: str = ""
    category: str = ""
    tier: str = ""
    duplicate: bool = False
    blocked_by: list[str] = field(default_factory=list)
    work_memory: dict[str, Any] = field(default_factory=dict)
    audit_trail: list[dict[str, Any]] = field(default_factory=list)
    review_status: str = ""
    active: bool = False
    promotion_state: str = ""
    superseded_record_id: str = ""
    governance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "message": self.message,
            "record_id": self.record_id,
            "category": self.category,
            "tier": self.tier,
            "duplicate": self.duplicate,
            "blocked_by": list(self.blocked_by),
            "work_memory": dict(self.work_memory),
            "audit_trail": list(self.audit_trail),
            "review_status": self.review_status,
            "active": self.active,
            "promotion_state": self.promotion_state,
            "superseded_record_id": self.superseded_record_id,
            "governance": dict(self.governance),
        }


class WorkMemoryManager:
    _ACTIVE_CONTEXT_CATEGORIES = (
        "active_project",
        "decision_ledger",
        "post_call_triage",
        "handoff",
    )
    _ASCII_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]{1,}")
    _CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
    _NON_WORD_RE = re.compile(r"[\W_]+", re.UNICODE)
    _QUERY_FIELDS = {
        "active_project": (
            "project_id",
            "name",
            "phase",
            "status",
            "summary",
            "content_excerpt",
            "blockers",
            "next_steps",
            "key_files",
            "owner",
        ),
        "decision_ledger": (
            "decision_id",
            "statement",
            "domain",
            "summary",
            "content_excerpt",
        ),
        "post_call_triage": (
            "call_id",
            "participants",
            "new_facts",
            "intended_actions",
            "ledger_update_candidates",
            "project_refs",
            "summary",
            "content_excerpt",
        ),
        "handoff": (
            "handoff_id",
            "project_refs",
            "current_situation",
            "changes_made",
            "open_loops",
            "next_pickup",
            "summary",
            "content_excerpt",
        ),
    }
    _QUERY_RECALL_WINDOW = 50

    def __init__(
        self,
        memory: MemoryManager,
        *,
        governance_policy: WorkMemoryGovernancePolicy | None = None,
    ):
        self._memory = memory
        self._governance_policy = governance_policy or load_work_memory_governance()

    def write_from_capture(
        self,
        *,
        category: str,
        title: str,
        content: str,
        summary: str,
        payload: dict[str, Any],
        source_ref: str,
        source_system: str,
        source_agent: str,
        role_id: str,
        session_id: str,
        account_id: str,
        thread_id: str,
        trace_id: str,
        confidence: float,
        provenance_quality: str,
        identity_gaps: list[str],
        import_metadata: dict[str, Any] | None = None,
        import_audit: dict[str, Any] | None = None,
    ) -> WorkMemoryWriteResult:
        try:
            work_memory = build_work_memory_object(
                category,
                payload,
                fallback_source_ref=source_ref,
            )
        except WorkMemoryValidationError as exc:
            return WorkMemoryWriteResult(
                ok=False,
                message=str(exc),
                category=category,
                blocked_by=[exc.blocked_by],
                promotion_state="blocked_validation",
            )

        governance = self._apply_review_governance(
            work_memory=work_memory,
            category=category,
            source_system=source_system,
            source_agent=source_agent,
            role_id=role_id,
            account_id=account_id,
            provenance_quality=provenance_quality,
            identity_gaps=identity_gaps,
        )
        record_value = work_memory.to_dict()
        project_scope = self._project_scope_from_payload(record_value)
        record_value.update(
            {
                "title": title,
                "summary": summary,
                "content_excerpt": str(content or "")[:500],
                "trace_id": trace_id,
                "source_system": source_system,
                "provenance_quality": provenance_quality,
                "identity_gaps": list(identity_gaps),
            }
        )
        if import_metadata:
            record_value["import_metadata"] = dict(import_metadata)
        if import_audit:
            record_value["import_audit"] = dict(import_audit)
        target_tier = MemoryTier.EPISODIC
        bounded_confidence = max(0.0, min(float(confidence), 1.0))
        record = MemoryRecord(
            category=category,
            key=work_memory.object_id,
            value=record_value,
            confidence=bounded_confidence,
            source=MemorySource(
                type=SourceType.USER_INPUT.value,
                agent=source_agent,
                role=role_id,
                session_id=session_id,
                account_id=account_id,
                thread_id=thread_id,
                project_id=project_scope,
                task_id=trace_id,
            ).to_dict(),
            evidence_span=str(content or "")[:500],
        )
        record_id = self._memory.stage(record)
        promoted = self._memory.promote(record_id, target_tier, "work-memory capture")
        audit_trail = self._memory.audit_trail(record_id)
        duplicate = any(entry.get("action") == "update" for entry in audit_trail)
        if not promoted:
            return WorkMemoryWriteResult(
                ok=False,
                message="work-memory promotion blocked",
                record_id=record_id,
                category=category,
                tier=MemoryTier.STAGING.value,
                duplicate=duplicate,
                blocked_by=["promotion"],
                work_memory=record_value,
                audit_trail=audit_trail,
                review_status=work_memory.review_status,
                active=False,
                promotion_state="staged_only",
                governance=governance,
            )

        superseded_record_id = ""
        if (
            isinstance(work_memory, DecisionLedgerObject)
            and work_memory.supersedes_decision_id
            and work_memory_is_active(work_memory)
        ):
            superseded_record_id = self._supersede_decision(
                previous_decision_id=work_memory.supersedes_decision_id,
                new_decision_id=work_memory.decision_id,
                valid_to=work_memory.valid_from,
            )
            audit_trail = self._memory.audit_trail(record_id)

        effective_active = work_memory_is_active(work_memory)
        promotion_state = "promoted" if effective_active else "promoted_staged"
        message = "captured" if effective_active else "captured as staged"
        if governance.get("requested_active") and not governance.get("approved_by_policy"):
            promotion_state = "promoted_requires_review"
            message = "captured as staged; review required"

        return WorkMemoryWriteResult(
            ok=True,
            message=message,
            record_id=record_id,
            category=category,
            tier=target_tier.value,
            duplicate=duplicate,
            work_memory=record_value,
            audit_trail=audit_trail,
            review_status=work_memory.review_status,
            active=effective_active,
            promotion_state=promotion_state,
            superseded_record_id=superseded_record_id,
            governance=governance,
        )

    def build_active_context(
        self,
        *,
        query: str,
        session_id: str,
        account_id: str,
        agent_id: str,
        role_id: str,
        thread_id: str,
        project_id: str = "",
        item_limit: int = 2,
    ) -> tuple[str, dict[str, Any]]:
        query_terms = self._query_terms(query)
        identity_gaps = [
            gap
            for gap, value in (
                ("missing_role_id", role_id),
                ("missing_account_id", account_id),
                ("missing_thread_id", thread_id),
            )
            if not str(value or "").strip()
        ]
        sections: list[str] = []
        counts: dict[str, int] = {}
        scope_hits: dict[str, str] = {}
        import_hits: list[dict[str, Any]] = []
        for category in self._ACTIVE_CONTEXT_CATEGORIES:
            active_payloads, scope_name = self._load_active_payloads(
                category=category,
                item_limit=item_limit,
                session_id=session_id,
                account_id=account_id,
                agent_id=agent_id,
                role_id=role_id,
                thread_id=thread_id,
                project_id=project_id,
                query=query,
                query_terms=query_terms,
            )
            if not active_payloads:
                continue
            counts[category] = len(active_payloads)
            scope_hits[category] = scope_name
            import_hits.extend(
                hit
                for hit in (
                    self._import_hit_metadata(category=category, payload=payload)
                    for payload in active_payloads
                )
                if hit
            )
            if category == "active_project":
                sections.append(self._format_active_projects(active_payloads))
            elif category == "decision_ledger":
                sections.append(self._format_decisions(active_payloads))
            elif category == "post_call_triage":
                sections.append(self._format_triage(active_payloads))
            elif category == "handoff":
                sections.append(self._format_handoffs(active_payloads))
        return "\n\n".join(section for section in sections if section.strip()), {
            "category_counts": counts,
            "identity_gaps": identity_gaps,
            "scope_hits": scope_hits,
            "query_sensitive": bool(query_terms),
            "import_hits": import_hits,
        }

    def _apply_review_governance(
        self,
        *,
        work_memory: WorkMemoryObject,
        category: str,
        source_system: str,
        source_agent: str,
        role_id: str,
        account_id: str,
        provenance_quality: str,
        identity_gaps: list[str],
    ) -> dict[str, Any]:
        requested_review_status = str(work_memory.review_status or "staged").strip().lower()
        requested_active = requested_review_status in WORK_MEMORY_ACTIVE_REVIEW_STATUSES
        normalized_source = str(source_system or "").strip().lower()
        normalized_agent = str(source_agent or "").strip().lower()
        governance = {
            "category": category,
            "approval_policy": self._governance_policy.approval_policy,
            "requested_review_status": requested_review_status,
            "effective_review_status": requested_review_status,
            "requested_active": requested_active,
            "approved_by_policy": requested_active,
            "reasons": [],
        }
        if not requested_active:
            return governance

        reasons: list[str] = []
        if (
            normalized_source not in self._governance_policy.allow_approved_sources
            and normalized_agent not in self._governance_policy.allow_approved_sources
        ):
            reasons.append("source_not_allowlisted")
        for field_name in self._governance_policy.require_identity_fields:
            if field_name == "account_id" and not str(account_id or "").strip():
                reasons.append("missing_account_id")
            elif field_name == "role_id" and not str(role_id or "").strip():
                reasons.append("missing_role_id")
        if str(provenance_quality or "").strip().lower() != self._governance_policy.require_provenance_quality:
            reasons.append("provenance_not_complete")
        if identity_gaps:
            reasons.extend(
                gap for gap in identity_gaps
                if gap not in reasons
            )

        if not reasons:
            return governance

        work_memory.review_status = "staged"
        governance["effective_review_status"] = "staged"
        governance["approved_by_policy"] = False
        governance["reasons"] = reasons
        return governance

    def _load_active_payloads(
        self,
        *,
        category: str,
        item_limit: int,
        session_id: str,
        account_id: str,
        agent_id: str,
        role_id: str,
        thread_id: str,
        project_id: str,
        query: str,
        query_terms: list[str],
    ) -> tuple[list[dict[str, Any]], str]:
        for scope_name, filters in self._scope_candidates(
            category=category,
            session_id=session_id,
            account_id=account_id,
            agent_id=agent_id,
            role_id=role_id,
            thread_id=thread_id,
            project_id=project_id,
        ):
            recall_limit = max(item_limit * 3, item_limit)
            if query_terms:
                recall_limit = max(recall_limit, self._QUERY_RECALL_WINDOW)
            records = self._memory.get_episodic(
                query="",
                category=category,
                limit=recall_limit,
                agent_id=filters.get("agent_id", ""),
                session_id=filters.get("session_id", ""),
                role_id=filters.get("role_id", ""),
                account_id=filters.get("account_id", ""),
                thread_id=filters.get("thread_id", ""),
                project_id=filters.get("project_id", ""),
            )
            ranked_records = sorted(
                (
                    record
                    for record in records
                    if isinstance(record.value, dict) and work_memory_is_active(record.value)
                ),
                key=lambda record: (
                    self._query_score(category=category, payload=record.value, query=query, query_terms=query_terms),
                    str(record.updated_at or ""),
                    float(record.confidence or 0.0),
                ),
                reverse=True,
            )
            payloads: list[dict[str, Any]] = []
            seen_ids: set[str] = set()
            for record in ranked_records:
                dedupe_key = str(record.value.get("object_id") or record.key or record.record_id)
                if dedupe_key in seen_ids:
                    continue
                seen_ids.add(dedupe_key)
                payloads.append(record.value)
                if len(payloads) >= item_limit:
                    break
            if payloads:
                return payloads, scope_name
        return [], ""

    def _scope_candidates(
        self,
        *,
        category: str,
        session_id: str,
        account_id: str,
        agent_id: str,
        role_id: str,
        thread_id: str,
        project_id: str,
    ) -> list[tuple[str, dict[str, str]]]:
        candidates: list[tuple[str, dict[str, str]]] = []
        seen: set[tuple[tuple[str, str], ...]] = set()

        def _add_scope(name: str, **filters: str) -> None:
            normalized = {
                key: str(value).strip()
                for key, value in filters.items()
                if str(value or "").strip()
            }
            if not normalized:
                return
            marker = tuple(sorted(normalized.items()))
            if marker in seen:
                return
            seen.add(marker)
            candidates.append((name, normalized))

        if category in {"active_project", "decision_ledger"}:
            _add_scope("account_role_project", account_id=account_id, role_id=role_id, project_id=project_id)
            _add_scope("account_project", account_id=account_id, project_id=project_id)
            _add_scope("thread_project", thread_id=thread_id, project_id=project_id)
            _add_scope("session_project", session_id=session_id, project_id=project_id)
            _add_scope("account_role", account_id=account_id, role_id=role_id)
            _add_scope("account_thread", account_id=account_id, thread_id=thread_id)
            _add_scope("account", account_id=account_id)
            _add_scope("thread_role", thread_id=thread_id, role_id=role_id)
            _add_scope("thread", thread_id=thread_id)
            _add_scope("session_role", session_id=session_id, role_id=role_id)
            _add_scope("session_agent", session_id=session_id, agent_id=agent_id)
            _add_scope("session", session_id=session_id)
            return candidates

        if category == "post_call_triage":
            _add_scope(
                "account_role_thread_project",
                account_id=account_id,
                role_id=role_id,
                thread_id=thread_id,
                project_id=project_id,
            )
            _add_scope("account_project", account_id=account_id, project_id=project_id)
            _add_scope("account_role_thread", account_id=account_id, role_id=role_id, thread_id=thread_id)
            _add_scope("account_thread", account_id=account_id, thread_id=thread_id)
            _add_scope("thread", thread_id=thread_id)
            _add_scope("account_role", account_id=account_id, role_id=role_id)
            _add_scope("account", account_id=account_id)
            _add_scope("session_thread", session_id=session_id, thread_id=thread_id)
            _add_scope("session", session_id=session_id)
            return candidates

        if category == "handoff":
            _add_scope(
                "account_role_thread_project",
                account_id=account_id,
                role_id=role_id,
                thread_id=thread_id,
                project_id=project_id,
            )
            _add_scope("account_project", account_id=account_id, project_id=project_id)
            _add_scope("account_role_thread", account_id=account_id, role_id=role_id, thread_id=thread_id)
            _add_scope("account_role", account_id=account_id, role_id=role_id)
            _add_scope("account", account_id=account_id)
            _add_scope("thread", thread_id=thread_id)
            _add_scope("session", session_id=session_id)
            return candidates

        _add_scope("session", session_id=session_id)
        return candidates

    @staticmethod
    def _project_scope_from_payload(payload: dict[str, Any]) -> str:
        direct = str(payload.get("project_id") or "").strip()
        if direct:
            return direct
        refs = payload.get("project_refs")
        if isinstance(refs, list):
            for raw in refs:
                candidate = str(raw or "").strip()
                if candidate:
                    return candidate
        return ""

    @classmethod
    def _query_terms(cls, query: str) -> list[str]:
        raw = str(query or "").strip().lower()
        if not raw:
            return []
        terms: list[str] = []
        seen: set[str] = set()
        for token in cls._ASCII_TOKEN_RE.findall(raw):
            if token not in seen:
                seen.add(token)
                terms.append(token)
        for token in cls._CJK_RUN_RE.findall(raw):
            if token not in seen:
                seen.add(token)
                terms.append(token)
        compact = cls._NON_WORD_RE.sub("", raw)
        if compact and compact not in seen:
            terms.append(compact)
        return terms

    @classmethod
    def _query_score(
        cls,
        *,
        category: str,
        payload: dict[str, Any],
        query: str,
        query_terms: list[str],
    ) -> float:
        if not query_terms:
            return 0.0
        normalized_query = cls._normalize_text(query)
        search_text = cls._payload_search_text(category=category, payload=payload)
        score = 0.0
        if normalized_query and normalized_query in search_text:
            score += 8.0
        for term in query_terms:
            if term and term in search_text:
                score += max(1.0, min(len(term), 6))
        exact_fields = (
            cls._normalize_text(payload.get("project_id")),
            cls._normalize_text(payload.get("name")),
            cls._normalize_text(payload.get("decision_id")),
            cls._normalize_text(payload.get("handoff_id")),
            cls._normalize_text(payload.get("call_id")),
        )
        for term in query_terms:
            normalized_term = cls._normalize_text(term)
            if normalized_term and normalized_term in exact_fields:
                score += 4.0
        return score

    @classmethod
    def _payload_search_text(cls, *, category: str, payload: dict[str, Any]) -> str:
        fields = cls._QUERY_FIELDS.get(category, ())
        fragments: list[str] = []
        for field_name in fields:
            value = payload.get(field_name)
            if isinstance(value, list):
                fragments.extend(str(item).strip() for item in value if str(item).strip())
            elif str(value or "").strip():
                fragments.append(str(value).strip())
        if not fragments:
            fragments.append(str(payload))
        return cls._normalize_text(" ".join(fragments))

    @classmethod
    def _normalize_text(cls, value: Any) -> str:
        raw = str(value or "").strip().lower()
        if not raw:
            return ""
        return cls._NON_WORD_RE.sub("", raw)

    def _supersede_decision(
        self,
        *,
        previous_decision_id: str,
        new_decision_id: str,
        valid_to: str,
    ) -> str:
        previous = self._memory.get_by_key(previous_decision_id)
        if previous is None or not isinstance(previous.value, dict):
            raise WorkMemoryValidationError(
                f"supersedes_decision_id not found: {previous_decision_id}",
                blocked_by="missing_supersedes_target",
            )
        updated_value = dict(previous.value)
        updated_value["valid_to"] = valid_to
        updated_value["superseded_by"] = new_decision_id
        updated_value["review_status"] = "superseded"
        self._memory.update_record_value(
            previous.record_id,
            updated_value,
            reason=f"superseded by {new_decision_id}",
        )
        return previous.record_id

    @staticmethod
    def _import_hit_metadata(*, category: str, payload: dict[str, Any]) -> dict[str, Any]:
        raw = payload.get("import_metadata")
        if not isinstance(raw, dict):
            return {}
        return {
            "category": category,
            "object_id": str(payload.get("object_id") or ""),
            "manifest_id": str(raw.get("manifest_id") or ""),
            "seed_id": str(raw.get("seed_id") or ""),
            "import_gate": str(raw.get("import_gate") or ""),
            "source_seed_doc": str(raw.get("source_seed_doc") or ""),
        }

    @staticmethod
    def _format_active_projects(payloads: list[dict[str, Any]]) -> str:
        lines = ["### Active Project Map"]
        for payload in payloads:
            lines.append(
                f"- {payload.get('name') or payload.get('project_id')}: "
                f"phase={payload.get('phase') or ''}; "
                f"status={payload.get('status') or ''}; "
                f"blockers={'; '.join(payload.get('blockers') or []) or 'none'}; "
                f"next={'; '.join(payload.get('next_steps') or []) or 'none'}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_decisions(payloads: list[dict[str, Any]]) -> str:
        lines = ["### Decision Ledger"]
        for payload in payloads:
            lines.append(
                f"- {payload.get('decision_id')}: "
                f"{payload.get('statement') or ''} "
                f"(domain={payload.get('domain') or ''}, valid_from={payload.get('valid_from') or ''})"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_triage(payloads: list[dict[str, Any]]) -> str:
        lines = ["### Recent Post-call Triage"]
        for payload in payloads:
            lines.append(
                f"- {payload.get('call_id')}: "
                f"new_facts={'; '.join(payload.get('new_facts') or []) or 'none'}; "
                f"actions={'; '.join(payload.get('intended_actions') or []) or 'none'}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_handoffs(payloads: list[dict[str, Any]]) -> str:
        lines = ["### Recent Handoff"]
        for payload in payloads:
            lines.append(
                f"- {payload.get('handoff_id')}: "
                f"current={payload.get('current_situation') or ''}; "
                f"next={payload.get('next_pickup') or ''}"
            )
        return "\n".join(lines)
