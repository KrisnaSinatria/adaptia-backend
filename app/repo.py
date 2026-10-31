"""Akses database. Semua query Supabase ada di sini supaya router tetap tipis dan bisa dites dengan DB palsu."""

from app.errors import ApiError


def _one(rows: list[dict], code: str, message: str) -> dict:
    if not rows:
        raise ApiError(404, code, message)
    return rows[0]


def get_session(db, session_id: str) -> dict:
    rows = db.table("sessions").select("*").eq("id", session_id).limit(1).execute().data
    return _one(rows, "session_not_found", f"Sesi {session_id} tidak ditemukan.")


def list_sessions(db, class_ids: list[str] | None = None) -> list[dict]:
    q = db.table("sessions").select("*")
    if class_ids is not None:
        q = q.in_("class_id", class_ids)
    return q.execute().data


def get_indicators(db, session_id: str) -> list[dict]:
    return db.table("indicators").select("*").eq("session_id", session_id).order("position").execute().data


def get_student(db, student_id: str) -> dict:
    rows = db.table("students").select("*").eq("id", student_id).limit(1).execute().data
    return _one(rows, "student_not_found", f"Mahasiswa {student_id} tidak ditemukan.")


def list_students(db, class_id: str | None = None, ids: list[str] | None = None) -> list[dict]:
    q = db.table("students").select("*")
    if class_id is not None:
        q = q.eq("class_id", class_id)
    if ids is not None:
        q = q.in_("id", ids)
    return q.execute().data


def get_attempt(db, attempt_id: str) -> dict:
    rows = db.table("attempts").select("*").eq("id", attempt_id).limit(1).execute().data
    return _one(rows, "attempt_not_found", "Percobaan tidak ditemukan.")


def list_attempts(db, session_id: str | None = None, student_id: str | None = None) -> list[dict]:
    q = db.table("attempts").select("*")
    if session_id is not None:
        q = q.eq("session_id", session_id)
    if student_id is not None:
        q = q.eq("student_id", student_id)
    return q.order("created_at").execute().data


def latest_by_student(attempts: list[dict]) -> dict[str, dict]:
    """Percobaan terbaru per mahasiswa; attempts harus sudah urut created_at naik."""
    return {a["student_id"]: a for a in attempts}


def latest_by_session(attempts: list[dict]) -> dict[str, dict]:
    return {a["session_id"]: a for a in attempts}


def insert_attempt(db, row: dict) -> dict:
    return db.table("attempts").insert(row).execute().data[0]


def update_attempt(db, attempt_id: str, fields: dict) -> dict:
    return db.table("attempts").update(fields).eq("id", attempt_id).execute().data[0]


def traps_for(db, indicator_ids: list[str]) -> list[dict]:
    if not indicator_ids:
        return []
    rows = db.table("traps").select("*").in_("indicator", indicator_ids).eq("active", True).execute().data
    return sorted(rows, key=lambda t: t["id"])


def get_trap(db, trap_id: str) -> dict | None:
    rows = db.table("traps").select("*").eq("id", trap_id).limit(1).execute().data
    return rows[0] if rows else None


def get_cached_analysis(db, key: str) -> dict | None:
    rows = db.table("analysis_cache").select("*").eq("transcript_hash", key).limit(1).execute().data
    return rows[0]["result"] if rows else None


def put_cached_analysis(db, key: str, result: dict) -> None:
    db.table("analysis_cache").upsert({"transcript_hash": key, "result": result}).execute()


def list_activities(db) -> list[dict]:
    return db.table("activities").select("*").eq("active", True).execute().data


def get_activity(db, activity_id: str) -> dict:
    rows = db.table("activities").select("*").eq("id", activity_id).limit(1).execute().data
    return _one(rows, "activity_not_found", f"Kegiatan {activity_id} tidak ditemukan.")


def list_assignments(db) -> list[dict]:
    return db.table("assignments").select("*").execute().data


def insert_assignment(db, row: dict) -> dict:
    return db.table("assignments").insert(row).execute().data[0]


def get_class(db, class_id: str) -> dict:
    rows = db.table("classes").select("*").eq("id", class_id).limit(1).execute().data
    return _one(rows, "class_not_found", f"Kelas {class_id} tidak ditemukan.")
