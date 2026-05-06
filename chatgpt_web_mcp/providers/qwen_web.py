from __future__ import annotations

import asyncio
import json
import os
import random
import re
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from chatgpt_web_mcp.config import ChatGPTWebConfig, _load_config
from chatgpt_web_mcp.env import _compile_env_regex, _env_int, _truthy_env
from chatgpt_web_mcp.idempotency import (
    _IdempotencyContext,
    _hash_request,
    _idempotency_begin,
    _idempotency_namespace,
    _idempotency_update,
    _normalize_idempotency_key,
    _run_id,
)
from chatgpt_web_mcp.proxy import _without_proxy_env

from chatgpt_web_mcp.playwright.cdp import (
    _cdp_fallback_enabled,
    _connect_over_cdp_resilient,
    _ensure_local_cdp_chrome_running,
    _restart_local_cdp_chrome,
)
from chatgpt_web_mcp.playwright.evidence import (
    _capture_debug_artifacts,
    _ui_screenshot,
    _ui_screenshot_from_viewport,
    _ui_snapshot_link,
    _ui_snapshot_run_dir,
)
from chatgpt_web_mcp.playwright.navigation import (
    _goto_with_retry,
    _navigation_timeout_ms,
    _prompt_action_timeout_ms,
)

from chatgpt_web_mcp.runtime.call_log import (
    _call_log_include_answers,
    _call_log_include_prompts,
    _maybe_append_call_log,
)
from chatgpt_web_mcp.runtime.concurrency import _is_tab_limit_error, _page_slot, _tab_limit_result
from chatgpt_web_mcp.runtime.locks import _ask_lock
from chatgpt_web_mcp.runtime.paths import _qwen_ui_snapshot_base_dir, _qwen_ui_snapshot_doc_path
from chatgpt_web_mcp.runtime.ratelimit import _qwen_min_prompt_interval_seconds, _respect_prompt_interval
from chatgpt_web_mcp.runtime.util import _ctx_info, _coerce_error_text
from chatgpt_web_mcp.runtime.humanize import _human_pause, _type_delay_ms
from chatgpt_web_mcp.runtime.answer_classification import _classify_deep_research_answer


_QWEN_SEND_LOCK: asyncio.Lock | None = None
_LAST_QWEN_PROMPT_SENT_AT: float = 0.0


def _qwen_send_lock() -> asyncio.Lock:
    global _QWEN_SEND_LOCK
    if _QWEN_SEND_LOCK is None:
        _QWEN_SEND_LOCK = asyncio.Lock()
    return _QWEN_SEND_LOCK


async def qwen_web_self_check(
    conversation_url: str | None = None,
    timeout_seconds: int = 30,
    ctx: Context | None = None,
) -> dict[str, Any]:
    cfg = _load_qwen_web_config()
    started_at = time.time()
    run_id = _run_id(tool="qwen_web_self_check")
    env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
    with env_ctx:
        async with _page_slot(kind="qwen", ctx=ctx), async_playwright() as p:
            browser = None
            context = None
            page = None
            close_context = False
            try:
                browser, context, page, close_context = await _open_qwen_page(
                    p,
                    cfg,
                    conversation_url=conversation_url,
                    ctx=ctx,
                )

                await _qwen_find_prompt_box(page, timeout_ms=max(5_000, int(timeout_seconds * 1000)))
                model_text = await _qwen_current_model_text(page)
                mode_buttons = await _qwen_mode_buttons_state(page)
                try:
                    title = (await page.title()).strip()
                except Exception:
                    title = ""
                result = {
                    "ok": True,
                    "status": "completed",
                    "conversation_url": (page.url if page is not None else conversation_url),
                    "title": title,
                    "model_text": model_text,
                    "mode_buttons": mode_buttons,
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                }
                _maybe_append_call_log(
                    {
                        "tool": "qwen_web_self_check",
                        "ok": True,
                        "status": "completed",
                        "conversation_url": result.get("conversation_url"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": run_id,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "conversation_url": conversation_url,
                        },
                    }
                )
                return result
            except Exception as exc:
                if _is_tab_limit_error(exc):
                    result = _tab_limit_result(
                        tool="qwen_web_self_check",
                        run_id=run_id,
                        started_at=started_at,
                        conversation_url=conversation_url,
                    )
                    _maybe_append_call_log(
                        {
                            "tool": "qwen_web_self_check",
                            "ok": False,
                            "status": result.get("status"),
                            "elapsed_seconds": result.get("elapsed_seconds"),
                            "run_id": run_id,
                            "params": {
                                "timeout_seconds": timeout_seconds,
                                "conversation_url": conversation_url,
                            },
                            "error_type": result.get("error_type"),
                            "error": result.get("error"),
                        }
                    )
                    return result
                artifacts: dict[str, str] = {}
                if page is not None:
                    try:
                        artifacts = await _capture_debug_artifacts(page, label="qwen_self_check_error")
                    except Exception:
                        artifacts = {}
                result = {
                    "ok": False,
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error": _coerce_error_text(exc),
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "conversation_url": (page.url if page is not None else conversation_url),
                    "debug_artifacts": artifacts,
                }
                _maybe_append_call_log(
                    {
                        "tool": "qwen_web_self_check",
                        "ok": False,
                        "status": "error",
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": run_id,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "conversation_url": conversation_url,
                        },
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "debug_artifacts": artifacts,
                    }
                )
                return result
            finally:
                try:
                    if page is not None:
                        try:
                            await page.close()
                        except Exception:
                            pass
                    if close_context and context is not None:
                        await context.close()
                finally:
                    if browser is not None:
                        await browser.close()


async def qwen_web_capture_ui(
    conversation_url: str | None = None,
    mode: str = "basic",
    timeout_seconds: int = 90,
    out_dir: str | None = None,
    write_doc: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    cfg = _load_qwen_web_config()
    started_at = time.time()
    run_id = _run_id(tool="qwen_web_capture_ui")
    normalized_mode = re.sub(r"[^a-z]+", "", (mode or "").strip().lower())
    if normalized_mode not in {"basic", "full"}:
        return {
            "ok": False,
            "error_type": "ValueError",
            "error": f"Unsupported mode: {mode} (use 'basic' or 'full')",
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
        }

    run_dir = Path(out_dir).expanduser() if (out_dir or "").strip() else _ui_snapshot_run_dir(_qwen_ui_snapshot_base_dir())
    doc_path = _qwen_ui_snapshot_doc_path()
    env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
    with env_ctx:
        async with _page_slot(kind="qwen", ctx=ctx), async_playwright() as p:
            browser = None
            context = None
            page = None
            close_context = False
            targets: list[dict[str, Any]] = []
            notes: list[str] = []
            title = ""
            model_text = ""
            mode_buttons: dict[str, Any] = {}
            conversation_url_effective = ""
            try:
                browser, context, page, close_context = await _open_qwen_page(
                    p,
                    cfg,
                    conversation_url=conversation_url,
                    ctx=ctx,
                )
                conversation_url_effective = (page.url or "").strip()

                prompt = await _qwen_find_prompt_box(page, timeout_ms=max(5_000, int(timeout_seconds * 1000)))
                model_text = await _qwen_current_model_text(page)
                mode_buttons = await _qwen_mode_buttons_state(page)
                try:
                    title = (await page.title()).strip()
                except Exception:
                    title = ""

                targets.append(await _ui_screenshot(page, target="page_full", out_dir=run_dir, full_page=True))
                targets.append(await _ui_screenshot(page, target="composer_prompt", out_dir=run_dir, locator=prompt))
                targets.append(
                    await _ui_screenshot(
                        page,
                        target="model_selector_button",
                        out_dir=run_dir,
                        locator=_qwen_model_selector_locator(page),
                    )
                )
                targets.append(
                    await _ui_screenshot(
                        page,
                        target="mode_deep_thinking_button",
                        out_dir=run_dir,
                        locator=await _qwen_find_mode_button(page, mode="deep_thinking"),
                    )
                )
                targets.append(
                    await _ui_screenshot(
                        page,
                        target="mode_deep_research_button",
                        out_dir=run_dir,
                        locator=await _qwen_find_mode_button(page, mode="deep_research"),
                    )
                )
                targets.append(await _ui_screenshot(page, target="send_button", out_dir=run_dir, locator=_qwen_send_button_locator(page)))
                targets.append(
                    await _ui_screenshot(
                        page,
                        target="sidebar_panel",
                        out_dir=run_dir,
                        locator=page.locator("aside, [class*='SideBar'], [class*='sidebar']").first,
                    )
                )

                if normalized_mode == "full":
                    model_selector = _qwen_model_selector_locator(page)
                    try:
                        if await model_selector.count() and await model_selector.first.is_visible():
                            await model_selector.first.click()
                            await _human_pause(page)
                            model_menu = page.locator("[role='menu']:visible").first
                            targets.append(
                                await _ui_screenshot(
                                    page,
                                    target="model_selector_menu",
                                    out_dir=run_dir,
                                    locator=model_menu,
                                )
                            )
                    except Exception as exc:
                        targets.append({"target": "model_selector_menu", "error_type": type(exc).__name__, "error": str(exc)})
                    finally:
                        try:
                            await page.keyboard.press("Escape")
                            await _human_pause(page)
                        except Exception:
                            pass

                    targets.append(
                        await _ui_screenshot(
                            page,
                            target="latest_answer_block",
                            out_dir=run_dir,
                            locator=page.locator("div.answerItem-SsrVa_, [class*='answerItem']").last,
                        )
                    )
                    if bool(mode_buttons.get("deep_research_quota_exhausted")):
                        notes.append("deep_research_quota_exhausted=true")

                run_dir.mkdir(parents=True, exist_ok=True)
                manifest_path = run_dir / "manifest.json"
                payload = {
                    "tool": "qwen_web_capture_ui",
                    "run_id": run_id,
                    "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "conversation_url": conversation_url_effective,
                    "title": title,
                    "model_text": model_text,
                    "mode": normalized_mode,
                    "mode_buttons": mode_buttons,
                    "targets": targets,
                    "notes": notes,
                }
                manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

                if write_doc:
                    await _qwen_ui_write_snapshot_doc(
                        doc_path=doc_path,
                        run_dir=run_dir,
                        conversation_url=conversation_url_effective,
                        title=title,
                        model_text=model_text,
                        mode_buttons=mode_buttons,
                        targets=targets,
                    )

                result = {
                    "ok": True,
                    "status": "completed",
                    "conversation_url": conversation_url_effective,
                    "run_id": run_id,
                    "mode": normalized_mode,
                    "out_dir": str(run_dir),
                    "manifest_path": str(manifest_path),
                    "doc_path": (str(doc_path) if write_doc else None),
                    "targets": targets,
                    "mode_buttons": mode_buttons,
                    "elapsed_seconds": round(time.time() - started_at, 3),
                }
                _maybe_append_call_log(
                    {
                        "tool": "qwen_web_capture_ui",
                        "ok": True,
                        "status": "completed",
                        "conversation_url": conversation_url_effective,
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": run_id,
                        "params": {
                            "conversation_url": conversation_url,
                            "mode": normalized_mode,
                            "timeout_seconds": timeout_seconds,
                            "out_dir": out_dir,
                            "write_doc": bool(write_doc),
                        },
                        "out_dir": str(run_dir),
                        "manifest_path": str(manifest_path),
                        "doc_path": (str(doc_path) if write_doc else None),
                    }
                )
                return result
            except Exception as exc:
                if _is_tab_limit_error(exc):
                    result = _tab_limit_result(
                        tool="qwen_web_capture_ui",
                        run_id=run_id,
                        started_at=started_at,
                        conversation_url=conversation_url_effective or conversation_url,
                        extra={
                            "out_dir": str(run_dir),
                            "doc_path": (str(doc_path) if write_doc else None),
                        },
                    )
                    _maybe_append_call_log(
                        {
                            "tool": "qwen_web_capture_ui",
                            "ok": False,
                            "status": result.get("status"),
                            "elapsed_seconds": result.get("elapsed_seconds"),
                            "run_id": run_id,
                            "params": {
                                "conversation_url": conversation_url,
                                "mode": normalized_mode,
                                "timeout_seconds": timeout_seconds,
                                "out_dir": out_dir,
                                "write_doc": bool(write_doc),
                            },
                            "error_type": result.get("error_type"),
                            "error": result.get("error"),
                        }
                    )
                    return result
                artifacts: dict[str, str] = {}
                if page is not None:
                    try:
                        artifacts = await _capture_debug_artifacts(page, label="qwen_capture_ui_error")
                    except Exception:
                        artifacts = {}
                result = {
                    "ok": False,
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error": _coerce_error_text(exc),
                    "run_id": run_id,
                    "conversation_url": conversation_url_effective or conversation_url,
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "debug_artifacts": artifacts,
                    "out_dir": str(run_dir),
                    "doc_path": (str(doc_path) if write_doc else None),
                }
                _maybe_append_call_log(
                    {
                        "tool": "qwen_web_capture_ui",
                        "ok": False,
                        "status": "error",
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": run_id,
                        "params": {
                            "conversation_url": conversation_url,
                            "mode": normalized_mode,
                            "timeout_seconds": timeout_seconds,
                            "out_dir": out_dir,
                            "write_doc": bool(write_doc),
                        },
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "debug_artifacts": artifacts,
                    }
                )
                return result
            finally:
                try:
                    if page is not None:
                        try:
                            await page.close()
                        except Exception:
                            pass
                    if close_context and context is not None:
                        await context.close()
                finally:
                    if browser is not None:
                        await browser.close()




def _qwen_model_selector_locator(page) -> Any:
    return page.locator("button").filter(has_text=re.compile(r"qwen\\s*\\d", re.I)).first


def _qwen_send_button_locator(page) -> Any:
    return page.locator(
        "button[aria-label='发送'], "
        "button[aria-label='Send'], "
        "button[class*='operateBtn'], "
        "div[class*='operateBtn']"
    ).first


async def _qwen_mode_buttons_state(page) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for mode in ("deep_thinking", "deep_research"):
        btn = await _qwen_find_mode_button(page, mode=mode)
        state: dict[str, Any] = {"visible": False, "enabled": False, "label": ""}
        if btn is not None:
            try:
                state["visible"] = bool(await btn.is_visible())
            except Exception:
                state["visible"] = False
            try:
                state["enabled"] = bool(await btn.is_enabled())
            except Exception:
                state["enabled"] = False
            try:
                state["label"] = str(await btn.inner_text(timeout=1000)).strip()
            except Exception:
                state["label"] = ""
        out[mode] = state
    try:
        body = (await page.locator("body").inner_text(timeout=2_000)).strip()
    except Exception:
        body = ""
    out["deep_research_quota_exhausted"] = bool(_QWEN_DEEP_RESEARCH_QUOTA_RE.search(body))
    return out


async def _qwen_ui_write_snapshot_doc(
    *,
    doc_path: Path,
    run_dir: Path,
    conversation_url: str,
    title: str,
    model_text: str,
    mode_buttons: dict[str, Any],
    targets: list[dict[str, Any]],
) -> None:
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Qwen Web UI Reference (autogenerated)")
    lines.append("")
    lines.append(f"- Updated: `{time.strftime('%Y-%m-%d %H:%M:%S %z')}`")
    lines.append(f"- Conversation URL: `{conversation_url}`")
    if title.strip():
        lines.append(f"- Page title: `{title.strip()}`")
    if model_text.strip():
        lines.append(f"- Model selector text: `{model_text.strip()}`")
    lines.append(f"- Run dir: `{run_dir}`")
    if isinstance(mode_buttons, dict):
        quota = mode_buttons.get("deep_research_quota_exhausted")
        lines.append(f"- Deep research quota exhausted: `{bool(quota)}`")
    lines.append("")
    lines.append("This doc points to local screenshots generated by `qwen_web_capture_ui`.")
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


async def qwen_web_ask(
    question: str,
    idempotency_key: str,
    conversation_url: str | None = None,
    preset: str = "deep_thinking",
    timeout_seconds: int = 600,
    ctx: Context | None = None,
) -> dict[str, Any]:
    tool_name = "qwen_web_ask"
    run_id = _run_id(tool=tool_name, idempotency_key=idempotency_key)
    normalized_preset = _qwen_normalize_preset(preset)
    idem = _IdempotencyContext(
        namespace=_idempotency_namespace(ctx),
        tool=tool_name,
        key=_normalize_idempotency_key(idempotency_key),
        request_hash=_hash_request(
            {
                "tool": tool_name,
                "question": question,
                "preset": normalized_preset,
            }
        ),
    )
    should_execute, existing = await _idempotency_begin(idem)
    if not should_execute:
        if isinstance((existing or {}).get("result"), dict):
            cached = dict(existing["result"])
            cached.setdefault("run_id", run_id)
            cached.setdefault(
                "ok",
                bool(
                    str(cached.get("status") or "").strip().lower() not in {"error", "blocked", "cooldown"}
                    and not str(cached.get("error_type") or "").strip()
                    and not str(cached.get("error") or "").strip()
                ),
            )
            cached["replayed"] = True
            return cached
        status = str((existing or {}).get("status") or "in_progress").strip()
        ok = status.lower() not in {"error", "blocked", "cooldown"}
        return {
            "ok": ok,
            "answer": "",
            "status": status,
            "conversation_url": str((existing or {}).get("conversation_url") or conversation_url or ""),
            "elapsed_seconds": 0.0,
            "run_id": run_id,
            "replayed": True,
            "error_type": None,
            "error": (str((existing or {}).get("error") or "").strip() or None),
        }

    async with _ask_lock():
        cfg = _load_qwen_web_config()
        if cfg.cdp_url is None and not cfg.storage_state_path.exists():
            msg = (
                f"Missing storage_state.json at {cfg.storage_state_path}. "
                "Set QWEN_CDP_URL (recommended) or provide QWEN_STORAGE_STATE."
            )
            result = {
                "ok": False,
                "status": "error",
                "answer": "",
                "conversation_url": str(conversation_url or "").strip(),
                "elapsed_seconds": 0.0,
                "run_id": run_id,
                "error_type": "RuntimeError",
                "error": msg,
            }
            try:
                await _idempotency_update(idem, status="error", result=result, error=f"RuntimeError: {msg}")
            except Exception:
                pass
            return result

        started_at = time.time()
        env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
        with env_ctx:
            async with _page_slot(kind="qwen", ctx=ctx), async_playwright() as p:
                browser = None
                context = None
                page = None
                close_context = False
                sent = False
                effective_conversation_url = str(conversation_url or "").strip()
                mode_effective = "deep_thinking"
                try:
                    browser, context, page, close_context = await _open_qwen_page(
                        p,
                        cfg,
                        conversation_url=conversation_url,
                        ctx=ctx,
                    )

                    if conversation_url is None:
                        await _goto_with_retry(page, cfg.url, ctx=ctx)
                        try:
                            await page.wait_for_load_state("domcontentloaded", timeout=20_000)
                        except Exception:
                            pass
                        await _human_pause(page)
                        await _qwen_click_new_chat(page)

                    await _qwen_find_prompt_box(page)
                    await _qwen_ensure_highest_model(page, ctx=ctx)
                    mode_effective = await _qwen_ensure_mode(page, preset=normalized_preset, ctx=ctx)
                    await _human_pause(page)

                    start_state = await _qwen_last_response_state(page)
                    start_answer_count = int(start_state.get("count") or 0)
                    prompt_box = await _qwen_find_prompt_box(page)
                    await prompt_box.click()
                    await _human_pause(page)
                    await _qwen_type_question(prompt_box, question)
                    await _human_pause(page)

                    await _qwen_click_send(page, prompt_box, ctx=ctx)
                    sent = True
                    try:
                        effective_conversation_url = await _qwen_wait_for_conversation_url(page, timeout_seconds=8.0)
                    except Exception:
                        effective_conversation_url = (page.url or "").strip() or effective_conversation_url
                    try:
                        await _idempotency_update(
                            idem,
                            sent=True,
                            conversation_url=(effective_conversation_url or conversation_url),
                        )
                    except Exception:
                        pass

                    min_chars = 0 if len((question or "").strip()) < 80 else (800 if mode_effective == "deep_research" else 200)
                    answer, is_complete = await _qwen_wait_for_model_response(
                        page,
                        started_answer_count=start_answer_count,
                        started_last_text=str(start_state.get("text") or ""),
                        timeout_seconds=timeout_seconds,
                        min_chars=min_chars,
                        require_new=True,
                    )

                    if answer and _QWEN_TRANSIENT_ERROR_RE.search(answer):
                        raise RuntimeError(f"Qwen returned a transient error message: {answer}")

                    if is_complete:
                        if mode_effective == "deep_research":
                            status = _classify_deep_research_answer(answer)
                        else:
                            status = "completed"
                    else:
                        status = "in_progress"
                    result = {
                        "ok": True,
                        "answer": answer,
                        "status": status,
                        "conversation_url": (page.url or effective_conversation_url),
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                        "preset": normalized_preset,
                        "mode": mode_effective,
                    }
                    try:
                        await _idempotency_update(
                            idem,
                            status=str(result.get("status") or "completed"),
                            conversation_url=str(result.get("conversation_url") or ""),
                            result=result,
                        )
                    except Exception:
                        pass
                    event: dict[str, Any] = {
                        "tool": "qwen_web_ask",
                        "status": result.get("status"),
                        "conversation_url": result.get("conversation_url"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": result.get("run_id") or run_id,
                        "idempotency_key": idem.key,
                        "idempotency_namespace": idem.namespace,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "conversation_url": conversation_url,
                            "preset": normalized_preset,
                            "mode": mode_effective,
                        },
                    }
                    if _call_log_include_prompts():
                        event["question"] = question
                    if _call_log_include_answers():
                        event["answer"] = result.get("answer")
                    else:
                        event["answer_chars"] = len((result.get("answer") or "").strip())
                    _maybe_append_call_log(event)
                    return result
                except Exception as exc:
                    err_text = _coerce_error_text(exc)
                    exc_type = type(exc).__name__
                    status = "in_progress" if sent else "error"
                    retry_after_seconds = None
                    if isinstance(exc, _QwenNotLoggedInError):
                        status = "needs_followup"
                        retry_after_seconds = int(exc.retry_after_seconds)
                    if isinstance(exc, _QwenModeQuotaError):
                        status = "cooldown"
                        retry_after_seconds = int(exc.retry_after_seconds)
                    artifacts: dict[str, str] = {}
                    if page is not None:
                        artifacts = await _capture_debug_artifacts(page, label="qwen_web_ask_error")
                        if ctx and artifacts:
                            await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")

                    result = {
                        "ok": False,
                        "status": status,
                        "answer": "",
                        "conversation_url": (page.url if page is not None else conversation_url),
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                        "error_type": exc_type,
                        "error": err_text,
                        "debug_artifacts": artifacts,
                        "preset": normalized_preset,
                        "mode": mode_effective,
                        "retry_after_seconds": retry_after_seconds,
                    }
                    try:
                        await _idempotency_update(
                            idem,
                            status=("in_progress" if sent else status),
                            sent=bool(sent),
                            conversation_url=str(result.get("conversation_url") or ""),
                            result=result,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    except Exception:
                        pass
                    event: dict[str, Any] = {
                        "tool": "qwen_web_ask",
                        "status": status,
                        "conversation_url": result.get("conversation_url"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": run_id,
                        "idempotency_key": idem.key,
                        "idempotency_namespace": idem.namespace,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "conversation_url": conversation_url,
                            "preset": normalized_preset,
                            "mode": mode_effective,
                        },
                        "error_type": exc_type,
                        "error": err_text,
                    }
                    if _call_log_include_prompts():
                        event["question"] = question
                    if artifacts:
                        event["debug_artifacts"] = artifacts
                    _maybe_append_call_log(event)
                    return result
                finally:
                    try:
                        if page is not None:
                            try:
                                await page.close()
                            except Exception:
                                pass
                        if close_context and context is not None:
                            await context.close()
                    finally:
                        if browser is not None:
                            await browser.close()


async def qwen_web_wait(
    conversation_url: str,
    timeout_seconds: int = 600,
    min_chars: int = 200,
    deep_research: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    run_id = _run_id(tool="qwen_web_wait")
    cfg = _load_qwen_web_config()
    started_at = time.time()
    env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
    with env_ctx:
        async with _page_slot(kind="qwen", ctx=ctx), async_playwright() as p:
            browser = None
            context = None
            page = None
            close_context = False
            try:
                browser, context, page, close_context = await _open_qwen_page(
                    p,
                    cfg,
                    conversation_url=conversation_url,
                    ctx=ctx,
                )

                await _qwen_find_prompt_box(page)
                effective_url = await _qwen_wait_for_conversation_url(page, timeout_seconds=5.0)
                answer, is_complete = await _qwen_wait_for_model_response(
                    page,
                    started_answer_count=0,
                    started_last_text="",
                    timeout_seconds=timeout_seconds,
                    min_chars=max(0, int(min_chars)),
                    require_new=False,
                )
                if answer and _QWEN_TRANSIENT_ERROR_RE.search(answer):
                    return {
                        "ok": False,
                        "answer": answer,
                        "status": "cooldown",
                        "conversation_url": (effective_url or page.url),
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                        "error_type": "RuntimeError",
                        "error": "Qwen returned a transient error message",
                        "retry_after_seconds": 30,
                    }
                if is_complete:
                    status = _classify_deep_research_answer(answer) if deep_research else "completed"
                else:
                    status = "in_progress"
                result = {
                    "ok": True,
                    "answer": answer,
                    "status": status,
                    "conversation_url": (effective_url or page.url),
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "error_type": None,
                    "error": None,
                }
                event: dict[str, Any] = {
                    "tool": "qwen_web_wait",
                    "status": result.get("status"),
                    "conversation_url": result.get("conversation_url"),
                    "elapsed_seconds": result.get("elapsed_seconds"),
                    "run_id": run_id,
                    "params": {
                        "timeout_seconds": timeout_seconds,
                        "min_chars": min_chars,
                        "deep_research": deep_research,
                        "conversation_url": conversation_url,
                    },
                }
                if _call_log_include_answers():
                    event["answer"] = result.get("answer")
                else:
                    event["answer_chars"] = len((result.get("answer") or "").strip())
                _maybe_append_call_log(event)
                return result
            except Exception as exc:
                err_text = _coerce_error_text(exc)
                status = "error"
                retry_after_seconds = None
                if isinstance(exc, _QwenNotLoggedInError):
                    status = "needs_followup"
                    retry_after_seconds = int(exc.retry_after_seconds)
                if isinstance(exc, _QwenModeQuotaError):
                    status = "cooldown"
                    retry_after_seconds = int(exc.retry_after_seconds)
                artifacts: dict[str, str] = {}
                if page is not None:
                    artifacts = await _capture_debug_artifacts(page, label="qwen_web_wait_error")
                    if ctx and artifacts:
                        await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")
                result = {
                    "ok": False,
                    "answer": "",
                    "status": status,
                    "conversation_url": (page.url if page is not None else conversation_url),
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "error_type": type(exc).__name__,
                    "error": err_text,
                    "debug_artifacts": artifacts,
                    "retry_after_seconds": retry_after_seconds,
                }
                event: dict[str, Any] = {
                    "tool": "qwen_web_wait",
                    "status": status,
                    "conversation_url": result.get("conversation_url"),
                    "elapsed_seconds": result.get("elapsed_seconds"),
                    "run_id": run_id,
                    "params": {
                        "timeout_seconds": timeout_seconds,
                        "min_chars": min_chars,
                        "deep_research": deep_research,
                        "conversation_url": conversation_url,
                    },
                    "error_type": type(exc).__name__,
                    "error": err_text,
                }
                if artifacts:
                    event["debug_artifacts"] = artifacts
                _maybe_append_call_log(event)
                return result
            finally:
                try:
                    if page is not None:
                        try:
                            await page.close()
                        except Exception:
                            pass
                    if close_context and context is not None:
                        await context.close()
                finally:
                    if browser is not None:
                        await browser.close()


_QWEN_THREAD_URL_RE = re.compile(r"^https?://(?:[^/]*\.)?qianwen\.com/chat/[0-9a-f]{32}(?:[/?#]|$)", re.I)
_QWEN_HIGHEST_MODEL_RE = re.compile(r"(Qwen\s*3\s*[-–]?\s*Max|Qwen3-Max)", re.I)
_QWEN_TRANSIENT_ERROR_RE = re.compile(r"(系统超时|稍后重试|服务繁忙|网络异常|请求过于频繁|temporary error)", re.I)
_QWEN_DEEP_RESEARCH_QUOTA_RE = re.compile(
    r"("
    r"今天还能研究\s*0\s*次|"
    r"今日.*?(研究|调研).*?(上限|用完|次数)|"
    r"深度研究.*?(额度|配额).*(不足|用完)|"
    r"每天.*5次.*(已用完|上限)"
    r")",
    re.I,
)
_QWEN_LOGIN_RE = re.compile(r"(登录|短信验证码|手机号|扫码登录|立即登录|请先登录)", re.I)
_QWEN_REPORT_CARD_ACK_RE = re.compile(r"(请查看研究报告|创建于\s*\d{2}-\d{2})", re.I)
_QWEN_SELF_REFLECTION_RE = re.compile(r"(用户要求|我应该|只回复|系统连通性测试|严格遵守|不能添加)", re.I)


def _qwen_viewer_run_dir() -> Path:
    raw = (os.environ.get("QWEN_VIEWER_RUN_DIR") or ".run/qwen_viewer").strip()
    return Path(raw).expanduser()


def _qwen_viewer_novnc_url() -> str | None:
    # Best-effort: surface the noVNC URL so operators can login when Qwen needs follow-up.
    host = ""
    try:
        host_path = _qwen_viewer_run_dir() / "novnc_bind_host.txt"
        if host_path.exists():
            host = host_path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        host = ""
    if not host:
        host = str(os.environ.get("QWEN_VIEWER_NOVNC_BIND_HOST") or "").strip()

    port_raw = str(os.environ.get("QWEN_VIEWER_NOVNC_PORT") or "").strip()
    try:
        port = int(port_raw) if port_raw else 6085
    except Exception:
        port = 6085
    if not (1 <= port <= 65535):
        port = 6085

    if not host:
        return None
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    return f"http://{host}:{port}/vnc.html"


class _QwenModeQuotaError(RuntimeError):
    def __init__(self, message: str, *, retry_after_seconds: int = 12 * 60 * 60) -> None:
        super().__init__(message)
        self.retry_after_seconds = max(60, int(retry_after_seconds))


class _QwenNotLoggedInError(RuntimeError):
    def __init__(self, message: str, *, retry_after_seconds: int = 5 * 60) -> None:
        super().__init__(message)
        self.retry_after_seconds = max(30, int(retry_after_seconds))


def _qwen_normalize_preset(value: str | None) -> str:
    raw = re.sub(r"[^a-z_\\-]+", "", str(value or "").strip().lower())
    if raw in {"", "auto", "default", "defaults", "deep_thinking", "deepthinking", "thinking", "deep-thinking"}:
        return "deep_thinking"
    if raw in {"deep_research", "deep-research", "deepresearch", "research"}:
        return "deep_research"
    raise ValueError(f"Unsupported Qwen preset: {value}")


def _load_qwen_web_config() -> ChatGPTWebConfig:
    base = _load_config()
    url = (os.environ.get("QWEN_WEB_URL") or "https://www.qianwen.com/chat").strip()
    storage_state_default = "secrets/qwen_storage_state.json"
    storage_state = Path(os.environ.get("QWEN_STORAGE_STATE") or storage_state_default).expanduser().resolve()
    cdp_url = (os.environ.get("QWEN_CDP_URL") or "http://127.0.0.1:9335").strip() or None
    headless = _truthy_env("QWEN_HEADLESS", base.headless)
    viewport_width = int(os.environ.get("QWEN_VIEWPORT_WIDTH") or base.viewport_width)
    viewport_height = int(os.environ.get("QWEN_VIEWPORT_HEIGHT") or base.viewport_height)

    proxy_server = os.environ.get("QWEN_PROXY_SERVER")
    proxy_username = os.environ.get("QWEN_PROXY_USERNAME")
    proxy_password = os.environ.get("QWEN_PROXY_PASSWORD")

    return ChatGPTWebConfig(
        url=url,
        storage_state_path=storage_state,
        cdp_url=cdp_url,
        headless=headless,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        proxy_server=proxy_server,
        proxy_username=proxy_username,
        proxy_password=proxy_password,
    )


async def _raise_if_qwen_blocked(page) -> None:
    title = ""
    try:
        title = (await page.title()).strip()
    except Exception:
        title = ""
    url = page.url or ""

    body = ""
    try:
        body = (await page.locator("body").inner_text(timeout=2_000)).strip()
    except Exception:
        body = ""

    hay = " ".join([title, url, body])
    if "qianwen.com" not in (url or ""):
        artifacts = await _capture_debug_artifacts(page, label="qwen_wrong_host")
        msg = f"Qwen page redirected to a non-qianwen host: {url}"
        if artifacts:
            msg += f" Debug artifacts: {artifacts}"
        raise RuntimeError(msg)

    if _QWEN_LOGIN_RE.search(hay):
        artifacts = await _capture_debug_artifacts(page, label="qwen_login")
        msg = "Qwen appears to require login in this browser profile."
        viewer_url = _qwen_viewer_novnc_url()
        if viewer_url:
            msg += f" Login via noVNC: {viewer_url}"
        else:
            msg += " Start the viewer with: bash ops/qwen_viewer_start.sh"
        if artifacts:
            msg += f" Debug artifacts: {artifacts}"
        raise _QwenNotLoggedInError(msg)


async def _open_qwen_page(p, cfg: ChatGPTWebConfig, *, conversation_url: str | None, ctx: Context | None):
    if cfg.cdp_url:
        await _ctx_info(ctx, f"Qwen: connecting over CDP: {cfg.cdp_url}")
    else:
        await _ctx_info(ctx, f"Qwen: launching Chromium (headless={cfg.headless})")

    use_cdp = bool(cfg.cdp_url)
    if use_cdp:
        await _ensure_local_cdp_chrome_running(kind="qwen", cdp_url=cfg.cdp_url, ctx=ctx)

        async def _open_over_cdp() -> tuple[Any, Any, Any, bool]:
            browser = await _connect_over_cdp_resilient(p, cfg.cdp_url, ctx=ctx)
            if browser is None:
                raise RuntimeError("connect_over_cdp returned null browser")
            if not browser.contexts:
                raise RuntimeError("No Chrome contexts found via Qwen CDP.")
            context = browser.contexts[0]
            # Always open a fresh page for each Qwen call to avoid inheriting stale
            # split-screen/sidebar UI state from an existing manual tab.
            page = await context.new_page()

            target_url = conversation_url or cfg.url
            current_url = page.url or ""
            if conversation_url:
                should_navigate = True
            else:
                if not current_url or current_url == "about:blank":
                    should_navigate = True
                else:
                    should_navigate = not bool(
                        re.match(r"^https?://(?:[^/]*\.)?qianwen\.com/chat(?:$|[/?#])", current_url, re.I)
                    )

            if should_navigate:
                await _ctx_info(ctx, f"Qwen: navigating to {target_url}")
                await _goto_with_retry(page, target_url, ctx=ctx)
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=20_000)
                except Exception:
                    pass
                await page.wait_for_timeout(1_500)

            close_context = False
            return browser, context, page, close_context

        cdp_ok = False
        try:
            browser, context, page, close_context = await _open_over_cdp()
            cdp_ok = True
        except Exception as e:
            restarted = await _restart_local_cdp_chrome(kind="qwen", cdp_url=cfg.cdp_url, ctx=ctx)
            if restarted:
                await _ctx_info(ctx, "Qwen: retrying CDP connect after Chrome restart …")
                try:
                    browser, context, page, close_context = await _open_over_cdp()
                    cdp_ok = True
                except Exception as e2:
                    e = e2

            if not cdp_ok:
                if not _cdp_fallback_enabled(kind="qwen"):
                    msg = (
                        f"Qwen CDP connect failed ({type(e).__name__}: {e}). "
                        "Ensure the dedicated Qwen Chrome is running and reachable via QWEN_CDP_URL."
                    )
                    raise RuntimeError(msg) from e
                await _ctx_info(ctx, f"Qwen CDP connect failed ({type(e).__name__}: {e}). Falling back to storage_state launch.")
                use_cdp = False

        if use_cdp:
            await _raise_if_qwen_blocked(page)
            return browser, context, page, close_context

    if not use_cdp:
        proxy = None
        if cfg.proxy_server:
            proxy = {"server": cfg.proxy_server}
            if cfg.proxy_username:
                proxy["username"] = cfg.proxy_username
            if cfg.proxy_password:
                proxy["password"] = cfg.proxy_password
            await _ctx_info(ctx, f"Qwen: using proxy override: {cfg.proxy_server}")

        browser = await p.chromium.launch(headless=cfg.headless, proxy=proxy)
        context = await browser.new_context(
            storage_state=str(cfg.storage_state_path),
            viewport={"width": cfg.viewport_width, "height": cfg.viewport_height},
        )
        page = await context.new_page()

        url = conversation_url or cfg.url
        await _ctx_info(ctx, f"Qwen: navigating to {url}")
        await _goto_with_retry(page, url, ctx=ctx)
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=20_000)
        except Exception:
            pass
        await page.wait_for_timeout(1_500)
        close_context = True

    await _raise_if_qwen_blocked(page)
    return browser, context, page, close_context


async def _qwen_click_new_chat(page) -> None:
    candidates = [
        "button:has-text('新对话')",
        "a:has-text('新对话')",
        "button:has-text('New chat')",
        "a:has-text('New chat')",
    ]
    for selector in candidates:
        locator = page.locator(selector).first
        try:
            if await locator.count() and await locator.is_visible():
                await locator.click()
                await _human_pause(page)
                return
        except Exception:
            continue


async def _qwen_find_prompt_box(page, *, timeout_ms: int = 15_000) -> Any:
    candidates = [
        "div[role='textbox'][contenteditable='true']",
        "div[contenteditable='true'][role='textbox']",
        "div[role='textbox']",
        "textarea",
        "div[contenteditable='true']",
    ]
    deadline = time.time() + max(0.5, timeout_ms / 1000)
    viewport_h = int((page.viewport_size or {}).get("height") or 900)
    while time.time() < deadline:
        for selector in candidates:
            locator = page.locator(selector)
            count = await locator.count()
            if count <= 0:
                continue
            for i in range(min(count, 12)):
                item = locator.nth(i)
                try:
                    if not await item.is_visible():
                        continue
                    box = await item.bounding_box()
                    if box and float(box.get("y", 0.0)) < (viewport_h * 0.2):
                        continue
                    return item
                except PlaywrightTimeoutError:
                    continue
                except Exception:
                    continue
        await page.wait_for_timeout(200)
    await _raise_if_qwen_blocked(page)
    raise RuntimeError("Cannot find Qwen prompt box.")


async def _qwen_wait_for_conversation_url(page, *, timeout_seconds: float = 8.0) -> str:
    deadline = time.time() + max(0.2, timeout_seconds)
    last = (page.url or "").strip()
    while time.time() < deadline:
        url = (page.url or "").strip()
        if url and url != last:
            last = url
        if _QWEN_THREAD_URL_RE.match(url):
            return url
        try:
            href = await page.evaluate("() => window.location && window.location.href ? String(window.location.href) : ''")
            href = (str(href or "").strip() if href is not None else "")
            if href and href != last:
                last = href
            if _QWEN_THREAD_URL_RE.match(href):
                return href
        except Exception:
            pass
        await page.wait_for_timeout(250)
    return last


async def _qwen_current_model_text(page) -> str:
    try:
        text = await page.evaluate(
            """() => {
                const vis=(el)=>{if(!el)return false; const s=getComputedStyle(el); if(s.display==='none'||s.visibility==='hidden'||s.opacity==='0') return false; const r=el.getBoundingClientRect(); return r.width>1&&r.height>1; };
                const re = /qwen\\s*\\d/i;
                const nodes = Array.from(document.querySelectorAll('button,div,span')).filter((el)=>{
                    if(!vis(el)) return false;
                    const t = (el.innerText || '').trim();
                    if(!t || t.length > 80) return false;
                    if(!re.test(t)) return false;
                    const r = el.getBoundingClientRect();
                    return r.y < 120 && r.x < 480;
                }).sort((a,b)=>{
                    const ra=a.getBoundingClientRect(), rb=b.getBoundingClientRect();
                    if (Math.abs(ra.y-rb.y) > 6) return ra.y-rb.y;
                    return ra.x-rb.x;
                });
                if(!nodes.length) return '';
                return (nodes[0].innerText || '').trim().replace(/\\s+/g,' ');
            }"""
        )
        return str(text or "").strip()
    except Exception:
        return ""


async def _qwen_ensure_highest_model(page, *, ctx: Context | None) -> None:
    current = await _qwen_current_model_text(page)
    if _QWEN_HIGHEST_MODEL_RE.search(current):
        return

    await _ctx_info(ctx, "Qwen: switching model → Qwen3-Max")
    clicked_menu = await page.evaluate(
        """() => {
            const vis=(el)=>{if(!el)return false; const s=getComputedStyle(el); if(s.display==='none'||s.visibility==='hidden'||s.opacity==='0') return false; const r=el.getBoundingClientRect(); return r.width>1&&r.height>1; };
            const re = /qwen\\s*\\d/i;
            const btns = Array.from(document.querySelectorAll('button')).filter((el)=>{
                if(!vis(el)) return false;
                const t=(el.innerText||'').trim();
                if(!t || t.length>80) return false;
                const r=el.getBoundingClientRect();
                return re.test(t) && r.y < 120 && r.x < 480;
            }).sort((a,b)=>{
                const ra=a.getBoundingClientRect(), rb=b.getBoundingClientRect();
                if (Math.abs(ra.y-rb.y) > 6) return ra.y-rb.y;
                return ra.x-rb.x;
            });
            if(!btns.length) return false;
            btns[0].click();
            return true;
        }"""
    )
    if not clicked_menu:
        raise RuntimeError(f"Qwen model selector not found (current={current!r}).")
    await _human_pause(page)

    selected = await page.evaluate(
        """() => {
            const vis=(el)=>{if(!el)return false; const s=getComputedStyle(el); if(s.display==='none'||s.visibility==='hidden'||s.opacity==='0') return false; const r=el.getBoundingClientRect(); return r.width>1&&r.height>1; };
            const re = /(Qwen\\s*3\\s*[-–]?\\s*Max|Qwen3-Max)/i;
            const nodes = Array.from(document.querySelectorAll('button,[role=\"menuitem\"],div')).filter((el)=>{
                if(!vis(el)) return false;
                const t=(el.innerText||'').trim();
                if(!t || t.length>120) return false;
                if(!re.test(t)) return false;
                const r = el.getBoundingClientRect();
                return r.y > 40;
            }).sort((a,b)=>{
                const ra=a.getBoundingClientRect(), rb=b.getBoundingClientRect();
                if (Math.abs(ra.y-rb.y) > 6) return ra.y-rb.y;
                return ra.x-rb.x;
            });
            if(!nodes.length) return {ok:false};
            nodes[0].dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));
            nodes[0].dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));
            nodes[0].dispatchEvent(new MouseEvent('click',{bubbles:true}));
            return {ok:true,text:(nodes[0].innerText||'').trim().replace(/\\s+/g,' ')};
        }"""
    )
    if not bool((selected or {}).get("ok")):
        raise RuntimeError("Qwen model menu opened but Qwen3-Max option was not found.")
    await _human_pause(page)

    final_text = await _qwen_current_model_text(page)
    if not _QWEN_HIGHEST_MODEL_RE.search(final_text):
        raise RuntimeError(f"Qwen model switch did not apply (current={final_text!r}).")


async def _qwen_find_mode_button(page, *, mode: str) -> Any | None:
    if mode == "deep_research":
        patterns = [re.compile(r"^(深度研究|深度调研|Deep Research)$", re.I)]
    else:
        patterns = [re.compile(r"^(深度思考|Deep Thinking)$", re.I)]
    for pat in patterns:
        locator = page.locator("button").filter(has_text=pat)
        try:
            count = await locator.count()
        except Exception:
            count = 0
        if count <= 0:
            continue
        for i in range(min(count, 8)):
            cand = locator.nth(i)
            try:
                if await cand.is_visible():
                    return cand
            except Exception:
                continue
    return None


async def _qwen_ensure_mode(page, *, preset: str, ctx: Context | None) -> str:
    target = "deep_research" if preset == "deep_research" else "deep_thinking"
    btn = await _qwen_find_mode_button(page, mode=target)
    if btn is None:
        if target == "deep_research":
            raise RuntimeError("Qwen deep research button not found.")
        await _ctx_info(ctx, "Qwen deep-thinking button not found; continuing best-effort.")
        return "unknown"
    try:
        if not await btn.is_enabled():
            if target == "deep_research":
                body = (await page.locator("body").inner_text(timeout=2_000)).strip()
                if _QWEN_DEEP_RESEARCH_QUOTA_RE.search(body):
                    raise _QwenModeQuotaError("Qwen deep research daily quota appears exhausted.")
            raise RuntimeError(f"Qwen mode button is disabled: {target}")
    except _QwenModeQuotaError:
        raise
    except Exception:
        pass
    try:
        await btn.click()
    except Exception:
        # Fallback to JS click for transient overlays.
        try:
            handle = await btn.element_handle()
            if handle is not None:
                await handle.evaluate("el => el.click()")
        except Exception:
            raise RuntimeError(f"Failed to click Qwen mode button: {target}") from None
    await _human_pause(page)
    if target == "deep_research":
        try:
            body = (await page.locator("body").inner_text(timeout=2_000)).strip()
        except Exception:
            body = ""
        if _QWEN_DEEP_RESEARCH_QUOTA_RE.search(body):
            raise _QwenModeQuotaError("Qwen deep research daily quota appears exhausted.")
    return target


async def _qwen_type_question(prompt_box, question: str) -> None:
    timeout_ms = _prompt_action_timeout_ms()
    try:
        await prompt_box.fill(question, timeout=timeout_ms)
        return
    except Exception:
        pass
    await prompt_box.click(timeout=timeout_ms)
    try:
        await prompt_box.press("Control+A")
        await prompt_box.press("Backspace")
    except Exception:
        pass
    await prompt_box.type(question, delay=max(0, _type_delay_ms()), timeout=timeout_ms)


async def _qwen_click_send(page, prompt_box, *, ctx: Context | None = None) -> None:
    global _LAST_QWEN_PROMPT_SENT_AT
    async with _qwen_send_lock():
        await _respect_prompt_interval(
            last_sent_at=float(_LAST_QWEN_PROMPT_SENT_AT or 0.0),
            min_interval_seconds=_qwen_min_prompt_interval_seconds(),
            label="Qwen",
            ctx=ctx,
        )

        send_btn = page.locator(
            "button[aria-label='发送'], "
            "button[aria-label='Send'], "
            "button[class*='operateBtn'], "
            "div[class*='operateBtn']"
        ).first
        clicked = False
        try:
            if await send_btn.count() and await send_btn.is_visible():
                try:
                    enabled = await send_btn.is_enabled()
                except Exception:
                    enabled = True
                if enabled:
                    await send_btn.click()
                    clicked = True
        except Exception:
            clicked = False

        if not clicked:
            await prompt_box.press("Enter")
        _LAST_QWEN_PROMPT_SENT_AT = time.time()


async def _qwen_last_response_state(page) -> dict[str, Any]:
    try:
        data = await page.evaluate(
            """() => {
                const out = {count: 0, text: '', complete: false, report_card: false, turns: []};
                const items = Array.from(document.querySelectorAll('div.answerItem-SsrVa_'));
                const turns = [];
                for (const item of items) {
                    const hasReportCard = !!item.querySelector('.report-card-wrap-B0qhPT, [class*=report-card]');
                    const markdownNodes = Array.from(item.querySelectorAll('div.qk-markdown'));
                    for (const md of markdownNodes) {
                        const text = (md.innerText || '').trim();
                        if (!text) continue;
                        const cls = (md.className || '').toString();
                        turns.push({
                            text,
                            complete: cls.includes('qk-markdown-complete'),
                            report_card: hasReportCard,
                        });
                    }
                }
                out.count = turns.length;
                if (turns.length > 0) {
                    out.text = turns[turns.length - 1].text;
                    out.complete = !!turns[turns.length - 1].complete;
                    out.report_card = !!turns[turns.length - 1].report_card;
                }
                out.turns = turns;
                return out;
            }"""
        )
        if isinstance(data, dict):
            turns_raw = data.get("turns")
            turns: list[dict[str, Any]] = []
            if isinstance(turns_raw, list):
                for item in turns_raw:
                    if not isinstance(item, dict):
                        continue
                    text = str(item.get("text") or "").strip()
                    if not text:
                        continue
                    turns.append(
                        {
                            "text": text,
                            "complete": bool(item.get("complete")),
                            "report_card": bool(item.get("report_card")),
                        }
                    )
            return {
                "count": int(data.get("count") or len(turns)),
                "text": str(data.get("text") or ""),
                "complete": bool(data.get("complete")),
                "report_card": bool(data.get("report_card")),
                "turns": turns,
            }
    except Exception:
        pass
    return {"count": 0, "text": "", "complete": False, "report_card": False, "turns": []}


async def _qwen_scroll_to_latest(page) -> None:
    try:
        await page.evaluate(
            """() => {
                const sels = [
                    '.message-list-scroll-container',
                    '.scrollWrapper-LOelOS',
                    '.scrollOutWrapper-DZw_rl',
                    '[class*=message-list-scroll-container]',
                    '[class*=scrollWrapper]',
                ];
                for (const sel of sels) {
                    const nodes = Array.from(document.querySelectorAll(sel));
                    for (const el of nodes) {
                        if (!el) continue;
                        const h = Number(el.scrollHeight || 0);
                        const c = Number(el.clientHeight || 0);
                        if (h > c + 2) {
                            el.scrollTop = h;
                        }
                    }
                }
                window.scrollTo(0, document.body ? document.body.scrollHeight : 0);
            }"""
        )
    except Exception:
        pass


async def _qwen_wait_for_model_response(
    page,
    *,
    started_answer_count: int,
    started_last_text: str = "",
    timeout_seconds: int,
    min_chars: int = 0,
    require_new: bool = True,
) -> tuple[str, bool]:
    deadline = time.time() + max(1, int(timeout_seconds))
    min_chars = max(0, int(min_chars))
    settle_seconds = 1.0
    complete_grace_seconds = 20.0 if require_new else 20.0
    stable_for_ms = 0
    last_text = ""
    last_snapshot_sig: tuple[int, str, bool] | None = None
    last_change_at = time.time()
    complete_seen_at: float | None = None
    complete_candidates_seen = 0

    def _pick_preferred_turn(turns: list[dict[str, Any]]) -> tuple[str, bool]:
        if not turns:
            return "", False
        preferred = turns[-1]
        text = str(preferred.get("text") or "").strip()
        is_report_card_ack = bool(preferred.get("report_card")) or bool(_QWEN_REPORT_CARD_ACK_RE.search(text))
        if is_report_card_ack:
            for cand in reversed(turns[:-1]):
                cand_text = str(cand.get("text") or "").strip()
                if not cand_text:
                    continue
                if bool(cand.get("report_card")) or _QWEN_REPORT_CARD_ACK_RE.search(cand_text):
                    continue
                preferred = cand
                break
        return str(preferred.get("text") or ""), bool(preferred.get("complete"))

    while time.time() < deadline:
        await _qwen_scroll_to_latest(page)
        state = await _qwen_last_response_state(page)
        count = int(state.get("count") or 0)
        state_last_text = str(state.get("text") or "")
        turns = state.get("turns")
        if not isinstance(turns, list):
            turns = []
        candidate_turns = turns[int(started_answer_count) :] if require_new else turns
        text, complete = _pick_preferred_turn(candidate_turns)
        if not text:
            text = str(state.get("text") or "")
            complete = bool(state.get("complete"))

        if require_new and (count <= int(started_answer_count)) and (not state_last_text or state_last_text == started_last_text):
            await page.wait_for_timeout(500)
            continue

        snapshot_sig = (int(count), text, bool(complete))
        now = time.time()
        if snapshot_sig != last_snapshot_sig:
            last_snapshot_sig = snapshot_sig
            last_change_at = now
            if text and complete:
                complete_seen_at = now
                complete_candidates_seen += 1
            elif not complete:
                complete_seen_at = None

        if text and text == last_text:
            stable_for_ms += 500
        else:
            stable_for_ms = 0
            last_text = text

        if min_chars and len(text) < min_chars:
            await page.wait_for_timeout(500)
            continue

        if text and complete:
            since_change = now - last_change_at
            since_complete = (now - complete_seen_at) if complete_seen_at is not None else 0.0
            grace = settle_seconds if complete_candidates_seen >= 2 else complete_grace_seconds
            if require_new and len(text) >= 80 and _QWEN_SELF_REFLECTION_RE.search(text):
                grace = max(grace, 60.0)
            if since_change >= settle_seconds and since_complete >= grace:
                return text, True
        if text and (not complete) and stable_for_ms >= 2_000:
            return text, True

        await page.wait_for_timeout(500)

    return last_text, False
