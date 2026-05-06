from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    import yaml
except Exception:  # pragma: no cover - repo runtime should already provide PyYAML
    yaml = None


DEFAULT_PLANNING_ROOT = Path("/vol1/1000/projects/planning")
DEFAULT_STALE_DAYS = 30
PROJECT_CONTEXT_SOFT_MAX_CHARS = 6000
REQUIRED_FRONTMATTER_FIELDS = (
    "project",
    "alias",
    "project_id",
    "planning_base",
    "owner",
    "last_reviewed_at",
    "authority_docs",
    "frozen_facts",
    "style_rules",
)
REQUIRED_BODY_HEADINGS = ("当前权威文档", "当前阶段")
ACTION_BODY_HEADINGS = ("当前待推进动作", "当前待执行修改", "当前待办", "下一步")


@dataclass(frozen=True)
class AuthorityDocumentStatus:
    path: str
    exists: bool
    non_empty: bool
    size_bytes: int
    modified_at: str
    age_days: float | None
    stale_status: str


@dataclass(frozen=True)
class AuthorityConflictPreview:
    source_type: str
    title: str
    authority_type: str
    authority_text: str
    conflicting_excerpt: str
    shared_terms: list[str]
    reason: str


@dataclass(frozen=True)
class AuthorityAnchor:
    project_id: str
    project: str
    alias: str
    owner: str
    last_reviewed_at: str
    stale_threshold_days: int
    stale_status: str
    anchor_path: str
    planning_base: str
    frozen_facts: list[str]
    style_rules: list[str]
    pinned_authority_inputs: list[str]
    current_phase_framing: str
    schema_gaps: list[str]
    missing_docs: list[str]
    authority_docs: list[AuthorityDocumentStatus]
    project_context: str

    def to_prompt_text(self) -> str:
        lines: list[str] = [
            f"- Project: {self.project}",
            f"- Project ID: {self.project_id}",
            f"- Owner: {self.owner}",
            f"- Last reviewed: {self.last_reviewed_at or 'unknown'}",
            f"- Anchor path: {self.anchor_path}",
            f"- Anchor freshness: {self.stale_status}",
        ]
        if self.current_phase_framing:
            lines.append("- Current phase framing:")
            for item in self.current_phase_framing.splitlines():
                if item.strip():
                    lines.append(f"  {item.strip()}")
        if self.frozen_facts:
            lines.append("- Frozen facts: " + "; ".join(self.frozen_facts))
        if self.style_rules:
            lines.append("- Style rules: " + "; ".join(self.style_rules))
        if self.pinned_authority_inputs:
            lines.append("- Pinned authority docs: " + ", ".join(self.pinned_authority_inputs))
        if self.project_context:
            lines.append("- Project context:")
            for item in self.project_context.splitlines():
                if item.strip():
                    lines.append(f"  {item}")
        return "\n".join(lines)

    def to_runtime_metadata(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project": self.project,
            "alias": self.alias,
            "owner": self.owner,
            "last_reviewed_at": self.last_reviewed_at,
            "review_age_days": _review_age_days(self.last_reviewed_at),
            "stale_threshold_days": self.stale_threshold_days,
            "stale_status": self.stale_status,
            "anchor_path": self.anchor_path,
            "planning_base": self.planning_base,
            "pinned_authority_inputs": list(self.pinned_authority_inputs),
            "current_phase_framing": self.current_phase_framing,
            "schema_gaps": list(self.schema_gaps),
            "missing_docs": list(self.missing_docs),
            "authority_docs": [doc.__dict__.copy() for doc in self.authority_docs],
        }


def inspect_authority_anchor_path(
    path: str | Path,
    *,
    stale_days: int = DEFAULT_STALE_DAYS,
) -> dict[str, Any]:
    context_path = Path(path)
    frontmatter, body = _parse_frontmatter_and_body(context_path)
    anchor = load_authority_anchor_from_path(context_path, stale_days=stale_days)

    required_frontmatter = {
        field: _frontmatter_field_present(frontmatter, field)
        for field in REQUIRED_FRONTMATTER_FIELDS
    }
    required_sections = {
        heading: bool(_extract_markdown_section(body, heading))
        for heading in REQUIRED_BODY_HEADINGS
    }
    required_sections["action_section"] = any(
        _extract_markdown_section(body, heading) for heading in ACTION_BODY_HEADINGS
    )

    errors: list[str] = []
    warnings: list[str] = []
    if not required_frontmatter["project"]:
        errors.append("missing_project_field")
    if not required_frontmatter["alias"]:
        errors.append("missing_alias_field")
    if not required_frontmatter["project_id"]:
        errors.append("missing_project_id_field")
    if not required_frontmatter["planning_base"]:
        errors.append("missing_planning_base_field")
    if not required_frontmatter["owner"] or anchor.owner == "unassigned":
        errors.append("missing_owner_field")
    if not required_frontmatter["last_reviewed_at"]:
        errors.append("missing_last_reviewed_at_field")
    elif _parse_datetime(anchor.last_reviewed_at) is None:
        errors.append("unparseable_last_reviewed_at")
    if not required_frontmatter["authority_docs"]:
        errors.append("missing_authority_docs_field")
    if not required_frontmatter["frozen_facts"] or not anchor.frozen_facts:
        errors.append("missing_frozen_facts")
    if not required_frontmatter["style_rules"] or not anchor.style_rules:
        errors.append("missing_style_rules")
    if not required_sections["当前权威文档"]:
        errors.append("missing_current_authority_docs_section")
    if not required_sections["当前阶段"]:
        errors.append("missing_current_phase_section")
    if not required_sections["action_section"]:
        errors.append("missing_action_section")
    if not anchor.project_context.strip():
        errors.append("missing_project_context_body")

    if anchor.stale_status == "stale":
        warnings.append("stale_anchor")
    elif anchor.stale_status in {"unknown", "unparseable"}:
        warnings.append("unreliable_anchor_freshness")
    if anchor.missing_docs:
        warnings.append("authority_docs_missing")
    if any(doc.stale_status == "stale" for doc in anchor.authority_docs):
        warnings.append("authority_docs_stale")
    if len(anchor.project_context) > PROJECT_CONTEXT_SOFT_MAX_CHARS:
        warnings.append("project_context_body_too_large")

    lint_status = "fail" if errors else "warn" if warnings else "pass"
    return {
        "project_id": anchor.project_id,
        "project": anchor.project,
        "alias": anchor.alias,
        "anchor_path": anchor.anchor_path,
        "owner": anchor.owner,
        "last_reviewed_at": anchor.last_reviewed_at,
        "review_age_days": _review_age_days(anchor.last_reviewed_at),
        "stale_status": anchor.stale_status,
        "schema_gaps": list(anchor.schema_gaps),
        "missing_docs": list(anchor.missing_docs),
        "required_frontmatter": required_frontmatter,
        "required_sections": required_sections,
        "frontmatter_keys": sorted(str(key) for key in frontmatter.keys()),
        "counts": {
            "authority_doc_count": len(anchor.authority_docs),
            "frozen_fact_count": len(anchor.frozen_facts),
            "style_rule_count": len(anchor.style_rules),
            "project_context_chars": len(anchor.project_context),
        },
        "errors": errors,
        "warnings": warnings,
        "lint_status": lint_status,
        "ok": not errors,
    }


def load_authority_anchor(
    project_id: str,
    *,
    planning_root: Path = DEFAULT_PLANNING_ROOT,
    stale_days: int = DEFAULT_STALE_DAYS,
) -> AuthorityAnchor | None:
    project_key = _normalize_key(project_id)
    if not project_key:
        return None
    context_path = _authority_index(str(planning_root)).get(project_key)
    if context_path is None:
        return None
    return load_authority_anchor_from_path(context_path, stale_days=stale_days)


def load_authority_anchor_from_path(
    path: str | Path,
    *,
    stale_days: int = DEFAULT_STALE_DAYS,
) -> AuthorityAnchor:
    context_path = Path(path)
    frontmatter, body = _parse_frontmatter_and_body(context_path)
    planning_base = str(frontmatter.get("planning_base") or context_path.parent)
    alias = str(frontmatter.get("alias") or "").strip()
    project_id = str(frontmatter.get("project_id") or alias or frontmatter.get("project") or "").strip()
    project = str(frontmatter.get("project") or project_id or alias).strip()
    last_reviewed_at = str(frontmatter.get("last_reviewed_at") or frontmatter.get("updated") or "").strip()
    owner = str(frontmatter.get("owner") or "").strip() or "unassigned"
    frozen_facts = _string_list(frontmatter.get("frozen_facts"))
    style_rules = _string_list(frontmatter.get("style_rules"))
    authority_doc_paths = _resolve_authority_doc_paths(
        frontmatter.get("authority_docs"),
        planning_base=Path(planning_base),
    )
    authority_docs = [_status_for_doc(path=item, stale_days=stale_days) for item in authority_doc_paths]
    missing_docs = [item.path for item in authority_docs if not item.exists or not item.non_empty]
    stale_status = _stale_status_for_text(last_reviewed_at, stale_days=stale_days)
    current_phase_framing = _extract_current_phase_framing(frontmatter=frontmatter, body=body)
    schema_gaps: list[str] = []
    if owner == "unassigned":
        schema_gaps.append("missing_owner")
    if not last_reviewed_at:
        schema_gaps.append("missing_last_reviewed_at")
    if not authority_doc_paths:
        schema_gaps.append("missing_pinned_authority_inputs")
    if not current_phase_framing:
        schema_gaps.append("missing_current_phase_framing")
    return AuthorityAnchor(
        project_id=project_id or alias or project,
        project=project or alias or project_id,
        alias=alias or project_id or project,
        owner=owner,
        last_reviewed_at=last_reviewed_at,
        stale_threshold_days=stale_days,
        stale_status=stale_status,
        anchor_path=str(context_path),
        planning_base=planning_base,
        frozen_facts=frozen_facts,
        style_rules=style_rules,
        pinned_authority_inputs=authority_doc_paths,
        current_phase_framing=current_phase_framing,
        schema_gaps=schema_gaps,
        missing_docs=missing_docs,
        authority_docs=authority_docs,
        project_context=body.strip(),
    )


def detect_authority_conflicts(
    anchor: AuthorityAnchor,
    *,
    blocks: Sequence[Any],
) -> list[AuthorityConflictPreview]:
    previews: list[AuthorityConflictPreview] = []
    for block in blocks:
        source_type = str(getattr(block, "source_type", "") or "")
        if source_type in {"authority", "policy"}:
            continue
        block_text = str(getattr(block, "text", "") or "").strip()
        if not block_text:
            continue
        block_title = str(getattr(block, "title", source_type.replace("_", " ").title()) or source_type).strip()
        block_excerpt = _clip(block_text)
        for text in anchor.frozen_facts:
            preview = _match_conflict(
                authority_type="frozen_fact",
                authority_text=text,
                block_text=block_text,
                source_type=source_type,
                title=block_title,
                excerpt=block_excerpt,
            )
            if preview is not None:
                previews.append(preview)
        for text in anchor.style_rules:
            preview = _match_style_conflict(
                authority_text=text,
                block_text=block_text,
                source_type=source_type,
                title=block_title,
                excerpt=block_excerpt,
            )
            if preview is not None:
                previews.append(preview)
    unique: list[AuthorityConflictPreview] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in previews:
        key = (item.source_type, item.title, item.authority_type, item.authority_text)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


@lru_cache(maxsize=8)
def _authority_index(planning_root: str) -> dict[str, str]:
    root = Path(planning_root)
    index: dict[str, str] = {}
    for anchor in sorted(root.rglob("_project_context.md")):
        try:
            frontmatter, _body = _parse_frontmatter_and_body(anchor)
        except Exception:
            continue
        keys = {
            str(frontmatter.get("project_id") or "").strip(),
            str(frontmatter.get("alias") or "").strip(),
            str(frontmatter.get("project") or "").strip(),
        }
        for key in keys:
            normalized = _normalize_key(key)
            if normalized:
                index[normalized] = str(anchor)
    return index


def _parse_frontmatter_and_body(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path} does not start with YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"{path} missing closing YAML frontmatter")
    if yaml is None:
        raise RuntimeError("pyyaml is required for authority-anchor parsing")
    loaded = yaml.safe_load(text[4:end])
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} frontmatter is not a mapping")
    return loaded, text[end + 5 :].strip()


def _normalize_key(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().lower())


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, Iterable):
        output: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                output.append(text)
        return output
    return []


def _frontmatter_field_present(frontmatter: dict[str, Any], field: str) -> bool:
    value = frontmatter.get(field)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Iterable):
        return any(str(item).strip() for item in value)
    return True


def _resolve_authority_doc_paths(raw: Any, *, planning_base: Path) -> list[str]:
    results: list[str] = []
    for item in _string_list(raw):
        path = Path(item)
        if not path.is_absolute():
            path = planning_base / path
        results.append(str(path))
    return results


def _status_for_doc(*, path: str, stale_days: int) -> AuthorityDocumentStatus:
    doc_path = Path(path)
    exists = doc_path.exists()
    size_bytes = doc_path.stat().st_size if exists else 0
    modified_at = _iso_from_ts(doc_path.stat().st_mtime) if exists else ""
    age_days = _age_days(doc_path.stat().st_mtime) if exists else None
    return AuthorityDocumentStatus(
        path=str(doc_path),
        exists=exists,
        non_empty=size_bytes > 0,
        size_bytes=size_bytes,
        modified_at=modified_at,
        age_days=age_days,
        stale_status=_stale_status(age_days=age_days, stale_days=stale_days),
    )


def _iso_from_ts(ts: float | int | None) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(float(ts), UTC).isoformat()


def _age_days(ts: float | int | None) -> float | None:
    if not ts:
        return None
    delta = datetime.now(UTC) - datetime.fromtimestamp(float(ts), UTC)
    return round(max(delta.total_seconds(), 0.0) / 86400.0, 3)


def _stale_status(*, age_days: float | None, stale_days: int) -> str:
    if age_days is None:
        return "unknown"
    return "stale" if age_days > stale_days else "fresh"


def _stale_status_for_text(value: str, *, stale_days: int) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return "unknown" if not value.strip() else "unparseable"
    return _stale_status(age_days=_age_days(parsed.timestamp()), stale_days=stale_days)


def _parse_datetime(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    for raw in (text, text.replace("Z", "+00:00")):
        try:
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except Exception:
            continue
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
        return parsed.replace(tzinfo=UTC)
    except Exception:
        return None


def _review_age_days(value: str) -> float | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    delta = datetime.now(UTC) - parsed
    return round(max(delta.total_seconds(), 0.0) / 86400.0, 3)


def _extract_current_phase_framing(*, frontmatter: dict[str, Any], body: str) -> str:
    explicit = str(frontmatter.get("current_phase_framing") or "").strip()
    if explicit:
        return explicit
    section = _extract_markdown_section(body, "当前阶段")
    if section:
        return section
    current_focus = _string_list(frontmatter.get("current_focus"))
    if current_focus:
        return "\n".join(f"- {item}" for item in current_focus)
    return ""


def _extract_markdown_section(body: str, heading: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)",
        re.MULTILINE,
    )
    match = pattern.search(body)
    if not match:
        return ""
    return match.group(1).strip()


_NEGATIVE_MARKERS = (
    "不能",
    "不可",
    "不要",
    "未确认",
    "blocked",
    "forbidden",
    "stale",
    "未冻结",
)
_POSITIVE_MARKERS = (
    "可以",
    "可行",
    "已确认",
    "confirmed",
    "ready",
    "final",
    "unblocked",
    "已冻结",
)


def _match_conflict(
    *,
    authority_type: str,
    authority_text: str,
    block_text: str,
    source_type: str,
    title: str,
    excerpt: str,
) -> AuthorityConflictPreview | None:
    if "contradict" in block_text.lower() or "冲突" in block_text:
        shared_terms = sorted(_shared_terms(authority_text, block_text))[:6]
        return AuthorityConflictPreview(
            source_type=source_type,
            title=title,
            authority_type=authority_type,
            authority_text=authority_text,
            conflicting_excerpt=excerpt,
            shared_terms=shared_terms,
            reason="lower-layer text explicitly self-labels a contradiction",
        )
    authority_polarity = _polarity(authority_text)
    block_polarity = _polarity(block_text)
    if not authority_polarity or not block_polarity or authority_polarity == block_polarity:
        return None
    shared_terms = sorted(_shared_terms(authority_text, block_text))
    if not shared_terms:
        return None
    return AuthorityConflictPreview(
        source_type=source_type,
        title=title,
        authority_type=authority_type,
        authority_text=authority_text,
        conflicting_excerpt=excerpt,
        shared_terms=shared_terms[:6],
        reason="shared terms with opposite polarity markers",
    )


def _match_style_conflict(
    *,
    authority_text: str,
    block_text: str,
    source_type: str,
    title: str,
    excerpt: str,
) -> AuthorityConflictPreview | None:
    normalized_rule = authority_text.replace(" ", "")
    if ("不是而是" in normalized_rule or ("不是" in normalized_rule and "而是" in normalized_rule)) and "不是" in block_text and "而是" in block_text:
        return AuthorityConflictPreview(
            source_type=source_type,
            title=title,
            authority_type="style_rule",
            authority_text=authority_text,
            conflicting_excerpt=excerpt,
            shared_terms=["不是", "而是"],
            reason="style rule forbids the '不是…而是…' structure but lower-layer text still uses it",
        )
    return None


def _polarity(text: str) -> str | None:
    lowered = f" {text.lower()} "
    normalized = lowered
    for marker in (" not confirmed ", " not ready ", " not final ", " remains blocked ", " still blocked "):
        normalized = normalized.replace(marker, " ")
    has_negative = " not " in lowered or any(marker in normalized for marker in _NEGATIVE_MARKERS)
    has_positive = any(marker in normalized for marker in _POSITIVE_MARKERS)
    if has_negative and not has_positive:
        return "negative"
    if has_positive and not has_negative:
        return "positive"
    return None


def _shared_terms(left: str, right: str) -> set[str]:
    return _meaningful_terms(left) & _meaningful_terms(right)


def _meaningful_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for token in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", text):
        if re.fullmatch(r"[A-Za-z0-9_]+", token):
            lowered = token.lower()
            if len(lowered) >= 3:
                terms.add(lowered)
            continue
        if len(token) <= 2:
            terms.add(token)
            continue
        for candidate in re.findall(r"[\u4e00-\u9fff]{2,4}", token):
            if len(candidate) >= 2:
                terms.add(candidate)
        for idx in range(0, len(token) - 1):
            for size in (2, 3, 4):
                if idx + size <= len(token):
                    terms.add(token[idx : idx + size])
    return {term for term in terms if term and term not in {"项目", "当前", "阶段", "需要", "should"}}


def _clip(text: str, limit: int = 240) -> str:
    stripped = " ".join(text.split())
    if len(stripped) <= limit:
        return stripped
    return f"{stripped[: limit - 3]}..."
