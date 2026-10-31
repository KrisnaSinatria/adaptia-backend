"""Tes emas: backend harus memberi status dan skor yang sama persis dengan frontend.

seed/golden.json dihitung langsung oleh src/lib/data.ts untuk 35 mahasiswa.
"""

import json
from pathlib import Path

import pytest

from app.logic import roster_row, roster_summary, score_of, shown_statuses, transcript_of
from app.seed import build_rows, load_seed

GOLDEN = json.loads((Path(__file__).resolve().parents[1] / "seed" / "golden.json").read_text(encoding="utf-8"))
SEED = load_seed()
GOLDEN_BY_ID = {g["id"]: g for g in GOLDEN["students"]}


@pytest.mark.parametrize("student", [s for s in SEED["students"] if s["evidence"]], ids=lambda s: s["id"])
def test_statuses_and_score_match_frontend(student):
    ev = student["evidence"]
    statuses = shown_statuses(ev["findings_raw"], transcript_of(ev))
    golden = GOLDEN_BY_ID[student["id"]]
    assert statuses == golden["statuses"]
    assert score_of(statuses, SEED["indicators"]) == golden["score"]


def roster_from_seed():
    rows = build_rows(SEED)
    by_student = {a["student_id"]: a for a in rows["attempts"]}
    return [roster_row(s, by_student.get(s["id"])) for s in rows["students"]]


def test_roster_rows_match_golden_state_score_and_statuses():
    roster = roster_from_seed()
    assert len(roster) == 35
    for row in roster:
        golden = GOLDEN_BY_ID[row["id"]]
        assert (row["state"], row["score"], row["statuses"]) == (golden["state"], golden["score"], golden["statuses"])


def test_roster_summary_matches_golden():
    assert roster_summary(roster_from_seed()) == GOLDEN["summary"]


def test_seed_has_a_quote_rejected_by_verifier():
    # Data seed sengaja memuat satu kutipan karangan supaya demo memperlihatkan pemverifikasi bekerja.
    bagas = next(s for s in SEED["students"] if s["id"] == "bagas")
    raw = {f["indicator"]: f["status"] for f in bagas["evidence"]["findings_raw"]}
    assert raw["i2"] != "ambigu"
    assert GOLDEN_BY_ID["bagas"]["statuses"]["i2"] == "ambigu"
