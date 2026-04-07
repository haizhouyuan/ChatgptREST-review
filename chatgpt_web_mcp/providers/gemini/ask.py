from __future__ import annotations

from chatgpt_web_mcp.idempotency import _idempotency_lookup
from chatgpt_web_mcp.providers.gemini.core import *  # noqa: F403


_GEMINI_IDEMPOTENT_TOOL_NAMES = {
    "gemini_web_ask",
    "gemini_web_ask_pro",
    "gemini_web_ask_pro_thinking",
    "gemini_web_ask_pro_deep_think",
    "gemini_web_deep_research",
}


async def gemini_web_idempotency_get(
    idempotency_key: str,
    tool_name: str = "gemini_web_ask",
    include_result: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Fetch the cached Gemini ask/deep-research idempotency record without sending a prompt."""
    started_at = time.time()
    run_id = _run_id(tool="gemini_web_idempotency_get")
    namespace = _idempotency_namespace(ctx)
    key = _normalize_idempotency_key(idempotency_key)
    tool = str(tool_name or "").strip()
    if tool not in _GEMINI_IDEMPOTENT_TOOL_NAMES:
        return {
            "ok": False,
            "status": "error",
            "found": False,
            "idempotency_namespace": namespace,
            "idempotency_key": key,
            "tool_name": tool,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": "ValueError",
            "error": f"unsupported Gemini idempotency tool: {tool or '<empty>'}",
        }

    record = await _idempotency_lookup(namespace=namespace, tool=tool, idempotency_key=key)
    if record is None:
        return {
            "ok": False,
            "status": "not_found",
            "found": False,
            "idempotency_namespace": namespace,
            "idempotency_key": key,
            "tool_name": tool,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
        }

    filtered = dict(record)
    if not include_result:
        filtered.pop("result", None)

    return {
        "ok": True,
        "status": "completed",
        "found": True,
        "idempotency_namespace": namespace,
        "idempotency_key": key,
        "tool_name": tool,
        "record": filtered,
        "elapsed_seconds": round(time.time() - started_at, 3),
        "run_id": run_id,
    }


def _gemini_idempotency_replay_result(
    *,
    existing: dict[str, Any] | None,
    run_id: str,
    conversation_url: str | None,
) -> dict[str, Any]:
    record = dict(existing or {})
    if isinstance(record.get("result"), dict):
        cached = dict(record["result"])
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

    status = str(record.get("status") or "in_progress").strip() or "in_progress"
    sent = bool(record.get("sent"))
    resolved_url = str(record.get("conversation_url") or conversation_url or "").strip()
    if (
        sent
        and status.lower() == "in_progress"
        and not _gemini_conversation_id_from_url(resolved_url)
    ):
        pending_url = resolved_url if _gemini_is_base_app_url(resolved_url) else "https://gemini.google.com/app"
        retry_after_seconds = 15
        return {
            "ok": True,
            "answer": "",
            "status": "in_progress",
            "conversation_url": pending_url,
            "elapsed_seconds": 0.0,
            "run_id": run_id,
            "replayed": True,
            "error_type": "GeminiSendPendingRecovery",
            "error": (
                "Gemini prompt was previously marked as sent, but no stable conversation URL was cached yet; "
                "recover via wait/sidebar instead of resending."
            ),
            "wait_handoff_ready": True,
            "wait_handoff_reason": "idempotency_sent_without_thread",
            "retry_after_seconds": retry_after_seconds,
            "not_before": float(time.time() + float(retry_after_seconds)),
        }

    ok = status.lower() not in {"error", "blocked", "cooldown"}
    return {
        "ok": ok,
        "answer": "",
        "status": status,
        "conversation_url": resolved_url,
        "elapsed_seconds": 0.0,
        "run_id": run_id,
        "replayed": True,
        "error_type": None,
        "error": (str(record.get("error") or "").strip() or None),
        }


def _gemini_resolve_repo_context(
    *,
    github_repo: str | None,
    repo_context_hint: str | None,
) -> tuple[str, str, str]:
    resolved_github_repo = str(github_repo or "").strip()
    resolved_repo_context_hint = str(repo_context_hint or "").strip()
    effective_repo_context = resolved_repo_context_hint or resolved_github_repo
    return resolved_github_repo, resolved_repo_context_hint, effective_repo_context


def _gemini_should_import_code(*, github_repo: str, enable_import_code: bool) -> bool:
    return bool(str(github_repo or "").strip()) and bool(enable_import_code)


def _gemini_initial_prompt_surface_needs_reopen(*, exc: Exception, page) -> bool:
    try:
        is_closed = getattr(page, "is_closed", None)
        if callable(is_closed) and bool(is_closed()):
            return True
    except Exception:
        pass
    error_text = _coerce_error_text(exc).strip().lower()
    if not error_text:
        return False
    return any(
        marker in error_text
        for marker in (
            "target closed",
            "target crashed",
            "target page, context or browser has been closed",
            "target page, context or browser is closed",
            "page.wait_for_timeout: target page, context or browser has been closed",
            "page has been closed",
            "context has been closed",
            "browser has been closed",
        )
    )


def _gemini_should_retry_initial_prompt_surface(*, exc: Exception) -> bool:
    if isinstance(exc, (asyncio.TimeoutError, PlaywrightTimeoutError)):
        return True
    error_text = _coerce_error_text(exc)
    if _looks_like_gemini_infra_error(error_text):
        return True
    hay = error_text.strip().lower()
    if not hay:
        return False
    return any(
        marker in hay
        for marker in (
            "cannot find gemini prompt box",
            "execution context was destroyed",
            "frame was detached",
        )
    )


async def _gemini_reload_initial_prompt_surface(
    page,
    *,
    conversation_url: str | None,
    ctx: Context | None,
    exc: Exception | None = None,
    reopen_surface=None,
):
    if exc is not None and reopen_surface is not None and _gemini_initial_prompt_surface_needs_reopen(exc=exc, page=page):
        await _ctx_info(ctx, "Gemini: initial prompt surface lost page/context; reopen once before retrying.")
        return await reopen_surface()
    try:
        await page.reload(wait_until="domcontentloaded", timeout=_navigation_timeout_ms())
    except Exception:
        pass
    await _human_pause(page)
    try:
        await _gemini_dismiss_overlays(page)
    except Exception:
        pass
    if conversation_url is None:
        try:
            await _gemini_click_new_chat(page)
        except Exception:
            pass
    return page


async def _gemini_prepare_pro_surface(
    page,
    *,
    conversation_url: str | None,
    total_timeout_seconds: float,
    ctx: Context | None,
    reopen_surface=None,
) -> tuple[Any, str]:
    attempt_timeout_seconds = max(6.0, min(20.0, float(total_timeout_seconds) * 0.2))
    prompt_timeout_ms = max(4_000, min(12_000, int(attempt_timeout_seconds * 1000)))
    reload_budget = 1
    reopen_budget = 2
    while True:
        try:
            async with asyncio.timeout(attempt_timeout_seconds):
                await _gemini_find_prompt_box(page, timeout_ms=prompt_timeout_ms)
                await _human_pause(page)
                await _gemini_clear_selected_tools(page, ctx=ctx)
                await _gemini_ensure_pro_mode(page, ctx=ctx)
                return page, await _gemini_current_mode_text(page)
        except Exception as exc:
            if not _gemini_should_retry_initial_prompt_surface(exc=exc):
                raise
            if _gemini_initial_prompt_surface_needs_reopen(exc=exc, page=page):
                if reopen_budget <= 0:
                    raise
                reopen_budget -= 1
                await _ctx_info(ctx, "Gemini: initial prompt surface unavailable; reopen before retrying.")
            else:
                if reload_budget <= 0:
                    raise
                reload_budget -= 1
                await _ctx_info(ctx, "Gemini: initial prompt surface unavailable; reload once before retrying.")
            page = await _gemini_reload_initial_prompt_surface(
                page,
                conversation_url=conversation_url,
                ctx=ctx,
                exc=exc,
                reopen_surface=reopen_surface,
            )


async def _gemini_close_surface_handles(
    *,
    browser,
    context,
    page,
    close_context: bool,
) -> None:
    try:
        if page is not None:
            try:
                await asyncio.wait_for(page.close(), timeout=5.0)
            except Exception:
                pass
        if close_context and context is not None:
            try:
                await asyncio.wait_for(context.close(), timeout=5.0)
            except Exception:
                pass
    finally:
        if browser is not None:
            try:
                await asyncio.wait_for(browser.close(), timeout=5.0)
            except Exception:
                pass


def _gemini_maybe_mark_send_timeout_pending(
    result: dict[str, Any],
    *,
    sent: bool,
) -> dict[str, Any]:
    if not sent:
        return result
    status = str(result.get("status") or "").strip().lower()
    if status != "in_progress":
        return result
    error_type = str(result.get("error_type") or "").strip()
    error_text = str(result.get("error") or "").strip()
    combined = f"{error_type} {error_text}".lower()
    if not any(marker in combined for marker in ("timeout", "timed out", "deadline exceeded", "empty error", "send unconfirmed")):
        return result
    conversation_url = str(result.get("conversation_url") or "").strip()
    response_started = bool(result.get("response_started"))
    has_thread_url = bool(_gemini_conversation_id_from_url(conversation_url))
    has_base_app_url = _gemini_is_base_app_url(conversation_url)
    debug_step = str(result.get("debug_step") or "").strip()
    timed_out_after_send = debug_step in {"wait_conversation_url", "wait_model_response"}
    if not (response_started or has_thread_url or has_base_app_url or timed_out_after_send):
        return result

    pending_url = conversation_url
    if not pending_url and timed_out_after_send:
        pending_url = "https://gemini.google.com/app"

    out = dict(result)
    out["conversation_url"] = pending_url
    retry_after_seconds = int(out.get("retry_after_seconds") or 15)
    out["wait_handoff_ready"] = True
    if response_started:
        if has_thread_url:
            out["error_type"] = "GeminiResponsePending"
            out["error"] = "Gemini response started but the final answer is still pending; recover via wait instead of retrying send."
        else:
            out["error_type"] = "GeminiThreadPending"
            out["error"] = "Gemini response started but the stable conversation thread is still pending; recover via wait/sidebar instead of retrying send."
        out["wait_handoff_reason"] = "response_started"
    else:
        out["error_type"] = (
            "GeminiDeepThinkSendPendingRecovery"
            if "deepthink" in combined
            else "GeminiSendPendingRecovery"
        )
        out["error"] = "Gemini prompt was sent but the stable conversation thread is still pending; recover via wait/sidebar instead of retrying send."
        out["wait_handoff_reason"] = "timeout_after_send"
    out.setdefault("retry_after_seconds", retry_after_seconds)
    out.setdefault("not_before", float(time.time() + float(retry_after_seconds)))
    return out


def _gemini_preferred_conversation_url(*candidates: str | None) -> str:
    best = ""
    best_rank = -1
    for candidate in candidates:
        url = str(candidate or "").strip()
        if not url:
            continue
        if _gemini_conversation_id_from_url(url):
            return url
        rank = 2 if _gemini_is_base_app_url(url) else 1
        if rank > best_rank:
            best = url
            best_rank = rank
    return best


def _gemini_capture_surface_url(page: Any | None, current: str | None = None) -> str:
    page_url = ""
    try:
        if page is not None:
            page_url = str(getattr(page, "url", "") or "").strip()
    except Exception:
        page_url = ""
    return _gemini_preferred_conversation_url(page_url, current)


async def gemini_web_ask(
    question: str,
    idempotency_key: str,
    conversation_url: str | None = None,
    timeout_seconds: int = 600,
    drive_files: str | list[str] | None = None,
    github_repo: str | None = None,
    repo_context_hint: str | None = None,
    enable_import_code: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    tool_name = "gemini_web_ask"
    resolved_drive_files = _gemini_resolve_drive_files(drive_files)
    resolved_github_repo, resolved_repo_context_hint, effective_repo_context = _gemini_resolve_repo_context(
        github_repo=github_repo,
        repo_context_hint=repo_context_hint,
    )
    run_id = _run_id(tool=tool_name, idempotency_key=idempotency_key)
    idem = _IdempotencyContext(
        namespace=_idempotency_namespace(ctx),
        tool=tool_name,
        key=_normalize_idempotency_key(idempotency_key),
        request_hash=_hash_request(
            {
                "tool": tool_name,
                "question": question,
                "drive_files": resolved_drive_files,
                "github_repo": resolved_github_repo,
                "repo_context_hint": resolved_repo_context_hint,
                "enable_import_code": bool(enable_import_code),
            }
        ),
    )
    should_execute, existing = await _idempotency_begin(idem)
    if not should_execute:
        return _gemini_idempotency_replay_result(existing=existing, run_id=run_id, conversation_url=conversation_url)

    async with _ask_lock():
        cfg = _load_gemini_web_config()
        if cfg.cdp_url is None and not cfg.storage_state_path.exists():
            msg = (
                f"Missing storage_state.json at {cfg.storage_state_path}. "
                "Set GEMINI_CDP_URL/CHATGPT_CDP_URL to use a running Chrome, or provide GEMINI_STORAGE_STATE."
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
            async with _page_slot(kind="gemini", ctx=ctx), async_playwright() as p:
                browser = None
                context = None
                page = None
                close_context = False
                sent = False
                start_response_count = 0
                progress_step = "open_page"
                effective_conversation_url = str(conversation_url or "").strip()
                mode_text_effective = ""
                import_code_fallback = None
                drive_attach_fallback = None
                try:
                    progress_step = "open_page"
                    browser, context, page, close_context = await _open_gemini_page(
                        p, cfg, conversation_url=conversation_url, ctx=ctx
                    )

                    if conversation_url is None:
                        progress_step = "new_chat"
                        await _gemini_click_new_chat(page)

                    progress_step = "find_prompt_box_initial"
                    await _gemini_find_prompt_box(page)
                    await _human_pause(page)
                    await _gemini_clear_selected_tools(page, ctx=ctx)

                    if _gemini_should_import_code(
                        github_repo=resolved_github_repo,
                        enable_import_code=enable_import_code,
                    ):
                        progress_step = "import_code"
                        import_code_fallback = await _gemini_maybe_import_code_repo(
                            page,
                            repo_url=resolved_github_repo,
                            drive_files=resolved_drive_files,
                            ctx=ctx,
                        )
                        await _human_pause(page)

                    if resolved_drive_files:
                        progress_step = "attach_drive_files"
                        drive_attach_fallback = await _gemini_maybe_attach_drive_files(
                            page,
                            drive_files=resolved_drive_files,
                            repo_url=effective_repo_context,
                            ctx=ctx,
                        )

                    start_response_count = await page.locator("model-response").count()
                    progress_step = "find_prompt_box_send"
                    prompt_box = await _gemini_find_prompt_box(page)
                    prompt_box = await _gemini_focus_prompt_box(page, prompt_box)
                    progress_step = "type_question"
                    await _gemini_type_question_with_app_mentions(page, question=question, ctx=ctx)
                    await _human_pause(page)

                    progress_step = "click_send"
                    await _gemini_click_send(page, prompt_box, ctx=ctx)
                    sent = True
                    try:
                        progress_step = "wait_conversation_url"
                        effective_conversation_url = await _gemini_wait_for_conversation_url(page, timeout_seconds=8.0)
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

                    await _ctx_info(ctx, "Waiting for Gemini answer…")

                    min_chars = 0 if len((question or "").strip()) < 80 else 200
                    progress_step = "wait_model_response"
                    answer = await _gemini_wait_for_model_response(
                        page,
                        started_at=started_at,
                        start_response_count=start_response_count,
                        timeout_seconds=timeout_seconds,
                        min_chars=min_chars,
                        require_new=True,
                    )

                    if _looks_like_transient_assistant_error(answer):
                        raise RuntimeError(f"Gemini returned a transient error message: {answer}")

                    best_effort_conversation_url = await _best_effort_gemini_conversation_url(page)
                    result = {
                        "ok": True,
                        "answer": answer,
                        "status": _classify_non_deep_research_answer(answer),
                        "conversation_url": _gemini_preferred_conversation_url(
                            effective_conversation_url,
                            best_effort_conversation_url,
                            page.url,
                            conversation_url,
                        ),
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                    }
                    if import_code_fallback is not None:
                        result["import_code_fallback"] = dict(import_code_fallback)
                    if drive_attach_fallback is not None:
                        result["drive_attach_fallback"] = dict(drive_attach_fallback)
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
                        "tool": "gemini_web_ask",
                        "status": result.get("status"),
                        "conversation_url": result.get("conversation_url"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": result.get("run_id") or run_id,
                        "idempotency_key": idem.key,
                        "idempotency_namespace": idem.namespace,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "conversation_url": conversation_url,
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
                    error_type = _gemini_classify_error_type(error_text=err_text, fallback=exc_type)
                    status = "in_progress" if sent else ("blocked" if _looks_like_gemini_blocked_error(err_text) else "error")
                    if not sent and _looks_like_gemini_infra_error(err_text):
                        status = "cooldown"
                        error_type = "InfraError"
                    artifacts: dict[str, str] = {}
                    if page is not None:
                        artifacts = await _capture_debug_artifacts(page, label="gemini_web_ask_error")
                        if ctx and artifacts:
                            await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")

                    best_effort_conversation_url = (
                        (await _best_effort_gemini_conversation_url(page)).strip() if page is not None else ""
                    )
                    result = {
                        "ok": False,
                        "status": status,
                        "answer": "",
                        "conversation_url": _gemini_preferred_conversation_url(
                            effective_conversation_url,
                            best_effort_conversation_url,
                            (page.url if page is not None else ""),
                            conversation_url,
                        ),
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                        "error_type": error_type,
                        "exc_type": exc_type,
                        "error": err_text,
                    "debug_step": progress_step,
                        "debug_artifacts": artifacts,
                    }
                    if sent and page is not None:
                        try:
                            result.update(await _gemini_collect_send_observation(page, start_response_count=start_response_count))
                        except Exception:
                            pass
                    result = _gemini_maybe_mark_send_timeout_pending(result, sent=sent)
                    status = str(result.get("status") or status).strip().lower()
                    error_type = str(result.get("error_type") or error_type).strip()
                    err_text = str(result.get("error") or err_text).strip()
                    if status == "cooldown" and error_type == "InfraError":
                        retry_after_seconds = _gemini_infra_retry_after_seconds()
                        result["retry_after_seconds"] = int(retry_after_seconds)
                        result["not_before"] = float(time.time() + float(retry_after_seconds))
                    try:
                        await _idempotency_update(
                            idem,
                            status=status,
                            sent=bool(sent),
                            conversation_url=str(result.get("conversation_url") or ""),
                            result=result,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    except Exception:
                        pass
                    event: dict[str, Any] = {
                        "tool": "gemini_web_ask",
                        "status": status,
                        "conversation_url": result.get("conversation_url"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": run_id,
                        "idempotency_key": idem.key,
                        "idempotency_namespace": idem.namespace,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "conversation_url": conversation_url,
                        },
                        "error_type": error_type,
                        "exc_type": exc_type,
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





async def gemini_web_ask_pro(
    question: str,
    idempotency_key: str,
    conversation_url: str | None = None,
    timeout_seconds: int = 600,
    drive_files: str | list[str] | None = None,
    github_repo: str | None = None,
    repo_context_hint: str | None = None,
    enable_import_code: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    tool_name = "gemini_web_ask_pro"
    resolved_drive_files = _gemini_resolve_drive_files(drive_files)
    resolved_github_repo, resolved_repo_context_hint, effective_repo_context = _gemini_resolve_repo_context(
        github_repo=github_repo,
        repo_context_hint=repo_context_hint,
    )
    run_id = _run_id(tool=tool_name, idempotency_key=idempotency_key)
    idem = _IdempotencyContext(
        namespace=_idempotency_namespace(ctx),
        tool=tool_name,
        key=_normalize_idempotency_key(idempotency_key),
        request_hash=_hash_request(
            {
                "tool": tool_name,
                "question": question,
                "drive_files": resolved_drive_files,
                "github_repo": resolved_github_repo,
                "repo_context_hint": resolved_repo_context_hint,
                "enable_import_code": bool(enable_import_code),
            }
        ),
    )
    should_execute, existing = await _idempotency_begin(idem)
    if not should_execute:
        return _gemini_idempotency_replay_result(existing=existing, run_id=run_id, conversation_url=conversation_url)

    async with _ask_lock():
        cfg = _load_gemini_web_config()
        if cfg.cdp_url is None and not cfg.storage_state_path.exists():
            msg = (
                f"Missing storage_state.json at {cfg.storage_state_path}. "
                "Set GEMINI_CDP_URL/CHATGPT_CDP_URL to use a running Chrome, or provide GEMINI_STORAGE_STATE."
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
        total_timeout_seconds = max(1.0, float(timeout_seconds))
        env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
        progress_step = "enter_timeout_scope"
        with env_ctx:
            try:
                progress_step = "page_slot"
                async with asyncio.timeout(total_timeout_seconds):
                    async with _page_slot(kind="gemini", ctx=ctx), async_playwright() as p:
                        browser = None
                        context = None
                        page = None
                        close_context = False
                        sent = False
                        start_response_count = 0
                        effective_conversation_url = str(conversation_url or "").strip()
                        mode_text_effective = ""
                        import_code_fallback = None
                        drive_attach_fallback = None
                        try:
                            progress_step = "open_page"
                            browser, context, page, close_context = await _open_gemini_page(
                                p, cfg, conversation_url=conversation_url, ctx=ctx
                            )

                            if conversation_url is None:
                                progress_step = "new_chat"
                                await _gemini_click_new_chat(page)

                            async def _reopen_initial_prompt_surface():
                                nonlocal browser, context, page, close_context
                                await _gemini_close_surface_handles(
                                    browser=browser,
                                    context=context,
                                    page=page,
                                    close_context=close_context,
                                )
                                if cfg.cdp_url:
                                    try:
                                        await _restart_local_cdp_chrome(kind="gemini", cdp_url=cfg.cdp_url, ctx=ctx)
                                    except Exception:
                                        pass
                                last_exc: Exception | None = None
                                for reopen_attempt in range(3):
                                    try:
                                        browser, context, page, close_context = await _open_gemini_page(
                                            p,
                                            cfg,
                                            conversation_url=conversation_url,
                                            ctx=ctx,
                                        )
                                        if conversation_url is None:
                                            await _gemini_click_new_chat(page)
                                        return page
                                    except Exception as exc:
                                        last_exc = exc
                                        if (
                                            reopen_attempt >= 2
                                            or not _gemini_should_retry_initial_prompt_surface(exc=exc)
                                        ):
                                            raise
                                        await _ctx_info(
                                            ctx,
                                            "Gemini: reopen surface failed to reconnect; wait briefly and retry.",
                                        )
                                        await asyncio.sleep(min(1.0 * (reopen_attempt + 1), 2.0))
                                assert last_exc is not None
                                raise last_exc

                            progress_step = "find_prompt_box_initial"
                            page, mode_text_effective = await _gemini_prepare_pro_surface(
                                page,
                                conversation_url=conversation_url,
                                total_timeout_seconds=total_timeout_seconds,
                                ctx=ctx,
                                reopen_surface=_reopen_initial_prompt_surface,
                            )

                            progress_step = "import_code"
                            if _gemini_should_import_code(
                                github_repo=resolved_github_repo,
                                enable_import_code=enable_import_code,
                            ):
                                import_code_fallback = await _gemini_maybe_import_code_repo(
                                    page,
                                    repo_url=resolved_github_repo,
                                    drive_files=resolved_drive_files,
                                    ctx=ctx,
                                )
                                await _human_pause(page)
                                try:
                                    await _gemini_ensure_pro_mode(page, ctx=ctx)
                                    mode_text_effective = await _gemini_current_mode_text(page)
                                except _GeminiModeQuotaError:
                                    raise
                                except Exception:
                                    pass

                            if resolved_drive_files:
                                progress_step = "attach_drive_files"
                                drive_attach_fallback = await _gemini_maybe_attach_drive_files(
                                    page,
                                    drive_files=resolved_drive_files,
                                    repo_url=effective_repo_context,
                                    ctx=ctx,
                                )
                                try:
                                    await _gemini_ensure_pro_mode(page, ctx=ctx)
                                    mode_text_effective = await _gemini_current_mode_text(page)
                                except _GeminiModeQuotaError:
                                    raise
                                except Exception:
                                    pass

                            progress_step = "prepare_prompt"
                            prepare_prompt_recoverable = not resolved_drive_files and not _gemini_should_import_code(
                                github_repo=resolved_github_repo,
                                enable_import_code=enable_import_code,
                            )
                            for prepare_prompt_attempt in range(2 if prepare_prompt_recoverable else 1):
                                try:
                                    start_response_count = await page.locator("model-response").count()
                                    prompt_box = await _gemini_find_prompt_box(page)
                                    prompt_box = await _gemini_focus_prompt_box(page, prompt_box)
                                    await _gemini_type_question_with_app_mentions(page, question=question, ctx=ctx)
                                    await _human_pause(page)
                                    break
                                except Exception as exc:
                                    if (
                                        prepare_prompt_attempt >= 1
                                        or not prepare_prompt_recoverable
                                        or not _gemini_should_retry_initial_prompt_surface(exc=exc)
                                    ):
                                        raise
                                    await _ctx_info(ctx, "Gemini: prepare prompt surface unavailable; reopen once before retrying.")
                                    page = await _reopen_initial_prompt_surface()
                                    page, mode_text_effective = await _gemini_prepare_pro_surface(
                                        page,
                                        conversation_url=conversation_url,
                                        total_timeout_seconds=total_timeout_seconds,
                                        ctx=ctx,
                                        reopen_surface=_reopen_initial_prompt_surface,
                                    )

                            progress_step = "pre_send_quota_check"
                            await _gemini_raise_if_quota_limited(page, wanted="Pro", ctx=ctx)
                            mode_text_effective = await _gemini_current_mode_text(page)
                            effective_conversation_url = _gemini_capture_surface_url(page, effective_conversation_url)

                            progress_step = "click_send"
                            await _gemini_click_send(page, prompt_box, ctx=ctx)
                            sent = True
                            try:
                                progress_step = "wait_conversation_url"
                                effective_conversation_url = await _gemini_wait_for_conversation_url(page, timeout_seconds=8.0)
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

                            await _ctx_info(ctx, "Waiting for Gemini answer…")

                            progress_step = "wait_model_response"
                            answer = await _gemini_wait_for_model_response(
                                page,
                                started_at=started_at,
                                start_response_count=start_response_count,
                                timeout_seconds=timeout_seconds,
                                min_chars=0,
                                require_new=True,
                            )

                            if _looks_like_transient_assistant_error(answer):
                                raise RuntimeError(f"Gemini returned a transient error message: {answer}")

                            mode_text_effective = await _gemini_current_mode_text(page)
                            result = {
                                "ok": True,
                                "answer": answer,
                                "status": _classify_non_deep_research_answer(answer),
                                "conversation_url": (
                                    await _best_effort_gemini_conversation_url(page)
                                    or effective_conversation_url
                                    or page.url
                                    or ""
                                ),
                                "elapsed_seconds": round(time.time() - started_at, 3),
                                "run_id": run_id,
                                "mode_text": mode_text_effective,
                                "error_type": None,
                                "error": None,
                            }
                            if import_code_fallback is not None:
                                result["import_code_fallback"] = dict(import_code_fallback)
                            if drive_attach_fallback is not None:
                                result["drive_attach_fallback"] = dict(drive_attach_fallback)
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
                                "tool": "gemini_web_ask_pro",
                                "status": result.get("status"),
                                "conversation_url": result.get("conversation_url"),
                                "elapsed_seconds": result.get("elapsed_seconds"),
                                "run_id": result.get("run_id") or run_id,
                                "idempotency_key": idem.key,
                                "idempotency_namespace": idem.namespace,
                                "params": {
                                    "timeout_seconds": timeout_seconds,
                                    "conversation_url": conversation_url,
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
                            quota_exc = exc if isinstance(exc, _GeminiModeQuotaError) else None
                            err_text = _coerce_error_text(exc)
                            exc_type = type(exc).__name__
                            quota_info: dict[str, Any] | None = None
                            if quota_exc is None and page is not None:
                                try:
                                    quota_hint = (await page.locator("body").inner_text(timeout=2_000)).strip()
                                except Exception:
                                    quota_hint = ""
                                quota_info = _gemini_quota_notice_from_text(quota_hint)
                            error_type = (
                                "GeminiModeQuotaExceeded"
                                if quota_exc is not None or quota_info is not None
                                else _gemini_classify_error_type(error_text=err_text, fallback=exc_type)
                            )
                            status = "in_progress" if sent else ("blocked" if _looks_like_gemini_blocked_error(err_text) else "error")
                            if (quota_exc is not None or quota_info is not None) and not sent:
                                status = "cooldown"
                            if quota_exc is None and not sent and _looks_like_gemini_infra_error(err_text):
                                status = "cooldown"
                                error_type = "InfraError"
                            artifacts: dict[str, str] = {}
                            if page is not None:
                                artifacts = await _capture_debug_artifacts(page, label="gemini_web_ask_pro_error")
                                if ctx and artifacts:
                                    await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")

                            try:
                                if page is not None:
                                    mode_text_effective = await _gemini_current_mode_text(page)
                            except Exception:
                                mode_text_effective = mode_text_effective

                            result = {
                                "ok": False,
                                "status": status,
                                "answer": "",
                                "conversation_url": (
                                    (
                                        (await _best_effort_gemini_conversation_url(page)) if page is not None else ""
                                    ).strip()
                                    or (page.url if page is not None else "")
                                    or effective_conversation_url
                                    or (str(conversation_url or "").strip())
                                ),
                                "elapsed_seconds": round(time.time() - started_at, 3),
                                "run_id": run_id,
                                "mode_text": mode_text_effective,
                                "error_type": error_type,
                                "exc_type": exc_type,
                                "error": (str(quota_exc) if quota_exc is not None else err_text),
                                "debug_step": progress_step,
                                "debug_artifacts": artifacts,
                                "debug_step": progress_step,
                            }
                            if sent and page is not None:
                                try:
                                    result.update(await _gemini_collect_send_observation(page, start_response_count=start_response_count))
                                except Exception:
                                    pass
                            result = _gemini_maybe_mark_send_timeout_pending(result, sent=sent)
                            status = str(result.get("status") or status).strip().lower()
                            error_type = str(result.get("error_type") or error_type).strip()
                            err_text = str(result.get("error") or err_text).strip()
                            if quota_exc is not None and not sent:
                                if quota_exc.retry_after_seconds is not None:
                                    result["retry_after_seconds"] = int(quota_exc.retry_after_seconds)
                                if quota_exc.not_before is not None:
                                    result["not_before"] = float(quota_exc.not_before)
                                if quota_exc.reset_at is not None:
                                    result["reset_at"] = float(quota_exc.reset_at)
                                if quota_exc.notice:
                                    result["quota_notice"] = str(quota_exc.notice)

                            elif status == "cooldown" and error_type == "InfraError":
                                retry_after_seconds = _gemini_infra_retry_after_seconds()
                                result["retry_after_seconds"] = int(retry_after_seconds)
                                result["not_before"] = float(time.time() + float(retry_after_seconds))
                            try:
                                await _idempotency_update(
                                    idem,
                                    status=status,
                                    sent=bool(sent),
                                    conversation_url=str(result.get("conversation_url") or ""),
                                    result=result,
                                    error=f"{type(exc).__name__}: {exc}",
                                )
                            except Exception:
                                pass
                            event: dict[str, Any] = {
                                "tool": "gemini_web_ask_pro",
                                "status": status,
                                "conversation_url": result.get("conversation_url"),
                                "elapsed_seconds": result.get("elapsed_seconds"),
                                "run_id": run_id,
                                "idempotency_key": idem.key,
                                "idempotency_namespace": idem.namespace,
                                "params": {
                                    "timeout_seconds": timeout_seconds,
                                    "conversation_url": conversation_url,
                                },
                                "error_type": error_type,
                                "exc_type": exc_type,
                                "error": (str(quota_exc) if quota_exc is not None else err_text),
                            }
                            if _call_log_include_prompts():
                                event["question"] = question
                            if artifacts:
                                event["debug_artifacts"] = artifacts
                            _maybe_append_call_log(event)
                            return result
                        finally:
                            await _gemini_close_surface_handles(
                                browser=browser,
                                context=context,
                                page=page,
                                close_context=close_context,
                            )
            except Exception as exc:
                err_text = _coerce_error_text(exc)
                exc_type = type(exc).__name__
                error_type = _gemini_classify_error_type(error_text=err_text, fallback=exc_type)
                status = "blocked" if _looks_like_gemini_blocked_error(err_text) else "error"
                if _looks_like_gemini_infra_error(err_text):
                    status = "cooldown"
                    error_type = "InfraError"
                result = {
                    "ok": False,
                    "status": status,
                    "answer": "",
                    "conversation_url": str(conversation_url or "").strip(),
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "mode_text": "",
                    "error_type": error_type,
                    "exc_type": exc_type,
                    "error": err_text,
                    "debug_artifacts": {},
                    "debug_step": progress_step,
                }
                if status == "cooldown" and error_type == "InfraError":
                    retry_after_seconds = _gemini_infra_retry_after_seconds()
                    result["retry_after_seconds"] = int(retry_after_seconds)
                    result["not_before"] = float(time.time() + float(retry_after_seconds))
                try:
                    await _idempotency_update(
                        idem,
                        status=status,
                        sent=False,
                        conversation_url=str(result.get("conversation_url") or ""),
                        result=result,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                except Exception:
                    pass
                event: dict[str, Any] = {
                    "tool": "gemini_web_ask_pro",
                    "status": status,
                    "conversation_url": result.get("conversation_url"),
                    "elapsed_seconds": result.get("elapsed_seconds"),
                    "run_id": run_id,
                    "idempotency_key": idem.key,
                    "idempotency_namespace": idem.namespace,
                    "params": {
                        "timeout_seconds": timeout_seconds,
                        "conversation_url": conversation_url,
                    },
                    "error_type": error_type,
                    "exc_type": exc_type,
                    "error": err_text,
                }
                if _call_log_include_prompts():
                    event["question"] = question
                _maybe_append_call_log(event)
                return result



async def gemini_web_ask_pro_thinking(
    question: str,
    idempotency_key: str,
    conversation_url: str | None = None,
    timeout_seconds: int = 600,
    drive_files: str | list[str] | None = None,
    github_repo: str | None = None,
    repo_context_hint: str | None = None,
    enable_import_code: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    tool_name = "gemini_web_ask_pro_thinking"
    resolved_drive_files = _gemini_resolve_drive_files(drive_files)
    resolved_github_repo, resolved_repo_context_hint, effective_repo_context = _gemini_resolve_repo_context(
        github_repo=github_repo,
        repo_context_hint=repo_context_hint,
    )
    run_id = _run_id(tool=tool_name, idempotency_key=idempotency_key)
    idem = _IdempotencyContext(
        namespace=_idempotency_namespace(ctx),
        tool=tool_name,
        key=_normalize_idempotency_key(idempotency_key),
        request_hash=_hash_request(
            {
                "tool": tool_name,
                "question": question,
                "drive_files": resolved_drive_files,
                "github_repo": resolved_github_repo,
                "repo_context_hint": resolved_repo_context_hint,
                "enable_import_code": bool(enable_import_code),
            }
        ),
    )
    should_execute, existing = await _idempotency_begin(idem)
    if not should_execute:
        return _gemini_idempotency_replay_result(existing=existing, run_id=run_id, conversation_url=conversation_url)

    async with _ask_lock():
        cfg = _load_gemini_web_config()
        if cfg.cdp_url is None and not cfg.storage_state_path.exists():
            msg = (
                f"Missing storage_state.json at {cfg.storage_state_path}. "
                "Set GEMINI_CDP_URL/CHATGPT_CDP_URL to use a running Chrome, or provide GEMINI_STORAGE_STATE."
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
            async with _page_slot(kind="gemini", ctx=ctx), async_playwright() as p:
                browser = None
                context = None
                page = None
                close_context = False
                sent = False
                start_response_count = 0
                effective_conversation_url = str(conversation_url or "").strip()
                mode_text_effective = ""
                import_code_fallback = None
                drive_attach_fallback = None
                try:
                    browser, context, page, close_context = await _open_gemini_page(
                        p, cfg, conversation_url=conversation_url, ctx=ctx
                    )

                    if conversation_url is None:
                        await _gemini_click_new_chat(page)

                    await _gemini_find_prompt_box(page)
                    await _human_pause(page)
                    await _gemini_clear_selected_tools(page, ctx=ctx)
                    await _gemini_ensure_thinking_mode(page, ctx=ctx)
                    mode_text_effective = await _gemini_current_mode_text(page)

                    if _gemini_should_import_code(
                        github_repo=resolved_github_repo,
                        enable_import_code=enable_import_code,
                    ):
                        import_code_fallback = await _gemini_maybe_import_code_repo(
                            page,
                            repo_url=resolved_github_repo,
                            drive_files=resolved_drive_files,
                            ctx=ctx,
                        )
                        await _human_pause(page)
                        try:
                            await _gemini_ensure_thinking_mode(page, ctx=ctx)
                            mode_text_effective = await _gemini_current_mode_text(page)
                        except _GeminiModeQuotaError:
                            raise
                        except Exception:
                            pass

                    if resolved_drive_files:
                        drive_attach_fallback = await _gemini_maybe_attach_drive_files(
                            page,
                            drive_files=resolved_drive_files,
                            repo_url=effective_repo_context,
                            ctx=ctx,
                        )
                        try:
                            await _gemini_ensure_thinking_mode(page, ctx=ctx)
                            mode_text_effective = await _gemini_current_mode_text(page)
                        except _GeminiModeQuotaError:
                            raise
                        except Exception:
                            pass

                    start_response_count = await page.locator("model-response").count()
                    prompt_box = await _gemini_find_prompt_box(page)
                    prompt_box = await _gemini_focus_prompt_box(page, prompt_box)
                    await _gemini_type_question_with_app_mentions(page, question=question, ctx=ctx)
                    await _human_pause(page)

                    await _gemini_raise_if_quota_limited(page, wanted="Thinking", ctx=ctx)
                    mode_text_effective = await _gemini_current_mode_text(page)

                    await _gemini_click_send(page, prompt_box, ctx=ctx)
                    sent = True
                    try:
                        effective_conversation_url = await _gemini_wait_for_conversation_url(page, timeout_seconds=8.0)
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

                    await _ctx_info(ctx, "Waiting for Gemini answer…")

                    answer = await _gemini_wait_for_model_response(
                        page,
                        started_at=started_at,
                        start_response_count=start_response_count,
                        timeout_seconds=timeout_seconds,
                        require_new=True,
                    )

                    if _looks_like_transient_assistant_error(answer):
                        raise RuntimeError(f"Gemini returned a transient error message: {answer}")

                    mode_text_effective = await _gemini_current_mode_text(page)
                    # Best-effort thinking trace capture
                    thinking_trace = None
                    try:
                        thinking_trace = await _gemini_capture_thinking_trace(page, ctx=ctx)
                    except Exception:
                        pass
                    result = {
                        "ok": True,
                        "answer": answer,
                        "status": "completed",
                        "conversation_url": (
                            await _best_effort_gemini_conversation_url(page)
                            or effective_conversation_url
                            or page.url
                            or ""
                        ),
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                        "mode_text": mode_text_effective,
                        "error_type": None,
                        "error": None,
                    }
                    if import_code_fallback is not None:
                        result["import_code_fallback"] = dict(import_code_fallback)
                    if drive_attach_fallback is not None:
                        result["drive_attach_fallback"] = dict(drive_attach_fallback)
                    if thinking_trace:
                        result["thinking_trace"] = thinking_trace
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
                        "tool": "gemini_web_ask_pro_thinking",
                        "status": result.get("status"),
                        "conversation_url": result.get("conversation_url"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": result.get("run_id") or run_id,
                        "idempotency_key": idem.key,
                        "idempotency_namespace": idem.namespace,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "conversation_url": conversation_url,
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
                    quota_exc = exc if isinstance(exc, _GeminiModeQuotaError) else None
                    err_text = _coerce_error_text(exc)
                    exc_type = type(exc).__name__
                    error_type = (
                        "GeminiModeQuotaExceeded"
                        if quota_exc is not None
                        else _gemini_classify_error_type(error_text=err_text, fallback=exc_type)
                    )
                    status = "in_progress" if sent else ("blocked" if _looks_like_gemini_blocked_error(err_text) else "error")
                    if quota_exc is not None and not sent:
                        status = "cooldown"
                    if quota_exc is None and not sent and _looks_like_gemini_infra_error(err_text):
                        status = "cooldown"
                        error_type = "InfraError"
                    artifacts: dict[str, str] = {}
                    if page is not None:
                        artifacts = await _capture_debug_artifacts(page, label="gemini_web_ask_pro_thinking_error")
                        if ctx and artifacts:
                            await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")

                    try:
                        if page is not None:
                            mode_text_effective = await _gemini_current_mode_text(page)
                    except Exception:
                        mode_text_effective = mode_text_effective

                    result = {
                        "ok": False,
                        "status": status,
                        "answer": "",
                        "conversation_url": (
                            (
                                (await _best_effort_gemini_conversation_url(page)) if page is not None else ""
                            ).strip()
                            or (page.url if page is not None else "")
                            or effective_conversation_url
                            or (str(conversation_url or "").strip())
                        ),
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                        "mode_text": mode_text_effective,
                        "error_type": error_type,
                        "exc_type": exc_type,
                        "error": (str(quota_exc) if quota_exc is not None else err_text),
                        "debug_artifacts": artifacts,
                    }
                    if sent and page is not None:
                        try:
                            result.update(await _gemini_collect_send_observation(page, start_response_count=start_response_count))
                        except Exception:
                            pass
                    result = _gemini_maybe_mark_send_timeout_pending(result, sent=sent)
                    status = str(result.get("status") or status).strip().lower()
                    error_type = str(result.get("error_type") or error_type).strip()
                    err_text = str(result.get("error") or err_text).strip()
                    if quota_exc is not None and not sent:
                        if quota_exc.retry_after_seconds is not None:
                            result["retry_after_seconds"] = int(quota_exc.retry_after_seconds)
                        if quota_exc.not_before is not None:
                            result["not_before"] = float(quota_exc.not_before)
                        if quota_exc.reset_at is not None:
                            result["reset_at"] = float(quota_exc.reset_at)
                        if quota_exc.notice:
                            result["quota_notice"] = str(quota_exc.notice)

                    elif status == "cooldown" and error_type == "InfraError":
                        retry_after_seconds = _gemini_infra_retry_after_seconds()
                        result["retry_after_seconds"] = int(retry_after_seconds)
                        result["not_before"] = float(time.time() + float(retry_after_seconds))
                    try:
                        await _idempotency_update(
                            idem,
                            status=status,
                            sent=bool(sent),
                            conversation_url=str(result.get("conversation_url") or ""),
                            result=result,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    except Exception:
                        pass
                    event: dict[str, Any] = {
                        "tool": "gemini_web_ask_pro_thinking",
                        "status": status,
                        "conversation_url": result.get("conversation_url"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": run_id,
                        "idempotency_key": idem.key,
                        "idempotency_namespace": idem.namespace,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "conversation_url": conversation_url,
                        },
                        "error_type": error_type,
                        "exc_type": exc_type,
                        "error": (str(quota_exc) if quota_exc is not None else err_text),
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


async def gemini_web_ask_pro_deep_think(
    question: str,
    idempotency_key: str,
    conversation_url: str | None = None,
    timeout_seconds: int = 600,
    drive_files: str | list[str] | None = None,
    github_repo: str | None = None,
    repo_context_hint: str | None = None,
    enable_import_code: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    tool_name = "gemini_web_ask_pro_deep_think"
    resolved_drive_files = _gemini_resolve_drive_files(drive_files)
    resolved_github_repo, resolved_repo_context_hint, effective_repo_context = _gemini_resolve_repo_context(
        github_repo=github_repo,
        repo_context_hint=repo_context_hint,
    )
    run_id = _run_id(tool=tool_name, idempotency_key=idempotency_key)
    idem = _IdempotencyContext(
        namespace=_idempotency_namespace(ctx),
        tool=tool_name,
        key=_normalize_idempotency_key(idempotency_key),
        request_hash=_hash_request(
            {
                "tool": tool_name,
                "question": question,
                "drive_files": resolved_drive_files,
                "github_repo": resolved_github_repo,
                "repo_context_hint": resolved_repo_context_hint,
                "enable_import_code": bool(enable_import_code),
            }
        ),
    )
    should_execute, existing = await _idempotency_begin(idem)
    if not should_execute:
        return _gemini_idempotency_replay_result(existing=existing, run_id=run_id, conversation_url=conversation_url)

    async with _ask_lock():
        cfg = _load_gemini_web_config()
        if cfg.cdp_url is None and not cfg.storage_state_path.exists():
            msg = (
                f"Missing storage_state.json at {cfg.storage_state_path}. "
                "Set GEMINI_CDP_URL/CHATGPT_CDP_URL to use a running Chrome, or provide GEMINI_STORAGE_STATE."
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
            async with _page_slot(kind="gemini", ctx=ctx), async_playwright() as p:
                browser = None
                context = None
                page = None
                close_context = False
                sent = False
                start_response_count = 0
                effective_conversation_url = str(conversation_url or "").strip()
                mode_text_effective = ""
                deep_think_retry_info: dict[str, Any] | None = None
                import_code_fallback = None
                drive_attach_fallback = None
                try:
                    browser, context, page, close_context = await _open_gemini_page(
                        p, cfg, conversation_url=conversation_url, ctx=ctx
                    )

                    if conversation_url is None:
                        await _gemini_click_new_chat(page)

                    await _gemini_find_prompt_box(page)
                    await _human_pause(page)
                    await _gemini_clear_selected_tools(page, ctx=ctx)
                    await _gemini_ensure_pro_mode(page, ctx=ctx)
                    await _gemini_set_tool_checked(
                        page,
                        label_re=_GEMINI_DEEP_THINK_TOOL_RE,
                        checked=True,
                        ctx=ctx,
                        fail_open=False,
                    )
                    mode_text_effective = await _gemini_current_mode_text(page)

                    if _gemini_should_import_code(
                        github_repo=resolved_github_repo,
                        enable_import_code=enable_import_code,
                    ):
                        import_code_fallback = await _gemini_maybe_import_code_repo(
                            page,
                            repo_url=resolved_github_repo,
                            drive_files=resolved_drive_files,
                            ctx=ctx,
                        )
                        await _human_pause(page)
                        try:
                            await _gemini_ensure_pro_mode(page, ctx=ctx)
                            await _gemini_set_tool_checked(
                                page,
                                label_re=_GEMINI_DEEP_THINK_TOOL_RE,
                                checked=True,
                                ctx=ctx,
                                fail_open=False,
                            )
                            mode_text_effective = await _gemini_current_mode_text(page)
                        except _GeminiModeQuotaError:
                            raise
                        except Exception:
                            pass

                    if resolved_drive_files:
                        drive_attach_fallback = await _gemini_maybe_attach_drive_files(
                            page,
                            drive_files=resolved_drive_files,
                            repo_url=effective_repo_context,
                            ctx=ctx,
                        )
                        try:
                            await _gemini_ensure_pro_mode(page, ctx=ctx)
                            await _gemini_set_tool_checked(
                                page,
                                label_re=_GEMINI_DEEP_THINK_TOOL_RE,
                                checked=True,
                                ctx=ctx,
                                fail_open=False,
                            )
                            mode_text_effective = await _gemini_current_mode_text(page)
                        except _GeminiModeQuotaError:
                            raise
                        except Exception:
                            pass

                    start_response_count = await page.locator("model-response").count()
                    prompt_box = await _gemini_find_prompt_box(page)
                    prompt_box = await _gemini_focus_prompt_box(page, prompt_box)
                    await _gemini_type_question_with_app_mentions(page, question=question, ctx=ctx)
                    await _human_pause(page)

                    await _gemini_raise_if_quota_limited(page, wanted="Deep Think", ctx=ctx)
                    mode_text_effective = await _gemini_current_mode_text(page)

                    await _gemini_click_send(page, prompt_box, ctx=ctx)
                    sent = True
                    try:
                        effective_conversation_url = await _gemini_wait_for_conversation_url(page, timeout_seconds=8.0)
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

                    await _ctx_info(ctx, "Waiting for Gemini answer…")

                    answer = await _gemini_wait_for_model_response(
                        page,
                        started_at=started_at,
                        start_response_count=start_response_count,
                        timeout_seconds=timeout_seconds,
                        min_chars=0,
                        require_new=True,
                    )

                    async def _new_conversation_sender():
                        """Open a fresh Gemini page, send the same question with Deep Think, return (answer, url)."""
                        _nc_browser, _nc_context, _nc_page, _nc_close_context = None, None, None, False
                        try:
                            _nc_browser, _nc_context, _nc_page, _nc_close_context = await _open_gemini_page(
                                p, cfg, conversation_url=None, ctx=ctx
                            )
                            await _gemini_click_new_chat(_nc_page)
                            await _gemini_find_prompt_box(_nc_page)
                            await _human_pause(_nc_page)
                            await _gemini_clear_selected_tools(_nc_page, ctx=ctx)
                            await _gemini_ensure_pro_mode(_nc_page, ctx=ctx)
                            await _gemini_set_tool_checked(
                                _nc_page,
                                label_re=_GEMINI_DEEP_THINK_TOOL_RE,
                                checked=True,
                                ctx=ctx,
                                fail_open=False,
                            )
                            _nc_start_count = await _nc_page.locator("model-response").count()
                            _nc_prompt_box = await _gemini_find_prompt_box(_nc_page)
                            _nc_prompt_box = await _gemini_focus_prompt_box(_nc_page, _nc_prompt_box)
                            await _gemini_type_question_with_app_mentions(_nc_page, question=question, ctx=ctx)
                            await _human_pause(_nc_page)
                            await _gemini_click_send(_nc_page, _nc_prompt_box, ctx=ctx)
                            try:
                                _nc_url = await _gemini_wait_for_conversation_url(_nc_page, timeout_seconds=8.0)
                            except Exception:
                                _nc_url = (_nc_page.url or "").strip()
                            _nc_answer = await _gemini_wait_for_model_response(
                                _nc_page,
                                started_at=time.time(),
                                start_response_count=_nc_start_count,
                                timeout_seconds=timeout_seconds,
                                min_chars=0,
                                require_new=True,
                            )
                            return _nc_answer, _nc_url
                        finally:
                            try:
                                if _nc_page is not None:
                                    await _nc_page.close()
                            except Exception:
                                pass
                            if _nc_close_context and _nc_context is not None:
                                try:
                                    await _nc_context.close()
                                except Exception:
                                    pass
                            if _nc_browser is not None:
                                try:
                                    await _nc_browser.close()
                                except Exception:
                                    pass

                    answer, deep_think_retry_info = await _gemini_retry_deep_think_overloaded_answer(
                        page,
                        answer=answer,
                        timeout_seconds=timeout_seconds,
                        ctx=ctx,
                        new_conversation_sender=_new_conversation_sender,
                    )

                    if _looks_like_transient_assistant_error(answer):
                        raise RuntimeError(f"Gemini returned a transient error message: {answer}")

                    mode_text_effective = await _gemini_current_mode_text(page)
                    result = {
                        "ok": True,
                        "answer": answer,
                        "status": _classify_non_deep_research_answer(answer),
                        "conversation_url": (
                            await _best_effort_gemini_conversation_url(page)
                            or effective_conversation_url
                            or page.url
                            or ""
                        ),
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                        "mode_text": mode_text_effective,
                        "error_type": None,
                        "error": None,
                    }
                    if import_code_fallback is not None:
                        result["import_code_fallback"] = dict(import_code_fallback)
                    if drive_attach_fallback is not None:
                        result["drive_attach_fallback"] = dict(drive_attach_fallback)
                    if deep_think_retry_info is not None:
                        result["deep_think_retry"] = deep_think_retry_info
                    # Best-effort thinking trace capture
                    try:
                        thinking_trace = await _gemini_capture_thinking_trace(page, ctx=ctx)
                        if thinking_trace:
                            result["thinking_trace"] = thinking_trace
                    except Exception:
                        pass
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
                        "tool": tool_name,
                        "status": result.get("status"),
                        "conversation_url": result.get("conversation_url"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": result.get("run_id") or run_id,
                        "idempotency_key": idem.key,
                        "idempotency_namespace": idem.namespace,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "conversation_url": conversation_url,
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
                    quota_exc = exc if isinstance(exc, _GeminiModeQuotaError) else None
                    err_text = _coerce_error_text(exc)
                    exc_type = type(exc).__name__
                    error_type = (
                        "GeminiModeQuotaExceeded"
                        if quota_exc is not None
                        else _gemini_classify_error_type(error_text=err_text, fallback=exc_type)
                    )
                    status = "in_progress" if sent else ("blocked" if _looks_like_gemini_blocked_error(err_text) else "error")
                    if quota_exc is not None and not sent:
                        status = "cooldown"
                    if quota_exc is None and not sent and _looks_like_gemini_infra_error(err_text):
                        status = "cooldown"
                        error_type = "InfraError"
                    artifacts: dict[str, str] = {}
                    if page is not None:
                        artifacts = await _capture_debug_artifacts(page, label="gemini_web_ask_pro_deep_think_error")
                        if ctx and artifacts:
                            await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")

                    try:
                        if page is not None:
                            mode_text_effective = await _gemini_current_mode_text(page)
                    except Exception:
                        mode_text_effective = mode_text_effective

                    result = {
                        "ok": False,
                        "status": status,
                        "answer": "",
                        "conversation_url": (
                            (
                                (await _best_effort_gemini_conversation_url(page)) if page is not None else ""
                            ).strip()
                            or (page.url if page is not None else "")
                            or effective_conversation_url
                            or (str(conversation_url or "").strip())
                        ),
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                        "mode_text": mode_text_effective,
                        "error_type": error_type,
                        "exc_type": exc_type,
                        "error": (
                            str(quota_exc)
                            if quota_exc is not None
                            else str((quota_info or {}).get("notice") or err_text)
                        ),
                        "debug_artifacts": artifacts,
                    }
                    if sent and page is not None:
                        try:
                            result.update(await _gemini_collect_send_observation(page, start_response_count=start_response_count))
                        except Exception:
                            pass
                    if quota_exc is None and quota_info is not None:
                        status = "cooldown"
                        result["status"] = "cooldown"
                        result["error_type"] = "GeminiModeQuotaExceeded"
                        result["error"] = str(quota_info.get("notice") or err_text or "Gemini Deep Think mode appears quota-limited.")
                    if quota_exc is None and quota_info is None and sent:
                        response_started = bool(result.get("response_started"))
                        pending_conversation_url = str(result.get("conversation_url") or "").strip()
                        has_thread_url = bool(_gemini_conversation_id_from_url(pending_conversation_url))
                        if response_started:
                            pending_type = "GeminiDeepThinkResponsePending" if has_thread_url else "GeminiDeepThinkThreadPending"
                            retry_after_seconds = 15
                            result["status"] = "in_progress"
                            result["error_type"] = pending_type
                            result["error"] = (
                                "Gemini Deep Think response started but the final answer is still pending; "
                                "hand off this run to wait instead of resending."
                            )
                            result["wait_handoff_ready"] = True
                            result["wait_handoff_reason"] = "response_started"
                            result.setdefault("retry_after_seconds", int(retry_after_seconds))
                            result.setdefault("not_before", float(time.time() + float(retry_after_seconds)))
                        elif str(result.get("error_type") or "").strip() == "TimeoutError":
                            result["error_type"] = "GeminiDeepThinkSendUnconfirmed"
                            result["error"] = (
                                "Gemini Deep Think send timed out before a new response started; "
                                "stay on send and retry with recovery instead of entering wait."
                            )
                    if deep_think_retry_info is not None:
                        result["deep_think_retry"] = deep_think_retry_info
                    result = _gemini_maybe_mark_send_timeout_pending(result, sent=sent)
                    status = str(result.get("status") or status).strip().lower()
                    error_type = str(result.get("error_type") or error_type).strip()
                    err_text = str(result.get("error") or err_text).strip()
                    if quota_exc is not None or quota_info is not None:
                        quota_retry_after = (
                            int(quota_exc.retry_after_seconds)
                            if quota_exc is not None and quota_exc.retry_after_seconds is not None
                            else int(quota_info.get("retry_after_seconds") or 0)
                        )
                        quota_not_before = (
                            float(quota_exc.not_before)
                            if quota_exc is not None and quota_exc.not_before is not None
                            else float(quota_info.get("not_before") or 0.0)
                        )
                        quota_reset_at = (
                            float(quota_exc.reset_at)
                            if quota_exc is not None and quota_exc.reset_at is not None
                            else float(quota_info.get("reset_at") or 0.0)
                        )
                        quota_notice = (
                            str(quota_exc.notice)
                            if quota_exc is not None and quota_exc.notice
                            else str(quota_info.get("notice") or "")
                        )
                        if quota_retry_after > 0:
                            result["retry_after_seconds"] = int(quota_retry_after)
                        if quota_not_before > 0:
                            result["not_before"] = float(quota_not_before)
                        if quota_reset_at > 0:
                            result["reset_at"] = float(quota_reset_at)
                        if quota_notice:
                            result["quota_notice"] = quota_notice

                    elif status == "cooldown" and error_type == "InfraError":
                        retry_after_seconds = _gemini_infra_retry_after_seconds()
                        result["retry_after_seconds"] = int(retry_after_seconds)
                        result["not_before"] = float(time.time() + float(retry_after_seconds))
                    try:
                        await _idempotency_update(
                            idem,
                            status=status,
                            sent=bool(sent),
                            conversation_url=str(result.get("conversation_url") or ""),
                            result=result,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    except Exception:
                        pass
                    event = {
                        "tool": tool_name,
                        "status": status,
                        "conversation_url": result.get("conversation_url"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": run_id,
                        "idempotency_key": idem.key,
                        "idempotency_namespace": idem.namespace,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "conversation_url": conversation_url,
                        },
                        "error_type": error_type,
                        "exc_type": exc_type,
                        "error": (str(quota_exc) if quota_exc is not None else err_text),
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


async def gemini_web_extract_answer(
    conversation_url: str,
    timeout_seconds: int = 60,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Open an existing Gemini conversation URL and extract the last model response.

    This is read-only — no question is sent. Useful for retrieving answers from
    conversations that were started manually or by another process.
    """
    tool_name = "gemini_web_extract_answer"
    url = str(conversation_url or "").strip()
    if not url:
        return {
            "ok": False,
            "status": "error",
            "answer": "",
            "conversation_url": "",
            "error_type": "ValueError",
            "error": "conversation_url is required",
        }

    async with _ask_lock():
        cfg = _load_gemini_web_config()
        if cfg.cdp_url is None and not cfg.storage_state_path.exists():
            return {
                "ok": False,
                "status": "error",
                "answer": "",
                "conversation_url": url,
                "error_type": "RuntimeError",
                "error": "Missing storage state or CDP URL",
            }

        started_at = time.time()
        env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
        with env_ctx:
            async with _page_slot(kind="gemini", ctx=ctx), async_playwright() as p:
                browser = None
                context = None
                page = None
                close_context = False
                try:
                    browser, context, page, close_context = await _open_gemini_page(
                        p, cfg, conversation_url=url, ctx=ctx
                    )

                    # Wait for model-response elements to render (Gemini loads async)
                    try:
                        await page.wait_for_selector(
                            "model-response", timeout=30_000, state="attached"
                        )
                    except Exception:
                        pass
                    # Extra settle time for markdown rendering
                    await page.wait_for_timeout(2000)

                    # Extract the last model-response
                    responses = page.locator("model-response")
                    count = await responses.count()
                    if count <= 0:
                        return {
                            "ok": False,
                            "status": "error",
                            "answer": "",
                            "conversation_url": url,
                            "elapsed_seconds": round(time.time() - started_at, 3),
                            "error_type": "NoModelResponse",
                            "error": f"No model-response elements found on {url}",
                        }

                    last_response = responses.nth(count - 1)

                    # Try to extract markdown-rich text
                    markdown_loc = last_response.locator("message-content .markdown")
                    md_count = await markdown_loc.count()
                    if md_count > 0:
                        answer = await _gemini_extract_markdown_text(markdown_loc.nth(md_count - 1))
                    else:
                        try:
                            answer = (await last_response.inner_text(timeout=10_000)).strip()
                        except Exception:
                            answer = ""

                    answer = _gemini_clean_response_text(answer)

                    # Best-effort thinking trace capture
                    thinking_trace = None
                    try:
                        thinking_trace = await _gemini_capture_thinking_trace(page, ctx=ctx)
                    except Exception:
                        pass

                    result: dict[str, Any] = {
                        "ok": bool(answer),
                        "status": "completed" if answer else "error",
                        "answer": answer,
                        "conversation_url": (page.url or url),
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "response_count": int(count),
                        "error_type": None if answer else "EmptyAnswer",
                        "error": None if answer else "Extracted answer is empty",
                    }
                    if thinking_trace:
                        result["thinking_trace"] = thinking_trace
                    return result
                except Exception as exc:
                    return {
                        "ok": False,
                        "status": "error",
                        "answer": "",
                        "conversation_url": url,
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "error_type": type(exc).__name__,
                        "error": _coerce_error_text(exc),
                    }
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
