"""Mode demo: satu akun per peran, tanpa kata sandi. Ini BUKAN autentikasi.

Token JWT hanya membawa peran dan id pengguna demo supaya endpoint bisa membedakan
mahasiswa dari dosen dan membatasi laju per token.
"""

from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt
from fastapi import Depends, Header

from app.config import get_settings
from app.errors import ApiError
from app.seed import seed_config

TOKEN_TTL = timedelta(hours=12)


@lru_cache
def demo_users() -> dict[str, dict]:
    seed = seed_config()
    me, lecturer = seed["me"], seed["lecturer"]
    return {
        "mahasiswa": {"id": me["id"], "name": me["name"], "nim": me["nim"], "initials": me["initials"],
                      "role": "mahasiswa"},
        "dosen": {"id": "rina", "name": lecturer["name"], "initials": lecturer["initials"],
                  "title": lecturer["role"], "role": "dosen"},
    }


def _secret() -> str:
    secret = get_settings().jwt_secret
    if not secret:
        raise ApiError(503, "auth_unconfigured", "JWT_SECRET belum diisi.")
    return secret


def create_token(user: dict) -> str:
    now = datetime.now(timezone.utc)
    claims = {"sub": user["id"], "role": user["role"], "iat": now, "exp": now + TOKEN_TTL}
    return jwt.encode(claims, _secret(), algorithm="HS256")


def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiError(401, "unauthorized", "Masuk dulu lewat mode demo.")
    try:
        claims = jwt.decode(authorization[7:], _secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ApiError(401, "token_expired", "Sesi demo kedaluwarsa. Masuk lagi.")
    except jwt.InvalidTokenError:
        raise ApiError(401, "unauthorized", "Token tidak valid.")
    user = demo_users().get(claims.get("role"))
    if not user or user["id"] != claims.get("sub"):
        raise ApiError(401, "unauthorized", "Token tidak valid.")
    return user


def require_student(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "mahasiswa":
        raise ApiError(403, "forbidden", "Hanya untuk mahasiswa.")
    return user


def require_lecturer(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "dosen":
        raise ApiError(403, "forbidden", "Hanya untuk dosen.")
    return user
