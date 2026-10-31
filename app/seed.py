"""Muat seed/seed.json ke Supabase.  Jalankan: python -m app.seed

Dipakai juga oleh POST /demo/reset supaya kondisi awal demo selalu sama.
"""

import json
import re
from pathlib import Path

from app.logic import score_of, shown_statuses, transcript_of

SEED_PATH = Path(__file__).resolve().parents[1] / "seed" / "seed.json"

# Kolom tiap tabel; kunci camelCase dari seed dipetakan ke snake_case dan sisanya dibuang.
COLUMNS = {
    "classes": ["id", "code", "name", "group", "join_code", "material", "enrolled"],
    "students": ["id", "name", "nim", "initials", "class_id"],
    "sessions": ["id", "title", "class_id", "type", "format", "due", "state", "instruction", "goal", "penerapan"],
    "indicators": ["id", "session_id", "name", "concept", "weight", "position"],
    "traps": ["id", "topic", "statement", "misconception", "correction_key", "indicator", "active"],
    "activities": ["id", "title", "kind", "concepts", "minutes", "level", "goal", "steps", "outcome", "active"],
    "assignments": ["id", "activity_id", "student_ids", "start", "due", "mode", "state", "done"],
}

# Urutan hapus (anak dulu) dan urutan isi (induk dulu).
INSERT_ORDER = ["classes", "students", "sessions", "indicators", "traps", "activities", "assignments", "attempts"]


def snake(key: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()


def pick(entry: dict, table: str) -> dict:
    flat = {snake(k): v for k, v in entry.items()}
    return {c: flat[c] for c in COLUMNS[table] if c in flat}


def load_seed(path: Path = SEED_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{path} belum ada. Ekspor dari src/lib/data.ts terlebih dahulu.")
    return json.loads(path.read_text(encoding="utf-8"))


def attempt_row(student: dict, indicators_by_session: dict) -> dict:
    ev = student["evidence"]
    session_id = ev["sessionId"]
    transcript = transcript_of(ev)
    statuses = shown_statuses(ev["findings_raw"], transcript)
    return {
        "session_id": session_id,
        "student_id": student["id"],
        "state": ev["state"],
        "code": ev["code"],
        "explain": ev["explain"],
        "dialog": ev["dialog"],
        "answers": ev["answers"],
        "findings": ev["findings_raw"],
        "misconception": ev.get("misconception"),
        "summary": ev.get("summary", ""),
        "score": score_of(statuses, indicators_by_session[session_id]),
        "decisions": ev.get("decisions", {}),
        "corrections": ev.get("corrections", {}),
        "note": ev.get("note", ""),
        "reviewed_at": ev.get("reviewedAt"),
    }


def build_rows(seed: dict) -> dict[str, list[dict]]:
    rows = {t: [pick(e, t) for e in seed.get(t, [])] for t in COLUMNS}
    for pos, ind in enumerate(rows["indicators"]):
        ind["position"] = pos

    by_session: dict[str, list[dict]] = {}
    for ind in rows["indicators"]:
        by_session.setdefault(ind["session_id"], []).append(ind)

    rows["attempts"] = [attempt_row(s, by_session) for s in seed["students"] if s.get("evidence")]
    return rows


def reset_database(db, seed: dict | None = None) -> dict[str, int]:
    rows = build_rows(seed or load_seed())
    # attempts memakai uuid; tabel lain memakai id text. analysis_cache sengaja dipertahankan.
    db.table("attempts").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    for table in reversed(INSERT_ORDER[:-1]):
        db.table(table).delete().neq("id", "").execute()
    for table in INSERT_ORDER:
        if rows[table]:
            db.table(table).insert(rows[table]).execute()
    return {t: len(rows[t]) for t in INSERT_ORDER}


if __name__ == "__main__":
    from app.db import get_db

    for table, n in reset_database(get_db()).items():
        print(f"{table}: {n}")
