"""P1: kegiatan penguatan, penugasan, dan tren kelas."""

from fastapi import APIRouter, Depends

from app import repo
from app.auth import current_user, require_lecturer
from app.db import get_db
from app.errors import ApiError
from app.logic import roster_row, roster_summary, trend_of
from app.models import AssignmentIn
from app.serialize import camel

router = APIRouter(tags=["P1"])


@router.get("/activities")
def activities(_: dict = Depends(current_user), db=Depends(get_db)):
    return [camel(a) for a in repo.list_activities(db)]


@router.get("/assignments")
def assignments(_: dict = Depends(require_lecturer), db=Depends(get_db)):
    return [camel(a) for a in repo.list_assignments(db)]


@router.post("/assignments")
def create_assignment(body: AssignmentIn, _: dict = Depends(require_lecturer), db=Depends(get_db)):
    activity = repo.get_activity(db, body.activity_id)
    ids = list(dict.fromkeys(body.student_ids))
    found = {s["id"] for s in repo.list_students(db, ids=ids)}
    missing = [i for i in ids if i not in found]
    if missing:
        raise ApiError(422, "unknown_students", f"Mahasiswa tidak ditemukan: {', '.join(missing)}")
    taken = {a["id"] for a in repo.list_assignments(db)}
    n = len(taken) + 1
    while f"pd-{n:02d}" in taken:
        n += 1
    row = repo.insert_assignment(db, {
        "id": f"pd-{n:02d}", "title": activity["title"], "activity_id": activity["id"], "student_ids": ids,
        "start": body.start, "due": body.due, "mode": body.mode, "state": "pelaksanaan", "done": 0,
    })
    return camel(row)


@router.get("/classes/{class_id}/trend")
def class_trend(class_id: str, _: dict = Depends(require_lecturer), db=Depends(get_db)):
    repo.get_class(db, class_id)
    sessions = repo.list_sessions(db, [class_id])
    students = repo.list_students(db, class_id=class_id)
    for s in sessions:
        attempts = repo.list_attempts(db, session_id=s["id"])
        if attempts:
            # Sesi yang punya percobaan di database dihitung langsung, jadi koreksi dosen ikut terlihat.
            latest = repo.latest_by_student(attempts)
            s["avg"] = roster_summary([roster_row(st, latest.get(st["id"])) for st in students])["avg"]
    return trend_of(sessions)
