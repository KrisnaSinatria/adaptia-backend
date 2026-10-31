from fastapi import APIRouter, Depends

from app import repo
from app.auth import current_user
from app.db import get_db
from app.models import SessionDetail

router = APIRouter(tags=["sesi"])


@router.get("/sessions/{session_id}", response_model=SessionDetail, response_model_by_alias=True)
def get_session(session_id: str, _: dict = Depends(current_user), db=Depends(get_db)):
    session = repo.get_session(db, session_id)
    return SessionDetail(**session, indicators=repo.get_indicators(db, session_id))
