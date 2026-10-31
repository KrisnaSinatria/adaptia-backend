"""Logika deterministik. Murni, tanpa I/O.

verify_quote, shown_status, score_of, dan transcript_of adalah terjemahan langsung
fungsi di frontend src/lib/data.ts. Jangan diubah tanpa mengubah frontend juga:
tes emas (tests/test_golden.py) memastikan keduanya memberi hasil yang sama.
"""

import math
import re
from datetime import date

MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "mei": 5, "jun": 6, "jul": 7, "agu": 8, "agt": 8,
          "sep": 9, "okt": 10, "nov": 11, "des": 12}


def parse_due(text: str | None) -> date | None:
    """Tanggal gaya data.ts, misalnya "28 Okt 2026" atau "6 Nov 2026, 23.59 WIB"."""
    m = re.match(r"\s*(\d{1,2})\s+([A-Za-z]{3})[A-Za-z]*\s+(\d{4})", text or "")
    if not m or m.group(2).lower() not in MONTHS:
        return None
    return date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))


def trend_of(sessions: list[dict]) -> dict:
    """Rata-rata kelas per sesi yang sudah punya nilai, urut tanggal."""
    points = sorted(((parse_due(s["due"]), s["avg"]) for s in sessions if s.get("avg") is not None and parse_due(s["due"])))
    labels = [f"{d.day} {next(k for k, v in MONTHS.items() if v == d.month).capitalize()}" for d, _ in points]
    return {"labels": labels, "values": [v for _, v in points]}


def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[.!?]+$", "", s)
    return s.strip()


def transcript_of(ev) -> str:
    return "\n".join([ev["code"], ev["explain"], *[t["text"] for t in ev["dialog"]], *ev["answers"]])


def student_parts(ev) -> dict:
    """Teks yang ditulis mahasiswa sendiri, per tahap. Ucapan Boby sengaja tidak termasuk."""
    return {
        "praktik": "\n".join([ev["code"], ev["explain"]]),
        "reverse_tutor": "\n".join(t["text"] for t in ev["dialog"] if t["who"] == "mhs"),
        "penerapan": "\n".join(ev["answers"]),
    }


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


def summary_of(statuses: dict, indicators: list) -> str:
    """Ringkasan deterministik dari status per indikator, tanpa LLM."""
    met = [i for i in indicators if statuses.get(i["id"]) == "terpenuhi"]
    weak = [i["name"] for i in indicators if statuses.get(i["id"]) in ("sebagian", "belum")]
    unclear = sum(1 for i in indicators if statuses.get(i["id"]) == "ambigu")
    parts = [f"{len(met)} dari {len(indicators)} indikator terpenuhi."]
    if weak:
        parts.append("Perlu diperjelas: " + "; ".join(weak) + ".")
    if unclear:
        parts.append(f"{unclear} temuan perlu pemeriksaan tambahan.")
    return " ".join(parts)


def trap_misconception(dialog: list, traps_by_id: dict) -> str | None:
    """Hasil jebakan dicatat aturan: menyetujui pernyataan keliru memunculkan miskonsepsi dari bank."""
    for i, t in enumerate(dialog):
        if t.get("trap") and i + 1 < len(dialog) and dialog[i + 1].get("choice") == "Setuju":
            trap = traps_by_id.get(t.get("trapId"))
            return (trap or {}).get("misconception") or "Menyetujui pernyataan keliru Boby."
    return None


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


def recommend_activity(statuses: dict, indicators: list, need: dict, archetype: str | None = None) -> dict:
    """Peta konsep lemah ke satu kegiatan dari bank `need`, tanpa LLM.

    Data seed membawa archetype yang langsung menunjuk entri `need`. Untuk percobaan baru:
    entri penguatan pertama yang konsepnya lemah (belum), lalu entri pemantauan (sebagian/ambigu),
    lalu entri tanpa kebutuhan.
    """
    if archetype in need:
        key = archetype
    else:
        concept_status = {i["concept"]: statuses.get(i["id"]) for i in indicators}
        weak = {c for c, s in concept_status.items() if s == "belum"}
        watch = {c for c, s in concept_status.items() if s in ("sebagian", "ambigu")}
        key = (
            next((k for k, n in need.items() if n["need"] == "penguatan" and weak & set(n["concepts"])), None)
            or next((k for k, n in need.items() if n["need"] == "penguatan" and weak), None)
            or next((k for k, n in need.items() if n["need"] == "pemantauan" and watch & set(n["concepts"])), None)
            or next((k for k, n in need.items() if n["need"] == "pemantauan" and watch), None)
            or next((k for k, n in need.items() if n["need"] == "tidak"), None)
        )
    if key is None:
        return {"need": "tidak", "concepts": [], "activityId": None}
    entry = need[key]
    return {"need": entry["need"], "concepts": entry["concepts"], "activityId": entry["activity"]}


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
