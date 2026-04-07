from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chatgptrest.advisor.runtime import AdvisorRuntime
from chatgptrest.evomap.knowledge.schema import (
    Atom,
    AtomStatus,
    Document,
    Edge,
    Entity,
    Episode,
    EpisodeType,
    Evidence,
    Stability,
)
from chatgptrest.kernel.event_bus import TraceEvent
from chatgptrest.kernel.policy_engine import QualityContext

_GRAPH_MIRROR_ALLOWED_MODES = {"governed_projection", "migration_rebuild"}


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-")
    return text or "artifact"


def _hash_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _graph_mirror_mode() -> str:
    raw = os.environ.get("OPENMIND_COGNITIVE_GRAPH_MIRROR_MODE", "governed_projection")
    return str(raw).strip().lower() or "governed_projection"


@dataclass
class KnowledgeEntitySeed:
    name: str
    entity_type: str = "tag"
    normalized_name: str = ""


@dataclass
class KnowledgeIngestItem:
    title: str
    content: str
    trace_id: str = ""
    session_id: str = ""
    source_system: str = "openclaw"
    source_ref: str = ""
    content_type: str = "markdown"
    project_id: str = ""
    para_bucket: str = "resource"
    structural_role: str = "analysis"
    domain_tags: list[str] = field(default_factory=list)
    audience: str = "internal"
    security_label: str = "internal"
    risk_level: str = "low"
    estimated_tokens: int = 0
    source_quality: float | None = None
    graph_extract: bool = True
    entities: list[KnowledgeEntitySeed] = field(default_factory=list)


@dataclass
class KnowledgeIngestItemResult:
    ok: bool
    trace_id: str
    title: str
    artifact_id: str = ""
    file_path: str = ""
    accepted: bool = True
    message: str = ""
    quality_gate: dict[str, Any] = field(default_factory=dict)
    graph_refs: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.ok

    @property
    def knowledge_plane(self) -> str:
        return str((self.graph_refs or {}).get("knowledge_plane") or "")

    @property
    def write_path(self) -> str:
        return str((self.graph_refs or {}).get("write_path") or "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "success": self.success,
            "trace_id": self.trace_id,
            "title": self.title,
            "artifact_id": self.artifact_id,
            "file_path": self.file_path,
            "accepted": self.accepted,
            "message": self.message,
            "quality_gate": self.quality_gate,
            "knowledge_plane": self.knowledge_plane,
            "write_path": self.write_path,
            "graph_refs": self.graph_refs,
        }


@dataclass
class KnowledgeIngestResult:
    ok: bool
    results: list[KnowledgeIngestItemResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "results": [item.to_dict() for item in self.results],
        }


class KnowledgeIngestService:
    def __init__(self, runtime: AdvisorRuntime):
        self._runtime = runtime

    def ingest(self, items: list[KnowledgeIngestItem]) -> KnowledgeIngestResult:
        results = [self._ingest_one(item) for item in items]
        return KnowledgeIngestResult(ok=all(r.ok for r in results), results=results)

    def _ingest_one(self, item: KnowledgeIngestItem) -> KnowledgeIngestItemResult:
        trace_id = item.trace_id or str(uuid.uuid4())
        policy = self._runtime.policy_engine
        quality_gate = {}
        if policy is not None:
            quality_gate = policy.run_quality_gate(
                QualityContext(
                    audience=item.audience,
                    security_label=item.security_label,
                    content=item.content,
                    estimated_tokens=item.estimated_tokens or max(1, len(item.content) // 4),
                    channel=item.source_system,
                    risk_level=item.risk_level,
                    execution_success=True,
                    business_success=True,
                    claims=[],
                )
            ).to_dict()
            if not quality_gate.get("allowed", False):
                return KnowledgeIngestItemResult(
                    ok=False,
                    trace_id=trace_id,
                    title=item.title,
                    accepted=False,
                    message=quality_gate.get("reason", "blocked"),
                    quality_gate=quality_gate,
                )

        writeback = self._runtime.writeback_service
        if writeback is None:
            return KnowledgeIngestItemResult(
                ok=False,
                trace_id=trace_id,
                title=item.title,
                accepted=False,
                message="writeback_service unavailable",
                quality_gate=quality_gate,
            )

        output_root = Path(
            os.environ.get(
                "OPENMIND_COGNITIVE_INGEST_DIR",
                str(Path.cwd() / "artifacts" / "cognitive_ingest"),
            )
        )
        _CT_EXT = {
            "markdown": ".md", "text/markdown": ".md",
            "text/plain": ".txt", "plain": ".txt",
            "application/json": ".json", "json": ".json",
            "text/html": ".html", "html": ".html",
            "text/csv": ".csv", "csv": ".csv",
        }
        ct = (item.content_type or "markdown").strip().lower()
        ext = _CT_EXT.get(ct, f".{ct.rsplit('/', 1)[-1]}")
        file_name = f"{trace_id}-{_slugify(item.title)[:40]}{ext}"
        writeback_result = writeback.writeback(
            content=item.content,
            trace_id=trace_id,
            content_type=item.content_type,
            title=item.title,
            output_dir=output_root / item.para_bucket,
            file_name=file_name,
            project_id=item.project_id,
            para_bucket=item.para_bucket,
            structural_role=item.structural_role,
            domain_tags=item.domain_tags,
            source_system=item.source_system,
        )
        if not writeback_result.success:
            return KnowledgeIngestItemResult(
                ok=False,
                trace_id=trace_id,
                title=item.title,
                accepted=False,
                message=writeback_result.error or "writeback failed",
                quality_gate=quality_gate,
            )

        if item.graph_extract:
            graph_refs: dict[str, Any] = {
                "knowledge_plane": "canonical_knowledge",
                "write_path": "canonical_requested",
                "status": "pending_projection",
            }
        else:
            graph_refs = {
                "knowledge_plane": "runtime_working",
                "write_path": "working_only",
                "status": "working_plane_only",
            }
        graph_error: str | None = None
        graph_mode = _graph_mirror_mode()
        if item.graph_extract and self._runtime.evomap_knowledge_db is not None:
            if graph_mode in _GRAPH_MIRROR_ALLOWED_MODES:
                try:
                    graph_refs = self._mirror_into_graph(item=item, trace_id=trace_id, file_path=writeback_result.file_path)
                    graph_refs.setdefault("graph_mode", graph_mode)
                    graph_refs.setdefault("knowledge_plane", "canonical_knowledge")
                    graph_refs.setdefault("write_path", "canonical_projected")
                    graph_refs.setdefault("status", "canonical_projected")
                except Exception as exc:
                    import logging
                    logging.getLogger(__name__).error(
                        "graph mirror failed for trace_id=%s: %s", trace_id, exc,
                    )
                    graph_error = str(exc)
                    graph_refs = {
                        "error": graph_error,
                        "status": "partial_failure",
                        "graph_mode": graph_mode,
                        "knowledge_plane": "canonical_knowledge",
                        "write_path": "canonical_partial_failure",
                    }
            else:
                graph_refs = {
                    "status": "skipped_policy",
                    "graph_mode": graph_mode,
                    "knowledge_plane": "canonical_knowledge",
                    "write_path": "canonical_policy_blocked",
                    "reason": "graph projection blocked by policy mode",
                }
        elif item.graph_extract:
            graph_refs = {
                "status": "runtime_unavailable",
                "graph_mode": graph_mode,
                "knowledge_plane": "canonical_knowledge",
                "write_path": "canonical_runtime_unavailable",
                "reason": "evomap knowledge db unavailable",
            }

        if self._runtime.event_bus is not None:
            event = TraceEvent.create(
                source=item.source_system,
                event_type="kb.writeback",
                trace_id=trace_id,
                session_id=item.session_id,
                security_label=item.security_label,
                data={
                    "artifact_id": writeback_result.artifact_id,
                    "file_path": writeback_result.file_path,
                    "title": item.title,
                    "project_id": item.project_id,
                    "graph_extract": item.graph_extract,
                    "graph_mode": graph_mode,
                    "graph_failed": graph_error is not None,
                    "graph_skipped_policy": graph_refs.get("status") == "skipped_policy",
                    "graph_error": graph_error,
                    "knowledge_plane": graph_refs.get("knowledge_plane"),
                    "write_path": graph_refs.get("write_path"),
                },
            )
            self._runtime.event_bus.emit(event)

        return KnowledgeIngestItemResult(
            ok=graph_error is None,
            trace_id=trace_id,
            title=item.title,
            artifact_id=writeback_result.artifact_id,
            file_path=writeback_result.file_path,
            accepted=True,
            message="ingested" if graph_error is None else "ingested_partial",
            quality_gate=quality_gate,
            graph_refs=graph_refs,
        )

    def _mirror_into_graph(self, *, item: KnowledgeIngestItem, trace_id: str, file_path: str) -> dict[str, Any]:
        db = self._runtime.evomap_knowledge_db
        assert db is not None

        digest = _hash_text(f"{item.title}|{item.content}")
        score_bundle = self._derive_graph_scores(item)
        document = Document(
            doc_id=f"doc_ingest_{digest}",
            source=item.source_system,
            project=item.project_id,
            raw_ref=item.source_ref or file_path,
            title=item.title,
            hash=digest,
        )
        episode = Episode(
            episode_id=f"ep_ingest_{digest}",
            doc_id=document.doc_id,
            episode_type=EpisodeType.MD_SECTION.value,
            title=item.title,
            summary=item.content[:300],
        )
        atom = Atom(
            atom_id=f"at_ingest_{digest}",
            episode_id=episode.episode_id,
            atom_type="lesson",
            question=item.title,
            answer=item.content[:4000],
            canonical_question=item.title,
            status=AtomStatus.CANDIDATE.value,
            scope_project=item.project_id,
            stability=Stability.VERSIONED.value,
            quality_auto=score_bundle["quality_auto"],
            value_auto=score_bundle["value_auto"],
            groundedness=score_bundle["groundedness"],
            source_quality=score_bundle["source_quality"],
        )
        atom.compute_hash()

        # Evidence ID includes source context so each ingest source
        # produces a unique evidence record (append-safe provenance)
        evidence_digest = _hash_text(
            f"{digest}|{item.source_ref}|{trace_id}"
        )
        evidence = Evidence(
            evidence_id=f"ev_ingest_{evidence_digest}",
            atom_id=atom.atom_id,
            doc_id=document.doc_id,
            span_ref=item.source_ref or file_path,
            excerpt=item.content[:600],
            excerpt_hash=_hash_text(item.content[:600]),
            evidence_role="source",
        )

        # Use if_absent for doc/ep/atom to preserve existing records;
        # evidence always uses INSERT OR REPLACE (unique ID per source)
        db.put_document_if_absent(document)
        db.put_episode_if_absent(episode)
        db.put_atom_if_absent(atom)
        db.put_evidence(evidence)

        entity_ids: list[str] = []
        for seed in item.entities:
            normalized = seed.normalized_name or seed.name.strip().lower()
            entity_id = f"ent_ingest_{_hash_text(f'{seed.entity_type}|{normalized}')}"
            entity = Entity(
                entity_id=entity_id,
                entity_type=seed.entity_type,
                name=seed.name,
                normalized_name=normalized,
            )
            db.put_entity(entity)
            db.put_edge(
                Edge(
                    from_id=entity.entity_id,
                    to_id=atom.atom_id,
                    edge_type="references",
                    weight=0.9,
                    from_kind="entity",
                    to_kind="atom",
                    meta_json=f'{{"trace_id":"{trace_id}"}}',
                )
            )
            entity_ids.append(entity.entity_id)

        db.commit()
        return {
            "document_id": document.doc_id,
            "episode_id": episode.episode_id,
            "atom_id": atom.atom_id,
            "evidence_id": evidence.evidence_id,
            "entity_ids": entity_ids,
            "trust_level": "staged_low_trust",
            "scores": score_bundle,
        }

    def _derive_graph_scores(self, item: KnowledgeIngestItem) -> dict[str, float]:
        """Keep ingested artifacts conservative until richer extract/refine passes run."""
        source_quality = item.source_quality
        if source_quality is None:
            source_quality = 0.45 if item.source_ref else 0.25
            if item.entities:
                source_quality = min(source_quality + 0.1, 0.6)
        source_quality = max(0.0, min(float(source_quality), 1.0))

        groundedness = 0.2
        if item.source_ref:
            groundedness += 0.2
        if item.entities:
            groundedness += 0.1
        groundedness = min(groundedness, 0.6)

        value_auto = 0.25
        if item.domain_tags:
            value_auto += 0.1
        if item.entities:
            value_auto += 0.1
        value_auto = min(value_auto, 0.5)

        quality_auto = min(source_quality, 0.6)
        return {
            "source_quality": round(source_quality, 3),
            "quality_auto": round(quality_auto, 3),
            "value_auto": round(value_auto, 3),
            "groundedness": round(groundedness, 3),
        }
