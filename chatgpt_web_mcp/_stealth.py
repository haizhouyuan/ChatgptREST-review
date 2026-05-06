"""Anti-detection stealth scripts, viewport jitter, and human-like mouse movement.

Extracted from _tools_impl.py — ~215 lines of stealth / input-simulation
helpers.  All public names are re-exported by _tools_impl.
"""
from __future__ import annotations

import math
import os
import random
import weakref
from typing import Any

from mcp.server.fastmcp import Context

from chatgpt_web_mcp.env import _truthy_env, _env_float, _env_int_range
from chatgpt_web_mcp.runtime.humanize import _random_log, _human_pause
from chatgpt_web_mcp.runtime.util import _ctx_info

_CHATGPT_STEALTH_INIT_JS = r"""
() => {
  try {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  } catch {}
  try {
    window.chrome = window.chrome || { runtime: {} };
  } catch {}
};
"""

_CHATGPT_DISABLE_ANSWER_NOW_INIT_JS = r"""
() => {
  // Prevent accidental clicks on the "Answer now" affordance inside the thinking panel.
  // This is a UI control that can shorten/skip the thinking phase and degrade output quality.
  //
  // Installed per automation page (does not affect other tabs).
  try {
    window.__chatgptrest_answer_now_blocked_clicks = window.__chatgptrest_answer_now_blocked_clicks || 0;
    window.__chatgptrest_answer_now_blocked_last_ts = window.__chatgptrest_answer_now_blocked_last_ts || 0;
  } catch {}
  const patterns = [
    /answer\s*now/i,
    /立即回答/,
    /现在回答/,
  ];
  function isAnswerNowControl(el) {
    if (!el || !(el instanceof Element)) return false;
    const text = String(el.innerText || el.textContent || "").trim();
    const aria = String(el.getAttribute("aria-label") || "").trim();
    const title = String(el.getAttribute("title") || "").trim();
    const hay = [text, aria, title].filter(Boolean).join("\n");
    if (!hay) return false;
    return patterns.some((re) => re.test(hay));
  }
  document.addEventListener(
    "click",
    (e) => {
      const target = e.target;
      if (!(target instanceof Element)) return;
      const control = target.closest("button, a, [role='button'], [role='link'], input[type='button']");
      if (control && isAnswerNowControl(control)) {
        try {
          try {
            window.__chatgptrest_answer_now_blocked_clicks = (window.__chatgptrest_answer_now_blocked_clicks || 0) + 1;
            window.__chatgptrest_answer_now_blocked_last_ts = Date.now();
          } catch {}
          try { console.info("[chatgptrest] blocked Answer now click"); } catch {}
          e.preventDefault();
          e.stopImmediatePropagation();
        } catch {}
      }
    },
    true
  );
};
"""


_MOUSE_POSITIONS: "weakref.WeakKeyDictionary[Any, tuple[float, float]]" = weakref.WeakKeyDictionary()


def _viewport_jitter_px() -> tuple[int, int]:
    raw = (os.environ.get("CHATGPT_VIEWPORT_JITTER_PX") or "").strip()
    if not raw:
        return (8, 8)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return (8, 8)
    if len(parts) == 1:
        jitter = max(0, int(parts[0]))
        return (jitter, jitter)
    return (max(0, int(parts[0])), max(0, int(parts[1])))


def _apply_viewport_jitter(width: int, height: int) -> tuple[int, int]:
    jitter_w, jitter_h = _viewport_jitter_px()
    if jitter_w <= 0 and jitter_h <= 0:
        return width, height
    delta_w = random.randint(-jitter_w, jitter_w) if jitter_w > 0 else 0
    delta_h = random.randint(-jitter_h, jitter_h) if jitter_h > 0 else 0
    return max(320, width + delta_w), max(240, height + delta_h)


async def _install_stealth_init_script(page, *, ctx: Context | None) -> None:
    if not _truthy_env("CHATGPT_STEALTH_INIT_SCRIPT", True):
        return
    try:
        await page.add_init_script(_CHATGPT_STEALTH_INIT_JS)
    except Exception as exc:
        await _ctx_info(ctx, f"Failed to install stealth init script: {exc}")
    if _truthy_env("CHATGPT_DISABLE_ANSWER_NOW", True):
        try:
            await page.add_init_script(_CHATGPT_DISABLE_ANSWER_NOW_INIT_JS)
        except Exception as exc:
            await _ctx_info(ctx, f"Failed to install Answer-now blocker init script: {exc}")


def _page_viewport_size(page) -> tuple[int, int]:
    size = page.viewport_size or {"width": 1280, "height": 720}
    width = int(size.get("width") or 1280)
    height = int(size.get("height") or 720)
    return max(1, width), max(1, height)


def _clamp_point(x: float, y: float, width: int, height: int) -> tuple[float, float]:
    return (
        max(0.0, min(float(width - 1), x)),
        max(0.0, min(float(height - 1), y)),
    )


def _bezier_point(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float], t: float) -> tuple[float, float]:
    inv = 1.0 - t
    x = (inv**3) * p0[0] + 3 * (inv**2) * t * p1[0] + 3 * inv * (t**2) * p2[0] + (t**3) * p3[0]
    y = (inv**3) * p0[1] + 3 * (inv**2) * t * p1[1] + 3 * inv * (t**2) * p2[1] + (t**3) * p3[1]
    return (x, y)


async def _human_move_mouse(page, *, target: tuple[float, float]) -> None:
    width, height = _page_viewport_size(page)
    start = _MOUSE_POSITIONS.get(page)
    if start is None:
        start = (
            random.uniform(0.2, 0.8) * width,
            random.uniform(0.2, 0.8) * height,
        )
    end = _clamp_point(float(target[0]), float(target[1]), width, height)
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    distance = math.hypot(dx, dy)
    steps = int(min(25, max(8, distance / 80)))

    jitter = max(30.0, min(120.0, distance / 3.0))
    c1 = _clamp_point(start[0] + random.uniform(-jitter, jitter), start[1] + random.uniform(-jitter, jitter), width, height)
    c2 = _clamp_point(end[0] + random.uniform(-jitter, jitter), end[1] + random.uniform(-jitter, jitter), width, height)

    for i in range(1, steps + 1):
        t = i / steps
        x, y = _bezier_point(start, c1, c2, end, t)
        try:
            await page.mouse.move(x, y)
        except Exception:
            break
    _MOUSE_POSITIONS[page] = end


async def _human_move_to_locator(page, locator) -> bool:
    try:
        box = await locator.bounding_box()
    except Exception:
        return False
    if not box:
        return False
    width, height = _page_viewport_size(page)
    target_x = float(box.get("x", 0.0)) + float(box.get("width", 0.0)) * random.uniform(0.35, 0.65)
    target_y = float(box.get("y", 0.0)) + float(box.get("height", 0.0)) * random.uniform(0.35, 0.65)
    target = _clamp_point(target_x, target_y, width, height)
    await _human_move_mouse(page, target=target)
    return True


async def _human_click(page, locator, *, timeout_ms: int = 5_000) -> None:
    try:
        await locator.wait_for(state="visible", timeout=timeout_ms)
    except Exception:
        pass
    try:
        await locator.is_enabled(timeout=timeout_ms)
    except Exception:
        pass
    try:
        await _human_move_to_locator(page, locator)
    except Exception:
        pass
    try:
        await locator.click(timeout=timeout_ms)
        return
    except Exception:
        pass
    try:
        box = await locator.bounding_box()
        if box:
            target_x = float(box.get("x", 0.0)) + float(box.get("width", 0.0)) * 0.5
            target_y = float(box.get("y", 0.0)) + float(box.get("height", 0.0)) * 0.5
            await page.mouse.click(target_x, target_y)
    except Exception:
        return


async def _maybe_idle_interaction(page, *, ctx: Context | None = None) -> None:
    chance = _env_float("CHATGPT_IDLE_ACTION_CHANCE", 0.03)
    if chance <= 0 or random.random() >= chance:
        return
    scroll_low, scroll_high = _env_int_range("CHATGPT_IDLE_SCROLL_PX", 60, 180)
    action_roll = random.random()
    if action_roll < 0.6:
        delta = random.randint(scroll_low, max(scroll_low, scroll_high))
        if random.random() < 0.5:
            delta = -delta
        try:
            await page.mouse.wheel(0, delta)
            await _random_log(ctx, f"idle_scroll delta={delta}")
        except Exception:
            return
        return
    width, height = _page_viewport_size(page)
    target = (
        random.uniform(0.1, 0.9) * width,
        random.uniform(0.1, 0.9) * height,
    )
    try:
        await _human_move_mouse(page, target=target)
        await _random_log(ctx, f"idle_mouse_move x={target[0]:.1f} y={target[1]:.1f}")
    except Exception:
        return
