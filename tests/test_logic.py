from app.logic import decided_statuses, norm, score_of, shown_status, transcript_of, verify_quote

INDICATORS = [
    {"id": "i1", "weight": 40},
    {"id": "i2", "weight": 30},
    {"id": "i3", "weight": 30},
]

EV = {
    "code": "q.append(x)\nq.popleft()",
    "explain": "Queue itu FIFO,   yang masuk duluan keluar duluan.",
    "dialog": [
        {"who": "boby", "text": "Kenapa pakai popleft?"},
        {"who": "mhs", "text": "Karena elemen paling depan yang keluar!"},
    ],
    "answers": ["Antrean loket cocok pakai queue."],
}


def test_norm_lowercases_collapses_space_and_drops_end_punctuation():
    assert norm("  Halo   Dunia?!") == "halo dunia"
    # Urutan sama dengan frontend: tanda baca dibuang sebelum trim, jadi spasi di ujung menahannya.
    assert norm("Halo?! ") == "halo?!"
    assert norm("A.\nB") == "a. b"


def test_transcript_joins_all_parts_in_order():
    t = transcript_of(EV)
    assert t.split("\n")[0] == "q.append(x)"
    assert t.endswith("Antrean loket cocok pakai queue.")
    assert "Kenapa pakai popleft?" in t


def test_quote_found_despite_case_space_and_end_punctuation():
    t = transcript_of(EV)
    assert verify_quote("queue itu fifo, yang masuk duluan keluar duluan", t)
    assert verify_quote("Karena elemen paling depan yang keluar.", t)


def test_quote_not_in_transcript_becomes_ambigu():
    t = transcript_of(EV)
    f = {"indicator": "i1", "status": "terpenuhi", "quote": "stack itu LIFO"}
    assert shown_status(f, t) == "ambigu"


def test_verified_quote_keeps_ai_status():
    t = transcript_of(EV)
    f = {"indicator": "i1", "status": "sebagian", "quote": "Queue itu FIFO"}
    assert shown_status(f, t) == "sebagian"


def test_ambigu_is_not_counted_in_score():
    statuses = {"i1": "terpenuhi", "i2": "ambigu", "i3": "belum"}
    # (1*40 + 0*30) / 70 = 57.14 -> 57
    assert score_of(statuses, INDICATORS) == 57


def test_all_ambigu_scores_zero():
    assert score_of({"i1": "ambigu", "i2": "ambigu", "i3": "ambigu"}, INDICATORS) == 0


def test_half_rounds_up_not_to_even():
    inds = [{"id": "a", "weight": 1}, {"id": "b", "weight": 99}]
    # sebagian pada bobot 1 dari 100 -> 0.5 -> 1 (round() Python akan memberi 0)
    assert score_of({"a": "sebagian", "b": "belum"}, inds) == 1
    inds = [{"id": "a", "weight": 5}, {"id": "b", "weight": 95}]
    # 2.5 -> 3 (round() Python akan memberi 2)
    assert score_of({"a": "sebagian", "b": "belum"}, inds) == 3


def test_decisions_correction_wins_reject_drops_pending_keeps_ai():
    ai = {"i1": "terpenuhi", "i2": "belum", "i3": "sebagian"}
    out = decided_statuses(ai, {"i1": "reject", "i2": "correct"}, {"i2": "terpenuhi"})
    assert out == {"i2": "terpenuhi", "i3": "sebagian"}
    # (1*30 + 0.5*30) / 60 = 75
    assert score_of(out, INDICATORS) == 75


def test_accept_keeps_ai_status_even_with_stale_correction():
    out = decided_statuses({"i1": "belum"}, {"i1": "accept"}, {"i1": "terpenuhi"})
    assert out == {"i1": "belum"}
