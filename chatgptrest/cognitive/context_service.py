from __future__ import annotations

import copy
import os
import uuid
from dataclasses import dataclass, field
from typing import Any

from chatgptrest.advisor.runtime import AdvisorRuntime
from chatgptrest.evomap.knowledge.retrieval import (
    RetrievalSurface,
    runtime_retrieval_config,
    summarize_promotion_statuses,
)
from chatgptrest.kernel.context_assembler import ContextAssembler, ContextPack, ContextSource


_SOURCE_KIND_MAP = {
    "working": "memory",
    "episodic": "memory",
    "captured": "memory",
    "semantic": "memory",
    "calendar": "knowledge",
    "obsidian": "knowledge",
    "kb": "knowledge",
    "evomap": "graph",
}

_SOURCE_TITLE_MAP = {
    "working": "Working Memory",
    "episodic": "Episodic Memory",
    "captured": "Remembered Guidance",
    "semantic": "Semantic Memory",
    "calendar": "Calendar Context",
    "obsidian": "Obsidian Notes",
    "kb": "Knowledge Evidence",
    "evomap": "Graph Knowledge",
}

_SOURCE_PLANE_MAP = {
    "memory": "runtime_working",
    "knowledge": "kb_working_set",
    "graph": "canonical_knowledge",
    "policy": "runtime_policy",
}


@dataclass
class ContextResolveOptions:
    query: str
    session_id: str = ""
    account_id: str = ""
    agent_id: str = ""
    role_id: str = ""
    thread_id: str = ""
    trace_id: str = ""
    token_budget: int = 8000
    sources: tuple[str, ...] = ("memory", "knowledge", "graph", "policy")
    graph_scopes: tuple[str, ...] = ("personal",)
    repo: str = ""
    working_limit: int = 10
    episodic_limit: int = 5
    semantic_limit: int = 3
    kb_top_k: int = 5


@dataclass
class ContextBlock:
    kind: str
    title: str
    text: str
    source_type: str
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "text": self.text,
            "source_type": self.source_type,
            "token_count": self.token_count,
            "metadata": self.metadata,
            "provenance": self.provenance,
        }


@dataclass
class ContextResolveResult:
    ok: bool
    trace_id: str
    prompt_prefix: str
    context_blocks: list[ContextBlock]
    used_tokens: int
    requested_sources: list[str]
    resolved_sources: list[str]
    cache_ttl_seconds: int
    degraded: bool
    degraded_sources: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "trace_id": self.trace_id,
            "prompt_prefix": self.prompt_prefix,
            "context_blocks": [block.to_dict() for block in self.context_blocks],
            "used_tokens": self.used_tokens,
            "requested_sources": self.requested_sources,
            "resolved_sources": self.resolved_sources,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "degraded": self.degraded,
            "degraded_sources": self.degraded_sources,
            "metadata": self.metadata,
        }


class ContextResolver:
    """Resolve OpenMind hot-path context for an execution shell."""

    def __init__(self, runtime: AdvisorRuntime):
        self._runtime = runtime

    def resolve(self, options: ContextResolveOptions) -> ContextResolveResult:
        requested_sources = list(dict.fromkeys(options.sources or ("memory", "knowledge", "graph", "policy")))
        requested_graph_scopes = list(dict.fromkeys(options.graph_scopes or ("personal",)))
        token_budget = max(1500, min(int(options.token_budget or 8000), 32000))
        trace_id = options.trace_id or str(uuid.uuid4())

        include_knowledge = any(name in requested_sources for name in ("knowledge", "graph"))
        include_personal_graph = "graph" in requested_sources and "personal" in requested_graph_scopes
        resolved_role_id, role_spec = self._resolve_role(options)
        kb_scope_tags = list(getattr(role_spec, "kb_scope_tags", []) or [])
        kb_scope_mode = _resolve_kb_scope_mode(kb_scope_tags)

        assembler = _LocalOnlyContextAssembler(
            memory_manager=self._runtime.memory,
            kb_hub=(
                _NoEmbedKBHub(
                    self._runtime.kb_hub,
                    scope_tags=kb_scope_tags,
                    scope_mode=kb_scope_mode,
                )
                if include_knowledge and self._runtime.kb_hub
                else None
            ),
            evomap_db=self._runtime.evomap_knowledge_db if include_personal_graph else None,
            max_tokens=token_budget,
        )
        pack = assembler.build(
            query=options.query,
            session_id=options.session_id,
            account_id=options.account_id,
            agent_id=options.agent_id,
            role_id=resolved_role_id,
            thread_id=options.thread_id,
            working_limit=options.working_limit,
            episodic_limit=options.episodic_limit,
            semantic_limit=options.semantic_limit,
            kb_top_k=options.kb_top_k,
        )

        filtered_sources = []
        blocks: list[ContextBlock] = []
        resolved_kinds: list[str] = []
        for source in pack.sources:
            kind = _SOURCE_KIND_MAP.get(source.source_type, source.source_type)
            if kind not in requested_sources:
                continue
            filtered_sources.append(source)
            if kind not in resolved_kinds:
                resolved_kinds.append(kind)
            provenance = self._build_provenance(pack, source.source_type)
            if source.source_type == "captured":
                provenance = [
                    {"type": "memory_record", "id": rec.record_id, "key": rec.key}
                    for rec in getattr(pack, "captured_memory", [])[:5]
                ]
            blocks.append(
                ContextBlock(
                    kind=kind,
                    title=_SOURCE_TITLE_MAP.get(source.source_type, source.source_type.replace("_", " ").title()),
                    text=source.content,
                    source_type=source.source_type,
                    token_count=source.token_count,
                    metadata=dict(source.metadata),
                    provenance=provenance,
                )
            )

        degraded_sources: list[str] = []
        captured_scope = str(getattr(pack, "captured_memory_scope", "unavailable") or "unavailable")
        if "graph" in requested_sources and "repo" in requested_graph_scopes:
            degraded_sources.append("repo_graph")
        if "graph" in requested_sources and include_personal_graph and not pack.evomap_hits:
            degraded_sources.append("personal_graph_empty")
        if "memory" in requested_sources and not options.session_id.strip() and not options.account_id.strip() and not options.thread_id.strip():
            degraded_sources.append("memory_identity_missing")
        if "memory" in requested_sources and captured_scope == "blocked_missing_identity":
            degraded_sources.append("captured_memory_identity_missing")

        policy_block = None
        if "policy" in requested_sources:
            policy_lines = self._build_policy_hints(
                options=options,
                pack=pack,
                resolved_kinds=resolved_kinds,
                degraded_sources=degraded_sources,
            )
            if policy_lines:
                policy_text = "\n".join(f"- {line}" for line in policy_lines)
                policy_block = ContextBlock(
                    kind="policy",
                    title="Execution Hints",
                    text=policy_text,
                    source_type="policy",
                    token_count=max(1, len(policy_text) // 4),
                    metadata={"hint_count": len(policy_lines)},
                    provenance=[],
                )
                blocks.append(policy_block)
                resolved_kinds.append("policy")

        prompt_pack = copy.copy(pack)
        prompt_pack.sources = filtered_sources
        prompt_prefix = assembler.to_system_prompt(prompt_pack)
        captured_block = next((block for block in blocks if block.source_type == "captured"), None)
        if captured_block is not None:
            suffix = f"## Remembered Guidance\n{captured_block.text}"
            prompt_prefix = f"{prompt_prefix}\n\n{suffix}" if prompt_prefix else suffix
        if policy_block is not None:
            suffix = f"## Policy Hints\n{policy_block.text}"
            prompt_prefix = f"{prompt_prefix}\n\n{suffix}" if prompt_prefix else suffix

        used_tokens = sum(block.token_count for block in blocks)
        identity_gaps = self._request_identity_gaps(options)
        retrieval_plan = self._build_retrieval_plan(
            requested_sources=requested_sources,
            resolved_kinds=resolved_kinds,
            degraded_sources=degraded_sources,
            blocks=blocks,
        )
        source_planes = {
            kind: _SOURCE_PLANE_MAP.get(kind, "runtime_unknown")
            for kind in requested_sources
        }
        return ContextResolveResult(
            ok=True,
            trace_id=trace_id,
            prompt_prefix=prompt_prefix,
            context_blocks=blocks,
            used_tokens=used_tokens,
            requested_sources=requested_sources,
            resolved_sources=resolved_kinds,
            cache_ttl_seconds=120,
            degraded=bool(degraded_sources),
            degraded_sources=degraded_sources,
            metadata={
                "session_id": options.session_id,
                "account_id": options.account_id,
                "agent_id": options.agent_id,
                "role_id": resolved_role_id,
                "role_known": role_spec is not None,
                "thread_id": options.thread_id,
                "graph_scopes": requested_graph_scopes,
                "repo": options.repo,
                "promotion_status_counts": summarize_promotion_statuses(getattr(pack, "evomap_hits", []) or []),
                "kb_scope_mode": kb_scope_mode,
                "kb_scope_tags": kb_scope_tags,
                "captured_memory_scope": captured_scope,
                "identity_gaps": identity_gaps,
                "identity_scope": "complete" if not identity_gaps else "partial",
                "source_planes": source_planes,
                "retrieval_plan": retrieval_plan,
            },
        )

    @staticmethod
    def _resolve_role(options: ContextResolveOptions) -> tuple[str, Any | None]:
        resolved_role_id = options.role_id.strip()
        role_spec = None
        if not resolved_role_id:
            try:
                from chatgptrest.kernel.role_context import get_current_role_name

                resolved_role_id = get_current_role_name()
            except ImportError:
                resolved_role_id = ""
        if resolved_role_id:
            try:
                from chatgptrest.kernel.role_loader import get_role

                role_spec = get_role(resolved_role_id)
            except Exception:
                role_spec = None
        return resolved_role_id, role_spec

    @staticmethod
    def _request_identity_gaps(options: ContextResolveOptions) -> list[str]:
        gaps: list[str] = []
        if not options.session_id.strip():
            gaps.append("missing_session_key")
        if not options.agent_id.strip():
            gaps.append("missing_agent_id")
        if not options.account_id.strip():
            gaps.append("missing_account_id")
        if not options.thread_id.strip():
            gaps.append("missing_thread_id")
        return gaps

    def _build_policy_hints(
        self,
        *,
        options: ContextResolveOptions,
        pack: Any,
        resolved_kinds: list[str],
        degraded_sources: list[str],
    ) -> list[str]:
        hints: list[str] = []

        if pack.working_memory:
            hints.append("Preserve conversation continuity using recent working memory before introducing new framing.")
        if pack.semantic_memory:
            hints.append("Honor known user or project preferences captured in semantic memory.")
        if pack.evomap_hits:
            hints.append("Prefer graph-backed atoms when summarizing decisions, procedures, or lessons.")
        if not pack.kb_hits and not pack.evomap_hits:
            hints.append("Knowledge coverage is low; escalate to /v2/advisor/ask for deep research if confidence is critical.")
        if options.repo and "repo" in options.graph_scopes:
            hints.append("Repository-specific graph retrieval was requested; call /v2/graph/query for repo_graph before heavy synthesis.")
        if "repo_graph" in degraded_sources:
            hints.append("Repo graph is not yet injected into hot-path context; treat any repository recall as partial.")
        if "graph" in resolved_kinds and "memory" not in resolved_kinds:
            hints.append("Graph-only context was requested; avoid inventing user preferences that are not grounded in retrieved evidence.")
        return hints

    def _build_provenance(self, pack: Any, source_type: str) -> list[dict[str, Any]]:
        if source_type == "working":
            return [
                {"type": "memory_record", "id": rec.record_id, "key": rec.key}
                for rec in pack.working_memory[:5]
            ]
        if source_type == "episodic":
            return [
                {"type": "memory_record", "id": rec.record_id, "key": rec.key}
                for rec in pack.episodic_memory[:5]
            ]
        if source_type == "semantic":
            return [
                {"type": "memory_record", "id": rec.record_id, "key": rec.key}
                for rec in pack.semantic_memory[:5]
            ]
        if source_type == "kb":
            return [
                {
                    "type": "kb_hit",
                    "artifact_id": hit.artifact_id,
                    "title": hit.title,
                    "score": round(hit.score, 4),
                }
                for hit in pack.kb_hits[:5]
            ]
        if source_type == "evomap":
            return [
                {
                    "type": "atom",
                    "id": scored.atom.atom_id,
                    "question": scored.atom.question,
                    "score": round(scored.final_score, 4),
                }
                for scored in pack.evomap_hits[:5]
            ]
        if source_type == "obsidian":
            return [
                {"type": "obsidian_note", "path": hit.get("path", ""), "score": hit.get("score")}
                for hit in pack.obsidian_hits[:5]
            ]
        if source_type == "calendar":
            return [
                {"type": "calendar_event", "id": hit.get("id", ""), "title": hit.get("summary", "")}
                for hit in pack.calendar_hits[:5]
            ]
        return []

    @staticmethod
    def _build_retrieval_plan(
        *,
        requested_sources: list[str],
        resolved_kinds: list[str],
        degraded_sources: list[str],
        blocks: list[ContextBlock],
    ) -> list[dict[str, Any]]:
        block_counts: dict[str, int] = {}
        for block in blocks:
            block_counts[block.kind] = block_counts.get(block.kind, 0) + 1

        plan: list[dict[str, Any]] = []
        for kind in requested_sources:
            plane = _SOURCE_PLANE_MAP.get(kind, "runtime_unknown")
            resolved = kind in resolved_kinds
            reason = "requested_for_resolution"
            if kind == "memory":
                reason = "identity-scoped working or episodic memory was requested"
                if resolved:
                    reason = "memory records matched the current identity scope"
            elif kind == "knowledge":
                reason = "KB working set was requested for evidence lookup"
                if resolved:
                    reason = "kb_hub returned indexed evidence hits"
            elif kind == "graph":
                reason = "canonical graph recall was requested"
                if resolved:
                    reason = "EvoMap knowledge retrieval returned promoted graph atoms"
                elif "repo_graph" in degraded_sources:
                    reason = "repo graph was requested but only the personal graph hot path is injected"
            elif kind == "policy":
                reason = "runtime policy hints were requested"
                if resolved:
                    reason = "policy hints were derived from resolved context and route heuristics"

            plan.append(
                {
                    "kind": kind,
                    "plane": plane,
                    "resolved": resolved,
                    "block_count": block_counts.get(kind, 0),
                    "reason": reason,
                }
            )
        return plan


class _NoEmbedKBHub:
    """Force ContextAssembler to stay on the cheap FTS path for hot-path recall."""

    def __init__(self, hub: Any, *, scope_tags: list[str] | None = None, scope_mode: str = "off"):
        self._hub = hub
        self._scope_tags = [tag.strip() for tag in (scope_tags or []) if str(tag).strip()]
        self._scope_mode = scope_mode if scope_mode in {"off", "hint", "enforce"} else "off"

    def search(self, query: str, top_k: int = 5):
        base_hits = list(self._hub.search(query, top_k=top_k, auto_embed=False))
        if self._scope_mode == "off" or not self._scope_tags:
            return base_hits

        tagged_hits = self._tagged_fts_hits(query=query, limit=max(top_k * 2, 10))
        if not tagged_hits:
            return base_hits
        if self._scope_mode == "enforce":
            return tagged_hits[:top_k]
        return self._merge_hint_hits(tagged_hits, base_hits, top_k=top_k)

    def _tagged_fts_hits(self, *, query: str, limit: int) -> list[Any]:
        retriever = getattr(self._hub, "_fts", None)
        if retriever is None:
            return []
        try:
            raw_hits = retriever.search(query, limit=limit, min_quality=0.0, tags=self._scope_tags)
        except Exception:
            return []

        from chatgptrest.kb.hub import HybridHit

        return [
            HybridHit(
                artifact_id=hit.artifact_id,
                title=hit.title,
                snippet=hit.snippet,
                score=hit.score,
                fts_score=hit.score,
                vec_score=0.0,
                source_path=hit.source_path,
                content_type=hit.content_type,
                quality_score=hit.quality_score,
                metadata={
                    "kb_scope_mode": self._scope_mode,
                    "kb_scope_tags": list(self._scope_tags),
                },
            )
            for hit in raw_hits
        ]

    @staticmethod
    def _merge_hint_hits(tagged_hits: list[Any], base_hits: list[Any], *, top_k: int) -> list[Any]:
        merged: list[Any] = []
        seen: set[str] = set()
        for hit in tagged_hits + base_hits:
            artifact_id = str(getattr(hit, "artifact_id", "") or "")
            if not artifact_id or artifact_id in seen:
                continue
            seen.add(artifact_id)
            merged.append(hit)
            if len(merged) >= top_k:
                break
        return merged


class _LocalOnlyContextAssembler(ContextAssembler):
    """ContextAssembler variant that keeps hot-path retrieval local-only.

    This mirrors the existing ContextAssembler behavior for memory, KB, and EvoMap
    without mutating module globals for calendar / Obsidian integrations.
    """

    def build(
        self,
        query: str,
        session_id: str = "",
        account_id: str = "",
        agent_id: str = "",
        *,
        role_id: str = "",
        thread_id: str = "",
        working_limit: int = 10,
        episodic_limit: int = 5,
        semantic_limit: int = 3,
        kb_top_k: int = 5,
    ) -> ContextPack:
        # Auto-resolve role_id from contextvars if not explicitly provided
        if not role_id:
            try:
                from chatgptrest.kernel.role_context import get_current_role_name
                role_id = get_current_role_name()
            except ImportError:
                pass

        pack = ContextPack(
            query=query,
            session_id=session_id,
            budget=self._budget,
        )

        working = []
        if session_id:
            working = self._memory.get_working_context(
                session_id=session_id,
                limit=working_limit,
            )
        pack.working_memory = working
        if working:
            content = self._format_working_memory(working)
            pack.sources.append(
                ContextSource(
                    source_type="working",
                    priority=self.SOURCE_PRIORITY["working"],
                    content=content,
                    token_count=self._estimate_tokens(content),
                    metadata={"record_count": len(working)},
                )
            )

        episodic = []
        if session_id or account_id or thread_id:
            episodic = self._memory.get_episodic(
                query=query,
                limit=episodic_limit,
                agent_id=agent_id,
                session_id=session_id,
                role_id=role_id,
                account_id=account_id,
                thread_id=thread_id,
            )
        episodic = [record for record in episodic if record.category != "captured_memory"]
        pack.episodic_memory = episodic
        if episodic:
            content = self._format_episodic_memory(episodic)
            pack.sources.append(
                ContextSource(
                    source_type="episodic",
                    priority=self.SOURCE_PRIORITY["episodic"],
                    content=content,
                    token_count=self._estimate_tokens(content),
                    metadata={"record_count": len(episodic)},
                )
            )

        captured: list[Any] = []
        captured_scope = "blocked_missing_identity"
        capture_limit = max(1, min(episodic_limit, 3))
        if thread_id:
            captured_scope = "thread"
            captured = self._memory.get_episodic(
                query=query,
                category="captured_memory",
                limit=capture_limit,
                agent_id=agent_id,
                role_id=role_id,
                thread_id=thread_id,
            )
            if not captured and query:
                captured = self._memory.get_episodic(
                    category="captured_memory",
                    limit=max(1, min(episodic_limit, 2)),
                    agent_id=agent_id,
                    role_id=role_id,
                    thread_id=thread_id,
                )
        if not captured and session_id:
            captured_scope = "session"
            captured = self._memory.get_episodic(
                query=query,
                category="captured_memory",
                limit=capture_limit,
                agent_id=agent_id,
                session_id=session_id,
                role_id=role_id,
            )
            if not captured and query:
                captured = self._memory.get_episodic(
                    category="captured_memory",
                    limit=max(1, min(episodic_limit, 2)),
                    agent_id=agent_id,
                    session_id=session_id,
                    role_id=role_id,
                )
        if not captured and account_id:
            captured_scope = "account_cross_session"
            captured = self._memory.get_episodic(
                query=query,
                category="captured_memory",
                limit=capture_limit,
                agent_id=agent_id,
                role_id=role_id,
                account_id=account_id,
            )
            if not captured and query:
                captured = self._memory.get_episodic(
                    category="captured_memory",
                    limit=max(1, min(episodic_limit, 2)),
                    agent_id=agent_id,
                    role_id=role_id,
                    account_id=account_id,
                )
        if not captured and (session_id or account_id or thread_id):
            captured_scope = "no_match"
        setattr(pack, "captured_memory", captured)
        setattr(pack, "captured_memory_scope", captured_scope)
        if captured:
            content = self._format_captured_memory(captured)
            pack.sources.append(
                ContextSource(
                    source_type="captured",
                    priority=self.SOURCE_PRIORITY["episodic"] - 0.5,
                    content=content,
                    token_count=self._estimate_tokens(content),
                    metadata={"record_count": len(captured), "scope": captured_scope},
                )
            )

        semantic = []
        if session_id or account_id or thread_id:
            semantic = self._memory.get_semantic(
                domain="user_profile",
                agent_id=agent_id,
                session_id=session_id,
                role_id=role_id,
                account_id=account_id,
                thread_id=thread_id,
            )
        if semantic:
            semantic = semantic[:semantic_limit]
        pack.semantic_memory = semantic
        if semantic:
            content = self._format_semantic_memory(semantic)
            pack.sources.append(
                ContextSource(
                    source_type="semantic",
                    priority=self.SOURCE_PRIORITY["semantic"],
                    content=content,
                    token_count=self._estimate_tokens(content),
                    metadata={"record_count": len(semantic)},
                )
            )

        if self._kb_hub:
            try:
                kb_hits = self._kb_hub.search(query, top_k=kb_top_k)
                pack.kb_hits = kb_hits
                if kb_hits:
                    content = self._format_kb_hits(kb_hits)
                    pack.sources.append(
                        ContextSource(
                            source_type="kb",
                            priority=self.SOURCE_PRIORITY["kb"],
                            content=content,
                            token_count=self._estimate_tokens(content),
                            metadata={"hit_count": len(kb_hits)},
                        )
                    )
            except Exception:
                pack.kb_hits = []

        if self._evomap_db is not None:
            try:
                from chatgptrest.evomap.knowledge.retrieval import retrieve as evomap_retrieve
            except Exception:
                evomap_retrieve = None

            if evomap_retrieve is not None:
                try:
                    from chatgptrest.evomap.knowledge.retrieval import RetrievalConfig

                    evomap_hits = evomap_retrieve(
                        self._evomap_db,
                        query,
                        config=runtime_retrieval_config(
                            surface=RetrievalSurface.USER_HOT_PATH,
                        ),
                    )
                    pack.evomap_hits = evomap_hits
                    if evomap_hits:
                        content = self._format_evomap_hits(evomap_hits)
                        pack.sources.append(
                            ContextSource(
                                source_type="evomap",
                                priority=self.SOURCE_PRIORITY["evomap"],
                                content=content,
                                token_count=self._estimate_tokens(content),
                                metadata={
                                    "hit_count": len(evomap_hits),
                                    "top_score": round(evomap_hits[0].final_score, 3),
                                    "promotion_status_counts": summarize_promotion_statuses(evomap_hits),
                                },
                            )
                        )
                except Exception:
                    pack.evomap_hits = []

        pack = self._apply_budget(pack)
        pack.used_tokens = sum(source.token_count for source in pack.sources)
        return pack

    def _format_captured_memory(self, records: list[Any]) -> str:
        lines = []
        for rec in records:
            value = rec.value if isinstance(rec.value, dict) else {}
            title = str(value.get("title") or rec.key or "Captured memory").strip()
            summary = str(value.get("summary") or value.get("content") or rec.value).strip()
            if len(summary) > 240:
                summary = f"{summary[:237]}..."
            lines.append(f"- {title}: {summary}")
        return "\n".join(lines)


def _resolve_kb_scope_mode(scope_tags: list[str]) -> str:
    if not scope_tags:
        return "off"
    raw = str(os.environ.get("OPENMIND_ROLE_KB_SCOPE_MODE", "hint")).strip().lower()
    if raw not in {"off", "hint", "enforce"}:
        return "hint"
    return raw
