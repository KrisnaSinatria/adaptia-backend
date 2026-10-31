from fastapi import APIRouter

from app.config import get_settings
from app.db import get_db

router = APIRouter(tags=["demo"])


@router.get("/health")
def health():
    # Sengaja tanpa Depends(get_db): health harus tetap menjawab saat database belum dikonfigurasi.
    try:
        get_db().table("classes").select("id").limit(1).execute()
        db = "ok"
    except Exception:
        db = "error"
    s = get_settings()
    return {"ok": db == "ok", "db": db, "llmMode": "live" if s.llm_live else "scripted"}
