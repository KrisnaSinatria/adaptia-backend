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
