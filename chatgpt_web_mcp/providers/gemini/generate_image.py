from __future__ import annotations

from chatgpt_web_mcp.providers.gemini.core import *  # noqa: F403

async def gemini_web_generate_image(
    prompt: str,
    idempotency_key: str,
    conversation_url: str | None = None,
    timeout_seconds: int = 600,
    drive_files: str | list[str] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    tool_name = "gemini_web_generate_image"
    resolved_drive_files = _gemini_resolve_drive_files(drive_files)
    run_id = _run_id(tool=tool_name, idempotency_key=idempotency_key)
    request_payload: dict[str, Any] = {"tool": tool_name, "prompt": prompt}
    if resolved_drive_files:
        request_payload["drive_files"] = resolved_drive_files
    idem = _IdempotencyContext(
        namespace=_idempotency_namespace(ctx),
        tool=tool_name,
        key=_normalize_idempotency_key(idempotency_key),
        request_hash=_hash_request(request_payload),
    )
    should_execute, existing = await _idempotency_begin(idem)
    resume_only = False
    if not should_execute:
        existing_record = existing or {}
        existing_status = str(existing_record.get("status") or "in_progress").strip()
        existing_sent = bool(existing_record.get("sent"))
        existing_url = str(existing_record.get("conversation_url") or "").strip()
        existing_result = existing_record.get("result")
        if not existing_url and isinstance(existing_result, dict):
            existing_url = str(existing_result.get("conversation_url") or "").strip()

        if existing_sent and existing_status.strip().lower() == "in_progress" and existing_url:
            resume_only = True
            conversation_url = existing_url
        else:
            if isinstance(existing_result, dict):
                cached = dict(existing_result)
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
            ok = existing_status.lower() not in {"error", "blocked", "cooldown"}
            return {
                "ok": ok,
                "status": existing_status,
                "images": [],
                "conversation_url": str(existing_url or conversation_url or ""),
                "elapsed_seconds": 0.0,
                "run_id": run_id,
                "replayed": True,
                "error_type": None,
                "error": (str(existing_record.get("error") or "").strip() or None),
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
                "images": [],
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
                sent = bool(resume_only)
                effective_conversation_url = str(conversation_url or "").strip()
                try:
                    browser, context, page, close_context = await _open_gemini_page(
                        p, cfg, conversation_url=conversation_url, ctx=ctx
                    )

                    if (conversation_url is None) and (not resume_only):
                        await _gemini_click_new_chat(page)

                    if not resume_only:
                        await _gemini_find_prompt_box(page)
                        await _human_pause(page)
                        if resolved_drive_files:
                            await _ctx_info(ctx, f"Gemini: attaching {len(resolved_drive_files)} Drive file(s)…")
                            for q in resolved_drive_files:
                                await _gemini_attach_drive_file(page, query=q, ctx=ctx)
                                await _human_pause(page)
                        await _gemini_set_tool_checked(
                            page,
                            label_re=re.compile(r"(生成图片|生成图像|制作图片|Generate image|Create image)", re.I),
                            checked=True,
                            ctx=ctx,
                            fail_open=True,
                        )
                        placeholder_re = re.compile(r"(描述你的图片|Describe your image)", re.I)
                        try:
                            await _gemini_wait_for_prompt_placeholder(page, placeholder_re=placeholder_re)
                        except Exception:
                            await _human_pause(page)
                            await _gemini_set_tool_checked(
                                page,
                                label_re=re.compile(r"(生成图片|生成图像|制作图片|Generate image|Create image)", re.I),
                                checked=True,
                                ctx=ctx,
                                fail_open=True,
                            )
                            try:
                                await _gemini_wait_for_prompt_placeholder(page, placeholder_re=placeholder_re)
                            except Exception:
                                pass # ignore strict placeholder mismatch if fail_open=True

                        prompt_box = await _gemini_find_prompt_box(page)
                        prompt_box = await _gemini_focus_prompt_box(page, prompt_box)
                        await _type_question(prompt_box, prompt)
                        await _human_pause(page)
                        await _gemini_click_send(page, prompt_box, ctx=ctx)
                        sent = True
                        try:
                            await _idempotency_update(idem, sent=True, conversation_url=(page.url or "").strip() or conversation_url)
                        except Exception:
                            pass

                    await _ctx_info(ctx, "Waiting for Gemini image…")

                    images = await _wait_for_generated_images(
                        page,
                        started_at=started_at,
                        timeout_seconds=timeout_seconds,
                        min_area=_gemini_image_min_area(),
                    )

                    out_dir = _gemini_output_dir()
                    out_dir.mkdir(parents=True, exist_ok=True)
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    slug = _slugify(prompt[:80])

                    saved: list[dict[str, Any]] = []
                    for img in images:
                        src = str(img.get("src") or "")
                        if not src:
                            continue
                        raw, mime_type = await _gemini_fetch_bytes(page, context, src)
                        ext = {
                            "image/png": "png",
                            "image/jpeg": "jpg",
                            "image/jpg": "jpg",
                            "image/webp": "webp",
                        }.get(mime_type.lower(), "bin")
                        path = out_dir / f"{ts}_{slug}_{random.randint(1000, 9999)}.{ext}"
                        path.write_bytes(raw)
                        saved.append(
                            {
                                "path": str(path),
                                "mime_type": mime_type,
                                "bytes": len(raw),
                                "width": img.get("width"),
                                "height": img.get("height"),
                            }
                        )

                    result = {
                        "ok": True,
                        "status": "completed",
                        "images": saved,
                        "conversation_url": page.url,
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                        "resumed": bool(resume_only),
                        "error_type": None,
                        "error": None,
                    }
                    try:
                        await _idempotency_update(
                            idem,
                            status="completed",
                            conversation_url=str(result.get("conversation_url") or ""),
                            result=result,
                        )
                    except Exception:
                        pass
                    event: dict[str, Any] = {
                        "tool": "gemini_web_generate_image",
                        "conversation_url": result.get("conversation_url"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "run_id": result.get("run_id") or run_id,
                        "idempotency_key": idem.key,
                        "idempotency_namespace": idem.namespace,
                        "params": {
                            "timeout_seconds": timeout_seconds,
                            "conversation_url": conversation_url,
                        },
                        "images_count": len(saved),
                    }
                    if _call_log_include_prompts():
                        event["prompt"] = prompt
                    _maybe_append_call_log(event)
                    return result
                except Exception as exc:
                    err_text = _coerce_error_text(exc)
                    exc_type = type(exc).__name__
                    error_type = _gemini_classify_error_type(error_text=err_text, fallback=exc_type)
                    status = (
                        "in_progress"
                        if sent
                        else ("blocked" if _looks_like_gemini_blocked_error(err_text) else "error")
                    )
                    artifacts: dict[str, str] = {}
                    if page is not None:
                        artifacts = await _capture_debug_artifacts(page, label="gemini_web_generate_image_error")
                        if ctx and artifacts:
                            await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")

                    result = {
                        "ok": False,
                        "status": status,
                        "images": [],
                        "conversation_url": (page.url if page is not None else conversation_url),
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                        "error_type": error_type,
                        "exc_type": exc_type,
                        "error": err_text,
                        "debug_artifacts": artifacts,
                    }
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
                        "tool": "gemini_web_generate_image",
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
                        event["prompt"] = prompt
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

