from __future__ import annotations

import json
import math
import os
import random
import time
from pathlib import Path
from typing import Any

from chatgpt_web_mcp.env import _env_int, _truthy_env
from chatgpt_web_mcp.runtime.paths import _debug_dir
from chatgpt_web_mcp.runtime.util import _slugify


def _debug_perf_resource_limit() -> int:
    raw = (os.environ.get("CHATGPT_DEBUG_PERF_RESOURCE_LIMIT") or "").strip()
    if not raw:
        return 200
    try:
        return max(0, int(raw))
    except ValueError:
        return 200


def _should_capture_perf(label: str) -> bool:
    if _truthy_env("CHATGPT_DEBUG_CAPTURE_PERF", False):
        return True
    hay = (label or "").lower()
    return any(token in hay for token in ("network", "proxy", "transient", "cdp", "connect"))


async def _capture_debug_artifacts(page, *, label: str) -> dict[str, str]:
    debug_dir = _debug_dir()
    if debug_dir is None:
        return {}

    debug_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    stem = f"{ts}_{_slugify(label)}_{random.randint(1000, 9999)}"

    screenshot_path = debug_dir / f"{stem}.png"
    html_path = debug_dir / f"{stem}.html"
    txt_path = debug_dir / f"{stem}.txt"

    artifacts: dict[str, str] = {}

    try:
        await page.screenshot(path=str(screenshot_path), full_page=True)
        artifacts["screenshot"] = str(screenshot_path)
    except Exception:
        pass
    try:
        html_path.write_text(await page.content(), encoding="utf-8")
        artifacts["html"] = str(html_path)
    except Exception:
        pass
    try:
        title = ""
        try:
            title = (await page.title()).strip()
        except Exception:
            title = ""
        url = (page.url or "").strip()
        body = (await page.locator("body").inner_text(timeout=2_000)).strip()

        lines: list[str] = []
        if url:
            lines.append(f"URL: {url}")
        if title:
            lines.append(f"Title: {title}")
        if body:
            if lines:
                lines.append("")
            lines.append(body)
        txt_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        artifacts["text"] = str(txt_path)
    except Exception:
        pass

    if _should_capture_perf(label):
        perf_path = debug_dir / f"{stem}.performance.json"
        limit = _debug_perf_resource_limit()
        try:
            perf = await page.evaluate(
                """(limit) => {
  const safeClone = (value) => {
    try {
      return JSON.parse(JSON.stringify(value));
    } catch (e) {
      return null;
    }
  };
  const toEntry = (entry) => ({
    name: entry.name,
    entryType: entry.entryType,
    startTime: entry.startTime,
    duration: entry.duration,
    initiatorType: entry.initiatorType,
    transferSize: entry.transferSize,
    encodedBodySize: entry.encodedBodySize,
    decodedBodySize: entry.decodedBodySize,
    fetchStart: entry.fetchStart,
    domainLookupStart: entry.domainLookupStart,
    domainLookupEnd: entry.domainLookupEnd,
    connectStart: entry.connectStart,
    connectEnd: entry.connectEnd,
    secureConnectionStart: entry.secureConnectionStart,
    requestStart: entry.requestStart,
    responseStart: entry.responseStart,
    responseEnd: entry.responseEnd,
    nextHopProtocol: entry.nextHopProtocol,
    type: entry.type,
  });
  const nav = performance.getEntriesByType ? performance.getEntriesByType("navigation").map(toEntry) : [];
  const resources = performance.getEntriesByType
    ? performance.getEntriesByType("resource").slice(0, Math.max(0, limit)).map(toEntry)
    : [];
  return {
    url: String(location && location.href ? location.href : ""),
    timing: safeClone(performance.timing || null),
    navigation: nav,
    resources: resources,
  };
}""",
                limit,
            )
            perf_path.write_text(json.dumps(perf, ensure_ascii=False, indent=2), encoding="utf-8")
            artifacts["performance"] = str(perf_path)
        except Exception:
            pass

    return artifacts


def _ui_snapshot_run_dir(base_dir: Path) -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    return base_dir / f"{ts}_{random.randint(1000, 9999)}"


def _ui_snapshot_link(doc_path: Path, target_path: Path) -> str:
    try:
        rel = os.path.relpath(str(target_path), start=str(doc_path.parent))
        return rel
    except Exception:
        return str(target_path)


async def _ui_screenshot(
    page,
    *,
    target: str,
    out_dir: Path,
    locator: Any | None = None,
    full_page: bool = False,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{_slugify(target)}.png"

    try:
        if locator is not None:
            if not await locator.count():
                return {"target": target, "error_type": "NotFound", "error": "element not found"}
            candidate = locator.first
            if not await candidate.is_visible():
                return {"target": target, "error_type": "NotVisible", "error": "element found but not visible"}
            await candidate.screenshot(path=str(path))
            return {"target": target, "path": str(path), "mode": "element"}

        await page.screenshot(path=str(path), full_page=bool(full_page))
        return {"target": target, "path": str(path), "mode": "page"}
    except Exception as exc:
        return {"target": target, "error_type": type(exc).__name__, "error": str(exc)}


def _crop_viewport_png(
    *,
    src_path: Path,
    dst_path: Path,
    box: dict[str, Any],
    scroll_x: float,
    scroll_y: float,
    inner_width: float,
    inner_height: float,
) -> None:
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - optional dependency in some envs
        raise RuntimeError("Pillow (PIL) is required for viewport crop screenshots") from exc

    img = Image.open(src_path)
    img_w, img_h = img.size

    iw = float(inner_width or 0.0)
    ih = float(inner_height or 0.0)
    if iw <= 0 or ih <= 0:
        iw, ih = float(img_w), float(img_h)

    scale_x = float(img_w) / iw
    scale_y = float(img_h) / ih

    x0 = (float(box.get("x") or 0.0) - float(scroll_x or 0.0)) * scale_x
    y0 = (float(box.get("y") or 0.0) - float(scroll_y or 0.0)) * scale_y
    x1 = x0 + float(box.get("width") or 0.0) * scale_x
    y1 = y0 + float(box.get("height") or 0.0) * scale_y

    left = max(0, int(math.floor(x0)))
    top = max(0, int(math.floor(y0)))
    right = min(img_w, int(math.ceil(x1)))
    bottom = min(img_h, int(math.ceil(y1)))
    if right <= left or bottom <= top:
        raise ValueError(f"Empty crop rectangle: {(left, top, right, bottom)} from box={box}")

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    img.crop((left, top, right, bottom)).save(dst_path)


async def _ui_screenshot_from_viewport(
    page,
    *,
    target: str,
    out_dir: Path,
    viewport_path: Path,
    viewport_metrics: dict[str, Any],
    locator: Any,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{_slugify(target)}.png"

    try:
        if locator is None:
            return {"target": target, "error_type": "ValueError", "error": "locator is required"}
        if not await locator.count():
            return {"target": target, "error_type": "NotFound", "error": "element not found"}
        candidate = locator.first
        if not await candidate.is_visible():
            return {"target": target, "error_type": "NotVisible", "error": "element found but not visible"}
        box = await candidate.bounding_box()
        if not box:
            return {"target": target, "error_type": "NotVisible", "error": "element has no bounding box"}

        _crop_viewport_png(
            src_path=viewport_path,
            dst_path=path,
            box=box,
            scroll_x=float(viewport_metrics.get("scroll_x") or 0.0),
            scroll_y=float(viewport_metrics.get("scroll_y") or 0.0),
            inner_width=float(viewport_metrics.get("inner_width") or 0.0),
            inner_height=float(viewport_metrics.get("inner_height") or 0.0),
        )
        return {"target": target, "path": str(path), "mode": "crop"}
    except Exception as exc:
        return {"target": target, "error_type": type(exc).__name__, "error": str(exc)}


async def _ui_write_snapshot_doc(
    *,
    doc_path: Path,
    run_dir: Path,
    conversation_url: str,
    title: str,
    model_text: str,
    targets: list[dict[str, Any]],
) -> None:
    doc_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# ChatGPT Web UI Reference (autogenerated)")
    lines.append("")
    lines.append(f"- Updated: `{time.strftime('%Y-%m-%d %H:%M:%S %z')}`")
    lines.append(f"- Conversation URL: `{conversation_url}`")
    if title.strip():
        lines.append(f"- Page title: `{title.strip()}`")
    if model_text.strip():
        lines.append(f"- Model selector text: `{model_text.strip()}`")
    lines.append(f"- Run dir: `{run_dir}`")
    lines.append("")
    lines.append("This doc points to **local screenshots** generated by `chatgpt_web_capture_ui`.")
    lines.append("If images are missing, re-run the tool to regenerate.")
    lines.append("")
    lines.append("## Snapshots")
    lines.append("")

    for item in targets:
        target = str(item.get("target") or "").strip()
        if not target:
            continue
        lines.append(f"### {target}")
        path_raw = item.get("path")
        if isinstance(path_raw, str) and path_raw.strip():
            link = _ui_snapshot_link(doc_path, Path(path_raw))
            lines.append(f"![](<{link}>)")
        else:
            err_type = str(item.get("error_type") or "").strip()
            err = str(item.get("error") or "").strip()
            if err_type or err:
                lines.append(f"- Error: `{(err_type + ': ' if err_type else '') + err}`")
        lines.append("")

    doc_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
