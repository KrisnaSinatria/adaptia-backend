"""Logika deterministik. Murni, tanpa I/O.

verify_quote, shown_status, score_of, dan transcript_of adalah terjemahan langsung
fungsi di frontend src/lib/data.ts. Jangan diubah tanpa mengubah frontend juga:
tes emas (tests/test_golden.py) memastikan keduanya memberi hasil yang sama.
"""

import math
import re


def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[.!?]+$", "", s)
    return s.strip()


def transcript_of(ev) -> str:
    return "\n".join([ev["code"], ev["explain"], *[t["text"] for t in ev["dialog"]], *ev["answers"]])


def verify_quote(quote: str, transcript: str) -> bool:
    return norm(quote) in norm(transcript)


def shown_status(finding, transcript) -> str:
    return finding["status"] if verify_quote(finding["quote"], transcript) else "ambigu"


VALUE = {"terpenuhi": 1, "sebagian": 0.5, "belum": 0, "ambigu": None}


def score_of(statuses: dict, indicators: list) -> int:
    s = w = 0
    for i in indicators:
        v = VALUE.get(statuses.get(i["id"]))
        if v is None:
            continue
        s += v * i["weight"]
        w += i["weight"]
    # Setengah dibulatkan ke atas seperti Math.round di frontend; round() Python membulatkan ke genap.
    return math.floor((s / w) * 100 + 0.5) if w else 0


def shown_statuses(findings: list, transcript: str) -> dict:
    return {f["indicator"]: shown_status(f, transcript) for f in findings}


SUBMITTED_STATES = ("perlu", "selesai", "kurang")


def pending_of(attempt: dict) -> int:
    """Temuan yang masih menunggu keputusan dosen; hanya ada pada percobaan berstatus perlu."""
    if attempt["state"] != "perlu":
        return 0
    decisions = attempt.get("decisions") or {}
    return sum(1 for f in attempt.get("findings") or [] if f["indicator"] not in decisions)


def attempt_statuses(attempt: dict) -> dict:
    """Status per indikator yang ditampilkan: hasil pemverifikasi, lalu keputusan dosen."""
    findings = attempt.get("findings") or []
    if not findings:
        return {}
    ai = shown_statuses(findings, transcript_of(attempt))
    return decided_statuses(ai, attempt.get("decisions") or {}, attempt.get("corrections") or {})


def roster_row(student: dict, attempt: dict | None) -> dict:
    if attempt is None:
        return {"id": student["id"], "name": student["name"], "nim": student["nim"], "state": "belum",
                "score": None, "summary": "", "pending": 0, "statuses": {}}
    return {
        "id": student["id"], "name": student["name"], "nim": student["nim"],
        "state": attempt["state"], "score": attempt.get("score"), "summary": attempt.get("summary") or "",
        "pending": pending_of(attempt), "statuses": attempt_statuses(attempt),
    }


def roster_summary(rows: list[dict]) -> dict:
    """rows: satu per mahasiswa dengan kunci state, score, pending."""
    scores = [r["score"] for r in rows if r["score"] is not None]
    count = {st: sum(1 for r in rows if r["state"] == st) for st in ("perlu", "selesai", "kurang", "belum")}
    return {
        **count,
        "submitted": sum(1 for r in rows if r["state"] in SUBMITTED_STATES),
        "pendingFindings": sum(r["pending"] for r in rows),
        "avg": math.floor(sum(scores) / len(scores) + 0.5) if scores else None,
        "scoredCount": len(scores),
    }


def decided_statuses(ai_statuses: dict, decisions: dict, corrections: dict) -> dict:
    """Status setelah tinjauan dosen: koreksi menang, temuan ditolak tidak dihitung.

    Temuan yang belum diputuskan tetap memakai status AI (skor masih sementara).
    """
    out = {}
    for ind, status in ai_statuses.items():
        decision = decisions.get(ind)
        if decision == "reject":
            continue
        out[ind] = corrections.get(ind, status) if decision == "correct" else status
    return out
