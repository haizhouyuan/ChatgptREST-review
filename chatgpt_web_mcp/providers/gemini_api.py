from __future__ import annotations

import asyncio
import base64
import os
import random
import time
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import Context


from chatgpt_web_mcp.providers.gemini_common import _gemini_output_dir

from chatgpt_web_mcp.runtime.call_log import (
    _call_log_include_answers,
    _call_log_include_prompts,
    _maybe_append_call_log,
)
from chatgpt_web_mcp.runtime.util import _ctx_info, _coerce_error_text, _slugify

from chatgpt_web_mcp.idempotency import _run_id


def _gemini_api_key() -> str:
    raw = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not raw:
        raise RuntimeError("Missing GEMINI_API_KEY (or GOOGLE_API_KEY).")
    return raw


def _gemini_api_base() -> str:
    return (os.environ.get("GEMINI_API_BASE") or "https://generativelanguage.googleapis.com").rstrip("/")


def _gemini_pro_thinking_model() -> str:
    return (os.environ.get("GEMINI_PRO_THINKING_MODEL") or "gemini-2.5-pro").strip()


def _gemini_image_model() -> str:
    return (os.environ.get("GEMINI_IMAGE_MODEL") or "gemini-2.5-flash-image").strip()


def _gemini_deep_research_agent() -> str:
    return (os.environ.get("GEMINI_DEEP_RESEARCH_AGENT") or "deep-research-pro-preview-12-2025").strip()



async def _gemini_request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    headers = {"x-goog-api-key": _gemini_api_key()}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await client.request(method, url, headers=headers, json=payload)
    if resp.status_code >= 400:
        text = (resp.text or "").strip()
        if len(text) > 1000:
            text = text[:1000] + "…"
        raise RuntimeError(f"Gemini API error {resp.status_code}: {text}")
    try:
        data = resp.json()
    except Exception:
        text = (resp.text or "").strip()
        if len(text) > 1000:
            text = text[:1000] + "…"
        raise RuntimeError(f"Gemini API returned non-JSON response: {text}")
    if not isinstance(data, dict):
        raise RuntimeError(f"Gemini API returned unexpected JSON type: {type(data).__name__}")
    return data


def _gemini_extract_text_from_generate_content(data: dict[str, Any]) -> str:
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""
    candidate = candidates[0] if isinstance(candidates[0], dict) else None
    if not candidate:
        return ""
    content = candidate.get("content")
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""
    texts: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
    return "\n".join(texts).strip()


def _gemini_extract_inline_images_from_generate_content(data: dict[str, Any]) -> list[dict[str, str]]:
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return []
    candidate = candidates[0] if isinstance(candidates[0], dict) else None
    if not candidate:
        return []
    content = candidate.get("content")
    if not isinstance(content, dict):
        return []
    parts = content.get("parts")
    if not isinstance(parts, list):
        return []

    images: list[dict[str, str]] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        inline = part.get("inlineData") or part.get("inline_data") or part.get("inline_data".upper())
        if not isinstance(inline, dict):
            continue
        mime_type = inline.get("mimeType") or inline.get("mime_type") or "application/octet-stream"
        data_b64 = inline.get("data")
        if not isinstance(data_b64, str) or not data_b64.strip():
            continue
        images.append({"mime_type": str(mime_type), "data_base64": data_b64})
    return images


def _gemini_extract_deep_research_text(interaction: dict[str, Any]) -> str:
    outputs = interaction.get("outputs")
    if isinstance(outputs, list) and outputs:
        for item in reversed(outputs):
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
    text = interaction.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return ""







async def gemini_ask_pro_thinking(
    question: str,
    model: str | None = None,
    thinking_budget: int = -1,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    timeout_seconds: int = 300,
    ctx: Context | None = None,
) -> dict[str, Any]:
    started_at = time.time()
    run_id = _run_id(tool="gemini_ask_pro_thinking")
    chosen_model = (model or _gemini_pro_thinking_model()).strip()
    await _ctx_info(ctx, f"Gemini generateContent → {chosen_model} (thinking_budget={thinking_budget})")

    generation_config: dict[str, Any] = {"thinkingConfig": {"thinkingBudget": thinking_budget}}
    if temperature is not None:
        generation_config["temperature"] = temperature
    if max_output_tokens is not None:
        generation_config["maxOutputTokens"] = max_output_tokens

    payload: dict[str, Any] = {
        "contents": [{"parts": [{"text": question}]}],
        "generationConfig": generation_config,
    }

    url = f"{_gemini_api_base()}/v1beta/models/{chosen_model}:generateContent"
    try:
        data = await _gemini_request_json("POST", url, payload=payload, timeout_seconds=timeout_seconds)

        answer = _gemini_extract_text_from_generate_content(data)
        usage = data.get("usageMetadata") if isinstance(data.get("usageMetadata"), dict) else None

        result = {
            "ok": True,
            "status": "completed",
            "answer": answer,
            "model": chosen_model,
            "usage": usage,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": None,
            "error": None,
        }
        event: dict[str, Any] = {
            "tool": "gemini_ask_pro_thinking",
            "status": result.get("status"),
            "conversation_url": None,
            "elapsed_seconds": result.get("elapsed_seconds"),
            "run_id": run_id,
            "params": {
                "timeout_seconds": timeout_seconds,
                "model": chosen_model,
                "thinking_budget": thinking_budget,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
            },
            "usage": usage,
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
        result = {
            "ok": False,
            "status": "error",
            "answer": "",
            "model": chosen_model,
            "usage": None,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": type(exc).__name__,
            "error": err_text,
        }
        event: dict[str, Any] = {
            "tool": "gemini_ask_pro_thinking",
            "status": result.get("status"),
            "conversation_url": None,
            "elapsed_seconds": result.get("elapsed_seconds"),
            "run_id": run_id,
            "params": {
                "timeout_seconds": timeout_seconds,
                "model": chosen_model,
                "thinking_budget": thinking_budget,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
            },
            "error_type": type(exc).__name__,
            "error": err_text,
        }
        if _call_log_include_prompts():
            event["question"] = question
        _maybe_append_call_log(event)
        return result


async def gemini_generate_image(
    prompt: str,
    model: str | None = None,
    timeout_seconds: int = 600,
    ctx: Context | None = None,
) -> dict[str, Any]:
    started_at = time.time()
    run_id = _run_id(tool="gemini_generate_image")
    chosen_model = (model or _gemini_image_model()).strip()
    await _ctx_info(ctx, f"Gemini generateContent → {chosen_model} (image)")

    payload: dict[str, Any] = {"contents": [{"parts": [{"text": prompt}]}]}
    url = f"{_gemini_api_base()}/v1beta/models/{chosen_model}:generateContent"
    try:
        data = await _gemini_request_json("POST", url, payload=payload, timeout_seconds=timeout_seconds)

        out_dir = _gemini_output_dir()
        out_dir.mkdir(parents=True, exist_ok=True)

        images = _gemini_extract_inline_images_from_generate_content(data)
        saved: list[dict[str, Any]] = []
        ts = time.strftime("%Y%m%d_%H%M%S")
        slug = _slugify(prompt[:80])
        for item in images:
            mime_type = str(item.get("mime_type") or "application/octet-stream")
            b64 = str(item.get("data_base64") or "")
            if not b64.strip():
                continue

            ext = {
                "image/png": "png",
                "image/jpeg": "jpg",
                "image/jpg": "jpg",
                "image/webp": "webp",
            }.get(mime_type.lower(), "bin")

            path = out_dir / f"{ts}_{slug}_{random.randint(1000, 9999)}.{ext}"
            raw = base64.b64decode(b64)
            path.write_bytes(raw)
            saved.append({"path": str(path), "mime_type": mime_type, "bytes": len(raw)})

        text = _gemini_extract_text_from_generate_content(data)
        usage = data.get("usageMetadata") if isinstance(data.get("usageMetadata"), dict) else None

        result = {
            "ok": True,
            "status": "completed",
            "images": saved,
            "text": text,
            "model": chosen_model,
            "usage": usage,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": None,
            "error": None,
        }
        event: dict[str, Any] = {
            "tool": "gemini_generate_image",
            "status": result.get("status"),
            "conversation_url": None,
            "elapsed_seconds": result.get("elapsed_seconds"),
            "run_id": run_id,
            "params": {
                "timeout_seconds": timeout_seconds,
                "model": chosen_model,
            },
            "images_count": len(saved),
            "usage": usage,
        }
        if _call_log_include_prompts():
            event["prompt"] = prompt
        _maybe_append_call_log(event)
        return result
    except Exception as exc:
        err_text = _coerce_error_text(exc)
        result = {
            "ok": False,
            "status": "error",
            "images": [],
            "text": "",
            "model": chosen_model,
            "usage": None,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": type(exc).__name__,
            "error": err_text,
        }
        event: dict[str, Any] = {
            "tool": "gemini_generate_image",
            "status": result.get("status"),
            "conversation_url": None,
            "elapsed_seconds": result.get("elapsed_seconds"),
            "run_id": run_id,
            "params": {
                "timeout_seconds": timeout_seconds,
                "model": chosen_model,
            },
            "error_type": type(exc).__name__,
            "error": err_text,
        }
        if _call_log_include_prompts():
            event["prompt"] = prompt
        _maybe_append_call_log(event)
        return result


async def gemini_deep_research(
    question: str | None = None,
    interaction_id: str | None = None,
    agent: str | None = None,
    timeout_seconds: int = 7200,
    poll_interval_seconds: int = 10,
    ctx: Context | None = None,
) -> dict[str, Any]:
    started_at = time.time()
    run_id = _run_id(tool="gemini_deep_research")
    if bool(question) == bool(interaction_id):
        err = "Provide exactly one of: question, interaction_id"
        return {
            "ok": False,
            "status": "error",
            "interaction_id": interaction_id,
            "agent": (agent or _gemini_deep_research_agent()).strip(),
            "report_text": "",
            "error": err,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": "ValueError",
        }

    chosen_agent = (agent or _gemini_deep_research_agent()).strip()
    base = _gemini_api_base()

    status: str = "in_progress"
    error: str | None = None
    report_text: str = ""

    try:
        if question:
            await _ctx_info(ctx, f"Gemini deep research start → agent={chosen_agent}")
            create = await _gemini_request_json(
                "POST",
                f"{base}/v1beta/interactions",
                payload={"input": question, "agent": chosen_agent, "background": True},
                timeout_seconds=min(60, timeout_seconds),
            )
            interaction_id = str(create.get("id") or create.get("interactionId") or "").strip() or None
            status = str(create.get("status") or "in_progress")
            if interaction_id is None:
                raise RuntimeError(f"Gemini Deep Research did not return an interaction id: {create}")

        deadline = started_at + timeout_seconds
        while time.time() < deadline:
            await _ctx_info(ctx, f"Gemini deep research poll… ({interaction_id})")

            interaction = await _gemini_request_json(
                "GET",
                f"{base}/v1beta/interactions/{interaction_id}",
                payload=None,
                timeout_seconds=min(60, max(10, int(deadline - time.time()))),
            )
            status = str(interaction.get("status") or "in_progress")
            if status == "completed":
                report_text = _gemini_extract_deep_research_text(interaction)
                break
            if status == "failed":
                err = interaction.get("error")
                error = err if isinstance(err, str) else str(err) if err is not None else "unknown_error"
                break
            await asyncio.sleep(max(1, int(poll_interval_seconds)))
    except Exception as exc:
        err_text = _coerce_error_text(exc)
        result = {
            "ok": False,
            "status": "error",
            "interaction_id": interaction_id,
            "agent": chosen_agent,
            "report_text": report_text,
            "error": err_text,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": type(exc).__name__,
        }
        event: dict[str, Any] = {
            "tool": "gemini_deep_research",
            "status": result.get("status"),
            "interaction_id": interaction_id,
            "elapsed_seconds": result.get("elapsed_seconds"),
            "run_id": run_id,
            "params": {
                "timeout_seconds": timeout_seconds,
                "poll_interval_seconds": poll_interval_seconds,
                "agent": chosen_agent,
                "mode": "start" if question else "poll",
            },
            "error_type": type(exc).__name__,
            "error": err_text,
        }
        if _call_log_include_prompts() and question:
            event["question"] = question
        _maybe_append_call_log(event)
        return result

    ok = (status != "failed") and (error is None)
    error_type = None
    if status == "failed":
        error_type = "GeminiDeepResearchFailed"
    result = {
        "ok": ok,
        "status": status,
        "interaction_id": interaction_id,
        "agent": chosen_agent,
        "report_text": report_text,
        "error": error,
        "elapsed_seconds": round(time.time() - started_at, 3),
        "run_id": run_id,
        "error_type": error_type,
    }
    event: dict[str, Any] = {
        "tool": "gemini_deep_research",
        "status": result.get("status"),
        "interaction_id": interaction_id,
        "elapsed_seconds": result.get("elapsed_seconds"),
        "run_id": run_id,
        "params": {
            "timeout_seconds": timeout_seconds,
            "poll_interval_seconds": poll_interval_seconds,
            "agent": chosen_agent,
            "mode": "start" if question else "poll",
        },
    }
    if _call_log_include_prompts() and question:
        event["question"] = question
    if _call_log_include_answers():
        event["report_text"] = report_text
    else:
        event["report_chars"] = len((report_text or "").strip())
    if error:
        event["error"] = error
    _maybe_append_call_log(event)
    return result
