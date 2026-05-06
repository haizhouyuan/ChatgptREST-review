#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
from zipfile import ZipFile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

SKILL_DIR = Path("/vol1/1000/home-yuanhaizhou/.codex-shared/skills/minimax-skills/skills/minimax-xlsx")
UNPACK_SCRIPT = SKILL_DIR / "scripts" / "xlsx_unpack.py"
PACK_SCRIPT = SKILL_DIR / "scripts" / "xlsx_pack.py"

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
NS_X14AC = "http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac"
NS_XR = "http://schemas.microsoft.com/office/spreadsheetml/2014/revision"
NS_XR2 = "http://schemas.microsoft.com/office/spreadsheetml/2015/revision2"
NS_XR3 = "http://schemas.microsoft.com/office/spreadsheetml/2016/revision3"
NS = {"main": NS_MAIN, "pkg": NS_PKG}
IGNORABLE_NAMESPACE_URIS = {
    "x14ac": NS_X14AC,
    "xr": NS_XR,
    "xr2": NS_XR2,
    "xr3": NS_XR3,
}

ET.register_namespace("", NS_MAIN)
ET.register_namespace("mc", NS_MC)
ET.register_namespace("x14ac", NS_X14AC)
ET.register_namespace("xr", NS_XR)
ET.register_namespace("xr2", NS_XR2)
ET.register_namespace("xr3", NS_XR3)
_SKIP_ASSIGNMENT = object()

CELL_ASSIGNMENT_RE = re.compile(r"^\s*-\s*`([A-Z]+[0-9]+(?::[A-Z]+[0-9]+)?)`\s*[：:]\s*(.+?)\s*$")
YAML_CELL_RE = re.compile(r"^\s*([A-Z]+[0-9]+(?::[A-Z]+[0-9]+)?)\s*:\s*(.*?)\s*$")
INLINE_ASSIGNMENT_RE = re.compile(r"([A-Z]+[0-9]+(?::[A-Z]+[0-9]+)?)\s*=\s*(.*?)(?=(?:\s+\|\s+[A-Z]+[0-9]+(?::[A-Z]+[0-9]+)?\s*=)|$)")
MERGE_DIRECTIVE_RE = re.compile(r"^\s*@MERGE\s+([A-Z]+[0-9]+:[A-Z]+[0-9]+)\s*$", re.IGNORECASE)
STYLE_COPY_DIRECTIVE_RE = re.compile(r"^\s*@STYLE\s+([A-Z]+[0-9]+)\s*<-\s*([A-Z]+[0-9]+)\s*$", re.IGNORECASE)
ROW_HEIGHT_DIRECTIVE_RE = re.compile(r"^\s*@ROW\s+([0-9]+)\s+HEIGHT\s+([0-9]+(?:\.[0-9]+)?)\s*$", re.IGNORECASE)


def _display_width(text: str) -> int:
    width = 0
    for ch in str(text or ""):
        width += 2 if unicodedata.east_asian_width(ch) in {"W", "F"} else 1
    return width


def _load_shared_strings_from_archive(archive: ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values: list[str] = []
    for si in root.findall(f"{{{NS_MAIN}}}si"):
        parts: list[str] = []
        for node in si.iter():
            if node.tag == f"{{{NS_MAIN}}}t" and node.text is not None:
                parts.append(node.text)
        values.append("".join(parts))
    return values


def _column_index(col_letters: str) -> int:
    value = 0
    for ch in col_letters:
        value = value * 26 + (ord(ch) - 64)
    return value


def _template_sheet_snapshot_from_archive(
    *,
    workbook_path: Path,
    sheet_name: str,
    refs: list[str],
    columns: tuple[str, ...],
) -> tuple[dict[str, Any], dict[str, float]]:
    requested = {ref.upper() for ref in refs}
    with ZipFile(workbook_path) as archive:
        shared_strings = _load_shared_strings_from_archive(archive)
        sheet_target = _resolve_sheet_target_in_archive(archive, sheet_name)
        sheet_root = ET.fromstring(archive.read(sheet_target))
    values: dict[str, Any] = {}
    for cell in sheet_root.findall(f".//{{{NS_MAIN}}}c"):
        ref = str(cell.attrib.get("r") or "").upper()
        if ref not in requested:
            continue
        value_node = cell.find(f"{{{NS_MAIN}}}v")
        if value_node is None or value_node.text is None:
            values[ref] = None
            continue
        raw = value_node.text
        if cell.attrib.get("t") == "s":
            try:
                values[ref] = shared_strings[int(raw)]
            except Exception:
                values[ref] = raw
        else:
            values[ref] = raw
    widths: dict[str, float] = {col: 10.0 for col in columns}
    cols_root = sheet_root.find(f"{{{NS_MAIN}}}cols")
    if cols_root is not None:
        for col_node in cols_root.findall(f"{{{NS_MAIN}}}col"):
            min_idx = int(col_node.attrib.get("min", "0"))
            max_idx = int(col_node.attrib.get("max", "0"))
            width = float(col_node.attrib.get("width", "10") or 10.0)
            for col in columns:
                idx = _column_index(col)
                if min_idx <= idx <= max_idx:
                    widths[col] = width
    return values, widths


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize a performance-sheet draft into an existing xlsx template.")
    parser.add_argument("--template", required=True, help="Existing xlsx template to fill")
    parser.add_argument("--answer-file", required=True, help="Text/markdown answer file containing cell assignments")
    parser.add_argument("--output", required=True, help="Output xlsx path")
    parser.add_argument("--sheet-name", default="绩效考核表", help="Target sheet name")
    parser.add_argument(
        "--autofit-performance-rows",
        action="store_true",
        help="Auto-compact KPI rows 5:9 based on current cell content",
    )
    return parser.parse_args()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _load_answer_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".json":
        payload = json.loads(text)
        if isinstance(payload, dict):
            answer = payload.get("answer")
            if isinstance(answer, str):
                return answer
    return text


def _expand_range(ref: str) -> list[str]:
    if ":" not in ref:
        return [ref]
    start, end = ref.split(":", 1)
    start_col = re.match(r"([A-Z]+)", start).group(1)  # type: ignore[union-attr]
    end_col = re.match(r"([A-Z]+)", end).group(1)  # type: ignore[union-attr]
    start_row = int(re.search(r"([0-9]+)$", start).group(1))  # type: ignore[union-attr]
    end_row = int(re.search(r"([0-9]+)$", end).group(1))  # type: ignore[union-attr]
    if len(start_col) != 1 or len(end_col) != 1:
        raise ValueError(f"only single-letter columns are supported for ranges: {ref}")
    expanded: list[str] = []
    for row in range(start_row, end_row + 1):
        for col in range(ord(start_col), ord(end_col) + 1):
            expanded.append(f"{chr(col)}{row}")
    return expanded


def _parse_assignments(answer_text: str) -> tuple[dict[str, str | None], dict[str, Any]]:
    assignments: dict[str, str | None] = {}
    bullet_assignments: dict[str, str | None] = {}
    directives: dict[str, Any] = {
        "merge_ranges": [],
        "style_copies": [],
        "row_heights": {},
    }
    lines = str(answer_text or "").splitlines()

    def resolve_value(value: str) -> str | None | object:
        normalized = value.strip()
        if normalized.startswith(("`", "'")) and normalized.endswith(("`", "'")) and len(normalized) >= 2:
            normalized = normalized[1:-1].strip()
        if normalized.startswith('"') and normalized.endswith('"') and len(normalized) >= 2:
            normalized = normalized[1:-1]
        if normalized in {"本轮留空", "留空", "空", ""}:
            return None
        if normalized.startswith(("留空", "先留空", "暂留空")):
            return None
        if normalized.startswith(("暂不填写", "先不填写")):
            return None
        if normalized.startswith(("保留", "保持模板原样")):
            return _SKIP_ASSIGNMENT
        return normalized

    def assign_value(cell_ref: str, raw_value: str) -> None:
        resolved = resolve_value(raw_value)
        if resolved is _SKIP_ASSIGNMENT:
            return
        for expanded in _expand_range(cell_ref):
            assignments[expanded] = resolved

    for raw_line in lines:
        match = CELL_ASSIGNMENT_RE.match(raw_line)
        if not match:
            continue
        cell_ref, raw_value = match.groups()
        resolved = resolve_value(raw_value)
        if resolved is _SKIP_ASSIGNMENT:
            continue
        for expanded in _expand_range(cell_ref):
            bullet_assignments[expanded] = resolved

    in_fence = False
    pending_cell: str | None = None
    pending_lines: list[str] = []

    def flush_pending() -> None:
        nonlocal pending_cell, pending_lines
        if pending_cell is None:
            return
        value = "\n".join(item.rstrip() for item in pending_lines).strip()
        assign_value(pending_cell, value)
        pending_cell = None
        pending_lines = []

    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            if in_fence:
                flush_pending()
            in_fence = not in_fence
            continue
        if not in_fence:
            continue
        inline_matches = INLINE_ASSIGNMENT_RE.findall(raw_line)
        if inline_matches:
            flush_pending()
            for cell_ref, raw_value in inline_matches:
                assign_value(cell_ref, raw_value)
            continue
        merge_match = MERGE_DIRECTIVE_RE.match(raw_line)
        if merge_match:
            directives["merge_ranges"].append(str(merge_match.group(1)).upper())
            continue
        style_match = STYLE_COPY_DIRECTIVE_RE.match(raw_line)
        if style_match:
            directives["style_copies"].append(
                {
                    "target": str(style_match.group(1)).upper(),
                    "source": str(style_match.group(2)).upper(),
                }
            )
            continue
        row_height_match = ROW_HEIGHT_DIRECTIVE_RE.match(raw_line)
        if row_height_match:
            directives["row_heights"][int(row_height_match.group(1))] = float(row_height_match.group(2))
            continue
        match = YAML_CELL_RE.match(raw_line)
        if match:
            flush_pending()
            cell_ref, raw_value = match.groups()
            value = raw_value.strip()
            if value == "|":
                pending_cell = cell_ref
                pending_lines = []
                continue
            assign_value(cell_ref, value)
            continue
        if pending_cell is not None:
            pending_lines.append(raw_line.strip())
    flush_pending()
    if assignments:
        return assignments, directives
    if bullet_assignments:
        return bullet_assignments, directives
    raise ValueError("no cell assignments found in answer")


def _resolve_sheet_path(work_dir: Path, sheet_name: str) -> Path:
    workbook_xml = ET.parse(work_dir / "xl" / "workbook.xml").getroot()
    rels_xml = ET.parse(work_dir / "xl" / "_rels" / "workbook.xml.rels").getroot()
    rels: dict[str, str] = {}
    for rel in rels_xml.findall("pkg:Relationship", NS):
        rel_id = str(rel.attrib.get("Id") or "").strip()
        target = str(rel.attrib.get("Target") or "").strip()
        if rel_id and target:
            rels[rel_id] = target
    for sheet in workbook_xml.findall("main:sheets/main:sheet", {"main": NS_MAIN}):
        name = str(sheet.attrib.get("name") or "").strip()
        rel_id = str(sheet.attrib.get(f"{{{NS_REL}}}id") or "").strip()
        if name == sheet_name and rel_id in rels:
            return work_dir / "xl" / rels[rel_id]
    raise FileNotFoundError(f"sheet not found: {sheet_name}")


def _resolve_sheet_target_in_archive(archive: ZipFile, sheet_name: str) -> str:
    workbook_xml = ET.fromstring(archive.read("xl/workbook.xml"))
    rels_xml = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rels: dict[str, str] = {}
    for rel in rels_xml.findall("pkg:Relationship", NS):
        rel_id = str(rel.attrib.get("Id") or "").strip()
        target = str(rel.attrib.get("Target") or "").strip()
        if rel_id and target:
            rels[rel_id] = target
    for sheet in workbook_xml.findall("main:sheets/main:sheet", {"main": NS_MAIN}):
        name = str(sheet.attrib.get("name") or "").strip()
        rel_id = str(sheet.attrib.get(f"{{{NS_REL}}}id") or "").strip()
        if name == sheet_name and rel_id in rels:
            target = rels[rel_id].lstrip("/")
            return target if target.startswith("xl/") else f"xl/{target}"
    raise FileNotFoundError(f"sheet not found in archive: {sheet_name}")


def _column_letters(ref: str) -> str:
    match = re.match(r"([A-Z]+)", ref)
    if not match:
        raise ValueError(f"invalid cell ref: {ref}")
    return match.group(1)


def _row_number(ref: str) -> int:
    match = re.search(r"([0-9]+)$", ref)
    if not match:
        raise ValueError(f"invalid cell ref: {ref}")
    return int(match.group(1))


def _append_shared_string(shared_root: ET.Element, value: str) -> int:
    items = shared_root.findall(f"{{{NS_MAIN}}}si")
    index = len(items)
    si = ET.SubElement(shared_root, f"{{{NS_MAIN}}}si")
    t = ET.SubElement(si, f"{{{NS_MAIN}}}t")
    if value[:1].isspace() or value[-1:].isspace():
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = value
    count = int(shared_root.attrib.get("count", str(len(items))))
    unique = int(shared_root.attrib.get("uniqueCount", str(len(items))))
    shared_root.attrib["count"] = str(count + 1)
    shared_root.attrib["uniqueCount"] = str(unique + 1)
    return index


def _ensure_shared_strings(work_dir: Path) -> ET.ElementTree:
    path = work_dir / "xl" / "sharedStrings.xml"
    if path.exists():
        return ET.parse(path)
    root = ET.Element(f"{{{NS_MAIN}}}sst", {"count": "0", "uniqueCount": "0"})
    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return tree


def _repair_ignorable_prefix_declarations(xml_path: Path) -> None:
    text = xml_path.read_text(encoding="utf-8")
    root_start_match = re.search(r"<(?:\w+:)?worksheet\b[^>]*>", text)
    if not root_start_match:
        return
    root_start = root_start_match.group(0)
    ignorable_match = re.search(r'\b(?:mc:|ns\d+:)?Ignorable="([^"]+)"', root_start)
    if not ignorable_match:
        return
    updated_root = root_start
    for prefix in ignorable_match.group(1).split():
        uri = IGNORABLE_NAMESPACE_URIS.get(prefix)
        if not uri:
            continue
        if f'xmlns:{prefix}=' in updated_root:
            continue
        updated_root = updated_root[:-1] + f' xmlns:{prefix}="{uri}">'
    if updated_root != root_start:
        text = text.replace(root_start, updated_root, 1)
        xml_path.write_text(text, encoding="utf-8")


def _drop_calc_chain(work_dir: Path) -> None:
    calc_chain = work_dir / "xl" / "calcChain.xml"
    if calc_chain.exists():
        calc_chain.unlink()

    content_types_path = work_dir / "[Content_Types].xml"
    if content_types_path.exists():
        tree = ET.parse(content_types_path)
        root = tree.getroot()
        override_tag = f"{{{NS_CONTENT_TYPES}}}Override"
        changed = False
        for node in list(root.findall(override_tag)):
            if node.attrib.get("PartName") == "/xl/calcChain.xml":
                root.remove(node)
                changed = True
        if changed:
            tree.write(content_types_path, encoding="utf-8", xml_declaration=True)

    workbook_rels_path = work_dir / "xl" / "_rels" / "workbook.xml.rels"
    if workbook_rels_path.exists():
        tree = ET.parse(workbook_rels_path)
        root = tree.getroot()
        rel_tag = f"{{{NS_PKG}}}Relationship"
        changed = False
        for node in list(root.findall(rel_tag)):
            if node.attrib.get("Target") == "calcChain.xml":
                root.remove(node)
                changed = True
        if changed:
            tree.write(workbook_rels_path, encoding="utf-8", xml_declaration=True)


def _ensure_row(sheet_root: ET.Element, row_num: int) -> ET.Element:
    sheet_data = sheet_root.find(f"{{{NS_MAIN}}}sheetData")
    if sheet_data is None:
        sheet_data = ET.SubElement(sheet_root, f"{{{NS_MAIN}}}sheetData")
    for row in sheet_data.findall(f"{{{NS_MAIN}}}row"):
        if int(row.attrib.get("r", "0")) == row_num:
            return row
    row = ET.SubElement(sheet_data, f"{{{NS_MAIN}}}row", {"r": str(row_num)})
    return row


def _find_cell(row: ET.Element, ref: str) -> ET.Element | None:
    for cell in row.findall(f"{{{NS_MAIN}}}c"):
        if cell.attrib.get("r") == ref:
            return cell
    return None


def _cell_sort_key(ref: str) -> tuple[int, int]:
    col = 0
    for ch in _column_letters(ref):
        col = col * 26 + (ord(ch) - 64)
    return (_row_number(ref), col)


def _set_cell(cell: ET.Element, value: str | None, shared_root: ET.Element) -> None:
    for child in list(cell):
        if child.tag in {f"{{{NS_MAIN}}}v", f"{{{NS_MAIN}}}f", f"{{{NS_MAIN}}}is"}:
            cell.remove(child)
    if value is None:
        cell.attrib.pop("t", None)
        return
    numeric_like = re.fullmatch(r"-?\d+(?:\.\d+)?", value or "") is not None
    if numeric_like:
        cell.attrib.pop("t", None)
        v = ET.SubElement(cell, f"{{{NS_MAIN}}}v")
        v.text = value
        return
    cell.attrib["t"] = "s"
    index = _append_shared_string(shared_root, value)
    v = ET.SubElement(cell, f"{{{NS_MAIN}}}v")
    v.text = str(index)


def _ensure_merge_cell_container(sheet_root: ET.Element) -> ET.Element:
    container = sheet_root.find(f"{{{NS_MAIN}}}mergeCells")
    if container is None:
        container = ET.SubElement(sheet_root, f"{{{NS_MAIN}}}mergeCells", {"count": "0"})
    return container


def _ensure_cell(sheet_root: ET.Element, ref: str) -> ET.Element:
    row = _ensure_row(sheet_root, _row_number(ref))
    cell = _find_cell(row, ref)
    if cell is None:
        cell = ET.Element(f"{{{NS_MAIN}}}c", {"r": ref})
        row.append(cell)
        row[:] = sorted(list(row), key=lambda c: _cell_sort_key(str(c.attrib.get("r") or "")))
    return cell


def _copy_style(sheet_root: ET.Element, *, source_ref: str, target_ref: str) -> None:
    source = _ensure_cell(sheet_root, source_ref)
    target = _ensure_cell(sheet_root, target_ref)
    if "s" in source.attrib:
        target.attrib["s"] = source.attrib["s"]
    else:
        target.attrib.pop("s", None)


def _merge_ref_bounds(ref: str) -> tuple[int, int, int, int]:
    start_ref, end_ref = (ref.split(":", 1) + [ref])[:2]
    start_col = _column_index(_column_letters(start_ref))
    end_col = _column_index(_column_letters(end_ref))
    start_row = _row_number(start_ref)
    end_row = _row_number(end_ref)
    return (
        min(start_col, end_col),
        min(start_row, end_row),
        max(start_col, end_col),
        max(start_row, end_row),
    )


def _merge_refs_overlap(left: str, right: str) -> bool:
    left_min_col, left_min_row, left_max_col, left_max_row = _merge_ref_bounds(left)
    right_min_col, right_min_row, right_max_col, right_max_row = _merge_ref_bounds(right)
    return not (
        left_max_col < right_min_col
        or right_max_col < left_min_col
        or left_max_row < right_min_row
        or right_max_row < left_min_row
    )


def _apply_layout_directives(sheet_root: ET.Element, directives: dict[str, Any]) -> None:
    merge_ranges = [str(item).upper() for item in list(directives.get("merge_ranges") or []) if str(item).strip()]
    style_copies = list(directives.get("style_copies") or [])
    row_heights = dict(directives.get("row_heights") or {})

    if merge_ranges:
        container = _ensure_merge_cell_container(sheet_root)
        existing_nodes = list(container.findall(f"{{{NS_MAIN}}}mergeCell"))
        existing = {str(node.attrib.get("ref") or "").upper() for node in existing_nodes}
        for merge_ref in merge_ranges:
            for node in list(container.findall(f"{{{NS_MAIN}}}mergeCell")):
                current_ref = str(node.attrib.get("ref") or "").upper()
                if current_ref and current_ref != merge_ref and _merge_refs_overlap(current_ref, merge_ref):
                    container.remove(node)
                    existing.discard(current_ref)
            if merge_ref in existing:
                continue
            ET.SubElement(container, f"{{{NS_MAIN}}}mergeCell", {"ref": merge_ref})
            existing.add(merge_ref)
        container.attrib["count"] = str(len(existing))

    for item in style_copies:
        target = str(item.get("target") or "").upper()
        source = str(item.get("source") or "").upper()
        if target and source:
            _copy_style(sheet_root, source_ref=source, target_ref=target)

    for raw_row, raw_height in row_heights.items():
        row_num = int(raw_row)
        row = _ensure_row(sheet_root, row_num)
        row.attrib["ht"] = str(raw_height)
        row.attrib["customHeight"] = "1"


def _recommended_performance_row_heights(
    *,
    workbook_path: Path,
    sheet_name: str,
    assignments: dict[str, str | None],
    rows: range = range(5, 10),
    columns: tuple[str, ...] = ("B", "C", "E", "F"),
) -> dict[int, float]:
    refs = [f"{col}{row_num}" for row_num in rows for col in columns]
    existing_values, column_widths = _template_sheet_snapshot_from_archive(
        workbook_path=workbook_path,
        sheet_name=sheet_name,
        refs=refs,
        columns=columns,
    )
    heights: dict[int, float] = {}
    for row_num in rows:
        max_lines = 1
        for col in columns:
            ref = f"{col}{row_num}"
            value = assignments.get(ref, existing_values.get(ref))
            text = "" if value is None else str(value)
            if not text.strip():
                continue
            column_width = float(column_widths.get(col, 10.0))
            chars_per_line = max(6, int(column_width * 1.45))
            line_count = 0
            for part in text.splitlines() or [""]:
                width = _display_width(part)
                line_count += max(1, int((width + chars_per_line - 1) / chars_per_line))
            max_lines = max(max_lines, line_count)
        heights[row_num] = max(36.0, min(180.0, 12.0 + max_lines * 20.0))
    return heights


def _merge_performance_row_heights(
    *,
    auto_heights: dict[int, float],
    explicit_heights: dict[int, float] | None = None,
) -> dict[int, float]:
    merged = dict(explicit_heights or {})
    for row_num, auto_height in auto_heights.items():
        # For the main performance body, model-provided @ROW values have proven
        # too noisy. Keep auto-fit authoritative so readability is stable.
        merged[int(row_num)] = float(auto_height)
    return merged


def _apply_assignments(
    work_dir: Path,
    *,
    sheet_name: str,
    assignments: dict[str, str | None],
    directives: dict[str, Any] | None = None,
) -> None:
    sheet_path = _resolve_sheet_path(work_dir, sheet_name)
    sheet_tree = ET.parse(sheet_path)
    sheet_root = sheet_tree.getroot()
    shared_tree = _ensure_shared_strings(work_dir)
    shared_root = shared_tree.getroot()
    by_row: dict[int, list[str]] = {}
    for ref in assignments:
        by_row.setdefault(_row_number(ref), []).append(ref)
    for row_num, refs in by_row.items():
        row = _ensure_row(sheet_root, row_num)
        for ref in sorted(refs, key=_cell_sort_key):
            cell = _find_cell(row, ref)
            if cell is None:
                cell = ET.Element(f"{{{NS_MAIN}}}c", {"r": ref})
                row.append(cell)
            _set_cell(cell, assignments[ref], shared_root)
        row[:] = sorted(list(row), key=lambda c: _cell_sort_key(str(c.attrib.get("r") or "")))
    _apply_layout_directives(sheet_root, directives or {})
    sheet_tree.write(sheet_path, encoding="utf-8", xml_declaration=True)
    _repair_ignorable_prefix_declarations(sheet_path)
    shared_tree.write(work_dir / "xl" / "sharedStrings.xml", encoding="utf-8", xml_declaration=True)


def _validate_assignments(
    assignments: dict[str, str | None],
    *,
    template_path: Path | None = None,
    sheet_name: str = "绩效考核表",
) -> None:
    required = ["A5", "B5", "C5", "D5", "E5", "F5", "A9", "F9"]
    missing = [item for item in required if item not in assignments]
    if missing and template_path is not None and template_path.exists():
        template_values, _ = _template_sheet_snapshot_from_archive(
            workbook_path=template_path,
            sheet_name=sheet_name,
            refs=missing,
            columns=tuple(sorted({_column_letters(ref) for ref in missing})),
        )
        missing = [
            item
            for item in missing
            if (lambda value: value is None or (isinstance(value, str) and not value.strip()))(template_values.get(item))
        ]
    if missing:
        raise ValueError(f"missing required assignments: {', '.join(missing)}")


def main() -> None:
    args = _parse_args()
    template = Path(args.template).resolve()
    answer_file = Path(args.answer_file).resolve()
    output = Path(args.output).resolve()
    if not template.exists():
        raise FileNotFoundError(template)
    if not answer_file.exists():
        raise FileNotFoundError(answer_file)
    answer_text = _load_answer_text(answer_file)
    assignments, directives = _parse_assignments(answer_text)
    _validate_assignments(assignments, template_path=template, sheet_name=str(args.sheet_name))
    if args.autofit_performance_rows:
        auto_heights = _recommended_performance_row_heights(
            workbook_path=template,
            sheet_name=str(args.sheet_name),
            assignments=assignments,
        )
        explicit_row_heights = dict(directives.get("row_heights") or {})
        directives = {
            **directives,
            "row_heights": _merge_performance_row_heights(
                auto_heights=auto_heights,
                explicit_heights=explicit_row_heights,
            ),
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="perf-sheet-") as tmp:
        tmp_path = Path(tmp)
        unpack_dir = tmp_path / "workbook"
        _run(["python3", str(UNPACK_SCRIPT), str(template), str(unpack_dir)])
        _apply_assignments(
            unpack_dir,
            sheet_name=str(args.sheet_name),
            assignments=assignments,
            directives=directives,
        )
        _drop_calc_chain(unpack_dir)
        packed = tmp_path / output.name
        _run(["python3", str(PACK_SCRIPT), str(unpack_dir), str(packed)])
        shutil.copy2(packed, output)
    print(json.dumps({
        "ok": True,
        "template": str(template),
        "answer_file": str(answer_file),
        "output": str(output),
        "sheet_name": str(args.sheet_name),
        "applied_cells": sorted(assignments.keys()),
        "layout_directives": directives,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
