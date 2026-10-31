"""Alur dosen: roster -> kartu bukti -> terima/koreksi/tolak per temuan -> finalisasi."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app import repo
from app.auth import current_user, require_lecturer
from app.db import get_db
from app.errors import ApiError
from app.logic import (attempt_statuses, pending_of, recommend_activity, roster_row, roster_summary, score_of,
                       transcript_of)
from app.models import DecisionIn, FinalizeIn
from app.seed import seed_config
from app.serialize import attempt_out

router = APIRouter(tags=["dosen"])


@router.get("/sessions/{session_id}/roster")
def roster(session_id: str, _: dict = Depends(require_lecturer), db=Depends(get_db)):
    session = repo.get_session(db, session_id)
    students = repo.list_students(db, class_id=session["class_id"])
    latest = repo.latest_by_student(repo.list_attempts(db, session_id=session_id))
    rows = [{**roster_row(s, latest.get(s["id"])), "attemptId": (latest.get(s["id"]) or {}).get("id"),
             "prev": s.get("prev")}
            for s in students]
    return {"summary": roster_summary(rows), "rows": rows}


@router.get("/attempts/{attempt_id}")
def attempt_detail(attempt_id: str, user: dict = Depends(current_user), db=Depends(get_db)):
    """Bukti lengkap untuk dosen. Mahasiswa hanya boleh membuka percobaannya sendiri."""
    attempt = repo.get_attempt(db, attempt_id)
    if user["role"] == "mahasiswa" and attempt["student_id"] != user["id"]:
        raise ApiError(403, "forbidden", "Percobaan ini milik mahasiswa lain.")
    student = repo.get_student(db, attempt["student_id"])
    indicators = repo.get_indicators(db, attempt["session_id"])
    statuses = attempt_statuses(attempt)
    recommendation = (
        recommend_activity(statuses, indicators, seed_config()["need"], student.get("archetype"))
        if attempt["findings"] else None
    )
    return {
        **attempt_out(attempt),
        "transcript": transcript_of(attempt),
        "student": {"id": student["id"], "name": student["name"], "nim": student["nim"]},
        "indicators": [{k: i[k] for k in ("id", "name", "concept", "weight")} for i in indicators],
        "recommendation": recommendation,
    }


def _reviewable(db, attempt_id: str) -> dict:
    attempt = repo.get_attempt(db, attempt_id)
    if attempt["reviewed_at"] is not None:
        raise ApiError(409, "attempt_finalized", "Tinjauan sudah difinalkan; skor terkunci.")
    if attempt["state"] != "perlu" or not attempt["findings"]:
        raise ApiError(409, "nothing_to_review", "Percobaan ini tidak punya temuan yang menunggu tinjauan.")
    return attempt


@router.post("/attempts/{attempt_id}/decisions")
def decide(attempt_id: str, body: DecisionIn, _: dict = Depends(require_lecturer), db=Depends(get_db)):
    attempt = _reviewable(db, attempt_id)
    if body.indicator not in {f["indicator"] for f in attempt["findings"]}:
        raise ApiError(422, "unknown_indicator", f"Tidak ada temuan untuk indikator {body.indicator}.")
    if body.decision == "correct" and body.status is None:
        raise ApiError(422, "status_required", "Koreksi membutuhkan status pengganti.")

    decisions = {**attempt["decisions"], body.indicator: body.decision}
    corrections = {k: v for k, v in attempt["corrections"].items() if k != body.indicator}
    if body.decision == "correct":
        corrections[body.indicator] = body.status
    attempt = {**attempt, "decisions": decisions, "corrections": corrections}
    score = score_of(attempt_statuses(attempt), repo.get_indicators(db, attempt["session_id"]))
    repo.update_attempt(db, attempt_id, {"decisions": decisions, "corrections": corrections, "score": score})
    return {"score": score, "decisions": decisions, "corrections": corrections, "pending": pending_of(attempt)}


@router.post("/attempts/{attempt_id}/finalize")
def finalize(attempt_id: str, body: FinalizeIn, _: dict = Depends(require_lecturer), db=Depends(get_db)):
    attempt = _reviewable(db, attempt_id)
    waiting = pending_of(attempt)
    if waiting:
        # AI tidak pernah memberi nilai final: setiap temuan harus diputuskan dosen dulu.
        raise ApiError(409, "findings_pending", f"Masih ada {waiting} temuan yang belum diputuskan.")
    score = score_of(attempt_statuses(attempt), repo.get_indicators(db, attempt["session_id"]))
    reviewed_at = datetime.now(timezone.utc).isoformat()
    repo.update_attempt(db, attempt_id, {"note": body.note, "score": score, "state": "selesai",
                                         "reviewed_at": reviewed_at})
    return {"ok": True, "score": score, "reviewedAt": reviewed_at}
