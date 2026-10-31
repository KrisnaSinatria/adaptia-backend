"""Satu-satunya pintu ke model. Setiap panggilan punya batas waktu dan tercatat di log.

Pemanggil wajib menyiapkan cadangan: fungsi di sini mengembalikan None bila model tidak
dipakai (mode skrip), lewat batas waktu, atau galat.
"""

import json
import logging
import time
from functools import lru_cache

import anthropic

from app.config import get_settings

log = logging.getLogger("adaptia.llm")


@lru_cache
def _client() -> anthropic.Anthropic:
    s = get_settings()
    # Tanpa retry otomatis: retry memperpanjang tunggu melewati batas waktu dan cadangan jadi telat.
    return anthropic.Anthropic(api_key=s.anthropic_api_key, max_retries=0, timeout=s.llm_timeout_seconds)


def _call(kind: str, prompt: str, max_tokens: int, output_config: dict | None = None) -> str | None:
    s = get_settings()
    if not s.llm_live:
        log.info("llm kind=%s skipped mode=%s", kind, s.llm_mode)
        return None
    start = time.monotonic()
    try:
        kwargs = {"output_config": output_config} if output_config else {}
        msg = _client().messages.create(
            model=s.llm_model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            timeout=s.llm_timeout_seconds,
            **kwargs,
        )
        text = next((b.text for b in msg.content if b.type == "text"), None)
        log.info("llm kind=%s ok latency_ms=%d", kind, (time.monotonic() - start) * 1000)
        return text
    except anthropic.APITimeoutError:
        log.warning("llm kind=%s timeout latency_ms=%d", kind, (time.monotonic() - start) * 1000)
    except anthropic.APIError as exc:
        log.warning("llm kind=%s error=%s latency_ms=%d", kind, type(exc).__name__, (time.monotonic() - start) * 1000)
    return None


def complete_text(kind: str, prompt: str, max_tokens: int = 200) -> str | None:
    return _call(kind, prompt, max_tokens)


def complete_json(kind: str, prompt: str, schema: dict, max_tokens: int = 2000) -> dict | None:
    """Keluaran terstruktur. None bila model tidak dipakai, gagal, atau JSON rusak."""
    text = _call(kind, prompt, max_tokens, {"format": {"type": "json_schema", "schema": schema}})
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning("llm kind=%s invalid_json", kind)
        return None


def fence(text: str) -> str:
    """Bungkus teks mahasiswa sebagai data. Pembatas di dalam teks dibuang supaya tidak bisa ditutup dari dalam."""
    return "<<<" + text.replace("<<<", "").replace(">>>", "") + ">>>"
