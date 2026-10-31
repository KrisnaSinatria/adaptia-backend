from fastapi import APIRouter

from app.config import get_settings
from app.db import get_db

router = APIRouter(tags=["demo"])


@router.get("/health")
def health():
    try:
        get_db().table("classes").select("id").limit(1).execute()
        db = "ok"
    except Exception:
        db = "error"
    return {"ok": db == "ok", "db": db, "llmMode": get_settings().llm_mode}
