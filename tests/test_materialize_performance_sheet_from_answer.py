from __future__ import annotations

import subprocess
from pathlib import Path
from zipfile import ZipFile

from ops.materialize_performance_sheet_from_answer import (
    _apply_assignments,
    _drop_calc_chain,
    _expand_range,
    _merge_performance_row_heights,
    _parse_assignments,
    _repair_ignorable_prefix_declarations,
    _recommended_performance_row_heights,
    _validate_assignments,
)


def test_parse_assignments_expands_ranges_and_blanks() -> None:
    text = """
- `A5`：`1`
- `B5`：重点业务机会推进与客户协同
- `G5:J5`：`本轮留空`
"""
    assignments, directives = _parse_assignments(text)
    assert assignments["A5"] == "1"
    assert assignments["B5"] == "重点业务机会推进与客户协同"
    assert assignments["G5"] is None
    assert assignments["J5"] is None
    assert directives["merge_ranges"] == []


def test_expand_range_supports_rectangular_ranges() -> None:
    assert _expand_range("G5:H6") == ["G5", "H5", "G6", "H6"]


def test_parse_assignments_supports_yaml_block() -> None:
    text = """
```yaml
A1: 2026年Q1绩效考核表（袁海州）
D5: 0.30
E5: |
  - 第一条
  - 第二条
G5: 留空
```
"""
    assignments, _ = _parse_assignments(text)
    assert assignments["A1"] == "2026年Q1绩效考核表（袁海州）"
    assert assignments["D5"] == "0.30"
    assert assignments["E5"] == "- 第一条\n- 第二条"
    assert assignments["G5"] is None


def test_parse_assignments_supports_text_code_block_row_format() -> None:
    text = """
```text
A1=2026Q1绩效考核表（袁海州）
F2=2026年Q1（1–3月）
Row5: A5=1 | B5=短交通客户与平台机会推进 | D5=0.30 | G5=留空 | H5=留空 | I5=保留公式 =D5*H5 | J5=留空
C5=覆盖范围
E5=关键结果
F5=亮点难点
G5:H9 = 留空，待后续确认自评与主管评分
I5:I10 = 保留模板原公式
J5:J9 = 先留空；如你想显式标角色边界，可后续补“主导 / 牵头 / 参与支持”
B21 = 保留原公式
B22 = 暂不填写
```
"""
    assignments, _ = _parse_assignments(text)
    assert assignments["A1"] == "2026Q1绩效考核表（袁海州）"
    assert assignments["F2"] == "2026年Q1（1–3月）"
    assert assignments["A5"] == "1"
    assert assignments["B5"] == "短交通客户与平台机会推进"
    assert assignments["D5"] == "0.30"
    assert assignments["G5"] is None
    assert assignments["H5"] is None
    assert assignments["J5"] is None
    assert assignments["H9"] is None
    assert assignments["J9"] is None
    assert assignments["C5"] == "覆盖范围"
    assert assignments["E5"] == "关键结果"
    assert assignments["F5"] == "亮点难点"
    assert "I5" not in assignments
    assert "I10" not in assignments
    assert "B21" not in assignments
    assert assignments["B22"] is None


def test_parse_assignments_prefers_code_block_over_bullet_guidance() -> None:
    text = """
- `G5:H9`：自评、主管评分
- `J5:J9`：备注

```text
A5: 1
B5: 模块
C5: 覆盖
D5: 0.30
E5: 结果
F5: 亮点
A9: 5
F9: 收口
G5:H9: 留空
J5:J9: 留空
```
"""
    assignments, _ = _parse_assignments(text)
    assert assignments["A5"] == "1"
    assert assignments["F9"] == "收口"
    assert assignments["G5"] is None
    assert assignments["H9"] is None
    assert assignments["J5"] is None


def test_parse_assignments_supports_layout_directives() -> None:
    text = """
```text
A21: 总分(0–100)
A22: 考评人签字
E22: 日期
@MERGE B22:D22
@MERGE F22:G22
@STYLE F22 <- B22
@ROW 22 HEIGHT 30
```
"""
    assignments, directives = _parse_assignments(text)
    assert assignments["A21"] == "总分(0–100)"
    assert assignments["A22"] == "考评人签字"
    assert directives["merge_ranges"] == ["B22:D22", "F22:G22"]
    assert directives["style_copies"] == [{"target": "F22", "source": "B22"}]
    assert directives["row_heights"][22] == 30.0


def test_materialize_performance_sheet_from_answer_creates_filled_output(tmp_path: Path) -> None:
    skill_dir = Path("/vol1/1000/home-yuanhaizhou/.codex-shared/skills/minimax-skills/skills/minimax-xlsx")
    template_dir = skill_dir / "templates" / "minimal_xlsx"
    template = tmp_path / "template.xlsx"
    subprocess.run(
        ["python3", str(skill_dir / "scripts" / "xlsx_pack.py"), str(template_dir), str(template)],
        check=True,
    )

    answer = tmp_path / "answer.md"
    answer.write_text(
        "\n".join(
                [
                    "- `A5`：`1`",
                    "- `B5`：重点业务机会推进与客户协同",
                    "- `C5`：覆盖范围",
                    "- `D5`：`0.30`",
                    "- `E5`：关键结果",
                    "- `F5`：亮点难点",
                    "- `G5:J5`：`本轮留空`",
                    "- `A9`：`5`",
                    "- `F9`：组织协同亮点",
                ]
            ),
            encoding="utf-8",
        )
    output = tmp_path / "output.xlsx"
    subprocess.run(
        [
            "python3",
            "ops/materialize_performance_sheet_from_answer.py",
            "--template",
            str(template),
            "--answer-file",
            str(answer),
            "--output",
            str(output),
            "--sheet-name",
            "Sheet1",
        ],
        cwd="/vol1/1000/projects/ChatgptREST",
        check=True,
    )
    with ZipFile(output) as archive:
        sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8", errors="replace")
        shared_xml = archive.read("xl/sharedStrings.xml").decode("utf-8", errors="replace")
    assert 'r="A5"' in sheet_xml and "<v>1</v>" in sheet_xml
    assert 'r="D5"' in sheet_xml and "<v>0.30</v>" in sheet_xml
    assert 'r="A9"' in sheet_xml and "<v>5</v>" in sheet_xml
    assert 'r="G5" />' in sheet_xml
    assert "重点业务机会推进与客户协同" in shared_xml
    assert "组织协同亮点" in shared_xml


def test_apply_assignments_supports_layout_directives(tmp_path: Path) -> None:
    skill_dir = Path("/vol1/1000/home-yuanhaizhou/.codex-shared/skills/minimax-skills/skills/minimax-xlsx")
    template_dir = skill_dir / "templates" / "minimal_xlsx"
    template = tmp_path / "template.xlsx"
    subprocess.run(
        ["python3", str(skill_dir / "scripts" / "xlsx_pack.py"), str(template_dir), str(template)],
        check=True,
    )
    work_dir = tmp_path / "work"
    subprocess.run(
        ["python3", str(skill_dir / "scripts" / "xlsx_unpack.py"), str(template), str(work_dir)],
        check=True,
    )
    _apply_assignments(
        work_dir,
        sheet_name="Sheet1",
        assignments={"A5": "模块", "F9": "收口", "A22": "考评人签字", "E22": "日期"},
        directives={
            "merge_ranges": ["B22:D22", "F22:G22"],
            "style_copies": [{"target": "F22", "source": "B22"}],
            "row_heights": {22: 30.0},
        },
    )
    sheet_xml = (work_dir / "xl" / "worksheets" / "sheet1.xml").read_text(encoding="utf-8")
    assert 'mergeCell ref="B22:D22"' in sheet_xml
    assert 'mergeCell ref="F22:G22"' in sheet_xml
    assert 'r="22"' in sheet_xml
    assert 'ht="30.0"' in sheet_xml or 'ht="30"' in sheet_xml


def test_apply_assignments_replaces_overlapping_merge_ranges(tmp_path: Path) -> None:
    skill_dir = Path("/vol1/1000/home-yuanhaizhou/.codex-shared/skills/minimax-skills/skills/minimax-xlsx")
    template_dir = skill_dir / "templates" / "minimal_xlsx"
    template = tmp_path / "template.xlsx"
    subprocess.run(
        ["python3", str(skill_dir / "scripts" / "xlsx_pack.py"), str(template_dir), str(template)],
        check=True,
    )
    work_dir = tmp_path / "work"
    subprocess.run(
        ["python3", str(skill_dir / "scripts" / "xlsx_unpack.py"), str(template), str(work_dir)],
        check=True,
    )
    _apply_assignments(
        work_dir,
        sheet_name="Sheet1",
        assignments={"A22": "考评人签字"},
        directives={"merge_ranges": ["F22:H22"]},
    )
    _apply_assignments(
        work_dir,
        sheet_name="Sheet1",
        assignments={"E22": "日期"},
        directives={"merge_ranges": ["F22:J22"]},
    )
    sheet_xml = (work_dir / "xl" / "worksheets" / "sheet1.xml").read_text(encoding="utf-8")
    assert 'mergeCell ref="F22:J22"' in sheet_xml
    assert 'mergeCell ref="F22:H22"' not in sheet_xml


def test_recommended_performance_row_heights_compacts_rows(tmp_path: Path) -> None:
    skill_dir = Path("/vol1/1000/home-yuanhaizhou/.codex-shared/skills/minimax-skills/skills/minimax-xlsx")
    template_dir = skill_dir / "templates" / "minimal_xlsx"
    template = tmp_path / "template.xlsx"
    subprocess.run(
        ["python3", str(skill_dir / "scripts" / "xlsx_pack.py"), str(template_dir), str(template)],
        check=True,
    )
    heights = _recommended_performance_row_heights(
        workbook_path=template,
        sheet_name="Sheet1",
        assignments={
            "B5": "重点业务推进与客户拓展",
            "C5": "覆盖九号项目及绿源、新日等重点客户推进，从需求澄清到阶段计划确认。",
            "E5": "1. 持续推进九号车架/车轮项目。 2. 组织或参与绿源、新日客户拜访交流。 3. 针对九号推进受阻事项及时梳理卡点。",
            "F5": "1. 将零散沟通收敛为节点。 2. 提升领导可读性。",
        },
    )
    assert 5 in heights
    assert heights[5] >= 36.0
    assert heights[5] <= 180.0


def test_merge_performance_row_heights_prefers_auto_for_body_rows() -> None:
    merged = _merge_performance_row_heights(
        auto_heights={5: 112.0, 6: 96.0},
        explicit_heights={5: 225.0, 22: 30.0},
    )
    assert merged[5] == 112.0
    assert merged[6] == 96.0
    assert merged[22] == 30.0


def test_validate_assignments_allows_incremental_patch_when_template_has_required_cells(tmp_path: Path) -> None:
    skill_dir = Path("/vol1/1000/home-yuanhaizhou/.codex-shared/skills/minimax-skills/skills/minimax-xlsx")
    template_dir = skill_dir / "templates" / "minimal_xlsx"
    template = tmp_path / "template.xlsx"
    subprocess.run(
        ["python3", str(skill_dir / "scripts" / "xlsx_pack.py"), str(template_dir), str(template)],
        check=True,
    )
    work_dir = tmp_path / "work"
    subprocess.run(
        ["python3", str(skill_dir / "scripts" / "xlsx_unpack.py"), str(template), str(work_dir)],
        check=True,
    )
    _apply_assignments(
        work_dir,
        sheet_name="Sheet1",
        assignments={
            "A5": "1",
            "B5": "模块一",
            "C5": "说明",
            "D5": "0.3",
            "E5": "结果",
            "F5": "亮点",
            "A9": "5",
            "F9": "收口",
        },
    )
    subprocess.run(
        ["python3", str(skill_dir / "scripts" / "xlsx_pack.py"), str(work_dir), str(template)],
        check=True,
    )
    _validate_assignments({"A21": "总分(0–100)", "B21": "=I10"}, template_path=template, sheet_name="Sheet1")


def test_repair_ignorable_prefix_declarations_adds_missing_namespaces(tmp_path: Path) -> None:
    xml_path = tmp_path / "sheet1.xml"
    xml_path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" mc:Ignorable="x14ac xr xr2 xr3"><sheetData /></worksheet>
""",
        encoding="utf-8",
    )
    _repair_ignorable_prefix_declarations(xml_path)
    sheet_xml = xml_path.read_text(encoding="utf-8")
    assert 'Ignorable="x14ac xr xr2 xr3"' in sheet_xml
    assert 'xmlns:x14ac="http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac"' in sheet_xml
    assert 'xmlns:xr="http://schemas.microsoft.com/office/spreadsheetml/2014/revision"' in sheet_xml
    assert 'xmlns:xr2="http://schemas.microsoft.com/office/spreadsheetml/2015/revision2"' in sheet_xml
    assert 'xmlns:xr3="http://schemas.microsoft.com/office/spreadsheetml/2016/revision3"' in sheet_xml


def test_drop_calc_chain_removes_part_and_relationships(tmp_path: Path) -> None:
    work = tmp_path / "wb"
    (work / "xl" / "_rels").mkdir(parents=True)
    (work / "xl" / "calcChain.xml").write_text("<calcChain/>", encoding="utf-8")
    (work / "[Content_Types].xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Override PartName="/xl/calcChain.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.calcChain+xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
</Types>
""",
        encoding="utf-8",
    )
    (work / "xl" / "_rels" / "workbook.xml.rels").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/calcChain" Target="calcChain.xml"/>
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
""",
        encoding="utf-8",
    )
    _drop_calc_chain(work)
    assert not (work / "xl" / "calcChain.xml").exists()
    content_types = (work / "[Content_Types].xml").read_text(encoding="utf-8")
    rels = (work / "xl" / "_rels" / "workbook.xml.rels").read_text(encoding="utf-8")
    assert "/xl/calcChain.xml" not in content_types
    assert 'Target="calcChain.xml"' not in rels
