"""Alur mahasiswa: praktik -> Reverse-Tutor dengan Boby -> penerapan -> kirim."""

from fastapi import APIRouter, Depends, Request

from app import analyst, boby, repo
from app.auth import current_user, require_student
from app.config import get_settings
from app.db import get_db
from app.errors import ApiError
from app.limiter import LLM_LIMIT, limiter
from app.logic import parse_due, score_of, shown_statuses, summary_of, transcript_of, trap_misconception
from app.models import ApplicationIn, BobyTurnIn, PracticeIn
from app.serialize import findings_out, session_out

router = APIRouter(tags=["mahasiswa"])


def _mode() -> str:
    return "live" if get_settings().llm_live else "scripted"


def _open_attempt(db, attempt_id: str, user: dict) -> dict:
    attempt = repo.get_attempt(db, attempt_id)
    if attempt["student_id"] != user["id"]:
        raise ApiError(403, "forbidden", "Percobaan ini milik mahasiswa lain.")
    if attempt["state"] != "berlangsung":
        raise ApiError(409, "attempt_submitted", "Percobaan sudah dikirim dan tidak bisa diubah.")
    return attempt


@router.get("/me/sessions")
def my_sessions(user: dict = Depends(current_user), db=Depends(get_db)):
    """Sesi berjalan dan riwayat. Mahasiswa melihat kelasnya beserta percobaannya; dosen melihat semua sesi."""
    if user["role"] == "mahasiswa":
        student = repo.get_student(db, user["id"])
        sessions = repo.list_sessions(db, [student["class_id"]])
        mine = repo.latest_by_session(repo.list_attempts(db, student_id=user["id"]))
    else:
        sessions, mine = repo.list_sessions(db), {}

    def item(s):
        a = mine.get(s["id"])
        attempt = {"id": a["id"], "state": a["state"], "score": a["score"]} if a else None
        return {**session_out(s), "attempt": attempt}

    by_date = sorted(sessions, key=lambda s: parse_due(s["due"]) or parse_due("1 Jan 1970"), reverse=True)
    return {
        "active": [item(s) for s in by_date if s["state"] == "berlangsung"],
        "history": [item(s) for s in by_date if s["state"] != "berlangsung"],
    }


@router.post("/sessions/{session_id}/attempts")
def start_attempt(session_id: str, user: dict = Depends(require_student), db=Depends(get_db)):
    session = repo.get_session(db, session_id)
    if session["state"] != "berlangsung":
        raise ApiError(409, "session_closed", "Sesi ini sudah ditutup.")
    for a in repo.list_attempts(db, session_id=session_id, student_id=user["id"]):
        if a["state"] == "berlangsung":
            return {"attemptId": a["id"], "resumed": True}  # lanjutkan percobaan yang belum dikirim
    row = repo.insert_attempt(db, {"session_id": session_id, "student_id": user["id"], "state": "berlangsung"})
    return {"attemptId": row["id"], "resumed": False}


@router.put("/attempts/{attempt_id}/practice")
def save_practice(attempt_id: str, body: PracticeIn, user: dict = Depends(require_student), db=Depends(get_db)):
    _open_attempt(db, attempt_id, user)
    repo.update_attempt(db, attempt_id, {"code": body.code, "explain": body.explain})
    return {"ok": True}


@router.post("/attempts/{attempt_id}/boby/turn")
@limiter.limit(LLM_LIMIT)
def boby_turn(request: Request, attempt_id: str, body: BobyTurnIn,
              user: dict = Depends(require_student), db=Depends(get_db)):
    attempt = _open_attempt(db, attempt_id, user)
    dialog = list(attempt["dialog"])
    asked = boby.boby_turns(dialog)

    if asked == 0:
        if not (attempt["code"].strip() or attempt["explain"].strip()):
            raise ApiError(409, "practice_missing", "Simpan kode dan penjelasan dulu sebelum mengajari Boby.")
    else:
        if dialog[-1]["who"] != "boby":
            raise ApiError(409, "turn_order", "Boby belum bertanya lagi.")
        if not (body.text and body.text.strip()):
            raise ApiError(422, "text_required", "Tulis balasan untuk Boby.")
        reply = {"who": "mhs", "text": body.text.strip(), "time": boby.now_hhmm()}
        if dialog[-1].get("trap"):
            if body.choice is None:
                raise ApiError(422, "choice_required", "Pilih Setuju atau Tidak setuju, lalu beri alasan.")
            reply["choice"] = body.choice
        dialog.append(reply)

    if asked == boby.TURNS:
        repo.update_attempt(db, attempt_id, {"dialog": dialog})
        return {"turn": None, "index": asked, "done": True, "usedFallback": False, "mode": _mode()}

    session = repo.get_session(db, attempt["session_id"])
    indicator_ids = [i["id"] for i in repo.get_indicators(db, session["id"])]
    traps = repo.traps_for(db, indicator_ids)
    index = asked + 1
    if index == boby.TRAP_TURN:
        used = {t.get("trapId") for a in repo.list_attempts(db, session_id=session["id"], student_id=user["id"])
                for t in a["dialog"] if t.get("trap")}
        turn, used_fallback = boby.trap_turn(boby.pick_trap(traps, used), session), False
    else:
        keys = [t["correction_key"] for t in traps if t.get("correction_key")]
        text, used_fallback = boby.ask(index, session, {**attempt, "dialog": dialog}, keys)
        turn = {"who": "boby", "text": text, "time": boby.now_hhmm()}
    dialog.append(turn)
    repo.update_attempt(db, attempt_id, {"dialog": dialog})
    return {"turn": turn, "index": index, "done": False, "usedFallback": used_fallback, "mode": _mode()}


@router.put("/attempts/{attempt_id}/application")
def save_application(attempt_id: str, body: ApplicationIn, user: dict = Depends(require_student), db=Depends(get_db)):
    _open_attempt(db, attempt_id, user)
    repo.update_attempt(db, attempt_id, {"answers": body.answers})
    return {"ok": True}


def _check_complete(attempt: dict, session: dict) -> None:
    if not (attempt["code"].strip() or attempt["explain"].strip()):
        raise ApiError(409, "practice_missing", "Kode dan penjelasan belum disimpan.")
    dialog = attempt["dialog"]
    if boby.boby_turns(dialog) < boby.TURNS or dialog[-1]["who"] != "mhs":
        raise ApiError(409, "dialog_incomplete", "Selesaikan tiga giliran dengan Boby dulu.")
    expected = len(session.get("penerapan") or [])
    answers = [a for a in attempt["answers"] if a.strip()]
    if len(answers) < max(expected, 1):
        raise ApiError(409, "answers_incomplete", "Jawab semua soal penerapan dulu.")


@router.post("/attempts/{attempt_id}/submit")
@limiter.limit(LLM_LIMIT)
def submit(request: Request, attempt_id: str, user: dict = Depends(require_student), db=Depends(get_db)):
    attempt = _open_attempt(db, attempt_id, user)
    session = repo.get_session(db, attempt["session_id"])
    _check_complete(attempt, session)
    indicators = repo.get_indicators(db, session["id"])
    if not indicators:
        raise ApiError(409, "rubric_missing", "Sesi ini belum punya rubrik.")

    transcript = transcript_of(attempt)
    trap_ids = [t["trapId"] for t in attempt["dialog"] if t.get("trapId")]
    trap = repo.get_trap(db, trap_ids[0]) if trap_ids else None
    # Kunci cache memakai transkrip berlabel supaya pilihan Setuju/Tidak setuju ikut dibedakan.
    key = analyst.cache_key(session["id"], analyst.labeled_transcript(attempt), indicators)
    findings, used = repo.get_cached_analysis(db, key), "llm"
    if findings is None:
        findings = analyst.llm_findings(attempt, indicators, trap, session)
        if findings is not None:
            repo.put_cached_analysis(db, key, findings)
    if findings is None:
        findings, used = analyst.keyword_findings(attempt, indicators, (trap or {}).get("indicator")), "fallback"

    statuses = shown_statuses(findings, transcript)
    traps_by_id = {t["id"]: t for t in repo.traps_for(db, [i["id"] for i in indicators])}
    updated = repo.update_attempt(db, attempt_id, {
        "state": "perlu",
        "findings": findings,
        "score": score_of(statuses, indicators),
        "summary": summary_of(statuses, indicators),
        "misconception": trap_misconception(attempt["dialog"], traps_by_id),
        "analyst": used,
    })
    return {
        "findings": findings_out(updated),
        "score": updated["score"],
        "summary": updated["summary"],
        "misconception": updated["misconception"],
        "analyst": used,
        "mode": _mode(),
    }
