from fastapi import APIRouter

from app.db import get_db
from app.errors import ApiError
from app.seed import reset_database

router = APIRouter(tags=["demo"])


@router.post("/demo/reset")
def demo_reset():
    try:
        counts = reset_database(get_db())
    except FileNotFoundError as exc:
        raise ApiError(503, "seed_missing", str(exc))
    return {"ok": True, "counts": counts}
