"""Batas laju per token demo (atau per IP bila tanpa token) supaya kuota LLM tidak habis."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.config import get_settings

DEFAULT_LIMIT = "120/minute"
LLM_LIMIT = "20/minute"       # giliran Boby dan submit memanggil LLM
RESET_LIMIT = "5/minute"


def _key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    return auth[7:] if auth.startswith("Bearer ") else get_remote_address(request)


limiter = Limiter(key_func=_key, default_limits=[DEFAULT_LIMIT], enabled=get_settings().rate_limit_enabled)
