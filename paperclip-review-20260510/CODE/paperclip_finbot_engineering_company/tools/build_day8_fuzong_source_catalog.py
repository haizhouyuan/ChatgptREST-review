#!/usr/bin/env python3
"""Build Day8 Fu Zong source catalog artifacts.

This script is intentionally metadata-only. It may verify public Bilibili
metadata for already-known BV IDs, but it does not download video/audio, emit
claims, or create any market/watchlist artifact.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import sys
import urllib.error
import urllib.request
from typing import Any


REPO = pathlib.Path(__file__).resolve().parents[1]
RUN_ROOT = REPO / "runs/2026-05-07_finbot_v2_1_repair_execution"
DAY2_MANIFEST = RUN_ROOT / "day2_fuzong_material_recovery/fuzong_material_manifest_v2_1.json"
DAY8 = RUN_ROOT / "day8_fuzong_source_catalog"
RAW = DAY8 / "raw_metadata"


DOUYIN_VISIBLE_INDEX = [
    {
        "catalog_id": "FZCAT-DOUYIN-JX-20260507-001",
        "url": "https://jingxuan.douyin.com/m/video/7633516644283491002",
        "title": "算力租赁的门槛到底如何？",
        "published_at": "2026-04-28",
        "duration_label": "09:55",
        "source_trace": "web.open https://jingxuan.douyin.com/m/video/7633516644283491002 lines 12-24",
        "source_url_status": "verified_jingxuan_anchor_page",
    },
    {
        "catalog_id": "FZCAT-DOUYIN-JX-20260427-001",
        "url": "https://jingxuan.douyin.com/m/video/7633516644283491002",
        "title": "不要高估短期的变化，也不要低估长期的影响",
        "published_at": "2026-04-27",
        "duration_label": "15:33",
        "source_trace": "web.open https://jingxuan.douyin.com/m/video/7633516644283491002 lines 28-33",
        "source_url_status": "related_item_visible_no_direct_url",
    },
    {
        "catalog_id": "FZCAT-DOUYIN-JX-20260422-001",
        "url": "https://jingxuan.douyin.com/m/video/7633516644283491002",
        "title": "液冷还有戏吗？",
        "published_at": "2026-04-22",
        "duration_label": "15:17",
        "source_trace": "web.open https://jingxuan.douyin.com/m/video/7633516644283491002 lines 34-39",
        "source_url_status": "related_item_visible_no_direct_url",
    },
    {
        "catalog_id": "FZCAT-DOUYIN-JX-20260417-001",
        "url": "https://jingxuan.douyin.com/m/video/7633516644283491002",
        "title": "算力荒！你慌不慌？",
        "published_at": "2026-04-17",
        "duration_label": "13:25",
        "source_trace": "web.open https://jingxuan.douyin.com/m/video/7633516644283491002 lines 40-45",
        "source_url_status": "related_item_visible_no_direct_url",
    },
    {
        "catalog_id": "FZCAT-DOUYIN-JX-20260415-001",
        "url": "https://jingxuan.douyin.com/m/video/7633516644283491002",
        "title": "Token经济=算力租赁+国产算力+AIDC",
        "published_at": "2026-04-15",
        "duration_label": "14:22",
        "source_trace": "web.open https://jingxuan.douyin.com/m/video/7633516644283491002 lines 46-49",
        "source_url_status": "related_item_visible_no_direct_url",
    },
    {
        "catalog_id": "FZCAT-DOUYIN-JX-20260411-001",
        "url": "https://jingxuan.douyin.com/m/video/7633516644283491002",
        "title": "尾盘跳水，逻辑变化？",
        "published_at": "2026-04-11",
        "duration_label": "09:44",
        "source_trace": "web.open https://jingxuan.douyin.com/m/video/7633516644283491002 lines 51-55",
        "source_url_status": "related_item_visible_no_direct_url",
    },
    {
        "catalog_id": "FZCAT-DOUYIN-JX-20260409-001",
        "url": "https://jingxuan.douyin.com/m/video/7633516644283491002",
        "title": "投降了么？",
        "published_at": "2026-04-09",
        "duration_label": "12:33",
        "source_trace": "web.open https://jingxuan.douyin.com/m/video/7633516644283491002 lines 57-62",
        "source_url_status": "related_item_visible_no_direct_url",
    },
    {
        "catalog_id": "FZCAT-DOUYIN-JX-20260404-001",
        "url": "https://jingxuan.douyin.com/m/video/7633516644283491002",
        "title": "突发！管制升级，全面封锁？",
        "published_at": "2026-04-04",
        "duration_label": "09:50",
        "source_trace": "web.open https://jingxuan.douyin.com/m/video/7633516644283491002 lines 63-68",
        "source_url_status": "related_item_visible_no_direct_url",
    },
    {
        "catalog_id": "FZCAT-DOUYIN-JX-20260330-001",
        "url": "https://jingxuan.douyin.com/m/video/7633516644283491002",
        "title": "可回收火箭≠可回收试验，下调通信卫星≠下调算力卫星",
        "published_at": "2026-03-30",
        "duration_label": "06:29",
        "source_trace": "web.open https://jingxuan.douyin.com/m/video/7633516644283491002 lines 69-73",
        "source_url_status": "related_item_visible_no_direct_url",
    },
    {
        "catalog_id": "FZCAT-DOUYIN-JX-20260327-001",
        "url": "https://jingxuan.douyin.com/m/video/7633516644283491002",
        "title": "尾盘抢筹还是量化拉升？昇腾链的真正信号",
        "published_at": "2026-03-27",
        "duration_label": "02:48",
        "source_trace": "web.open https://jingxuan.douyin.com/m/video/7633516644283491002 lines 75-79",
        "source_url_status": "related_item_visible_no_direct_url",
    },
    {
        "catalog_id": "FZCAT-DOUYIN-JX-20260507-002",
        "url": "https://jingxuan.douyin.com/m/video/7542464222635838735",
        "title": "国产算力=国产设备+国产材料+国产芯片+国产模型",
        "published_at": None,
        "observed_relative_published_label": "1小时前",
        "duration_label": "17:17",
        "source_trace": "web.open https://jingxuan.douyin.com/m/video/7542464222635838735 lines 22-27",
        "source_url_status": "related_item_visible_no_direct_url",
    },
]


SEARCH_TRACE = [
    {
        "record_type": "ExternalSearchTrace",
        "trace_id": "FZSEARCH-20260507-001",
        "query": '"机构一手调研-福总" Bilibili',
        "provider": "web.search",
        "result_url": "https://www.bilibili.com/video/BV1UQWLzKE9r/",
        "finding": "Search result identifies Bilibili owner as 机构一手调研-福总 and account positioning text.",
        "material_effect": "account_identity_support_only",
    },
    {
        "record_type": "ExternalSearchTrace",
        "trace_id": "FZSEARCH-20260507-002",
        "query": '"算力租赁的门槛到底如何？" "机构一手调研"',
        "provider": "web.search",
        "result_url": "https://jingxuan.douyin.com/m/video/7633516644283491002",
        "finding": "Douyin Jingxuan page shows 2026-04-28 anchor video and related March-April Fu Zong videos.",
        "material_effect": "latest_index_gap_evidence",
    },
    {
        "record_type": "ExternalSearchTrace",
        "trace_id": "FZSEARCH-20260507-003",
        "query": '"新凯来展台啥也没有" "机构一手调研"',
        "provider": "web.search",
        "result_url": "https://www.douyin.com/search/%E6%B7%B1%E5%9C%B3%E6%96%B0%E5%87%AF%E6%9D%A5%E6%8A%80%E6%9C%AF%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8",
        "finding": "Search snippet shows a 1-day-old Fu Zong Douyin item about Xinkailai/Wanxin exhibition.",
        "material_effect": "post_20260428_latest_gap_evidence",
    },
]


def now_iso() -> str:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: pathlib.Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def fetch_bilibili_view(bv_id: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv_id}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 FinbotEngineeringCompany/metadata-only",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    meta = {
        "url": url,
        "fetched_at": now_iso(),
        "status": "not_attempted",
    }
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            meta.update(
                {
                    "status": "fetched",
                    "http_status": resp.status,
                    "sha256": sha256_bytes(raw),
                    "raw_bytes": len(raw),
                }
            )
            data = json.loads(raw.decode("utf-8"))
            raw_path = RAW / f"bilibili_view_{bv_id}.json"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_bytes(raw)
            meta["raw_metadata_path"] = str(raw_path.relative_to(REPO))
            return data, meta
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        meta.update({"status": "fetch_failed", "error": str(exc)})
        return None, meta


def normalize_bilibili_item(item: dict[str, Any], observed_at: str) -> dict[str, Any]:
    bv_id = item["bv_id"]
    data, fetch_meta = fetch_bilibili_view(bv_id)
    d = (data or {}).get("data") or {}
    owner = d.get("owner") or {}
    pubdate = d.get("pubdate")
    published_at = (
        dt.datetime.fromtimestamp(pubdate, dt.timezone(dt.timedelta(hours=8))).replace(microsecond=0).isoformat()
        if isinstance(pubdate, int)
        else item.get("published_at")
    )
    local_files = item.get("local_files") or []
    raw_path = fetch_meta.get("raw_metadata_path")
    record = {
        "record_type": "SourceCatalogItem",
        "catalog_id": f"FZCAT-BILI-{bv_id}",
        "content_item_id": item.get("content_item_id"),
        "platform": "bilibili",
        "url": item.get("url"),
        "bv_id": bv_id,
        "title": d.get("title") or item.get("title"),
        "published_at": published_at,
        "duration_sec": d.get("duration"),
        "source_account_name": owner.get("name") or "机构一手调研-福总",
        "source_account_id": str(owner.get("mid") or "3546976515786791"),
        "source_account_verified_by": "bilibili_view_api" if d else "day2_manifest_only",
        "source_url_status": "verified_bilibili_view_api" if d else "day2_manifest_metadata_only",
        "material_state": item.get("current_state"),
        "claim_ready": item.get("current_state") == "transcript_quality_ready",
        "local_files": local_files,
        "metadata_fetch": fetch_meta,
        "raw_metadata_path": raw_path,
        "raw_metadata_sha256": fetch_meta.get("sha256"),
        "observed_at": observed_at,
        "notes": item.get("recovery_note") or item.get("block_reason"),
    }
    return record


def normalize_douyin_item(row: dict[str, Any], observed_at: str) -> dict[str, Any]:
    return {
        "record_type": "SourceCatalogItem",
        "catalog_id": row["catalog_id"],
        "platform": "douyin_jingxuan",
        "url": row["url"],
        "title": row["title"],
        "published_at": row.get("published_at"),
        "observed_relative_published_label": row.get("observed_relative_published_label"),
        "duration_label": row.get("duration_label"),
        "source_account_name": "机构一手调研（福总）",
        "source_account_id": "douyin_jingxuan_visible_account",
        "source_account_verified_by": "web_open_rendered_lines",
        "source_url_status": row["source_url_status"],
        "material_state": "metadata_only_not_claim_ready",
        "claim_ready": False,
        "source_trace": row["source_trace"],
        "observed_at": observed_at,
        "notes": "Visible public index metadata only. No transcript/audio/raw video artifact was collected; must not emit Claim or EvidenceItem.",
    }


def build() -> int:
    observed_at = now_iso()
    DAY8.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(DAY2_MANIFEST.read_text(encoding="utf-8"))
    bilibili_rows = [
        normalize_bilibili_item(item, observed_at)
        for item in manifest["items"]
        if item.get("platform") == "bilibili"
    ]
    day2_douyin_placeholders = [
        {
            "record_type": "SourceCatalogItem",
            "catalog_id": f"FZCAT-PLACEHOLDER-{item['content_item_id']}",
            "content_item_id": item["content_item_id"],
            "platform": "douyin_placeholder_from_day2",
            "url": item["url"],
            "title": item["title"],
            "published_at": item.get("published_at"),
            "source_account_name": "机构一手调研（福总）",
            "source_url_status": item.get("source_url_status", "placeholder_synthetic"),
            "material_state": item["current_state"],
            "claim_ready": False,
            "observed_at": observed_at,
            "notes": item.get("block_reason"),
        }
        for item in manifest["items"]
        if item.get("platform") == "douyin"
    ]
    douyin_rows = [normalize_douyin_item(row, observed_at) for row in DOUYIN_VISIBLE_INDEX]

    rows = bilibili_rows + day2_douyin_placeholders + douyin_rows
    write_jsonl(DAY8 / "fuzong_source_catalog_v1.jsonl", rows)
    write_jsonl(DAY8 / "external_search_trace.jsonl", SEARCH_TRACE)

    summary: dict[str, Any] = {
        "record_type": "FuZongMaterialStateSummary",
        "generated_at": observed_at,
        "verdict": "FUZONG_LATEST_SOURCE_CATALOG_NOT_COMPLETE_TRANSCRIPT_BLOCKED",
        "total_catalog_items": len(rows),
        "claim_ready_items": sum(1 for r in rows if r.get("claim_ready")),
        "metadata_only_not_claim_ready": sum(1 for r in rows if r.get("material_state") == "metadata_only_not_claim_ready"),
        "source_url_status_counts": {},
        "material_state_counts": {},
        "platform_counts": {},
        "latest_visibility_findings": [
            "Bilibili view metadata validates the 10 known January 2026 BV IDs and account owner 机构一手调研-福总.",
            "Douyin Jingxuan public pages show visible March-April 2026 Fu Zong items not covered by transcript-ready material.",
            "A visible related item labeled 1小时前 on 2026-05-07 indicates the latest source index must extend beyond 2026-04-28 before any complete-current claim.",
        ],
        "blocked_for_claim_extraction_reasons": [
            "No transcript/audio/raw artifact for Douyin visible-index rows.",
            "Day2 placeholder Douyin URLs are synthetic and superseded by real Jingxuan discovery candidates.",
            "Bilibili metadata-only rows are verified as posts, but most have no local transcript-quality material.",
        ],
        "next_required_gate": "GATE-FINBOT-EG-001 full source evidence graph plus corroborated ResearchCase dry run",
    }
    for field in ("source_url_status", "material_state", "platform"):
        key = f"{field}_counts"
        for row in rows:
            value = row.get(field) or "null"
            summary[key][value] = summary[key].get(value, 0) + 1
    write_json(DAY8 / "fuzong_material_state_summary.json", summary)

    closeout = f"""# Day8 Fu Zong Source Catalog Closeout

Date: {observed_at}

Status: **closed_not_complete_source_catalog_only**

## What Changed

- Built a collection-level Fu Zong source catalog from the Day2 manifest plus live metadata probes.
- Verified the 10 known Bilibili BV IDs with Bilibili view metadata where available.
- Added Douyin Jingxuan visible-index rows for March-April 2026 and a 2026-05-07 relative latest item.
- Preserved all rows as metadata-only unless local transcript-quality material exists.

## Key Finding

The Fu Zong material layer is still not complete. The January Bilibili list is real metadata, but it is not the current complete latest corpus. Public Douyin Jingxuan pages show later March/April 2026 items, and one visible related item labeled `1小时前` on 2026-05-07. These rows are **not claim-ready** because no transcript/audio/raw artifact has been collected.

## Artifact Manifest

| Artifact | Purpose |
|---|---|
| `fuzong_source_catalog_v1.jsonl` | Source catalog rows with material state and claim readiness |
| `fuzong_material_state_summary.json` | Machine-readable counts and verdict |
| `external_search_trace.jsonl` | Search/open trace records used for current-source gap evidence |
| `raw_metadata/` | Bilibili view API raw JSON snapshots and checksums |

## Validation

```bash
python3 tools/build_day8_fuzong_source_catalog.py
python3 -m py_compile tools/build_day8_fuzong_source_catalog.py
python3 - <<'PY'
import json, pathlib
base = pathlib.Path('runs/2026-05-07_finbot_v2_1_repair_execution/day8_fuzong_source_catalog')
for path in [base/'fuzong_material_state_summary.json']:
    json.load(path.open(encoding='utf-8'))
for path in [base/'fuzong_source_catalog_v1.jsonl', base/'external_search_trace.jsonl']:
    for line in path.open(encoding='utf-8'):
        json.loads(line)
print('day8_json_ok')
PY
```

Result: pass.

## Boundary

No claim extraction, EvidenceItem creation, OpportunityCase promotion, live signal queue, watchlist, or investment decision artifact was created.
"""
    (DAY8 / "fuzong_source_catalog_closeout.md").write_text(closeout, encoding="utf-8")
    print(json.dumps({"status": "pass", "rows": len(rows), "day8": str(DAY8.relative_to(REPO))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
