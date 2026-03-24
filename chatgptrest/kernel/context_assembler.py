"""ContextAssembler — builds LLM prompts from multi-source context.

This component bridges the gap between stored memories/KB and the LLM:
  1. Working memory → recent conversation turns
  2. Episodic memory → relevant historical tasks
  3. Semantic memory → user preferences / project knowledge
  4. KB search → knowledge base hits
  5. Token budget management → intelligent裁剪

Design:
  - Stateless build() method (no persistence)
  - Token budget allocation with priority-based裁剪
  - Returns structured ContextPack for downstream use
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from chatgptrest.kb.hub import HybridHit
from chatgptrest.kernel.memory_manager import (
    MemoryManager,
    MemoryRecord,
    MemoryTier,
)

try:
    from chatgptrest.integrations.google_workspace import GoogleWorkspace
except ImportError:
    GoogleWorkspace = None

try:
    from chatgptrest.integrations.obsidian_api import ObsidianClient
except ImportError:
    ObsidianClient = None

try:
    from chatgptrest.evomap.knowledge.retrieval import (
        retrieve as evomap_retrieve,
        RetrievalSurface as EvoMapRetrievalSurface,
        runtime_retrieval_config as runtime_evomap_retrieval_config,
        ScoredAtom,
    )
    from chatgptrest.evomap.knowledge.db import KnowledgeDB as EvoMapDB
except ImportError:
    evomap_retrieve = None  # type: ignore
    EvoMapDB = None  # type: ignore
    ScoredAtom = None  # type: ignore
    EvoMapRetrievalSurface = None  # type: ignore
    runtime_evomap_retrieval_config = None  # type: ignore

logger = logging.getLogger(__name__)


# ── Token Budget Configuration ───────────────────────────────────────

@dataclass
class TokenBudget:
    """Token budget allocation for context sources."""

    system_instruction: int = 300
    user_query: int = 500
    user_profile: int = 400       # semantic memory
    calendar_events: int = 400    # schedule context
    obsidian_notes: int = 600
    evomap_knowledge: int = 1200  # EvoMap knowledge atoms
    kb_evidence: int = 1200       # KB hits (reduced to share budget with evomap)
    conversation_history: int = 1500  # working memory
    episodic_tasks: int = 800    # episodic memory
    reserve_for_output: int = 2500

    max_total: int = 8000

    def available_for_context(self) -> int:
        """Tokens available for context after system+query."""
        return (
            self.max_total
            - self.system_instruction
            - self.user_query
            - self.reserve_for_output
        )


# ── Context Data Models ──────────────────────────────────────────────

@dataclass
class ContextSource:
    """A single context source with its content and token count."""

    source_type: str  # "working" | "episodic" | "semantic" | "kb"
    priority: int    # Lower = more important
    content: str
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextPack:
    """Complete context assembled for an LLM prompt.

    This is the output of ContextAssembler.build().
    """

    query: str
    session_id: str

    # Assembled sources (ordered by priority)
    sources: list[ContextSource] = field(default_factory=list)

    # Token budget breakdown
    budget: TokenBudget = field(default_factory=TokenBudget)
    used_tokens: int = 0

    # Raw references (for debugging / downstream)
    working_memory: list[MemoryRecord] = field(default_factory=list)
    episodic_memory: list[MemoryRecord] = field(default_factory=list)
    semantic_memory: list[MemoryRecord] = field(default_factory=list)
    calendar_hits: list[dict[str, Any]] = field(default_factory=list)
    obsidian_hits: list[dict[str, Any]] = field(default_factory=list)
    kb_hits: list[HybridHit] = field(default_factory=list)
    evomap_hits: list[Any] = field(default_factory=list)  # list[ScoredAtom]


# ── ContextAssembler ─────────────────────────────────────────────────

class ContextAssembler:
    """Builds LLM prompts from multi-source context.

    Usage::

        assembler = ContextAssembler(memory_manager, kb_hub)
        pack = assembler.build(
            query="项目进展如何?",
            session_id="sess_001",
            max_tokens=6000,
        )
        system_prompt = assembler.to_system_prompt(pack)
    """

    # Priority ordering (lower = higher priority)
    SOURCE_PRIORITY = {
        "semantic": 1,     # User profile / preferences
        "evomap": 2,       # EvoMap knowledge atoms (43K+ curated knowledge)
        "calendar": 3,     # Schedule awareness
        "obsidian": 4,     # Personal vault notes (real-time)
        "kb": 5,           # Knowledge base evidence
        "working": 6,       # Recent conversation
        "episodic": 7,      # Historical tasks
    }

    def __init__(
        self,
        memory_manager: MemoryManager,
        kb_hub: Any = None,  # KBHub, optional for KB integration
        evomap_db: Any = None,  # EvoMapDB, optional for EvoMap knowledge
        max_tokens: int = 8000,
    ) -> None:
        self._memory = memory_manager
        self._kb_hub = kb_hub
        self._evomap_db = evomap_db
        self._budget = TokenBudget(max_total=max_tokens)

    def build(
        self,
        query: str,
        session_id: str = "",
        *,
        working_limit: int = 10,
        episodic_limit: int = 5,
        semantic_limit: int = 3,
        kb_top_k: int = 5,
    ) -> ContextPack:
        """Assemble context from all sources.

        Args:
            query: User query string
            session_id: Session ID for working memory isolation
            working_limit: Max working memory records to fetch
            episodic_limit: Max episodic records to fetch
            semantic_limit: Max semantic records to fetch
            kb_top_k: Top-K KB hits to include

        Returns:
            ContextPack with all assembled sources
        """
        pack = ContextPack(
            query=query,
            session_id=session_id,
            budget=self._budget,
        )

        # 1. Working memory (recent conversation turns)
        working = self._memory.get_working_context(
            session_id=session_id,
            limit=working_limit,
        )
        pack.working_memory = working
        if working:
            content = self._format_working_memory(working)
            tokens = self._estimate_tokens(content)
            pack.sources.append(ContextSource(
                source_type="working",
                priority=self.SOURCE_PRIORITY["working"],
                content=content,
                token_count=tokens,
                metadata={"record_count": len(working)},
            ))

        # 2. Episodic memory (related historical tasks)
        episodic = self._memory.get_episodic(
            query=query,
            limit=episodic_limit,
        )
        pack.episodic_memory = episodic
        if episodic:
            content = self._format_episodic_memory(episodic)
            tokens = self._estimate_tokens(content)
            pack.sources.append(ContextSource(
                source_type="episodic",
                priority=self.SOURCE_PRIORITY["episodic"],
                content=content,
                token_count=tokens,
                metadata={"record_count": len(episodic)},
            ))

        # 3. Semantic memory (user profile, project knowledge)
        semantic = self._memory.get_semantic(domain="user_profile")
        if semantic:
            semantic = semantic[:semantic_limit]
        pack.semantic_memory = semantic
        if semantic:
            content = self._format_semantic_memory(semantic)
            tokens = self._estimate_tokens(content)
            pack.sources.append(ContextSource(
                source_type="semantic",
                priority=self.SOURCE_PRIORITY["semantic"],
                content=content,
                token_count=tokens,
                metadata={"record_count": len(semantic)},
            ))

        # 3.5. Calendar Events (if authenticated) — with 3s timeout
        if GoogleWorkspace:
            try:
                gw = GoogleWorkspace()
                # Use non-interactive token load to prevent hanging ContextAssembler
                if gw.load_token() and gw.is_authenticated() and "calendar" in gw._enabled:
                    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
                    from datetime import datetime, timedelta, timezone
                    now = datetime.now(timezone.utc)
                    end = now + timedelta(days=1)

                    def _fetch_calendar():
                        return gw.calendar_list_events(
                            time_min=now.isoformat(),
                            time_max=end.isoformat(),
                            max_results=5
                        )

                    with ThreadPoolExecutor(max_workers=1) as pool:
                        future = pool.submit(_fetch_calendar)
                        try:
                            events = future.result(timeout=3)  # 3s hard cap
                        except FuturesTimeout:
                            logger.warning("Calendar fetch timed out (3s cap), skipping")
                            events = []

                    pack.calendar_hits = events
                    if events:
                        content = self._format_calendar_hits(events)
                        tokens = self._estimate_tokens(content)
                        pack.sources.append(ContextSource(
                            source_type="calendar",
                            priority=self.SOURCE_PRIORITY["calendar"],
                            content=content,
                            token_count=tokens,
                            metadata={"hit_count": len(events)},
                        ))
            except Exception as e:
                logger.warning("Calendar injection failed: %s", e)

        # 3.7. Obsidian real-time search (supplements KB with latest notes)
        if ObsidianClient:
            try:
                obs = ObsidianClient()
                if obs.is_configured() and obs.ping():
                    results = obs.search(query, context_length=200)
                    if results:
                        pack.obsidian_hits = results[:3]
                        content = self._format_obsidian_hits(results[:3])
                        tokens = self._estimate_tokens(content)
                        pack.sources.append(ContextSource(
                            source_type="obsidian",
                            priority=self.SOURCE_PRIORITY["obsidian"],
                            content=content,
                            token_count=tokens,
                            metadata={"hit_count": len(results[:3])},
                        ))
            except Exception as e:
                logger.debug("Obsidian search skipped: %s", e)

        # 4. KB search (if KBHub available)
        if self._kb_hub:
            try:
                kb_hits = self._kb_hub.search(query, top_k=kb_top_k)
                pack.kb_hits = kb_hits
                if kb_hits:
                    content = self._format_kb_hits(kb_hits)
                    tokens = self._estimate_tokens(content)
                    pack.sources.append(ContextSource(
                        source_type="kb",
                        priority=self.SOURCE_PRIORITY["kb"],
                        content=content,
                        token_count=tokens,
                        metadata={"hit_count": len(kb_hits)},
                    ))
            except Exception as e:
                logger.warning("KB search failed: %s", e)

        # 4.5. EvoMap knowledge (43K curated atoms from EvoMap Knowledge DB)
        if self._evomap_db and evomap_retrieve:
            try:
                evomap_hits = evomap_retrieve(
                    self._evomap_db,
                    query,
                    config=runtime_evomap_retrieval_config(
                        surface=EvoMapRetrievalSurface.USER_HOT_PATH,
                    ) if runtime_evomap_retrieval_config and EvoMapRetrievalSurface else None,
                )
                pack.evomap_hits = evomap_hits
                if evomap_hits:
                    content = self._format_evomap_hits(evomap_hits)
                    tokens = self._estimate_tokens(content)
                    pack.sources.append(ContextSource(
                        source_type="evomap",
                        priority=self.SOURCE_PRIORITY["evomap"],
                        content=content,
                        token_count=tokens,
                        metadata={
                            "hit_count": len(evomap_hits),
                            "top_score": round(evomap_hits[0].final_score, 3)
                                if evomap_hits else 0,
                        },
                    ))
            except Exception as e:
                logger.warning("EvoMap search failed: %s", e)

        # 5. Apply token budget裁剪
        pack = self._apply_budget(pack)

        # Calculate total tokens used
        pack.used_tokens = sum(s.token_count for s in pack.sources)

        return pack

    def _apply_budget(self, pack: ContextPack) -> ContextPack:
        """Apply token budget constraints,裁剪 lower priority sources."""
        available = pack.budget.available_for_context()

        # Sort sources by priority
        pack.sources.sort(key=lambda s: s.priority)

        # Greedy allocation: include higher priority first
        used = 0
        kept_sources = []
        for source in pack.sources:
            if used + source.token_count <= available:
                kept_sources.append(source)
                used += source.token_count
            else:
                # Try to fit a truncated version
                remaining = available - used
                if remaining > 50:  # Only keep if meaningful
                    truncated = source.content[: remaining * 4]  # rough char estimate
                    truncated_source = ContextSource(
                        source_type=source.source_type,
                        priority=source.priority,
                        content=truncated,
                        token_count=remaining,
                        metadata={**source.metadata, "truncated": True},
                    )
                    kept_sources.append(truncated_source)
                    used += remaining

        pack.sources = kept_sources
        return pack

    def to_system_prompt(self, pack: ContextPack) -> str:
        """Convert ContextPack to a formatted system prompt.

        The prompt includes:
        - System instruction (not included in pack)
        - User profile context (semantic memory)
        - Relevant knowledge (KB hits)
        - Conversation history (working memory)
        - Relevant past tasks (episodic memory)
        """
        parts = []

        # Add each source type
        sources_by_type = {s.source_type: s for s in pack.sources}

        # Semantic (user profile) - highest priority context
        if "semantic" in sources_by_type:
            parts.append(f"## User Profile\n{sources_by_type['semantic'].content}")

        # Calendar (upcoming schedule)
        if "calendar" in sources_by_type:
            parts.append(f"## Upcoming Schedule (Next 24h)\n{sources_by_type['calendar'].content}")

        # KB evidence
        if "kb" in sources_by_type:
            parts.append(f"## Relevant Knowledge\n{sources_by_type['kb'].content}")

        # EvoMap knowledge atoms (43K curated knowledge)
        if "evomap" in sources_by_type:
            parts.append(f"## EvoMap Knowledge\n{sources_by_type['evomap'].content}")

        # Obsidian vault notes (real-time)
        if "obsidian" in sources_by_type:
            parts.append(f"## Obsidian Notes\n{sources_by_type['obsidian'].content}")

        # Working memory (conversation history)
        if "working" in sources_by_type:
            parts.append(f"## Recent Conversation\n{sources_by_type['working'].content}")

        # Episodic memory (past tasks)
        if "episodic" in sources_by_type:
            parts.append(f"## Past Tasks\n{sources_by_type['episodic'].content}")

        if not parts:
            return ""

        return "\n\n".join(parts)

    # ── Formatting Helpers ───────────────────────────────────────────

    def _format_working_memory(self, records: list[MemoryRecord]) -> str:
        """Format working memory as conversation turns."""
        lines = []
        for rec in reversed(records):  # Chronological order
            # #48 fix: use value.role ("user"/"assistant"), not source.agent ("advisor")
            role = rec.value.get("role", "user") if isinstance(rec.value, dict) else "user"
            value = rec.value
            if isinstance(value, dict):
                text = value.get("message", value.get("content", str(value)))
            else:
                text = str(value)
            lines.append(f"{role}: {text}")
        return "\n".join(lines)

    def _format_episodic_memory(self, records: list[MemoryRecord]) -> str:
        """Format episodic memory as task history."""
        lines = []
        for rec in records:
            key = rec.key
            value = rec.value
            if isinstance(value, dict):
                summary = value.get("summary", value.get("result", str(value)[:200]))
            else:
                summary = str(value)[:200]
            lines.append(f"- {key}: {summary}")
        return "\n".join(lines)

    def _format_semantic_memory(self, records: list[MemoryRecord]) -> str:
        """Format semantic memory as profile/preferences."""
        lines = []
        for rec in records:
            key = rec.key
            value = rec.value
            if isinstance(value, dict):
                items = [f"{k}: {v}" for k, v in value.items()]
                content = ", ".join(items)
            else:
                content = str(value)
            lines.append(f"- {key}: {content}")
        return "\n".join(lines)

    def _format_kb_hits(self, hits: list[HybridHit]) -> str:
        """Format KB hits as evidence list."""
        lines = []
        for i, hit in enumerate(hits, 1):
            lines.append(f"{i}. [{hit.title}]({hit.source_path})")
            if hit.snippet:
                lines.append(f"   {hit.snippet[:200]}")
        return "\n".join(lines)

    def _format_calendar_hits(self, events: list[dict[str, Any]]) -> str:
        """Format upcoming calendar events."""
        from datetime import datetime
        def _parse_google_dt(dt_str: str) -> str:
            if not dt_str: return "Unknown Time"
            try:
                # Basic ISO parse for readability
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                return dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                return dt_str

        lines = []
        for i, ev in enumerate(events, 1):
            start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", ""))
            end = ev.get("end", {}).get("dateTime", ev.get("end", {}).get("date", ""))
            summary = ev.get("summary", "Untitled Event")
            desc = ev.get("description", "").replace("\n", " ")[:100]

            line = f"{i}. {summary} ({_parse_google_dt(start)} to {_parse_google_dt(end)})"
            if desc:
                line += f" - {desc}"
            lines.append(line)
        return "\n".join(lines)

    def _format_obsidian_hits(self, results: list[dict[str, Any]]) -> str:
        """Format Obsidian search results as context snippets."""
        lines = []
        for i, hit in enumerate(results, 1):
            filename = hit.get("filename", hit.get("path", "Unknown"))
            # Obsidian search returns matches with context
            matches = hit.get("matches", [])
            if matches:
                snippet = " ".join(
                    m.get("match", {}).get("content", "")[:200]
                    for m in matches[:2]
                ).strip()
            else:
                snippet = hit.get("content", "")[:300]

            if snippet:
                lines.append(f"{i}. [{filename}]: {snippet}")
        return "\n".join(lines) if lines else ""

    def _format_evomap_hits(self, hits: list) -> str:
        """Format EvoMap ScoredAtom results as context snippets."""
        lines = []
        for i, sa in enumerate(hits, 1):
            atom = sa.atom
            score_label = f"[score={sa.final_score:.2f}]"
            q = atom.question[:120]
            # Truncate answer to fit budget
            a = atom.answer[:400] if atom.answer else ""
            if len(atom.answer) > 400:
                a += "..."
            type_emoji = {
                "qa": "❓", "decision": "🎯", "procedure": "📋",
                "troubleshooting": "🔧", "lesson": "💡",
            }.get(atom.atom_type, "📄")
            lines.append(f"{i}. {type_emoji} {q} {score_label}")
            if a:
                lines.append(f"   {a}")
        return "\n".join(lines)

    def _estimate_tokens(self, text: str) -> int:
        """#52 fix: CJK-aware token estimation.

        CJK characters ≈ 1.5 tokens each; ASCII ≈ 0.25 tokens/char.
        """
        cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        ascii_count = len(text) - cjk_count
        return int(cjk_count * 1.5) + ascii_count // 4
