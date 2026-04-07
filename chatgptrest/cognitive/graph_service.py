from __future__ import annotations

import hashlib
import json
import os
import shlex
import sqlite3
import subprocess
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from chatgptrest.advisor.runtime import AdvisorRuntime
from chatgptrest.evomap.knowledge.retrieval import (
    RetrievalSurface,
    runtime_retrieval_config,
    retrieve,
    summarize_promotion_statuses,
)
from chatgptrest.evomap.knowledge.schema import Atom, Document, Edge, Entity, Episode, Evidence


@dataclass
class GraphQueryOptions:
    query: str
    scopes: tuple[str, ...] = ("business",)
    repo: str = ""
    project_id: str = ""
    limit: int = 10
    include_edges: bool = True
    include_paths: bool = True
    trace_id: str = ""


@dataclass
class GraphNode:
    node_id: str
    kind: str
    title: str
    snippet: str = ""
    score: float = 0.0
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.node_id,
            "kind": self.kind,
            "title": self.title,
            "snippet": self.snippet,
            "score": self.score,
            "source": self.source,
            "metadata": self.metadata,
        }


@dataclass
class GraphEdgeView:
    from_id: str
    to_id: str
    edge_type: str
    weight: float
    from_kind: str
    to_kind: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_id": self.from_id,
            "to_id": self.to_id,
            "edge_type": self.edge_type,
            "weight": self.weight,
            "from_kind": self.from_kind,
            "to_kind": self.to_kind,
            "source": self.source,
            "metadata": self.metadata,
        }


@dataclass
class GraphPathView:
    node_ids: list[str]
    edge_types: list[str]
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_ids": list(self.node_ids),
            "edge_types": list(self.edge_types),
            "source": self.source,
        }


@dataclass
class GraphEvidenceView:
    evidence_id: str
    kind: str
    title: str
    snippet: str
    source: str
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.evidence_id,
            "kind": self.kind,
            "title": self.title,
            "snippet": self.snippet,
            "source": self.source,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass
class GraphQueryResult:
    ok: bool
    trace_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdgeView]
    paths: list[GraphPathView]
    evidence: list[GraphEvidenceView]
    sources_used: list[str]
    degraded_sources: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "trace_id": self.trace_id,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "paths": [path.to_dict() for path in self.paths],
            "evidence": [item.to_dict() for item in self.evidence],
            "sources_used": list(self.sources_used),
            "degraded_sources": list(self.degraded_sources),
            "metadata": self.metadata,
        }


class RepoGraphAdapter(Protocol):
    def query(
        self,
        *,
        query: str,
        repo: str,
        limit: int,
    ) -> tuple[list[GraphNode], list[GraphEdgeView], list[GraphPathView], list[GraphEvidenceView], list[str], list[str]]: ...


class NullRepoGraphAdapter:
    def query(
        self,
        *,
        query: str,
        repo: str,
        limit: int,
    ) -> tuple[list[GraphNode], list[GraphEdgeView], list[GraphPathView], list[GraphEvidenceView], list[str], list[str]]:
        _ = (query, repo, limit)
        return [], [], [], [], [], ["repo_graph"]


class IssueGraphAdapter(Protocol):
    def query(
        self,
        *,
        query: str,
        limit: int,
    ) -> tuple[list[GraphNode], list[GraphEdgeView], list[GraphPathView], list[GraphEvidenceView], list[str], list[str]]: ...


class NullIssueGraphAdapter:
    def query(
        self,
        *,
        query: str,
        limit: int,
    ) -> tuple[list[GraphNode], list[GraphEdgeView], list[GraphPathView], list[GraphEvidenceView], list[str], list[str]]:
        _ = (query, limit)
        return [], [], [], [], [], ["issue_graph_unavailable"]


class CanonicalIssueGraphAdapter:
    def __init__(
        self,
        *,
        db_path: str | None = None,
        canonical_db_path: str | None = None,
        include_closed: bool = True,
        neighbor_depth: int = 2,
    ) -> None:
        from chatgptrest.core.config import load_config

        cfg = load_config()
        self._db_path = db_path or str(cfg.db_path)
        self._canonical_db_path = canonical_db_path or os.environ.get("CHATGPTREST_CANONICAL_DB_PATH", "").strip() or None
        self._include_closed = include_closed
        self._neighbor_depth = max(1, int(neighbor_depth))

    def query(
        self,
        *,
        query: str,
        limit: int,
    ) -> tuple[list[GraphNode], list[GraphEdgeView], list[GraphPathView], list[GraphEvidenceView], list[str], list[str]]:
        from pathlib import Path

        from chatgptrest.core import issue_canonical, issue_graph
        from chatgptrest.core.db import connect

        if not query.strip():
            return [], [], [], [], [], []

        degraded_sources: list[str] = []
        source_name = "issue_graph_canonical"
        try:
            with connect(Path(self._db_path)) as conn:
                try:
                    payload = issue_canonical.query_issue_graph_preferred(
                        authoritative_conn=conn,
                        canonical_db_path=self._canonical_db_path,
                        q=query,
                        include_closed=self._include_closed,
                        limit=max(1, int(limit)),
                        neighbor_depth=self._neighbor_depth,
                    )
                    if int((payload.get("summary") or {}).get("match_count") or 0) == 0:
                        legacy_snapshot = issue_graph.build_issue_graph_snapshot(
                            conn,
                            include_closed=self._include_closed,
                            max_issues=max(50, int(limit) * 20),
                            include_docs=True,
                        )
                        legacy_payload = issue_graph.query_issue_graph(
                            legacy_snapshot,
                            q=query,
                            include_closed=self._include_closed,
                            limit=max(1, int(limit)),
                            neighbor_depth=self._neighbor_depth,
                        )
                        if int((legacy_payload.get("summary") or {}).get("match_count") or 0) > 0:
                            legacy_payload.setdefault("summary", {})
                            legacy_payload["summary"]["read_plane"] = "legacy_query_fallback"
                            payload = legacy_payload
                            source_name = "issue_graph_legacy"
                            degraded_sources.append("issue_graph_canonical_query_miss")
                except (issue_canonical.IssueCanonicalUnavailable, sqlite3.Error, OSError):
                    snapshot = issue_graph.build_issue_graph_snapshot(
                        conn,
                        include_closed=self._include_closed,
                        max_issues=max(50, int(limit) * 20),
                        include_docs=True,
                    )
                    payload = issue_graph.query_issue_graph(
                        snapshot,
                        q=query,
                        include_closed=self._include_closed,
                        limit=max(1, int(limit)),
                        neighbor_depth=self._neighbor_depth,
                    )
                    payload.setdefault("summary", {})
                    payload["summary"]["read_plane"] = "legacy_fallback"
                    source_name = "issue_graph_legacy"
                    degraded_sources.append("issue_graph_canonical_unavailable")
        except Exception as exc:
            return (
                [],
                [],
                [],
                [
                    GraphEvidenceView(
                        evidence_id="issue-graph-error",
                        kind="issue_graph_error",
                        title="Issue graph adapter failed",
                        snippet=str(exc),
                        source="issue_graph_adapter",
                        metadata={"db_path": self._db_path},
                    )
                ],
                [],
                ["issue_graph_unavailable"],
            )

        nodes, edges, paths, evidence = self._normalize_payload(
            payload,
            source_name=source_name,
            limit=max(1, int(limit)),
        )
        return nodes, edges, paths, evidence, [source_name], list(dict.fromkeys(degraded_sources))

    def _normalize_payload(
        self,
        payload: dict[str, Any],
        *,
        source_name: str,
        limit: int,
    ) -> tuple[list[GraphNode], list[GraphEdgeView], list[GraphPathView], list[GraphEvidenceView]]:
        summary = dict(payload.get("summary") or {})
        matched_node_ids = self._matched_node_ids(payload)
        raw_nodes = [node for node in (payload.get("nodes") or []) if isinstance(node, dict)]
        kind_by_id = {str(node.get("id") or ""): str(node.get("kind") or "issue_node") for node in raw_nodes}

        nodes = [
            GraphNode(
                node_id=str(node.get("id") or f"issue-node-{idx}"),
                kind=str(node.get("kind") or "issue_node"),
                title=str(node.get("label") or node.get("id") or f"issue-node-{idx}"),
                snippet=self._node_snippet(dict(node.get("attrs") or {})),
                score=(1.0 if str(node.get("id") or "") in matched_node_ids else 0.6),
                source=source_name,
                metadata={
                    **dict(node.get("attrs") or {}),
                    "matched": str(node.get("id") or "") in matched_node_ids,
                    "read_plane": str(summary.get("read_plane") or ""),
                },
            )
            for idx, node in enumerate(raw_nodes)
        ]

        edges = [
            GraphEdgeView(
                from_id=str(edge.get("source") or ""),
                to_id=str(edge.get("target") or ""),
                edge_type=str(edge.get("type") or "related_to"),
                weight=float((edge.get("attrs") or {}).get("weight") or 1.0),
                from_kind=kind_by_id.get(str(edge.get("source") or ""), "issue_node"),
                to_kind=kind_by_id.get(str(edge.get("target") or ""), "issue_node"),
                source=source_name,
                metadata=dict(edge.get("attrs") or {}),
            )
            for edge in (payload.get("edges") or [])
            if isinstance(edge, dict)
        ]

        paths = [
            GraphPathView(
                node_ids=[edge.from_id, edge.to_id],
                edge_types=[edge.edge_type],
                source=source_name,
            )
            for edge in edges
            if edge.from_id in matched_node_ids or edge.to_id in matched_node_ids
        ][: limit * 2]

        evidence: list[GraphEvidenceView] = [
            GraphEvidenceView(
                evidence_id=f"{source_name}-summary",
                kind="issue_graph_summary",
                title="Issue execution graph summary",
                snippet=json.dumps(summary, ensure_ascii=False),
                source=source_name,
                metadata=summary,
            )
        ]
        for match in (payload.get("matches") or [])[:limit]:
            if not isinstance(match, dict):
                continue
            evidence.append(
                GraphEvidenceView(
                    evidence_id=str(match.get("object_id") or match.get("issue_id") or f"{source_name}-match"),
                    kind="issue_match",
                    title=str(match.get("title") or match.get("issue_id") or "Issue match"),
                    snippet=self._match_snippet(match),
                    source=source_name,
                    score=1.0,
                    metadata=dict(match),
                )
            )
        return nodes, edges, paths, evidence

    @staticmethod
    def _matched_node_ids(payload: dict[str, Any]) -> set[str]:
        matched: set[str] = set()
        for match in payload.get("matches") or []:
            if not isinstance(match, dict):
                continue
            object_id = str(match.get("object_id") or "").strip()
            issue_id = str(match.get("issue_id") or "").strip()
            if object_id:
                matched.add(object_id)
            elif issue_id:
                matched.add(f"issue:{issue_id}")
        return matched

    @staticmethod
    def _node_snippet(attrs: dict[str, Any]) -> str:
        parts = [
            str(attrs.get("summary") or "").strip(),
            str(attrs.get("symptom") or "").strip(),
            str(attrs.get("status") or "").strip(),
            str(attrs.get("job_id") or "").strip(),
            str(attrs.get("project") or "").strip(),
        ]
        snippet = " | ".join(part for part in parts if part)
        return snippet[:500]

    @staticmethod
    def _match_snippet(match: dict[str, Any]) -> str:
        payload = {
            key: value
            for key, value in match.items()
            if key not in {"title"} and value not in (None, "", [])
        }
        return json.dumps(payload, ensure_ascii=False)[:500]


class GitNexusCliAdapter:
    """Best-effort repo-graph adapter via local GitNexus CLI.

    The adapter is explicit opt-in because it shells out to a developer toolchain
    and is not suitable for the default hot path. When disabled or unavailable,
    callers should degrade cleanly.
    """

    def __init__(self) -> None:
        self._enabled = os.environ.get("OPENMIND_ENABLE_GITNEXUS_CLI", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        self._command = os.environ.get("OPENMIND_GITNEXUS_QUERY_CMD", "").strip()
        self._timeout_seconds = float(os.environ.get("OPENMIND_GITNEXUS_TIMEOUT_SECONDS", "8"))

    def query(
        self,
        *,
        query: str,
        repo: str,
        limit: int,
    ) -> tuple[list[GraphNode], list[GraphEdgeView], list[GraphPathView], list[GraphEvidenceView], list[str], list[str]]:
        if not self._enabled:
            return [], [], [], [], [], ["repo_graph"]

        cmd = self._build_command(query=query, repo=repo, limit=limit)
        if not cmd:
            return [], [], [], [], [], ["repo_graph"]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except Exception as exc:
            return [], [], [], [
                GraphEvidenceView(
                    evidence_id="gitnexus-error",
                    kind="repo_graph_error",
                    title="GitNexus CLI failed",
                    snippet=str(exc),
                    source="gitnexus_cli",
                    metadata={"repo": repo, "command": cmd},
                )
            ], [], ["repo_graph"]

        if proc.returncode != 0:
            snippet = (proc.stderr or proc.stdout or "").strip()[:2000]
            return [], [], [], [
                GraphEvidenceView(
                    evidence_id="gitnexus-error",
                    kind="repo_graph_error",
                    title="GitNexus CLI returned non-zero status",
                    snippet=snippet,
                    source="gitnexus_cli",
                    metadata={"repo": repo, "command": cmd, "returncode": proc.returncode},
                )
            ], [], ["repo_graph"]

        output = (proc.stdout or "").strip()
        if not output:
            return [], [], [], [], ["gitnexus_cli"], []

        return self._parse_output(output=output, repo=repo, command=cmd)

    def _build_command(self, *, query: str, repo: str, limit: int) -> list[str]:
        if self._command:
            cmd = shlex.split(self._command)
        else:
            cmd = ["npx", "--yes", "gitnexus", "query"]
        if repo:
            cmd.extend(["--repo", repo])
        if limit > 0:
            cmd.extend(["--limit", str(limit)])
        cmd.append(query)
        return cmd

    def _parse_output(
        self,
        *,
        output: str,
        repo: str,
        command: list[str],
    ) -> tuple[list[GraphNode], list[GraphEdgeView], list[GraphPathView], list[GraphEvidenceView], list[str], list[str]]:
        try:
            payload = json.loads(output)
        except Exception:
            return [], [], [], [
                GraphEvidenceView(
                    evidence_id=f"gitnexus-{hashlib.sha1(output.encode('utf-8')).hexdigest()[:12]}",
                    kind="repo_graph_result",
                    title=f"GitNexus query for {repo or 'current repo'}",
                    snippet=output[:4000],
                    source="gitnexus_cli",
                    metadata={"repo": repo, "command": command},
                )
            ], ["gitnexus_cli"], []

        if not isinstance(payload, dict):
            return [], [], [], [
                GraphEvidenceView(
                    evidence_id="gitnexus-non-dict",
                    kind="repo_graph_result",
                    title=f"GitNexus query for {repo or 'current repo'}",
                    snippet=str(payload)[:4000],
                    source="gitnexus_cli",
                    metadata={"repo": repo, "command": command},
                )
            ], ["gitnexus_cli"], []

        if any(key in payload for key in ("nodes", "edges", "paths", "evidence")):
            return self._normalize_graph_payload(payload, repo=repo, command=command)
        return self._normalize_gitnexus_query_payload(payload, repo=repo, command=command)

    def _normalize_graph_payload(
        self,
        payload: dict[str, Any],
        *,
        repo: str,
        command: list[str],
    ) -> tuple[list[GraphNode], list[GraphEdgeView], list[GraphPathView], list[GraphEvidenceView], list[str], list[str]]:
        nodes = [
            GraphNode(
                node_id=str(item.get("id") or item.get("node_id") or f"repo-node-{idx}"),
                kind=str(item.get("kind") or "symbol"),
                title=str(item.get("title") or item.get("name") or item.get("id") or f"node-{idx}"),
                snippet=str(item.get("snippet") or ""),
                score=float(item.get("score") or 0.0),
                source=str(item.get("source") or "gitnexus_cli"),
                metadata=dict(item.get("metadata") or {}),
            )
            for idx, item in enumerate(payload.get("nodes") or [])
            if isinstance(item, dict)
        ]
        edges = [
            GraphEdgeView(
                from_id=str(item.get("from_id") or item.get("from") or ""),
                to_id=str(item.get("to_id") or item.get("to") or ""),
                edge_type=str(item.get("edge_type") or item.get("type") or "related_to"),
                weight=float(item.get("weight") or 1.0),
                from_kind=str(item.get("from_kind") or "symbol"),
                to_kind=str(item.get("to_kind") or "symbol"),
                source=str(item.get("source") or "gitnexus_cli"),
                metadata=dict(item.get("metadata") or {}),
            )
            for item in (payload.get("edges") or [])
            if isinstance(item, dict)
        ]
        paths = [
            GraphPathView(
                node_ids=[str(node_id) for node_id in (item.get("node_ids") or [])],
                edge_types=[str(edge_type) for edge_type in (item.get("edge_types") or [])],
                source=str(item.get("source") or "gitnexus_cli"),
            )
            for item in (payload.get("paths") or [])
            if isinstance(item, dict)
        ]
        evidence = [
            GraphEvidenceView(
                evidence_id=str(item.get("id") or item.get("evidence_id") or f"repo-evidence-{idx}"),
                kind=str(item.get("kind") or "repo_graph_result"),
                title=str(item.get("title") or f"GitNexus evidence {idx + 1}"),
                snippet=str(item.get("snippet") or ""),
                source=str(item.get("source") or "gitnexus_cli"),
                score=float(item.get("score") or 0.0),
                metadata=dict(item.get("metadata") or {}),
            )
            for idx, item in enumerate(payload.get("evidence") or [])
            if isinstance(item, dict)
        ]
        sources_used = [str(source) for source in (payload.get("sources_used") or ["gitnexus_cli"])]
        degraded_sources = [str(source) for source in (payload.get("degraded_sources") or [])]
        if not nodes and not evidence:
            evidence.append(
                GraphEvidenceView(
                    evidence_id="gitnexus-empty",
                    kind="repo_graph_result",
                    title=f"GitNexus query for {repo or 'current repo'}",
                    snippet="Command returned structured payload without nodes or evidence.",
                    source="gitnexus_cli",
                    metadata={"repo": repo, "command": command},
                )
            )
        return nodes, edges, paths, evidence, list(dict.fromkeys(sources_used)), list(dict.fromkeys(degraded_sources))

    def _normalize_gitnexus_query_payload(
        self,
        payload: dict[str, Any],
        *,
        repo: str,
        command: list[str],
    ) -> tuple[list[GraphNode], list[GraphEdgeView], list[GraphPathView], list[GraphEvidenceView], list[str], list[str]]:
        nodes: dict[str, GraphNode] = {}
        evidence: list[GraphEvidenceView] = []
        paths: list[GraphPathView] = []
        process_steps: dict[str, list[tuple[int, str]]] = {}

        for idx, item in enumerate(payload.get("process_symbols") or []):
            if not isinstance(item, dict):
                continue
            node_id = str(item.get("id") or f"process-symbol-{idx}")
            process_id = str(item.get("process_id") or "")
            step_index = int(item.get("step_index") or 0)
            nodes[node_id] = GraphNode(
                node_id=node_id,
                kind="repo_symbol",
                title=str(item.get("name") or node_id),
                snippet=str(item.get("filePath") or ""),
                source="gitnexus_cli",
                metadata={
                    "file_path": item.get("filePath"),
                    "start_line": item.get("startLine"),
                    "end_line": item.get("endLine"),
                    "module": item.get("module"),
                    "process_id": process_id,
                    "step_index": step_index,
                },
            )
            if process_id:
                process_steps.setdefault(process_id, []).append((step_index, node_id))

        for idx, item in enumerate(payload.get("definitions") or []):
            if not isinstance(item, dict):
                continue
            node_id = str(item.get("id") or f"definition-{idx}")
            nodes.setdefault(
                node_id,
                GraphNode(
                    node_id=node_id,
                    kind="repo_definition",
                    title=str(item.get("name") or node_id),
                    snippet=str(item.get("filePath") or ""),
                    source="gitnexus_cli",
                    metadata={
                        "file_path": item.get("filePath"),
                        "start_line": item.get("startLine"),
                        "end_line": item.get("endLine"),
                        "module": item.get("module"),
                    },
                ),
            )

        for idx, item in enumerate(payload.get("processes") or []):
            if not isinstance(item, dict):
                continue
            process_id = str(item.get("id") or f"process-{idx}")
            title = str(item.get("summary") or process_id)
            evidence.append(
                GraphEvidenceView(
                    evidence_id=process_id,
                    kind="repo_graph_process",
                    title=title,
                    snippet=json.dumps(
                        {
                            "priority": item.get("priority"),
                            "process_type": item.get("process_type"),
                            "step_count": item.get("step_count"),
                            "symbol_count": item.get("symbol_count"),
                        },
                        ensure_ascii=False,
                    ),
                    source="gitnexus_cli",
                    metadata={"repo": repo},
                )
            )
            ordered = [node_id for _, node_id in sorted(process_steps.get(process_id, []))]
            if len(ordered) >= 2:
                paths.append(
                    GraphPathView(
                        node_ids=ordered,
                        edge_types=["step_in_process"] * (len(ordered) - 1),
                        source="gitnexus_cli",
                    )
                )

        markdown = str(payload.get("markdown") or "").strip()
        if markdown:
            evidence.append(
                GraphEvidenceView(
                    evidence_id=f"gitnexus-{hashlib.sha1(markdown.encode('utf-8')).hexdigest()[:12]}",
                    kind="repo_graph_markdown",
                    title=f"GitNexus query for {repo or 'current repo'}",
                    snippet=markdown[:4000],
                    source="gitnexus_cli",
                    metadata={"repo": repo, "command": command},
                )
            )

        if not nodes and not evidence:
            evidence.append(
                GraphEvidenceView(
                    evidence_id="gitnexus-empty",
                    kind="repo_graph_result",
                    title=f"GitNexus query for {repo or 'current repo'}",
                    snippet=json.dumps(payload, ensure_ascii=False)[:4000],
                    source="gitnexus_cli",
                    metadata={"repo": repo, "command": command},
                )
            )
        return list(nodes.values()), [], paths, evidence, ["gitnexus_cli"], []


class GraphQueryService:
    _SCOPE_ALIASES = {
        "personal_graph": "business",
        "personal": "business",
        "business": "business",
        "repo_graph": "repo_code",
        "repo": "repo_code",
        "repo_code": "repo_code",
        "issue_graph": "issue_execution",
        "issue_execution": "issue_execution",
    }

    def __init__(self, runtime: AdvisorRuntime, repo_graph_adapter: RepoGraphAdapter | None = None, issue_graph_adapter: IssueGraphAdapter | None = None):
        self._runtime = runtime
        self._repo_graph = repo_graph_adapter or GitNexusCliAdapter()
        self._issue_graph = issue_graph_adapter or CanonicalIssueGraphAdapter()

    def query(self, options: GraphQueryOptions) -> GraphQueryResult:
        trace_id = options.trace_id or str(uuid.uuid4())
        raw_requested_scopes = list(dict.fromkeys(options.scopes or ("business",)))
        requested_scopes, aliases_applied = self._normalize_scopes(raw_requested_scopes)
        limit = max(1, min(int(options.limit or 10), 50))

        nodes: dict[str, GraphNode] = {}
        edges: dict[tuple[str, str, str], GraphEdgeView] = {}
        paths: list[GraphPathView] = []
        evidence: list[GraphEvidenceView] = []
        sources_used: list[str] = []
        degraded_sources: list[str] = []
        personal_promotion_status_counts: dict[str, int] = {}

        if "personal_graph" in requested_scopes or "business" in requested_scopes:
            personal = self._query_personal_graph(
                query=options.query,
                limit=limit,
                include_edges=options.include_edges,
                include_paths=options.include_paths,
                project_id=options.project_id,
            )
            for node in personal["nodes"]:
                nodes[node.node_id] = node
            for edge in personal["edges"]:
                edges[(edge.from_id, edge.to_id, edge.edge_type)] = edge
            paths.extend(personal["paths"])
            evidence.extend(personal["evidence"])
            sources_used.extend(personal["sources_used"])
            degraded_sources.extend(personal["degraded_sources"])
            personal_promotion_status_counts = dict(personal.get("promotion_status_counts", {}) or {})

        if "repo_graph" in requested_scopes or "repo_code" in requested_scopes:
            repo_nodes, repo_edges, repo_paths, repo_evidence, repo_sources, repo_degraded = self._repo_graph.query(
                query=options.query,
                repo=options.repo,
                limit=limit,
            )
            for node in repo_nodes:
                nodes[node.node_id] = node
            for edge in repo_edges:
                edges[(edge.from_id, edge.to_id, edge.edge_type)] = edge
            paths.extend(repo_paths)
            evidence.extend(repo_evidence)
            sources_used.extend(repo_sources)
            degraded_sources.extend(repo_degraded)
            
        issue_graph_summary: dict[str, Any] = {}
        if "issue_execution" in requested_scopes:
            issue_nodes, issue_edges, issue_paths, issue_evidence, issue_sources, issue_degraded = self._issue_graph.query(
                query=options.query,
                limit=limit,
            )
            for node in issue_nodes:
                nodes[node.node_id] = node
            for edge in issue_edges:
                edges[(edge.from_id, edge.to_id, edge.edge_type)] = edge
            paths.extend(issue_paths)
            evidence.extend(issue_evidence)
            sources_used.extend(issue_sources)
            degraded_sources.extend(issue_degraded)
            issue_graph_summary = next(
                (
                    dict(item.metadata)
                    for item in issue_evidence
                    if item.kind == "issue_graph_summary" and isinstance(item.metadata, dict)
                ),
                {},
            )

        sources_used = list(dict.fromkeys(sources_used))
        degraded_sources = list(dict.fromkeys(degraded_sources))

        return GraphQueryResult(
            ok=True,
            trace_id=trace_id,
            nodes=list(nodes.values())[: limit * 3],
            edges=list(edges.values())[: limit * 4],
            paths=paths[: limit * 2],
            evidence=evidence[: limit * 4],
            sources_used=sources_used,
            degraded_sources=degraded_sources,
            metadata={
                "query": options.query,
                "scopes": requested_scopes,
                "requested_scopes": raw_requested_scopes,
                "repo": options.repo,
                "family_router": {
                    "requested_scopes": raw_requested_scopes,
                    "resolved_families": requested_scopes,
                    "aliases_applied": aliases_applied,
                    "explainability": self._family_explainability(
                        requested_scopes,
                        degraded_sources,
                        issue_graph_summary=issue_graph_summary,
                    ),
                },
                "issue_graph": issue_graph_summary,
                "promotion_status_counts": personal_promotion_status_counts,
                "promotion_audit": {
                    "distribution": personal_promotion_status_counts,
                    "issue_graph": issue_graph_summary,
                    "explainability": f"Loaded node distribution reflects {sum(personal_promotion_status_counts.values())} curated facts.",
                },
            },
        )

    @classmethod
    def _normalize_scopes(cls, scopes: list[str]) -> tuple[list[str], list[dict[str, str]]]:
        normalized: list[str] = []
        aliases_applied: list[dict[str, str]] = []
        for raw in scopes:
            cleaned = str(raw or "").strip()
            if not cleaned:
                continue
            mapped = cls._SCOPE_ALIASES.get(cleaned, cleaned)
            if mapped != cleaned:
                aliases_applied.append({"input": cleaned, "resolved": mapped})
            if mapped not in normalized:
                normalized.append(mapped)
        if not normalized:
            normalized.append("business")
        return normalized, aliases_applied

    @staticmethod
    def _family_explainability(
        scopes: list[str],
        degraded_sources: list[str],
        *,
        issue_graph_summary: dict[str, Any] | None = None,
    ) -> list[str]:
        notes: list[str] = []
        if "business" in scopes:
            notes.append("business routes to the local EvoMap diagnostic graph.")
        if "repo_code" in scopes:
            notes.append("repo_code routes to the GitNexus repo-graph adapter.")
        if "issue_execution" in scopes:
            notes.append("issue_execution routes to the canonical issue graph with legacy fallback when canonical sync is unavailable.")
        read_plane = str((issue_graph_summary or {}).get("read_plane") or "")
        if read_plane == "canonical":
            notes.append("issue_execution resolved through the canonical issue graph plane.")
        elif read_plane == "legacy_fallback":
            notes.append("issue_execution resolved through the legacy fallback issue graph plane.")
        for degraded in degraded_sources:
            if degraded == "repo_graph":
                notes.append("repo_code degraded because the repo-graph adapter is unavailable.")
            elif degraded == "issue_graph_unavailable":
                notes.append("issue_execution degraded because no issue graph adapter is configured.")
            elif degraded == "issue_graph_canonical_unavailable":
                notes.append("issue_execution fell back to the legacy issue graph because canonical sync was unavailable.")
            elif degraded == "issue_graph_canonical_query_miss":
                notes.append("issue_execution fell back to the legacy issue graph because canonical text matching returned no hits.")
            elif degraded == "personal_graph":
                notes.append("business degraded because the local knowledge DB is unavailable.")
        return notes

    def _query_personal_graph(
        self,
        *,
        query: str,
        limit: int,
        include_edges: bool,
        include_paths: bool,
        project_id: str = "",
    ) -> dict[str, Any]:
        db = self._runtime.evomap_knowledge_db
        if db is None:
            return {
                "nodes": [],
                "edges": [],
                "paths": [],
                "evidence": [],
                "sources_used": [],
                "degraded_sources": ["personal_graph"],
            }

        config = runtime_retrieval_config(
            surface=RetrievalSurface.DIAGNOSTIC_PATH,
            result_limit=limit,
            min_quality=0.15,
        )
        scored_atoms = retrieve(db, query, config=config)
        conn = db.connect()

        # Project isolation: filter atoms that belong to a different project
        if project_id:
            scored_atoms = self._filter_by_project(conn, scored_atoms, project_id)
        nodes: dict[str, GraphNode] = {}
        edges: dict[tuple[str, str, str], GraphEdgeView] = {}
        evidence: list[GraphEvidenceView] = []

        for item in scored_atoms[:limit]:
            atom = item.atom
            nodes[atom.atom_id] = self._atom_node(atom, score=item.final_score)
            for ev in db.list_evidence_for_atom(atom.atom_id)[:3]:
                evidence.append(self._evidence_view(ev))

            episode = self._fetch_episode(conn, atom.episode_id)
            if episode is not None:
                nodes[episode.episode_id] = self._episode_node(episode)
                edge = GraphEdgeView(
                    from_id=episode.episode_id,
                    to_id=atom.atom_id,
                    edge_type="contains",
                    weight=1.0,
                    from_kind="episode",
                    to_kind="atom",
                    source="knowledge_db",
                )
                edges[(edge.from_id, edge.to_id, edge.edge_type)] = edge
                document = self._fetch_document(conn, episode.doc_id)
                if document is not None:
                    nodes[document.doc_id] = self._document_node(document)
                    doc_edge = GraphEdgeView(
                        from_id=document.doc_id,
                        to_id=episode.episode_id,
                        edge_type="contains",
                        weight=1.0,
                        from_kind="document",
                        to_kind="episode",
                        source="knowledge_db",
                    )
                    edges[(doc_edge.from_id, doc_edge.to_id, doc_edge.edge_type)] = doc_edge

        query_terms = [part.strip().lower() for part in query.split() if part.strip()]
        if query_terms:
            if project_id:
                # Filter entities that are connected to atoms in this project
                entity_rows = conn.execute(
                    """
                    SELECT DISTINCT e.* FROM entities e
                    JOIN edges eg ON eg.from_id = e.entity_id
                    JOIN atoms a ON a.atom_id = eg.to_id
                    JOIN episodes ep ON ep.episode_id = a.episode_id
                    JOIN documents d ON d.doc_id = ep.doc_id
                    WHERE (e.normalized_name LIKE ? OR e.name LIKE ?)
                      AND d.project = ?
                    LIMIT ?
                    """,
                    (f"%{query_terms[0]}%", f"%{query_terms[0]}%", project_id, max(5, limit)),
                ).fetchall()
            else:
                entity_rows = conn.execute(
                    """
                    SELECT * FROM entities
                    WHERE normalized_name LIKE ? OR name LIKE ?
                    LIMIT ?
                    """,
                    (f"%{query_terms[0]}%", f"%{query_terms[0]}%", max(5, limit)),
                ).fetchall()
            for row in entity_rows:
                entity = Entity.from_row(dict(row))
                nodes[entity.entity_id] = self._entity_node(entity)

        if include_edges:
            candidate_ids = list(nodes.keys())[: limit * 3]
            for node_id in candidate_ids:
                for edge in db.get_edges_from(node_id)[:4] + db.get_edges_to(node_id)[:4]:
                    view = GraphEdgeView(
                        from_id=edge.from_id,
                        to_id=edge.to_id,
                        edge_type=edge.edge_type,
                        weight=edge.weight,
                        from_kind=edge.from_kind,
                        to_kind=edge.to_kind,
                        source="knowledge_db",
                        metadata=self._parse_json(edge.meta_json),
                    )
                    edges[(view.from_id, view.to_id, view.edge_type)] = view
                    for node_ref, node_kind in ((edge.from_id, edge.from_kind), (edge.to_id, edge.to_kind)):
                        if node_ref in nodes:
                            continue
                        loaded = self._load_node(conn, node_ref, node_kind)
                        if loaded is not None:
                            nodes[loaded.node_id] = loaded

        paths: list[GraphPathView] = []
        if include_paths:
            for edge in list(edges.values())[: limit * 2]:
                paths.append(
                    GraphPathView(
                        node_ids=[edge.from_id, edge.to_id],
                        edge_types=[edge.edge_type],
                        source=edge.source,
                    )
                )

        return {
            "nodes": list(nodes.values()),
            "edges": list(edges.values()),
            "paths": paths,
            "evidence": evidence,
            "sources_used": ["knowledge_db"],
            "degraded_sources": [],
            "promotion_status_counts": summarize_promotion_statuses(scored_atoms[:limit]),
        }

    def _filter_by_project(
        self,
        conn: Any,
        scored_atoms: list,
        project_id: str,
    ) -> list:
        """Filter scored atoms to only those belonging to the given project.

        Joins atoms → episodes → documents and checks documents.project.
        """
        if not scored_atoms:
            return scored_atoms

        atom_ids = [sa.atom.atom_id for sa in scored_atoms]
        placeholders = ",".join(["?"] * len(atom_ids))
        project_atom_ids = set()
        rows = conn.execute(
            f"""
            SELECT a.atom_id FROM atoms a
            JOIN episodes ep ON ep.episode_id = a.episode_id
            JOIN documents d ON d.doc_id = ep.doc_id
            WHERE a.atom_id IN ({placeholders})
              AND d.project = ?
            """,
            [*atom_ids, project_id],
        ).fetchall()
        for row in rows:
            project_atom_ids.add(row[0])

        return [sa for sa in scored_atoms if sa.atom.atom_id in project_atom_ids]

    def _load_node(self, conn: Any, node_id: str, kind: str) -> GraphNode | None:
        if kind == "atom":
            atom = self._fetch_atom(conn, node_id)
            return self._atom_node(atom) if atom is not None else None
        if kind == "episode":
            episode = self._fetch_episode(conn, node_id)
            return self._episode_node(episode) if episode is not None else None
        if kind == "document":
            document = self._fetch_document(conn, node_id)
            return self._document_node(document) if document is not None else None
        if kind == "entity":
            entity = self._fetch_entity(conn, node_id)
            return self._entity_node(entity) if entity is not None else None
        return None

    def _fetch_atom(self, conn: Any, atom_id: str) -> Atom | None:
        row = conn.execute("SELECT * FROM atoms WHERE atom_id = ?", (atom_id,)).fetchone()
        return Atom.from_row(dict(row)) if row is not None else None

    def _fetch_episode(self, conn: Any, episode_id: str) -> Episode | None:
        if not episode_id:
            return None
        row = conn.execute("SELECT * FROM episodes WHERE episode_id = ?", (episode_id,)).fetchone()
        return Episode.from_row(dict(row)) if row is not None else None

    def _fetch_document(self, conn: Any, doc_id: str) -> Document | None:
        if not doc_id:
            return None
        row = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
        return Document.from_row(dict(row)) if row is not None else None

    def _fetch_entity(self, conn: Any, entity_id: str) -> Entity | None:
        row = conn.execute("SELECT * FROM entities WHERE entity_id = ?", (entity_id,)).fetchone()
        return Entity.from_row(dict(row)) if row is not None else None

    def _atom_node(self, atom: Atom, *, score: float = 0.0) -> GraphNode:
        return GraphNode(
            node_id=atom.atom_id,
            kind="atom",
            title=atom.question or atom.canonical_question or atom.atom_id,
            snippet=atom.answer[:500],
            score=round(score, 4),
            source="knowledge_db",
            metadata={
                "atom_type": atom.atom_type,
                "status": atom.status,
                "stability": atom.stability,
                "promotion_status": atom.promotion_status,
                "episode_id": atom.episode_id,
            },
        )

    def _episode_node(self, episode: Episode) -> GraphNode:
        return GraphNode(
            node_id=episode.episode_id,
            kind="episode",
            title=episode.title or episode.episode_id,
            snippet=episode.summary[:300],
            source="knowledge_db",
            metadata={
                "episode_type": episode.episode_type,
                "doc_id": episode.doc_id,
            },
        )

    def _document_node(self, document: Document) -> GraphNode:
        return GraphNode(
            node_id=document.doc_id,
            kind="document",
            title=document.title or document.doc_id,
            snippet=document.raw_ref,
            source="knowledge_db",
            metadata={
                "project": document.project,
                "source": document.source,
            },
        )

    def _entity_node(self, entity: Entity) -> GraphNode:
        return GraphNode(
            node_id=entity.entity_id,
            kind="entity",
            title=entity.name or entity.entity_id,
            snippet=entity.entity_type,
            source="knowledge_db",
            metadata={"entity_type": entity.entity_type},
        )

    def _evidence_view(self, evidence: Evidence) -> GraphEvidenceView:
        return GraphEvidenceView(
            evidence_id=evidence.evidence_id,
            kind="evidence",
            title=evidence.evidence_role or evidence.evidence_id,
            snippet=evidence.excerpt[:600],
            source="knowledge_db",
            metadata={
                "atom_id": evidence.atom_id,
                "doc_id": evidence.doc_id,
                "span_ref": evidence.span_ref,
            },
        )

    def _parse_json(self, raw: str) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except Exception:
            return {"raw": raw}
        return value if isinstance(value, dict) else {"value": value}
