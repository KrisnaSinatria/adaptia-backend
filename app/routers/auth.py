from typing import Literal

from fastapi import APIRouter

from app.auth import create_token, demo_users
from app.models import CamelModel

router = APIRouter(tags=["mode demo"])


class DemoLogin(CamelModel):
    role: Literal["mahasiswa", "dosen"]


@router.post("/auth/demo", summary="Masuk mode demo (bukan autentikasi)")
def demo_login(body: DemoLogin):
    user = demo_users()[body.role]
    return {"token": create_token(user), "user": user}
