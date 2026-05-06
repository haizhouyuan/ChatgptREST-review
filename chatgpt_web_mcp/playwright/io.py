from __future__ import annotations

import base64
from typing import Any


_BROWSER_FETCH_DATA_URL_JS = """
async (url) => {
  const resp = await fetch(url, { credentials: 'include' });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }
  const blob = await resp.blob();
  const dataUrl = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
  const s = String(dataUrl);
  const idx = s.indexOf(',');
  const meta = idx >= 0 ? s.slice(0, idx) : '';
  const b64 = idx >= 0 ? s.slice(idx + 1) : s;
  const m = meta.match(/^data:([^;]+);base64$/);
  const mimeType = (m && m[1]) ? m[1] : (blob.type || 'application/octet-stream');
  return { mimeType, dataBase64: b64, bytes: blob.size };
}
"""


async def _fetch_bytes_via_browser(page: Any, url: str) -> tuple[bytes, str]:
    result = await page.evaluate(_BROWSER_FETCH_DATA_URL_JS, url)
    if not isinstance(result, dict):
        raise RuntimeError(f"Unexpected browser fetch result type: {type(result).__name__}")
    mime_type = str(result.get("mimeType") or "application/octet-stream")
    data_base64 = str(result.get("dataBase64") or "")
    if not data_base64.strip():
        raise RuntimeError("Browser fetch did not return dataBase64.")
    raw = base64.b64decode(data_base64)
    return raw, mime_type
