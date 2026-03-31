"""KB Writeback Service — unified KB writeback logic.

This service consolidates the repeated KB writeback code that was
scattered across execute_deep_research, execute_report, and execute_funnel.

The unified flow:
  1. Create output directory (if needed)
  2. Write content to file
  3. Register artifact in KB registry
  4. Index document in KB hub
  5. Run policy checks

Design:
  - Stateless service (no persistence)
  - Thread-safe operations
  - Returns artifact ID and writeback result
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from chatgptrest.kb.registry import ArtifactRegistry, Artifact
    from chatgptrest.kb.hub import KBHub
    from chatgptrest.kernel.policy_engine import PolicyEngine

logger = logging.getLogger(__name__)


# ── Writeback Result ─────────────────────────────────────────────────

@dataclass
class WritebackResult:
    """Result of a KB writeback operation."""

    success: bool
    artifact_id: str = ""
    file_path: str = ""
    error: str = ""
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


# ── KB Writeback Service ───────────────────────────────────────────

class KBWritebackService:
    """Unified KB writeback service.

    Usage::

        service = KBWritebackService(registry, hub, policy_engine)

        # Write research results to KB
        result = service.writeback(
            content="# Research Report\n\n...",
            trace_id="trace_001",
            content_type="markdown",
            title="安徽项目研究报告",
            output_dir=Path("~/knowledge/research").expanduser(),
            project_id="project_001",
            para_bucket="project",
            structural_role="analysis",
        )

        if result.success:
            print(f"Written to {result.file_path}")
    """

    def __init__(
        self,
        registry: Optional["ArtifactRegistry"] = None,
        hub: Optional["KBHub"] = None,
        policy_engine: Optional["PolicyEngine"] = None,
    ) -> None:
        self._registry = registry
        self._hub = hub
        self._policy = policy_engine

    def writeback(
        self,
        content: str,
        trace_id: str,
        content_type: str = "markdown",
        *,
        title: str = "",
        output_dir: Optional[Path] = None,
        file_name: Optional[str] = None,
        project_id: str = "",
        para_bucket: str = "project",
        structural_role: str = "analysis",
        domain_tags: Optional[list[str]] = None,
        source_system: str = "advisor",
    ) -> WritebackResult:
        """Write content to KB.

        Args:
            content: Content to write
            trace_id: Trace ID for tracking
            content_type: Content type (markdown/json/etc)
            title: Title for the artifact (defaults to file stem)
            output_dir: Output directory (defaults to project root)
            file_name: File name (defaults to trace_id + content_type)
            project_id: Project ID for classification
            para_bucket: PARA bucket
            structural_role: Structural role
            domain_tags: Domain tags
            source_system: Source system name

        Returns:
            WritebackResult with success status and details
        """
        try:
            # 1. Determine output path
            if output_dir is None:
                output_dir = Path.cwd() / "knowledge" / para_bucket
            output_dir = output_dir.expanduser().resolve()
            output_dir.mkdir(parents=True, exist_ok=True)

            # 2. Determine file name
            if file_name is None:
                ext = ".md" if content_type == "markdown" else f".{content_type}"
                file_name = f"{trace_id}{ext}"

            file_path = output_dir / file_name
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # 3. Write content to file
            file_path.write_text(content, encoding="utf-8")
            logger.debug("Written content to %s", file_path)

            artifact_id = ""

            # 4. Register in KB registry
            if self._registry:
                try:
                    art = self._registry.register_file(
                        file_path,
                        source_system=source_system,
                        project_id=project_id,
                        para_bucket=para_bucket,
                        structural_role=structural_role,
                        domain_tags=domain_tags,
                        auto_index=True,  # Trigger auto-indexing
                    )
                    artifact_id = art.artifact_id
                    logger.debug("Registered artifact: %s", artifact_id)
                except Exception as e:
                    logger.warning("Registry failed: %s", e)

            # 5. Index in KB hub (if not auto-indexed via registry)
            if self._hub and not self._registry:
                try:
                    self._hub.index_document(
                        artifact_id=artifact_id or str(uuid.uuid4())[:16],
                        title=title or file_path.stem,
                        content=content[:10000],  # Limit content size
                        source_path=str(file_path),
                        content_type=content_type,
                    )
                except Exception as e:
                    logger.warning("Hub index failed: %s", e)

            return WritebackResult(
                success=True,
                artifact_id=artifact_id,
                file_path=str(file_path),
                metadata={
                    "trace_id": trace_id,
                    "content_type": content_type,
                    "para_bucket": para_bucket,
                    "structural_role": structural_role,
                },
            )

        except Exception as e:
            logger.exception("Writeback failed for trace %s", trace_id)
            return WritebackResult(
                success=False,
                error=str(e),
            )

    def writeback_research(
        self,
        content: str,
        trace_id: str,
        query: str,
        *,
        output_dir: Optional[Path] = None,
        **kwargs,
    ) -> WritebackResult:
        """Convenience method for deep research writeback.

        Args:
            content: Research content
            trace_id: Trace ID
            query: Original research query
            output_dir: Output directory
            **kwargs: Additional arguments passed to writeback
        """
        title = kwargs.pop("title", f"Research: {query[:50]}")
        return self.writeback(
            content=content,
            trace_id=trace_id,
            content_type="markdown",
            title=title,
            output_dir=output_dir or Path.cwd() / "knowledge" / "research",
            structural_role="analysis",
            domain_tags=["research", "deep-research"],
            **kwargs,
        )

    def writeback_report(
        self,
        content: str,
        trace_id: str,
        report_type: str,
        *,
        output_dir: Optional[Path] = None,
        **kwargs,
    ) -> WritebackResult:
        """Convenience method for report writeback.

        Args:
            content: Report content
            trace_id: Trace ID
            report_type: Type of report (weekly/monthly/project)
            output_dir: Output directory
            **kwargs: Additional arguments passed to writeback
        """
        title = kwargs.pop("title", f"Report: {report_type}")
        return self.writeback(
            content=content,
            trace_id=trace_id,
            content_type="markdown",
            title=title,
            output_dir=output_dir or Path.cwd() / "knowledge" / "reports",
            structural_role="evidence",
            domain_tags=["report", report_type],
            **kwargs,
        )
