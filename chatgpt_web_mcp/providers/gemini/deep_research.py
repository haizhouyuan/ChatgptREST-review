from __future__ import annotations

from chatgpt_web_mcp.providers.gemini.core import *  # noqa: F403

async def gemini_web_deep_research(
    question: str,
    idempotency_key: str,
    conversation_url: str | None = None,
    timeout_seconds: int = 180,
    drive_files: str | list[str] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    tool_name = "gemini_web_deep_research"
    resolved_drive_files = _gemini_resolve_drive_files(drive_files)
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
                try:
                    browser, context, page, close_context = await _open_gemini_page(
                        p, cfg, conversation_url=conversation_url, ctx=ctx
                    )

                    if conversation_url is None:
                        await _gemini_click_new_chat(page)

                    await _gemini_find_prompt_box(page)
                    await _human_pause(page)
                    await _gemini_set_tool_checked(
                        page,
                        label_re=re.compile(
                            r"(Deep\s*Research|深入研究|深度研究|深入調研|深度調研|深入调研|深度调研)",
                            re.I,
                        ),
                        checked=True,
                        ctx=ctx,
                        fail_open=False,
                    )
                    mode_text_effective = await _gemini_current_mode_text(page)

                    if resolved_drive_files:
                        await _ctx_info(ctx, f"Gemini: attaching {len(resolved_drive_files)} Drive file(s)…")
                        for q in resolved_drive_files:
                            await _gemini_attach_drive_file(page, query=q, ctx=ctx)
                            await _human_pause(page)

                    start_response_count = await page.locator("model-response").count()
                    prompt_box = await _gemini_find_prompt_box(page)
                    await _gemini_dismiss_overlays(page)
                    await prompt_box.click()
                    await _human_pause(page)
                    await _gemini_type_question_with_app_mentions(page, question=question, ctx=ctx)
                    await _human_pause(page)

                    await _gemini_raise_if_quota_limited(page, wanted="Deep Research", ctx=ctx)
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

                    await _ctx_info(ctx, "Waiting for Gemini Deep Research…")

                    answer = ""
                    status = "in_progress"
                    try:
                        answer = await _gemini_wait_for_model_response(
                            page,
                            started_at=started_at,
                            start_response_count=start_response_count,
                            timeout_seconds=timeout_seconds,
                            require_new=True,
                        )
                        status = _classify_deep_research_answer(answer)
                    except TimeoutError:
                        hint = ""
                        try:
                            hint = (await page.locator("body").inner_text(timeout=2_000)).strip()
                        except Exception:
                            hint = ""
                        if re.search(r"(请稍候|正在|Working|Research)", hint, re.I):
                            status = "in_progress"
                        else:
                            raise

                    if _looks_like_transient_assistant_error(answer):
                        raise RuntimeError(f"Gemini returned a transient error message: {answer}")

                    mode_text_effective = await _gemini_current_mode_text(page)
                    result = {
                        "ok": True,
                        "answer": answer,
                        "status": status,
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
                    try:
                        await _idempotency_update(
                            idem,
                            status=str(result.get("status") or "in_progress"),
                            conversation_url=str(result.get("conversation_url") or ""),
                            result=result,
                        )
                    except Exception:
                        pass
                    event: dict[str, Any] = {
                        "tool": "gemini_web_deep_research",
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
                    artifacts: dict[str, str] = {}
                    if page is not None:
                        artifacts = await _capture_debug_artifacts(page, label="gemini_web_deep_research_error")
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
                    if quota_exc is not None and not sent:
                        if quota_exc.retry_after_seconds is not None:
                            result["retry_after_seconds"] = int(quota_exc.retry_after_seconds)
                        if quota_exc.not_before is not None:
                            result["not_before"] = float(quota_exc.not_before)
                        if quota_exc.reset_at is not None:
                            result["reset_at"] = float(quota_exc.reset_at)
                        if quota_exc.notice:
                            result["quota_notice"] = str(quota_exc.notice)
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
                        "tool": "gemini_web_deep_research",
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
