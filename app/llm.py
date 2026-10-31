"""Satu-satunya pintu ke model (Groq). Setiap panggilan punya batas waktu dan tercatat di log.

Pemanggil wajib menyiapkan cadangan: fungsi di sini mengembalikan None bila model tidak
dipakai (mode skrip), lewat batas waktu, atau galat.
"""

import json
import logging
import time
from functools import lru_cache

import groq

from app.config import get_settings

log = logging.getLogger("adaptia.llm")


@lru_cache
def _client() -> groq.Groq:
    s = get_settings()
    # Tanpa retry otomatis: retry memperpanjang tunggu melewati batas waktu dan cadangan jadi telat.
    return groq.Groq(api_key=s.groq_api_key, max_retries=0, timeout=s.llm_timeout_seconds)


def _call(kind: str, prompt: str, max_tokens: int, temperature: float, model: str,
          response_format: dict | None = None) -> str | None:
    s = get_settings()
    if not s.llm_live:
        log.info("llm kind=%s skipped mode=%s", kind, s.llm_mode)
        return None
    start = time.monotonic()
    kwargs = {}
    if response_format:
        kwargs["response_format"] = response_format
    if s.llm_reasoning_effort:
        # Model penalaran (gpt-oss): token penalaran ikut dihitung, jadi upaya rendah menjaga latensi.
        kwargs["reasoning_effort"] = s.llm_reasoning_effort
        kwargs["include_reasoning"] = False
    try:
        res = _client().chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=max_tokens,
            temperature=temperature,
            timeout=s.llm_timeout_seconds,
            **kwargs,
        )
        text = res.choices[0].message.content if res.choices else None
        log.info("llm kind=%s ok latency_ms=%d", kind, (time.monotonic() - start) * 1000)
        return text
    except groq.APITimeoutError:
        log.warning("llm kind=%s timeout latency_ms=%d", kind, (time.monotonic() - start) * 1000)
    except groq.APIError as exc:
        # Hanya kode galat; isi galat (mis. failed_generation) bisa memuat tulisan mahasiswa.
        body = getattr(exc, "body", None)
        code = (body.get("error") or {}).get("code") if isinstance(body, dict) else None
        log.warning("llm kind=%s model=%s error=%s code=%s latency_ms=%d", kind, model, type(exc).__name__, code,
                    (time.monotonic() - start) * 1000)
    return None


# Batas token kecil: Groq memesan max_completion_tokens dari kuota token per menit.
def complete_text(kind: str, prompt: str, max_tokens: int = 400) -> str | None:
    return _call(kind, prompt, max_tokens, temperature=0.7, model=get_settings().llm_model)


def complete_json(kind: str, prompt: str, schema: dict, max_tokens: int = 1600, model: str | None = None) -> dict | None:
    """Keluaran terstruktur (strict). None bila model tidak dipakai, gagal, atau JSON rusak."""
    fmt = {"type": "json_schema", "json_schema": {"name": kind, "strict": True, "schema": schema}}
    model = model or get_settings().analyst_model
    text = _call(kind, prompt, max_tokens, temperature=0.0, model=model, response_format=fmt)
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
