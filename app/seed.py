"""Muat seed/seed.json (ekspor src/lib/data.ts) ke Supabase.  Jalankan: python -m app.seed

Dipakai juga oleh POST /demo/reset supaya kondisi awal demo selalu sama.
"""

import json
from pathlib import Path

from app.logic import score_of, shown_statuses, transcript_of

SEED_PATH = Path(__file__).resolve().parents[1] / "seed" / "seed.json"

# Roster 35 mahasiswa dan rubrik i1–i4 di data.ts milik sesi asesmen awal "Operasi Stack".
ROSTER_SESSION = "operasi-stack"
STACK_TASK_SESSION = "operasi-stack"

# Urutan isi (induk dulu); hapus memakai urutan terbalik.
TABLES = ["classes", "students", "sessions", "indicators", "traps", "activities", "assignments", "attempts"]


def load_seed(path: Path = SEED_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{path} belum ada. Ekspor dari src/lib/data.ts terlebih dahulu.")
    return json.loads(path.read_text(encoding="utf-8"))


def _class_rows(seed):
    return [
        {"id": c["id"], "code": c["code"], "name": c["name"], "group": c["group"],
         "join_code": c["joinCode"], "material": c["material"], "enrolled": c["enrolled"]}
        for c in seed["classes"]
    ]


def _session_rows(seed):
    tasks = {STACK_TASK_SESSION: seed["stackTask"], seed["queueTask"]["id"]: seed["queueTask"]}
    rows = []
    for s in seed["sessions"]:
        task = tasks.get(s["id"], {})
        rows.append({
            "id": s["id"], "title": s["title"], "class_id": s["classId"], "type": s["type"],
            "format": s["format"], "due": s["due"], "state": s["state"],
            "instruction": task.get("instruction"), "goal": task.get("goal"),
            "penerapan": task.get("penerapan", []), "boby_script": task.get("boby", []),
            "submitted": s["submitted"], "enrolled": s["enrolled"], "avg": s["avg"], "pending": s["pending"],
        })
    return rows


def _student_rows(seed, class_id):
    return [
        {"id": st["id"], "name": st["name"], "nim": st["nim"],
         "initials": "".join(w[0] for w in st["name"].split()[:2]).upper(),
         "class_id": class_id, "prev": st.get("prev"), "archetype": st.get("archetype")}
        for st in seed["students"]
    ]


def _attempt_row(student, indicators):
    ev = student["evidence"]
    base = {"session_id": ROSTER_SESSION, "student_id": student["id"], "state": student["state"]}
    if ev is None:
        # "kurang": sudah mengumpulkan tetapi tidak lengkap, jadi tetap punya percobaan tanpa bukti.
        return {**base, "score": None}
    statuses = shown_statuses(ev["findings_raw"], transcript_of(ev))
    return {
        **base,
        "code": ev["code"], "explain": ev["explain"], "dialog": ev["dialog"], "answers": ev["answers"],
        "findings": ev["findings_raw"], "misconception": ev.get("misconception"),
        "summary": ev.get("summary", ""), "score": score_of(statuses, indicators),
    }


def _assignment_rows(seed):
    ids_by_name = {st["name"]: st["id"] for st in seed["students"]}
    rows = []
    for a in seed["assignments"]:
        missing = [n for n in a["students"] if n not in ids_by_name]
        if missing:
            raise ValueError(f"Penugasan {a['id']} merujuk mahasiswa yang tidak ada: {missing}")
        rows.append({
            "id": a["id"], "title": a["title"], "activity_id": a["activity"],
            "student_ids": [ids_by_name[n] for n in a["students"]],
            "start": a["start"], "due": a["due"], "mode": a["mode"], "state": a["state"], "done": a["done"],
        })
    return rows


def build_rows(seed: dict) -> dict[str, list[dict]]:
    roster_class = next(s["classId"] for s in seed["sessions"] if s["id"] == ROSTER_SESSION)
    indicators = [
        {"id": i["id"], "session_id": ROSTER_SESSION, "name": i["name"], "concept": i["concept"],
         "weight": i["weight"], "position": pos}
        for pos, i in enumerate(seed["indicators"])
    ]
    return {
        "classes": _class_rows(seed),
        "students": _student_rows(seed, roster_class),
        "sessions": _session_rows(seed),
        "indicators": indicators,
        "traps": [{k: t[k] for k in ("id", "topic", "statement", "misconception", "correction_key", "indicator")}
                  for t in seed["traps"]],
        "activities": [{k: a[k] for k in ("id", "title", "kind", "concepts", "minutes", "level", "goal",
                                          "steps", "outcome", "active")} for a in seed["activities"]],
        "assignments": _assignment_rows(seed),
        "attempts": [_attempt_row(st, seed["indicators"]) for st in seed["students"] if st["state"] != "belum"],
    }


def reset_database(db, seed: dict | None = None) -> dict[str, int]:
    rows = build_rows(seed or load_seed())
    # attempts memakai uuid; tabel lain memakai id text. analysis_cache sengaja dipertahankan.
    db.table("attempts").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    for table in reversed(TABLES[:-1]):
        db.table(table).delete().neq("id", "").execute()
    for table in TABLES:
        if rows[table]:
            db.table(table).insert(rows[table]).execute()
    return {t: len(rows[t]) for t in TABLES}


if __name__ == "__main__":
    from app.db import get_db

    for table, n in reset_database(get_db()).items():
        print(f"{table}: {n}")
