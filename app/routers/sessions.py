from fastapi import APIRouter

from app.db import get_db
from app.errors import ApiError
from app.models import SessionDetail

router = APIRouter(tags=["sesi"])


@router.get("/sessions/{session_id}", response_model=SessionDetail, response_model_by_alias=True)
def get_session(session_id: str):
    db = get_db()
    rows = db.table("sessions").select("*").eq("id", session_id).limit(1).execute().data
    if not rows:
        raise ApiError(404, "session_not_found", f"Sesi {session_id} tidak ditemukan.")
    indicators = db.table("indicators").select("*").eq("session_id", session_id).order("position").execute().data
    return SessionDetail(**rows[0], indicators=indicators)
