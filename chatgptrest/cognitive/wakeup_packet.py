from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Mapping

from chatgptrest.advisor.crystallized_learning import (
    build_interaction_learning_crystal,
    crystallized_learning_receipt,
)
from chatgptrest.cognitive.context_service import ContextResolveOptions, ContextResolveResult, ContextResolver


WAKE_UP_PACKET_SCHEMA_VERSION = "openmind-wakeup-packet-v1"
WAKE_UP_PACKET_SOURCE_PRECEDENCE = "authority anchor > project memory > EvoMap knowledge > runtime heuristics"
_AUTHORITY_KEYS = {
    "project_context",
    "project_ref",
    "planning_base",
    "frozen_facts",
    "style_rules",
    "authority_docs",
    "owner",
    "last_reviewed_at",
    "current_phase_framing",
}


@dataclass(frozen=True)
class WakeUpPacketLayer:
    layer_id: str
    title: str
    summary: str
    provenance: list[dict[str, Any]] = field(default_factory=list)
    signals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_id": self.layer_id,
            "title": self.title,
            "summary": self.summary,
            "provenance": list(self.provenance),
            "signals": dict(self.signals),
        }


@dataclass(frozen=True)
class WakeUpPacket:
    schema_version: str
    packet_id: str
    generated_at: str
    trace_id: str
    query: str
    project_id: str
    source_precedence: str
    degraded: bool
    degraded_sources: list[str]
    identity: dict[str, str]
    token_summary: dict[str, Any]
    provenance_summary: dict[str, Any]
    layers: list[WakeUpPacketLayer]
    crystallized_learning: dict[str, Any] | None = None
    quality_receipt: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "packet_id": self.packet_id,
            "generated_at": self.generated_at,
            "trace_id": self.trace_id,
            "query": self.query,
            "project_id": self.project_id,
            "source_precedence": self.source_precedence,
            "degraded": self.degraded,
            "degraded_sources": list(self.degraded_sources),
            "identity": dict(self.identity),
            "token_summary": dict(self.token_summary),
            "provenance_summary": dict(self.provenance_summary),
            "quality_receipt": dict(self.quality_receipt or {}),
            "layers": [layer.to_dict() for layer in self.layers],
            "crystallized_learning": dict(self.crystallized_learning or {}) if isinstance(self.crystallized_learning, Mapping) else self.crystallized_learning,
        }

    def to_markdown(
        self,
        *,
        include_authority_layer: bool = True,
        include_quality_receipt: bool = False,
    ) -> str:
        return render_wakeup_packet(
            self,
            include_authority_layer=include_authority_layer,
            include_quality_receipt=include_quality_receipt,
        )


def build_wakeup_packet(
    *,
    runtime: Any,
    query: str,
    session_id: str = "",
    account_id: str = "",
    agent_id: str = "",
    role_id: str = "",
    thread_id: str = "",
    project_id: str = "",
    trace_id: str = "",
    token_budget: int = 4500,
    planning_task_layer: Mapping[str, Any] | None = None,
    authority_inputs: Mapping[str, Any] | None = None,
    interaction_learning: Mapping[str, Any] | None = None,
) -> WakeUpPacket:
    resolver = ContextResolver(runtime)
    context_result = resolver.resolve(
        ContextResolveOptions(
            query=query,
            session_id=session_id,
            account_id=account_id,
            agent_id=agent_id,
            role_id=role_id,
            thread_id=thread_id,
            project_id=project_id,
            trace_id=trace_id,
            token_budget=token_budget,
        )
    )
    effective_project_id = (
        str(project_id or "").strip()
        or str((context_result.metadata or {}).get("project_id") or "").strip()
        or str(_extract_authority_inputs(authority_inputs).get("project_ref") or "").strip()
        or _planning_task_project_id(planning_task_layer)
    )
    layers = [
        _build_authority_layer(context_result=context_result, authority_inputs=authority_inputs),
        _build_active_memory_layer(context_result=context_result, planning_task_layer=planning_task_layer),
        _build_knowledge_layer(context_result=context_result),
        _build_runtime_handoff_layer(context_result=context_result, planning_task_layer=planning_task_layer),
    ]
    crystallized_learning = build_interaction_learning_crystal(interaction_learning)
    generated_at = datetime.now(UTC).isoformat()
    packet_key = "|".join(
        part for part in (trace_id.strip(), effective_project_id, " ".join(query.split())[:240], generated_at) if part
    )
    packet_id = hashlib.sha1(packet_key.encode("utf-8")).hexdigest()[:16]
    packet = WakeUpPacket(
        schema_version=WAKE_UP_PACKET_SCHEMA_VERSION,
        packet_id=packet_id,
        generated_at=generated_at,
        trace_id=str(trace_id or "").strip(),
        query=" ".join(str(query or "").split())[:1200],
        project_id=effective_project_id,
        source_precedence=WAKE_UP_PACKET_SOURCE_PRECEDENCE,
        degraded=bool(context_result.degraded),
        degraded_sources=list(context_result.degraded_sources or []),
        identity={
            "session_id": str(session_id or "").strip(),
            "account_id": str(account_id or "").strip(),
            "agent_id": str(agent_id or "").strip(),
            "role_id": str(role_id or "").strip(),
            "thread_id": str(thread_id or "").strip(),
        },
        token_summary={
            "context_used_tokens": int(context_result.used_tokens or 0),
            "requested_token_budget": int(token_budget or 0),
            "layer_count": len(layers),
        },
        provenance_summary={
            "authority_governance": dict((context_result.metadata or {}).get("authority_governance") or {}),
            "retrieval_plan": list((context_result.metadata or {}).get("retrieval_plan") or []),
            "promotion_audit": dict((context_result.metadata or {}).get("promotion_audit") or {}),
        },
        quality_receipt={},
        layers=layers,
        crystallized_learning=crystallized_learning,
    )
    quality_receipt = _build_quality_receipt(packet)
    quality_receipt["comparison_digest"] = _comparison_digest(packet, quality_receipt)
    return replace(packet, quality_receipt=quality_receipt)


def wakeup_packet_receipt(packet: WakeUpPacket | Mapping[str, Any]) -> dict[str, Any]:
    payload = packet.to_dict() if isinstance(packet, WakeUpPacket) else dict(packet or {})
    layers = list(payload.get("layers") or [])
    quality_receipt = dict(payload.get("quality_receipt") or {})
    crystal_receipt = crystallized_learning_receipt(payload.get("crystallized_learning"))
    return {
        "schema_version": str(payload.get("schema_version") or "").strip(),
        "packet_id": str(payload.get("packet_id") or "").strip(),
        "generated_at": str(payload.get("generated_at") or "").strip(),
        "project_id": str(payload.get("project_id") or "").strip(),
        "degraded": bool(payload.get("degraded")),
        "degraded_sources": list(payload.get("degraded_sources") or []),
        "source_precedence": str(payload.get("source_precedence") or "").strip(),
        "layer_ids": [str(dict(layer).get("layer_id") or "").strip() for layer in layers if isinstance(layer, Mapping)],
        "has_crystallized_learning": bool(crystal_receipt.get("applied")),
        "crystallized_learning": crystal_receipt,
        "quality_receipt": {
            "comparison_digest": str(quality_receipt.get("comparison_digest") or "").strip(),
            "layer_order": list(quality_receipt.get("layer_order") or []),
            "coverage_ratio": float(quality_receipt.get("coverage_ratio") or 0.0),
            "truncation_count": int(quality_receipt.get("truncation_count") or 0),
            "omission_count": int(quality_receipt.get("omission_count") or 0),
            "packet_char_count": int(quality_receipt.get("packet_char_count") or 0),
            "token_budget_ratio": float(quality_receipt.get("token_budget_ratio") or 0.0),
        },
    }


def render_wakeup_packet(
    packet: WakeUpPacket | Mapping[str, Any],
    *,
    include_authority_layer: bool = True,
    include_quality_receipt: bool = False,
) -> str:
    payload = packet.to_dict() if isinstance(packet, WakeUpPacket) else dict(packet or {})
    if not payload:
        return ""
    lines = [
        f"Wake-up packet ({str(payload.get('schema_version') or '').strip() or WAKE_UP_PACKET_SCHEMA_VERSION})",
    ]
    packet_id = str(payload.get("packet_id") or "").strip()
    if packet_id:
        lines.append(f"- Packet ID: {packet_id}")
    if str(payload.get("project_id") or "").strip():
        lines.append(f"- Project ID: {payload['project_id']}")
    if str(payload.get("query") or "").strip():
        lines.append(f"- Query focus: {_clip(str(payload['query']), max_chars=220)}")
    if payload.get("degraded"):
        degraded_sources = ", ".join(str(item).strip() for item in list(payload.get("degraded_sources") or []) if str(item).strip())
        lines.append(f"- Degraded: yes{f' ({degraded_sources})' if degraded_sources else ''}")
    lines.append(f"- Source precedence: {str(payload.get('source_precedence') or WAKE_UP_PACKET_SOURCE_PRECEDENCE).strip()}")

    for raw_layer in list(payload.get("layers") or []):
        if not isinstance(raw_layer, Mapping):
            continue
        layer_id = str(raw_layer.get("layer_id") or "").strip()
        if not layer_id:
            continue
        if layer_id == "L0" and not include_authority_layer:
            continue
        title = str(raw_layer.get("title") or "").strip() or layer_id
        summary = str(raw_layer.get("summary") or "").strip()
        lines.append("")
        lines.append(f"{layer_id} {title}")
        if summary:
            lines.append(summary)
        provenance = list(raw_layer.get("provenance") or [])
        provenance_line = _format_provenance_line(provenance)
        if provenance_line:
            lines.append(provenance_line)
    crystal = payload.get("crystallized_learning")
    if isinstance(crystal, Mapping) and dict(crystal.get("stable_preferences") or {}):
        governance = dict(crystal.get("governance") or {})
        supersession = dict(crystal.get("supersession") or {})
        lines.append("")
        lines.append("Crystallized learning (shadow observation; advisory; lower priority than the authority anchor)")
        if str(governance.get("projection_mode") or "").strip():
            lines.append(f"- Projection mode: {str(governance.get('projection_mode') or '').strip()}")
        if int(crystal.get("support_threshold") or 0) > 0:
            lines.append(f"- Support threshold: {int(crystal.get('support_threshold') or 0)}")
        for key, value in sorted(dict(crystal.get("stable_preferences") or {}).items()):
            lines.append(f"- {key}: {value}")
        if int(supersession.get("superseded_count") or 0) > 0:
            lines.append(f"- Superseded candidates: {int(supersession.get('superseded_count') or 0)}")
        invalidation = dict(crystal.get("invalidation") or {})
        if str(invalidation.get("rule") or "").strip():
            lines.append(f"- Invalidation: {str(invalidation.get('rule') or '').strip()}")
    if include_quality_receipt:
        quality = dict(payload.get("quality_receipt") or {})
        if quality:
            lines.append("")
            lines.append("Packet quality receipt")
            layer_order = ", ".join(str(item).strip() for item in list(quality.get("layer_order") or []) if str(item).strip())
            if layer_order:
                lines.append(f"- Layer order: {layer_order}")
            lines.append(f"- Coverage ratio: {float(quality.get('coverage_ratio') or 0.0):.3f}")
            lines.append(f"- Truncations: {int(quality.get('truncation_count') or 0)}")
            lines.append(f"- Omissions: {int(quality.get('omission_count') or 0)}")
            if int(quality.get("packet_char_count") or 0) > 0:
                lines.append(f"- Packet chars: {int(quality.get('packet_char_count') or 0)}")
            if str(quality.get("comparison_digest") or "").strip():
                lines.append(f"- Comparison digest: {str(quality.get('comparison_digest') or '').strip()}")
    return "\n".join(line for line in lines if line is not None).strip()


def _build_authority_layer(
    *,
    context_result: ContextResolveResult,
    authority_inputs: Mapping[str, Any] | None,
) -> WakeUpPacketLayer:
    authority_block = _block_by_source_type(context_result, "authority")
    governance = dict((context_result.metadata or {}).get("authority_governance") or {})
    authority_data = _extract_authority_inputs(authority_inputs)
    summary_lines: list[str] = []
    quality = _empty_layer_quality()
    if authority_block is not None and authority_block.text.strip():
        excerpt, receipt = _clip_with_receipt(authority_block.text, max_chars=950, label="authority_summary")
        summary_lines.append(excerpt)
        _record_truncation(quality, receipt)
    elif authority_data:
        summary_lines.extend(_authority_input_lines(authority_data, quality=quality))
    else:
        summary_lines.append("No project authority anchor resolved.")
    if str(governance.get("stale_status") or "").strip() and str(governance.get("stale_status") or "").strip() != "absent":
        summary_lines.append(f"Anchor freshness: {governance['stale_status']}")
    if int(governance.get("conflict_count") or 0) > 0:
        summary_lines.append(f"Lower-priority context conflicts detected: {int(governance.get('conflict_count') or 0)}")

    provenance: list[dict[str, Any]] = []
    anchor_path = str(governance.get("anchor_path") or authority_data.get("anchor_path") or "").strip()
    if anchor_path:
        provenance.append({"type": "authority_anchor", "path": anchor_path})
    for item in list(getattr(authority_block, "provenance", []) or []):
        if isinstance(item, Mapping):
            provenance.append(dict(item))
    authority_docs = authority_data.get("authority_docs")
    if isinstance(authority_docs, list):
        limited_docs, docs_omission = _limit_sequence(authority_docs, max_items=5, label="authority_docs")
        _record_omission(quality, docs_omission)
        for raw_doc in limited_docs:
            text = str(raw_doc or "").strip()
            if text:
                provenance.append({"type": "authority_doc", "path": text})
    provenance, provenance_omission = _limit_sequence(provenance, max_items=8, label="authority_provenance")
    _record_omission(quality, provenance_omission)

    return WakeUpPacketLayer(
        layer_id="L0",
        title="Authority anchor",
        summary="\n".join(summary_lines).strip(),
        provenance=provenance,
        signals={
            "stale_status": str(governance.get("stale_status") or "absent").strip() or "absent",
            "missing_docs": list(governance.get("missing_docs") or []),
            "schema_gaps": list(governance.get("schema_gaps") or []),
            "conflict_count": int(governance.get("conflict_count") or 0),
            "quality": _finalize_layer_quality(quality, summary="\n".join(summary_lines).strip(), provenance=provenance),
        },
    )


def _build_active_memory_layer(
    *,
    context_result: ContextResolveResult,
    planning_task_layer: Mapping[str, Any] | None,
) -> WakeUpPacketLayer:
    active_block = _block_by_source_type(context_result, "work_memory_active")
    summary_lines: list[str] = []
    quality = _empty_layer_quality()
    if active_block is not None and active_block.text.strip():
        excerpt, receipt = _clip_with_receipt(active_block.text, max_chars=1150, label="active_memory_summary")
        summary_lines.append(excerpt)
        _record_truncation(quality, receipt)
    planning_handoff = _planning_handoff_lines(planning_task_layer)
    if planning_handoff:
        if summary_lines:
            summary_lines.append("")
        summary_lines.extend(planning_handoff)
    if not summary_lines:
        summary_lines.append("No active project memory or open-loop handoff resolved.")
    metadata = dict(context_result.metadata or {})
    provenance: list[dict[str, Any]] = []
    if isinstance(active_block, object):
        for item in list(getattr(active_block, "provenance", []) or []):
            if isinstance(item, Mapping):
                provenance.append(dict(item))
    for item in list(metadata.get("work_memory_import_hits") or [])[:5]:
        if isinstance(item, Mapping):
            provenance.append(dict(item))
    planning_task_id = _planning_task_value(planning_task_layer, "task_id")
    if planning_task_id:
        provenance.append(
            {
                "type": "planning_task",
                "task_id": planning_task_id,
                "task_type": _planning_task_value(planning_task_layer, "task_type"),
            }
        )
    provenance, provenance_omission = _limit_sequence(provenance, max_items=8, label="active_memory_provenance")
    _record_omission(quality, provenance_omission)
    return WakeUpPacketLayer(
        layer_id="L1",
        title="Active project memory / open loops",
        summary="\n".join(summary_lines).strip(),
        provenance=provenance,
        signals={
            "category_counts": dict(metadata.get("work_memory_scope_hits") or {}),
            "identity_gaps": list(metadata.get("work_memory_identity_gaps") or []),
            "scope_hits": dict(metadata.get("work_memory_scope_hits") or {}),
            "quality": _finalize_layer_quality(quality, summary="\n".join(summary_lines).strip(), provenance=provenance),
        },
    )


def _build_knowledge_layer(*, context_result: ContextResolveResult) -> WakeUpPacketLayer:
    raw_knowledge_blocks = [
        block
        for block in list(context_result.context_blocks or [])
        if str(block.source_type or "").strip() in {"planning_pack", "kb", "evomap", "obsidian", "calendar"}
    ]
    quality = _empty_layer_quality()
    knowledge_blocks, block_omission = _limit_sequence(raw_knowledge_blocks, max_items=4, label="knowledge_blocks")
    _record_omission(quality, block_omission)
    summary_lines: list[str] = []
    provenance: list[dict[str, Any]] = []
    for block in knowledge_blocks:
        title = str(block.title or block.source_type).strip()
        excerpt, receipt = _clip_with_receipt(block.text, max_chars=480, label=f"knowledge:{title or block.source_type}")
        _record_truncation(quality, receipt)
        summary_lines.append(f"{title}: {excerpt}")
        block_provenance, block_provenance_omission = _limit_sequence(list(block.provenance or []), max_items=4, label=f"knowledge_provenance:{title or block.source_type}")
        _record_omission(quality, block_provenance_omission)
        for item in block_provenance:
            if isinstance(item, Mapping):
                provenance.append(dict(item))
    if not summary_lines:
        summary_lines.append("No retrieved project knowledge or entity context resolved.")
    metadata = dict(context_result.metadata or {})
    provenance, provenance_omission = _limit_sequence(provenance, max_items=10, label="knowledge_provenance_total")
    _record_omission(quality, provenance_omission)
    return WakeUpPacketLayer(
        layer_id="L2",
        title="Retrieved project knowledge / entity context",
        summary="\n".join(summary_lines).strip(),
        provenance=provenance,
        signals={
            "retrieval_plan": list(metadata.get("retrieval_plan") or []),
            "promotion_audit": dict(metadata.get("promotion_audit") or {}),
            "quality": _finalize_layer_quality(quality, summary="\n".join(summary_lines).strip(), provenance=provenance),
        },
    )


def _build_runtime_handoff_layer(
    *,
    context_result: ContextResolveResult,
    planning_task_layer: Mapping[str, Any] | None,
) -> WakeUpPacketLayer:
    policy_block = _block_by_source_type(context_result, "policy")
    summary_lines: list[str] = []
    quality = _empty_layer_quality()
    planning_handoff = _planning_runtime_handoff_lines(planning_task_layer)
    if planning_handoff:
        summary_lines.extend(planning_handoff)
    if policy_block is not None and policy_block.text.strip():
        if summary_lines:
            summary_lines.append("")
        summary_lines.append("Runtime policy hints:")
        excerpt, receipt = _clip_with_receipt(policy_block.text, max_chars=520, label="runtime_policy")
        summary_lines.append(excerpt)
        _record_truncation(quality, receipt)
    if not summary_lines:
        summary_lines.append("No explicit runtime handoff resolved; continue from the current objective and packet layers.")

    provenance: list[dict[str, Any]] = []
    planning_task_id = _planning_task_value(planning_task_layer, "task_id")
    if planning_task_id:
        provenance.append(
            {
                "type": "planning_task_handoff",
                "task_id": planning_task_id,
                "task_type": _planning_task_value(planning_task_layer, "task_type"),
            }
        )
    return WakeUpPacketLayer(
        layer_id="L3",
        title="Runtime handoff / recommended next step",
        summary="\n".join(summary_lines).strip(),
        provenance=provenance,
        signals={
            "planning_priority_mode": str((context_result.metadata or {}).get("planning_priority_mode") or "").strip(),
            "degraded_sources": list(context_result.degraded_sources or []),
            "quality": _finalize_layer_quality(quality, summary="\n".join(summary_lines).strip(), provenance=provenance),
        },
    )


def _extract_authority_inputs(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        key: value.get(key)
        for key in _AUTHORITY_KEYS
        if value.get(key) not in (None, "", [], {}, ())
    }


def _authority_input_lines(value: Mapping[str, Any], *, quality: dict[str, Any] | None = None) -> list[str]:
    lines: list[str] = []
    project_ref = str(value.get("project_ref") or "").strip()
    planning_base = str(value.get("planning_base") or "").strip()
    project_context = str(value.get("project_context") or "").strip()
    owner = str(value.get("owner") or "").strip()
    last_reviewed_at = str(value.get("last_reviewed_at") or "").strip()
    current_phase_framing = str(value.get("current_phase_framing") or "").strip()
    frozen_facts = [str(item).strip() for item in list(value.get("frozen_facts") or []) if str(item).strip()]
    style_rules = [str(item).strip() for item in list(value.get("style_rules") or []) if str(item).strip()]
    authority_docs = [str(item).strip() for item in list(value.get("authority_docs") or []) if str(item).strip()]
    if project_ref:
        lines.append(f"Project ref: {project_ref}")
    if planning_base:
        lines.append(f"Planning base: {planning_base}")
    if owner:
        lines.append(f"Owner: {owner}")
    if last_reviewed_at:
        lines.append(f"Last reviewed: {last_reviewed_at}")
    if current_phase_framing:
        excerpt, receipt = _clip_with_receipt(current_phase_framing, max_chars=200, label="current_phase_framing")
        if quality is not None:
            _record_truncation(quality, receipt)
        lines.append(f"Current phase framing: {excerpt}")
    if frozen_facts:
        limited_facts, omission = _limit_sequence(frozen_facts, max_items=5, label="frozen_facts")
        if quality is not None:
            _record_omission(quality, omission)
        lines.append("Frozen facts: " + "; ".join(limited_facts))
    if style_rules:
        limited_rules, omission = _limit_sequence(style_rules, max_items=5, label="style_rules")
        if quality is not None:
            _record_omission(quality, omission)
        lines.append("Style rules: " + "; ".join(limited_rules))
    if authority_docs:
        limited_docs, omission = _limit_sequence(authority_docs, max_items=5, label="authority_docs_lines")
        if quality is not None:
            _record_omission(quality, omission)
        lines.append("Authority docs: " + ", ".join(limited_docs))
    if project_context:
        excerpt, receipt = _clip_with_receipt(project_context, max_chars=480, label="project_context")
        if quality is not None:
            _record_truncation(quality, receipt)
        lines.append(excerpt)
    return lines or ["Authority inputs were provided through ingress metadata."]


def _planning_task_project_id(task_layer: Mapping[str, Any] | None) -> str:
    if not isinstance(task_layer, Mapping):
        return ""
    for key in ("project_id", "project_ref", "project_or_topic_ref", "topic_ref"):
        value = str(task_layer.get(key) or "").strip()
        if value:
            return value
    for nested_key in ("checkpoint", "handoff"):
        nested = task_layer.get(nested_key)
        if not isinstance(nested, Mapping):
            continue
        for key in ("project_id", "project_ref", "project_or_topic_ref", "topic_ref"):
            value = str(nested.get(key) or "").strip()
            if value:
                return value
    return ""


def _planning_task_value(task_layer: Mapping[str, Any] | None, key: str) -> str:
    if not isinstance(task_layer, Mapping):
        return ""
    direct = str(task_layer.get(key) or "").strip()
    if direct:
        return direct
    for nested_key in ("checkpoint", "handoff"):
        nested = task_layer.get(nested_key)
        if isinstance(nested, Mapping):
            nested_value = str(nested.get(key) or "").strip()
            if nested_value:
                return nested_value
    return ""


def _planning_task_list(task_layer: Mapping[str, Any] | None, key: str) -> list[str]:
    if not isinstance(task_layer, Mapping):
        return []
    items: list[str] = []
    for mapping in (task_layer, task_layer.get("handoff"), task_layer.get("checkpoint")):
        if not isinstance(mapping, Mapping):
            continue
        for raw in list(mapping.get(key) or []):
            text = str(raw or "").strip()
            if text and text not in items:
                items.append(text)
    return items


def _planning_handoff_lines(task_layer: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(task_layer, Mapping):
        return []
    lines: list[str] = []
    task_type = _planning_task_value(task_layer, "task_type")
    objective = _planning_task_value(task_layer, "objective")
    if task_type:
        lines.append(f"Planning task type: {task_type}")
    if objective:
        lines.append(f"Planning objective: {_clip(objective, max_chars=220)}")
    open_questions = _planning_task_list(task_layer, "open_questions")
    if open_questions:
        lines.append("Open questions: " + "; ".join(open_questions[:4]))
    return lines


def _planning_runtime_handoff_lines(task_layer: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(task_layer, Mapping):
        return []
    lines: list[str] = []
    task_id = _planning_task_value(task_layer, "task_id")
    current_status = _planning_task_value(task_layer, "current_status")
    next_step = _planning_task_value(task_layer, "next_recommended_step") or _planning_task_value(task_layer, "next_step")
    pending_actions = _planning_task_list(task_layer, "pending_actions") or _planning_task_list(task_layer, "next_actions")
    if task_id:
        lines.append(f"Planning task ID: {task_id}")
    if current_status:
        lines.append(f"Current status: {current_status}")
    if next_step:
        lines.append(f"Recommended next step: {_clip(next_step, max_chars=220)}")
    if pending_actions:
        lines.append("Pending actions: " + "; ".join(pending_actions[:5]))
    return lines


def _block_by_source_type(context_result: ContextResolveResult, source_type: str):
    return next(
        (
            block
            for block in list(context_result.context_blocks or [])
            if str(block.source_type or "").strip() == source_type
        ),
        None,
    )


def _format_provenance_line(items: list[dict[str, Any]]) -> str:
    labels: list[str] = []
    for raw in items[:4]:
        if not isinstance(raw, Mapping):
            continue
        item_type = str(raw.get("type") or "").strip() or "source"
        if raw.get("path"):
            labels.append(f"{item_type}:{str(raw.get('path')).strip()}")
            continue
        if raw.get("id"):
            labels.append(f"{item_type}:{str(raw.get('id')).strip()}")
            continue
        if raw.get("artifact_id"):
            labels.append(f"{item_type}:{str(raw.get('artifact_id')).strip()}")
            continue
        if raw.get("task_id"):
            labels.append(f"{item_type}:{str(raw.get('task_id')).strip()}")
            continue
        if raw.get("title"):
            labels.append(f"{item_type}:{_clip(str(raw.get('title')), max_chars=80)}")
            continue
        labels.append(item_type)
    if not labels:
        return ""
    return "Provenance: " + ", ".join(labels)


def _clip(value: str, *, max_chars: int) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return f"{text[: max(0, max_chars - 1)].rstrip()}…"


def _clip_with_receipt(value: str, *, max_chars: int, label: str) -> tuple[str, dict[str, Any]]:
    text = " ".join(str(value or "").split())
    clipped = _clip(text, max_chars=max_chars)
    return clipped, {
        "label": str(label or "").strip() or "segment",
        "input_chars": len(text),
        "output_chars": len(clipped),
        "truncated": bool(text and len(text) > max_chars),
    }


def _limit_sequence(items: list[Any], *, max_items: int, label: str) -> tuple[list[Any], dict[str, Any] | None]:
    limited = list(items[:max_items])
    omitted = max(0, len(items) - len(limited))
    if omitted <= 0:
        return limited, None
    return limited, {
        "label": str(label or "").strip() or "items",
        "input_count": len(items),
        "kept_count": len(limited),
        "omitted_count": omitted,
    }


def _empty_layer_quality() -> dict[str, Any]:
    return {
        "truncations": [],
        "omissions": [],
    }


def _record_truncation(bucket: dict[str, Any], receipt: Mapping[str, Any] | None) -> None:
    if not isinstance(receipt, Mapping):
        return
    if bool(receipt.get("truncated")):
        bucket.setdefault("truncations", []).append(dict(receipt))


def _record_omission(bucket: dict[str, Any], receipt: Mapping[str, Any] | None) -> None:
    if not isinstance(receipt, Mapping):
        return
    if int(receipt.get("omitted_count") or 0) > 0:
        bucket.setdefault("omissions", []).append(dict(receipt))


def _finalize_layer_quality(
    bucket: dict[str, Any],
    *,
    summary: str,
    provenance: list[dict[str, Any]],
) -> dict[str, Any]:
    truncations = [dict(item) for item in list(bucket.get("truncations") or []) if isinstance(item, Mapping)]
    omissions = [dict(item) for item in list(bucket.get("omissions") or []) if isinstance(item, Mapping)]
    return {
        "summary_chars": len(str(summary or "")),
        "summary_present": bool(str(summary or "").strip()),
        "provenance_count": len(list(provenance or [])),
        "truncation_count": len(truncations),
        "omission_count": sum(int(item.get("omitted_count") or 0) for item in omissions),
        "truncations": truncations,
        "omissions": omissions,
    }


def _build_quality_receipt(packet: WakeUpPacket) -> dict[str, Any]:
    layers = list(packet.layers or [])
    layer_order = [str(layer.layer_id or "").strip() for layer in layers if str(layer.layer_id or "").strip()]
    expected_layers = ["L0", "L1", "L2", "L3"]
    truncations: list[dict[str, Any]] = []
    omissions: list[dict[str, Any]] = []
    provenance_items = 0
    layers_without_provenance: list[str] = []
    populated_layers = 0
    for layer in layers:
        summary = str(layer.summary or "").strip()
        if summary:
            populated_layers += 1
        provenance_count = len(list(layer.provenance or []))
        provenance_items += provenance_count
        if provenance_count <= 0:
            layers_without_provenance.append(str(layer.layer_id or "").strip())
        quality = dict(layer.signals.get("quality") or {}) if isinstance(layer.signals, Mapping) else {}
        truncations.extend(dict(item) for item in list(quality.get("truncations") or []) if isinstance(item, Mapping))
        omissions.extend(dict(item) for item in list(quality.get("omissions") or []) if isinstance(item, Mapping))
    requested = int(packet.token_summary.get("requested_token_budget") or 0)
    used = int(packet.token_summary.get("context_used_tokens") or 0)
    packet_char_count = len(str(packet.query or "")) + sum(len(str(layer.summary or "")) for layer in layers)
    return {
        "schema_version": WAKE_UP_PACKET_SCHEMA_VERSION,
        "layer_order": layer_order,
        "expected_layers": expected_layers,
        "missing_layers": [layer_id for layer_id in expected_layers if layer_id not in layer_order],
        "populated_layer_count": populated_layers,
        "coverage_ratio": round(populated_layers / len(expected_layers), 6) if expected_layers else 0.0,
        "truncation_count": len(truncations),
        "truncations": truncations[:16],
        "omission_count": sum(int(item.get("omitted_count") or 0) for item in omissions),
        "omissions": omissions[:16],
        "provenance_item_count": provenance_items,
        "layers_without_provenance": [item for item in layers_without_provenance if item],
        "packet_char_count": packet_char_count,
        "token_budget_ratio": round(used / requested, 6) if requested > 0 else 0.0,
        "schema_locked": True,
    }


def _comparison_digest(packet: WakeUpPacket, quality_receipt: Mapping[str, Any]) -> str:
    payload = packet.to_dict()
    payload["packet_id"] = ""
    payload["generated_at"] = ""
    payload["trace_id"] = ""
    payload["identity"] = {}
    normalized_quality = dict(quality_receipt or {})
    normalized_quality.pop("comparison_digest", None)
    payload["quality_receipt"] = normalized_quality
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
