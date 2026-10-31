from fastapi import APIRouter, Depends, Request

from app.auth import require_lecturer
from app.db import get_db
from app.errors import ApiError
from app.limiter import RESET_LIMIT, limiter
from app.seed import reset_database

router = APIRouter(tags=["demo"])


@router.post("/demo/reset", summary="Kembalikan data demo ke kondisi awal seed")
@limiter.limit(RESET_LIMIT)
def demo_reset(request: Request, _: dict = Depends(require_lecturer), db=Depends(get_db)):
    try:
        counts = reset_database(db)
    except FileNotFoundError as exc:
        raise ApiError(503, "seed_missing", str(exc))
    return {"ok": True, "counts": counts}
