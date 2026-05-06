from __future__ import annotations

from chatgpt_web_mcp.providers.gemini.core import *  # noqa: F403


def _gemini_fail_closed_thread_mismatch_result(
    *,
    requested_conversation_url: str,
    observed_conversation_url: str,
    started_at: float,
    run_id: str,
    reason: str,
) -> dict[str, Any]:
    requested = str(requested_conversation_url or "").strip()
    observed = str(observed_conversation_url or "").strip()
    requested_cid = _gemini_conversation_id_from_url(requested)
    observed_cid = _gemini_conversation_id_from_url(observed)
    return {
        "ok": False,
        "answer": "",
        "status": "error",
        "conversation_url": requested,
        "observed_conversation_url": observed,
        "elapsed_seconds": round(time.time() - started_at, 3),
        "run_id": run_id,
        "error_type": "GeminiConversationThreadMismatch",
        "error": (
            "gemini_web_wait observed a different Gemini thread than requested. "
            f"expected={requested_cid or '<none>'} observed={observed_cid or '<none>'}; {reason}"
        ),
        "retry_after_seconds": _gemini_infra_retry_after_seconds(),
        "not_before": time.time() + float(_gemini_infra_retry_after_seconds()),
    }


def _gemini_wait_thread_guard_result(
    *,
    requested_conversation_url: str,
    observed_conversation_url: str,
    started_at: float,
    run_id: str,
) -> dict[str, Any] | None:
    requested = str(requested_conversation_url or "").strip()
    observed = str(observed_conversation_url or "").strip()
    requested_cid = _gemini_conversation_id_from_url(requested)
    if not requested_cid:
        return None
    observed_cid = _gemini_conversation_id_from_url(observed)
    if observed_cid == requested_cid:
        return None
    if not observed_cid:
        return _gemini_fail_closed_thread_mismatch_result(
            requested_conversation_url=requested,
            observed_conversation_url=observed,
            started_at=started_at,
            run_id=run_id,
            reason="wait did not remain on a concrete Gemini thread URL.",
        )
    return _gemini_fail_closed_thread_mismatch_result(
        requested_conversation_url=requested,
        observed_conversation_url=observed,
        started_at=started_at,
        run_id=run_id,
        reason="refusing to switch from one concrete Gemini thread to another during wait/export.",
    )


def _gemini_expected_wait_thread_url(
    *,
    requested_conversation_url: str,
    observed_conversation_url: str,
    selected_conversation_id: str = "",
) -> str:
    selected_cid = str(selected_conversation_id or "").strip()
    if selected_cid:
        return _gemini_build_conversation_url(
            base_url=str(observed_conversation_url or "").strip()
            or str(requested_conversation_url or "").strip()
            or "https://gemini.google.com/app",
            conversation_id=selected_cid,
        )
    observed = str(observed_conversation_url or "").strip()
    if _gemini_conversation_id_from_url(observed):
        return observed
    return str(requested_conversation_url or "").strip()


async def gemini_web_wait(
    conversation_url: str,
    timeout_seconds: int = 7200,
    min_chars: int = 0,
    conversation_hint: str | None = None,
    # Compatibility flag for older callers and MCP registry snapshot.
    # Wait behavior currently does not branch on this value.
    deep_research: bool | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    conversation_url = str(conversation_url or "").strip()
    started_at = time.time()
    run_id = _run_id(tool="gemini_web_wait")
    if _gemini_is_base_app_url(conversation_url):
        if not str(conversation_hint or "").strip():
            msg = (
                "conversation_url points to Gemini home (/app). Provide a conversation thread URL like "
                "https://gemini.google.com/app/<conversation_id>, or pass conversation_hint so the driver "
                "can locate the correct thread from the sidebar."
            )
            return {
                "ok": False,
                "answer": "",
                "status": "error",
                "conversation_url": conversation_url,
                "elapsed_seconds": round(time.time() - started_at, 3),
                "run_id": run_id,
                "error_type": "ValueError",
                "error": msg,
            }

    async with _ask_lock():
        cfg = _load_gemini_web_config()
        env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
        with env_ctx:
            async with _page_slot(kind="gemini", ctx=ctx), async_playwright() as p:
                browser = None
                context = None
                page = None
                close_context = False
                sidebar_debug: dict[str, Any] = {}
                expected_conversation_url = conversation_url
                requested_cid = _gemini_conversation_id_from_url(conversation_url)
                try:
                    browser, context, page, close_context = await _open_gemini_page(
                        p, cfg, conversation_url=conversation_url, ctx=ctx
                    )

                    try:
                        await _gemini_dismiss_overlays(page)
                    except Exception:
                        pass

                    responses = page.locator("model-response")
                    stop_btn = page.locator(_GEMINI_STOP_BUTTON_SELECTOR).first

                    def _is_gemini_root_url(url: str) -> bool:
                        raw = str(url or "").strip()
                        if not raw:
                            return False
                        base = raw.split("#", 1)[0].split("?", 1)[0].rstrip("/")
                        return base == "https://gemini.google.com/app"

                    async def _select_conversation_from_sidebar() -> None:
                        nonlocal expected_conversation_url
                        if not _is_gemini_root_url(conversation_url) and not _is_gemini_root_url(page.url):
                            return
                        sidebar_debug["attempted"] = True
                        sidebar_debug["requested_cid"] = requested_cid or ""
                        if requested_cid and _is_gemini_root_url(page.url):
                            sidebar_debug["requested_cid_direct_goto_attempted"] = True
                            try:
                                await _goto_with_retry(page, conversation_url, ctx=ctx)
                                after_direct_goto = await _gemini_wait_for_conversation_url(page, timeout_seconds=3.0)
                            except Exception as exc:
                                after_direct_goto = (page.url or "").strip()
                                sidebar_debug["requested_cid_direct_goto_error"] = _coerce_error_text(exc)
                            sidebar_debug["requested_cid_direct_goto_url"] = after_direct_goto
                            if _gemini_conversation_id_from_url(after_direct_goto) == requested_cid:
                                sidebar_debug["requested_cid_direct_goto_succeeded"] = True
                                expected_conversation_url = conversation_url
                                await page.wait_for_timeout(650)
                                return
                            sidebar_debug["requested_cid_direct_goto_succeeded"] = False
                        try:
                            if await responses.count() > 0:
                                sidebar_debug["skipped_reason"] = "has_model_response"
                                return
                        except Exception as exc:
                            sidebar_debug["skipped_reason"] = "responses_count_error"
                            sidebar_debug["error"] = _coerce_error_text(exc)
                            return

                        def _conversation_rows():
                            return page.locator(
                                "[data-test-id='conversation'][role='button'], "
                                "div.conversation-row[role='button']"
                            )

                        def _menu_button():
                            return page.locator(
                                "button[data-test-id='side-nav-menu-button'], "
                                "button[aria-label='主菜单'], "
                                "button[aria-label='Menu'], "
                                "button[aria-label='Open menu'], "
                                "button[aria-label='Main menu']"
                            ).first

                        rows = _conversation_rows()
                        try:
                            row_count = await rows.count()
                        except Exception:
                            row_count = 0
                        sidebar_debug["row_count_initial"] = row_count

                        first_clickable = False
                        if row_count > 0:
                            try:
                                await rows.first.click(timeout=2_000, trial=True)
                                first_clickable = True
                            except Exception:
                                first_clickable = False
                        sidebar_debug["first_row_clickable"] = first_clickable

                        if row_count <= 0 or not first_clickable:
                            menu_clicked = False
                            try:
                                btn = _menu_button()
                                if await btn.count():
                                    await btn.click(timeout=5_000)
                                    menu_clicked = True
                                    await page.wait_for_timeout(500)
                            except Exception as exc:
                                sidebar_debug["menu_click_error"] = _coerce_error_text(exc)
                            sidebar_debug["menu_clicked"] = menu_clicked

                        rows = _conversation_rows()
                        try:
                            row_count = await rows.count()
                        except Exception:
                            row_count = 0
                        sidebar_debug["row_count"] = row_count
                        if row_count <= 0:
                            sidebar_debug["failed_reason"] = "no_sidebar_rows"
                            return

                        tokens = _gemini_conversation_hint_tokens(conversation_hint, max_tokens=24)
                        sidebar_debug["token_count"] = len(tokens)
                        sidebar_debug["token_has_cjk"] = any(re.search(r"[\u4e00-\u9fff]", tok) for tok in tokens)

                        async def _open_row(row, *, reason: str, title_hint: str | None = None) -> None:
                            nonlocal expected_conversation_url
                            selected: dict[str, Any] = {"reason": reason}
                            if title_hint:
                                selected["title"] = (title_hint or "")[:160]
                            cid = None
                            try:
                                jslog = await row.get_attribute("jslog")
                                cid = _gemini_conversation_id_from_jslog(jslog)
                            except Exception:
                                cid = None
                            if not cid:
                                expected_conversation_url = conversation_url
                            if cid:
                                selected["cid"] = cid
                                if requested_cid and cid != requested_cid:
                                    selected["requested_cid_mismatch"] = True
                                    expected_conversation_url = conversation_url
                                else:
                                    expected_conversation_url = _gemini_expected_wait_thread_url(
                                        requested_conversation_url=conversation_url,
                                        observed_conversation_url=(page.url or "").strip(),
                                        selected_conversation_id=cid,
                                    )
                                selected["expected_conversation_url"] = expected_conversation_url
                            sidebar_debug["selected"] = selected

                            try:
                                await row.scroll_into_view_if_needed(timeout=2_000)
                            except Exception:
                                pass

                            click_kwargs: dict[str, Any] = {"timeout": 5_000}
                            try:
                                if not await row.is_visible():
                                    click_kwargs["force"] = True
                            except Exception:
                                click_kwargs["force"] = True

                            try:
                                await row.click(**click_kwargs)
                                selected["clicked"] = True
                            except Exception as exc:
                                selected["clicked"] = False
                                selected["click_error"] = _coerce_error_text(exc)

                            try:
                                after_click = await _gemini_wait_for_conversation_url(page, timeout_seconds=3.0)
                            except Exception:
                                after_click = (page.url or "").strip()
                            selected["url_after_click"] = after_click
                            if _gemini_conversation_id_from_url(after_click):
                                if not cid:
                                    if requested_cid:
                                        expected_conversation_url = conversation_url
                                    else:
                                        expected_conversation_url = _gemini_expected_wait_thread_url(
                                            requested_conversation_url=conversation_url,
                                            observed_conversation_url=after_click,
                                        )
                                    selected["expected_conversation_url"] = expected_conversation_url
                                else:
                                    selected["observed_thread_after_click"] = after_click
                                    selected["expected_conversation_url"] = expected_conversation_url
                                await page.wait_for_timeout(650)
                                return

                            if cid:
                                base = (page.url or "").strip() or conversation_url
                                target = _gemini_build_conversation_url(base_url=base, conversation_id=cid)
                                try:
                                    await _goto_with_retry(page, target, ctx=ctx)
                                    selected["goto"] = True
                                    selected["goto_target"] = target
                                except Exception as exc:
                                    selected["goto"] = False
                                    selected["goto_error"] = _coerce_error_text(exc)

                                try:
                                    after_goto = await _gemini_wait_for_conversation_url(page, timeout_seconds=3.0)
                                except Exception:
                                    after_goto = (page.url or "").strip()
                                selected["url_after_goto"] = after_goto
                                if _gemini_conversation_id_from_url(after_goto):
                                    selected["expected_conversation_url"] = expected_conversation_url
                                    selected["observed_thread_after_goto"] = after_goto

                            await page.wait_for_timeout(650)

                        skip_title_match = False
                        if requested_cid:
                            exact_scan_n = min(row_count, 20)
                            sidebar_debug["requested_cid_scan_n"] = exact_scan_n
                            sidebar_debug["requested_cid_match_found"] = False
                            for i in range(exact_scan_n):
                                row = rows.nth(i)
                                try:
                                    jslog = await row.get_attribute("jslog")
                                except Exception:
                                    jslog = None
                                row_cid = _gemini_conversation_id_from_jslog(jslog)
                                if row_cid != requested_cid:
                                    continue
                                sidebar_debug["requested_cid_match_found"] = True
                                await _open_row(row, reason="requested_cid_match")
                                return

                            # When the caller already supplied a concrete thread URL, keep that
                            # thread authoritative. We can still probe the sidebar/body to recover
                            # the same conversation, but we must not rebind onto another thread.
                            skip_title_match = True
                            sidebar_debug["requested_cid_fallback"] = "body_probe_only"

                        if tokens:
                            scan_n = min(row_count, 20)
                            best_idx: int | None = None
                            best_score = 0
                            best_title: str | None = None
                            for i in range(scan_n):
                                row = rows.nth(i)
                                try:
                                    title = (await row.inner_text(timeout=2_000)).strip()
                                except Exception:
                                    continue
                                if not title:
                                    continue
                                title_norm = title.lower()
                                score = 0
                                for tok in tokens:
                                    if tok.lower() in title_norm:
                                        score += len(tok)
                                if score > best_score:
                                    best_score = score
                                    best_idx = i
                                    best_title = title
                            sidebar_debug["title_scan_n"] = scan_n
                            sidebar_debug["best_score"] = best_score
                            sidebar_debug["best_index"] = best_idx
                            if not skip_title_match and best_idx is not None and best_score > 0:
                                await _open_row(rows.nth(best_idx), reason="title_match", title_hint=best_title)
                                return
                            if skip_title_match:
                                sidebar_debug["title_match_skipped_reason"] = "requested_cid_missing"

                            root_url = (conversation_url or "").strip() or "https://gemini.google.com/app"
                            for i in range(min(row_count, 6)):
                                await _open_row(rows.nth(i), reason="body_probe")
                                body_text = ""
                                try:
                                    body_text = (await page.locator("body").inner_text(timeout=2_000)).strip()
                                except Exception:
                                    body_text = ""
                                if body_text and any(tok.lower() in body_text.lower() for tok in tokens):
                                    return
                                try:
                                    await _goto_with_retry(page, root_url, ctx=ctx)
                                    await page.wait_for_timeout(400)
                                except Exception:
                                    break

                        if requested_cid:
                            return

                        try:
                            await _open_row(rows.first, reason="fallback_most_recent")
                        except Exception:
                            pass

                    await _select_conversation_from_sidebar()
                    if _gemini_is_base_app_url(expected_conversation_url):
                        selected_thread_url = str(page.url or "").strip()
                        if _gemini_conversation_id_from_url(selected_thread_url):
                            expected_conversation_url = selected_thread_url
                    deadline = started_at + timeout_seconds
                    last_text = ""
                    answer = ""
                    requested_cid_loop_reopen_attempts = 0
                    requested_cid_loop_reopen_total_attempts = 0
                    requested_cid_same_session_repair_consumed = False
                    requested_cid_total_recovery_attempts = 0
                    requested_cid_total_recovery_budget = 6
                    while time.time() < deadline:
                        current_thread_url = str(page.url or "").strip()
                        if _gemini_is_base_app_url(expected_conversation_url):
                            if _gemini_conversation_id_from_url(current_thread_url):
                                expected_conversation_url = current_thread_url
                        elif requested_cid and _is_gemini_root_url(current_thread_url):
                            if (
                                requested_cid_loop_reopen_attempts < 2
                                and requested_cid_total_recovery_attempts < requested_cid_total_recovery_budget
                            ):
                                requested_cid_loop_reopen_attempts += 1
                                requested_cid_loop_reopen_total_attempts += 1
                                requested_cid_total_recovery_attempts += 1
                                sidebar_debug["requested_cid_loop_reopen_attempts"] = requested_cid_loop_reopen_attempts
                                sidebar_debug["requested_cid_loop_reopen_total_attempts"] = requested_cid_loop_reopen_total_attempts
                                sidebar_debug["requested_cid_total_recovery_attempts"] = requested_cid_total_recovery_attempts
                                try:
                                    await _goto_with_retry(page, expected_conversation_url, ctx=ctx)
                                    reopened_url = await _gemini_wait_for_conversation_url(page, timeout_seconds=3.0)
                                except Exception as exc:
                                    reopened_url = (page.url or "").strip()
                                    sidebar_debug["requested_cid_loop_reopen_error"] = _coerce_error_text(exc)
                                sidebar_debug["requested_cid_loop_reopen_url"] = reopened_url
                                if _gemini_conversation_id_from_url(reopened_url) == requested_cid:
                                    await page.wait_for_timeout(650)
                                    continue
                            if (
                                not requested_cid_same_session_repair_consumed
                                and requested_cid_total_recovery_attempts < requested_cid_total_recovery_budget
                            ):
                                requested_cid_same_session_repair_consumed = True
                                requested_cid_total_recovery_attempts += 1
                                sidebar_debug["requested_cid_same_session_repair_attempted"] = True
                                sidebar_debug["requested_cid_total_recovery_attempts"] = requested_cid_total_recovery_attempts
                                try:
                                    await _select_conversation_from_sidebar()
                                    repaired_url = await _gemini_wait_for_conversation_url(page, timeout_seconds=3.0)
                                except Exception as exc:
                                    repaired_url = (page.url or "").strip()
                                    sidebar_debug["requested_cid_same_session_repair_error"] = _coerce_error_text(exc)
                                sidebar_debug["requested_cid_same_session_repair_url"] = repaired_url
                                if _gemini_conversation_id_from_url(repaired_url) == requested_cid:
                                    sidebar_debug["requested_cid_same_session_repair_succeeded"] = True
                                    requested_cid_loop_reopen_attempts = 0
                                    requested_cid_same_session_repair_consumed = False
                                    sidebar_debug["requested_cid_recovery_cycle_resets"] = int(sidebar_debug.get("requested_cid_recovery_cycle_resets") or 0) + 1
                                    await page.wait_for_timeout(650)
                                    continue
                                sidebar_debug["requested_cid_same_session_repair_succeeded"] = False
                        report_text = ""
                        # Gemini Deep Research outputs in a dedicated immersive panel (not in the
                        # normal chat "model-response"). Prefer extracting from the panel so we
                        # don't accidentally return the earlier "plan/starting…" chat text.
                        try:
                            panel = page.locator("deep-research-immersive-panel").first
                            if await panel.count():
                                panel_text = (await panel.inner_text(timeout=2_000)).strip()
                                if _looks_like_gemini_deep_research_report(panel_text):
                                    report_text = _slice_gemini_deep_research_report(panel_text)
                        except Exception:
                            report_text = ""

                        if not report_text:
                            body_text = ""
                            try:
                                body_text = (await page.locator("body").inner_text(timeout=2_000)).strip()
                            except Exception:
                                body_text = ""
                            if _looks_like_gemini_deep_research_report(body_text):
                                report_text = _slice_gemini_deep_research_report(body_text)

                        if report_text:
                            text = report_text
                            stop_visible = False
                            is_busy = False
                        else:
                            count = await responses.count()
                            if count <= 0:
                                await page.wait_for_timeout(500)
                                continue
                            text, is_busy = await _gemini_last_model_response_text_and_busy(page)

                            stop_visible = False
                            try:
                                if await stop_btn.count():
                                    stop_visible = await stop_btn.is_visible()
                            except PlaywrightTimeoutError:
                                stop_visible = False
                            if _looks_like_gemini_transient_response(text):
                                last_text = text
                                await page.wait_for_timeout(650)
                                continue

                        last_text = text

                        if is_busy:
                            await page.wait_for_timeout(700)
                            continue

                        if stop_visible:
                            await page.wait_for_timeout(700)
                            continue

                        if min_chars and len(text) < min_chars:
                            await page.wait_for_timeout(650)
                            continue

                        # If Gemini reports it is no longer busy (aria-busy/stop-button checks above),
                        # treat the latest non-transient response as final.
                        answer = text
                        break

                    artifacts: dict[str, str] = {}
                    if not answer:
                        try:
                            artifacts = await _capture_debug_artifacts(page, label="gemini_web_wait_timeout")
                        except Exception:
                            artifacts = {}
                        if ctx and artifacts:
                            await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")

                        status = "in_progress"
                        ok = True
                        error_type = None
                        error = None
                        if (
                            _gemini_is_base_app_url(page.url)
                            and _gemini_is_base_app_url(conversation_url)
                            and str(conversation_hint or "").strip()
                        ):
                            status = "error"
                            ok = False
                            error_type = "RuntimeError"
                            error = (
                                "gemini_web_wait stayed on Gemini home (/app) and could not open the conversation "
                                "thread from the sidebar. Provide a thread URL (https://gemini.google.com/app/<id>) "
                                "or adjust conversation_hint to match the conversation title."
                            )

                        result = {
                            "ok": ok,
                            "answer": last_text,
                            "status": status,
                            "conversation_url": page.url,
                            "elapsed_seconds": round(time.time() - started_at, 3),
                            "run_id": run_id,
                            "debug_artifacts": artifacts,
                            "sidebar_debug": sidebar_debug,
                            "error_type": error_type,
                            "error": error,
                        }
                    else:
                        result = {
                            "ok": True,
                            "answer": answer,
                            "status": (
                                _classify_deep_research_answer(answer)
                                if deep_research
                                else _classify_non_deep_research_answer(answer)
                            ),
                            "conversation_url": page.url,
                            "elapsed_seconds": round(time.time() - started_at, 3),
                            "run_id": run_id,
                            "sidebar_debug": sidebar_debug,
                            "error_type": None,
                            "error": None,
                        }

                    thread_guard = _gemini_wait_thread_guard_result(
                        requested_conversation_url=expected_conversation_url,
                        observed_conversation_url=(page.url or ""),
                        started_at=started_at,
                        run_id=run_id,
                    )
                    if thread_guard is not None:
                        thread_guard["sidebar_debug"] = sidebar_debug
                        if artifacts:
                            thread_guard["debug_artifacts"] = artifacts
                        result = thread_guard

                    event: dict[str, Any] = {
                        "tool": "gemini_web_wait",
                        "status": result.get("status"),
                        "conversation_url": result.get("conversation_url"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": run_id,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "min_chars": min_chars,
                            "deep_research": bool(deep_research),
                            "conversation_url": conversation_url,
                            "deep_research": deep_research,
                        },
                    }
                    if _call_log_include_answers():
                        event["answer"] = result.get("answer")
                    else:
                        event["answer_chars"] = len((result.get("answer") or "").strip())
                    if artifacts:
                        event["debug_artifacts"] = artifacts
                    _maybe_append_call_log(event)
                    return result
                except Exception as exc:
                    err_text = _coerce_error_text(exc)
                    exc_type = type(exc).__name__
                    error_type = _gemini_classify_error_type(error_text=err_text, fallback=exc_type)
                    status = "blocked" if _looks_like_gemini_blocked_error(err_text) else "error"
                    result = {
                        "ok": False,
                        "answer": "",
                        "status": status,
                        "conversation_url": (page.url if page is not None else conversation_url),
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                        "sidebar_debug": sidebar_debug,
                        "error_type": error_type,
                        "exc_type": exc_type,
                        "error": err_text,
                    }
                    event: dict[str, Any] = {
                        "tool": "gemini_web_wait",
                        "status": status,
                        "conversation_url": result.get("conversation_url"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": run_id,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "min_chars": min_chars,
                            "deep_research": bool(deep_research),
                            "conversation_url": conversation_url,
                            "deep_research": deep_research,
                        },
                        "error_type": error_type,
                        "exc_type": exc_type,
                        "error": err_text,
                    }
                    artifacts: dict[str, str] = {}
                    if page is not None:
                        artifacts = await _capture_debug_artifacts(page, label="gemini_web_wait_error")
                        if ctx and artifacts:
                            await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")
                    if artifacts:
                        event["debug_artifacts"] = artifacts
                    _maybe_append_call_log(event)
                    if artifacts:
                        result["debug_artifacts"] = artifacts
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
