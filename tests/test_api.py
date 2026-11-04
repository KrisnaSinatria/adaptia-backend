import json
from pathlib import Path

from app.limiter import limiter
from app import llm
from app.config import get_settings

QUEUE = "antrean-queue"
GOLDEN = json.loads((Path(__file__).resolve().parents[1] / "seed" / "golden.json").read_text(encoding="utf-8"))
PRACTICE = {
    "code": 'from collections import deque\nantrean = deque()\nantrean.append("Ani")\nantrean.append("Budi")\n'
            'antrean.popleft()\nantrean.append("Cici")\nantrean.popleft()',
    "explain": "Yang dilayani Ani lalu Budi, tersisa Cici, karena queue melayani yang datang lebih dulu.",
}
ANSWERS = ["Pakai queue, supaya penelepon yang datang lebih dulu dijawab lebih dulu.",
           "Stack, karena Kembali membuka halaman terakhir dulu, lalu halaman sebelumnya."]


def start(client, student):
    return client.post(f"/api/sessions/{QUEUE}/attempts", headers=student).json()["attemptId"]


def run_dialog(client, student, aid, choice="Tidak setuju"):
    turns = [client.post(f"/api/attempts/{aid}/boby/turn", headers=student, json={})]
    turns.append(client.post(f"/api/attempts/{aid}/boby/turn", headers=student,
                             json={"text": "Karena popleft mengambil dari depan, jadi Ani keluar duluan."}))
    turns.append(client.post(f"/api/attempts/{aid}/boby/turn", headers=student,
                             json={"text": "Bukan, queue mengeluarkan yang paling awal masuk.", "choice": choice}))
    turns.append(client.post(f"/api/attempts/{aid}/boby/turn", headers=student,
                             json={"text": "Undo pakai stack karena yang dibatalkan perubahan terakhir."}))
    return turns


def submitted_attempt(client, student, choice="Tidak setuju"):
    aid = start(client, student)
    client.put(f"/api/attempts/{aid}/practice", headers=student, json=PRACTICE)
    run_dialog(client, student, aid, choice)
    client.put(f"/api/attempts/{aid}/application", headers=student, json={"answers": ANSWERS})
    return aid, client.post(f"/api/attempts/{aid}/submit", headers=student)


# ---- mode demo dan galat ----

def test_demo_login_returns_profiles(client):
    s = client.post("/api/auth/demo", json={"role": "mahasiswa"}).json()
    d = client.post("/api/auth/demo", json={"role": "dosen"}).json()
    assert s["user"]["name"] == "Nadia Rahmawati" and s["token"]
    assert d["user"]["name"] == "Dr. Rina Anggraini"


def test_requests_without_token_or_wrong_role_are_rejected(client, student):
    assert client.get(f"/api/sessions/{QUEUE}").json()["error"]["code"] == "unauthorized"
    bad = client.get(f"/api/sessions/{QUEUE}", headers={"Authorization": "Bearer palsu"})
    assert bad.status_code == 401
    res = client.get(f"/api/sessions/{QUEUE}/roster", headers=student)
    assert res.status_code == 403 and res.json() == {"error": {"code": "forbidden", "message": "Hanya untuk dosen."}}


def test_validation_and_unknown_routes_use_uniform_errors(client, student):
    assert client.post("/api/auth/demo", json={"role": "admin"}).json()["error"]["code"] == "invalid_input"
    assert client.get("/api/tidak-ada").json()["error"]["code"] == "not_found"
    assert client.get("/api/sessions/tidak-ada", headers=student).json()["error"]["code"] == "session_not_found"


def test_input_longer_than_limit_is_rejected(client, student):
    aid = start(client, student)
    res = client.put(f"/api/attempts/{aid}/practice", headers=student, json={"code": "x" * 4001, "explain": ""})
    assert res.status_code == 422


def test_health_reports_unconfigured_db_without_crashing(client):
    body = client.get("/api/health").json()
    assert body == {"ok": False, "db": "error", "llmMode": "scripted"}


# ---- alur mahasiswa ----

def test_session_detail_has_rubric_and_tasks(client, student):
    body = client.get(f"/api/sessions/{QUEUE}", headers=student).json()
    assert set(body) == {"id", "title", "instruction", "goal", "indicators", "penerapan"}
    assert [i["id"] for i in body["indicators"]] == ["q1", "q2", "q3", "q4"]
    assert len(body["penerapan"]) == 2


def test_my_sessions_split_active_and_history(client, student):
    body = client.get("/api/me/sessions", headers=student).json()
    assert [s["id"] for s in body["active"]] == [QUEUE]
    stack = next(s for s in body["history"] if s["id"] == "operasi-stack")
    assert stack["attempt"]["state"] == "perlu" and stack["classId"] == "if203b"


def test_start_attempt_resumes_unsubmitted_attempt(client, student):
    first = client.post(f"/api/sessions/{QUEUE}/attempts", headers=student).json()
    again = client.post(f"/api/sessions/{QUEUE}/attempts", headers=student).json()
    assert again == {"attemptId": first["attemptId"], "resumed": True}


def test_closed_session_cannot_be_started(client, student):
    assert client.post("/api/sessions/operasi-stack/attempts", headers=student).status_code == 409


def test_boby_needs_practice_first(client, student):
    aid = start(client, student)
    res = client.post(f"/api/attempts/{aid}/boby/turn", headers=student, json={})
    assert res.json()["error"]["code"] == "practice_missing"


def test_boby_three_turns_with_trap_from_bank(client, student, db):
    aid = start(client, student)
    client.put(f"/api/attempts/{aid}/practice", headers=student, json=PRACTICE)
    t1, t2, t3, end = [r.json() for r in run_dialog(client, student, aid)]

    assert (t1["index"], t1["done"], t1["usedFallback"], t1["mode"]) == (1, False, True, "scripted")
    trap = next(t for t in db.tables["traps"] if t["id"] == "t5")
    assert t2["turn"] == {**t2["turn"], "text": trap["statement"], "trap": True, "trapId": "t5"}
    assert t2["usedFallback"] is False
    assert t3["index"] == 3 and not t3["turn"].get("trap")
    assert end["done"] is True and end["turn"] is None

    dialog = next(a for a in db.tables["attempts"] if a["id"] == aid)["dialog"]
    assert [t["who"] for t in dialog] == ["boby", "mhs"] * 3
    assert dialog[3]["choice"] == "Tidak setuju"


def test_live_boby_failure_does_not_append_dialog(client, student, db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_mode", "live")
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    aid = start(client, student)
    client.put(f"/api/attempts/{aid}/practice", headers=student, json=PRACTICE)
    row = next(a for a in db.tables["attempts"] if a["id"] == aid)

    monkeypatch.setattr(llm, "complete_text", lambda *_args, **_kwargs: None)
    failed_first = client.post(f"/api/attempts/{aid}/boby/turn", headers=student, json={})
    assert failed_first.status_code == 503
    assert failed_first.json()["error"]["code"] == "boby_unavailable"
    assert row["dialog"] == []

    monkeypatch.setattr(llm, "complete_text", lambda *_args, **_kwargs: "Kenapa Ani keluar duluan?")
    first = client.post(f"/api/attempts/{aid}/boby/turn", headers=student, json={})
    assert first.status_code == 200 and first.json()["turn"]["text"] == "Kenapa Ani keluar duluan?"
    client.post(f"/api/attempts/{aid}/boby/turn", headers=student, json={"text": "Karena Ani datang lebih dahulu."})
    before_third = list(row["dialog"])

    monkeypatch.setattr(llm, "complete_text", lambda *_args, **_kwargs: None)
    answer = {"text": "Saya tidak setuju karena queue melayani yang datang lebih dulu.", "choice": "Tidak setuju"}
    failed_third = client.post(f"/api/attempts/{aid}/boby/turn", headers=student, json=answer)
    assert failed_third.status_code == 503
    assert failed_third.json()["error"]["code"] == "boby_unavailable"
    assert row["dialog"] == before_third

    monkeypatch.setattr(llm, "complete_text", lambda *_args, **_kwargs: "Kenapa urutan kedatangan menentukan pilihanmu?")
    third = client.post(f"/api/attempts/{aid}/boby/turn", headers=student, json=answer)
    assert third.status_code == 200 and third.json()["index"] == 3
    assert [t["who"] for t in row["dialog"]] == ["boby", "mhs"] * 2 + ["boby"]
    assert row["dialog"][3]["choice"] == "Tidak setuju"


def test_empty_trap_does_not_create_blank_turn(client, student, db):
    aid = start(client, student)
    client.put(f"/api/attempts/{aid}/practice", headers=student, json=PRACTICE)
    client.post(f"/api/attempts/{aid}/boby/turn", headers=student, json={})
    row = next(a for a in db.tables["attempts"] if a["id"] == aid)
    before = list(row["dialog"])
    db.tables["traps"] = []
    next(s for s in db.tables["sessions"] if s["id"] == QUEUE)["boby_script"][1] = ""
    res = client.post(f"/api/attempts/{aid}/boby/turn", headers=student, json={"text": "Ani datang lebih dulu."})
    assert res.status_code == 409 and res.json()["error"]["code"] == "trap_missing"
    assert row["dialog"] == before


def test_trap_reply_requires_choice(client, student):
    aid = start(client, student)
    client.put(f"/api/attempts/{aid}/practice", headers=student, json=PRACTICE)
    client.post(f"/api/attempts/{aid}/boby/turn", headers=student, json={})
    client.post(f"/api/attempts/{aid}/boby/turn", headers=student, json={"text": "Karena dari depan."})
    res = client.post(f"/api/attempts/{aid}/boby/turn", headers=student, json={"text": "Tidak."})
    assert res.json()["error"]["code"] == "choice_required"


def test_submit_rejects_incomplete_attempt(client, student):
    aid = start(client, student)
    client.put(f"/api/attempts/{aid}/practice", headers=student, json=PRACTICE)
    res = client.post(f"/api/attempts/{aid}/submit", headers=student)
    assert res.json()["error"]["code"] == "dialog_incomplete"


def test_submit_in_scripted_mode_uses_fallback_analyst_with_verified_quotes(client, student):
    aid, res = submitted_attempt(client, student)
    body = res.json()
    assert res.status_code == 200
    assert body["analyst"] == "fallback" and body["mode"] == "scripted"
    assert [f["indicator"] for f in body["findings"]] == ["q1", "q2", "q3", "q4"]
    assert all(f["verified"] for f in body["findings"])
    assert isinstance(body["score"], int) and body["misconception"] is None
    # Setelah dikirim, percobaan terkunci.
    again = client.put(f"/api/attempts/{aid}/practice", headers=student, json=PRACTICE)
    assert again.json()["error"]["code"] == "attempt_submitted"


def test_agreeing_with_trap_records_bank_misconception(client, student, db):
    _, res = submitted_attempt(client, student, choice="Setuju")
    trap = next(t for t in db.tables["traps"] if t["id"] == "t5")
    body = res.json()
    assert body["misconception"] == trap["misconception"]
    q3 = next(f for f in body["findings"] if f["indicator"] == "q3")
    assert q3["status"] == "belum" and q3["stage"] == "reverse_tutor"


def test_student_cannot_open_other_students_attempt(client, student, db):
    other = next(a for a in db.tables["attempts"] if a["student_id"] == "bagas")
    assert client.get(f"/api/attempts/{other['id']}", headers=student).status_code == 403


# ---- alur dosen ----

def test_roster_of_seed_session_matches_golden(client, lecturer):
    body = client.get("/api/sessions/operasi-stack/roster", headers=lecturer).json()
    assert body["summary"] == GOLDEN["summary"]
    golden = {g["id"]: g for g in GOLDEN["students"]}
    assert len(body["rows"]) == 35
    for row in body["rows"]:
        assert (row["state"], row["score"], row["statuses"]) == (
            golden[row["id"]]["state"], golden[row["id"]]["score"], golden[row["id"]]["statuses"])


def test_attempt_detail_shows_verifier_rejection_and_recommendation(client, lecturer, db):
    bagas = next(a for a in db.tables["attempts"] if a["student_id"] == "bagas")
    body = client.get(f"/api/attempts/{bagas['id']}", headers=lecturer).json()
    i2 = next(f for f in body["findings"] if f["indicator"] == "i2")
    assert i2["status"] == "ambigu" and i2["verified"] is False and i2["aiStatus"] != "ambigu"
    assert body["student"]["name"] == "Bagas Pratama" and body["transcript"]
    assert body["recommendation"]["activityId"]
    assert {"sessionId", "studentId", "reviewedAt", "dialog", "decisions"} <= set(body)


def test_full_flow_from_student_to_lecturer_decision_persists(client, student, lecturer):
    aid, res = submitted_attempt(client, student)
    roster = client.get(f"/api/sessions/{QUEUE}/roster", headers=lecturer).json()
    nadia = next(r for r in roster["rows"] if r["id"] == "nadia")
    assert (nadia["state"], nadia["pending"], nadia["attemptId"]) == ("perlu", 4, aid)
    assert roster["summary"]["perlu"] == 1 and roster["summary"]["belum"] == 34

    post = lambda path, body: client.post(f"/api/attempts/{aid}/{path}", headers=lecturer, json=body)  # noqa: E731
    assert post("finalize", {"note": ""}).json()["error"]["code"] == "findings_pending"
    assert post("decisions", {"indicator": "q1", "decision": "correct"}).json()["error"]["code"] == "status_required"
    post("decisions", {"indicator": "q1", "decision": "correct", "status": "terpenuhi"})
    post("decisions", {"indicator": "q2", "decision": "reject"})
    post("decisions", {"indicator": "q3", "decision": "accept"})
    last = post("decisions", {"indicator": "q4", "decision": "accept"}).json()
    assert last["pending"] == 0 and last["corrections"] == {"q1": "terpenuhi"}

    final = post("finalize", {"note": "Bagus, perjelas operasi dequeue."}).json()
    assert final["ok"] and final["score"] == last["score"]

    # "Setelah reload": baca ulang dari database.
    detail = client.get(f"/api/attempts/{aid}", headers=lecturer).json()
    assert detail["state"] == "selesai" and detail["reviewedAt"] and detail["note"].startswith("Bagus")
    assert detail["decisions"] == {"q1": "correct", "q2": "reject", "q3": "accept", "q4": "accept"}
    assert "q2" not in detail["statuses"] and detail["statuses"]["q1"] == "terpenuhi"
    assert post("decisions", {"indicator": "q3", "decision": "reject"}).json()["error"]["code"] == "attempt_finalized"

    mine = client.get(f"/api/attempts/{aid}", headers=student).json()
    assert mine["score"] == final["score"] and mine["note"] == detail["note"]


def test_new_attempt_recommendation_ignores_seed_archetype(client, student, lecturer, db):
    from app.seed import load_seed
    need = load_seed()["need"]
    aid, _ = submitted_attempt(client, student)  # mode skrip: semua indikator "sebagian"
    rec = client.get(f"/api/attempts/{aid}", headers=lecturer).json()["recommendation"]
    assert rec["need"] == "pemantauan"
    assert rec["activityId"] in {n["activity"] for n in need.values() if n["need"] == "pemantauan"}
    seeded = next(a for a in db.tables["attempts"] if a["student_id"] == "nadia" and a["session_id"] == "operasi-stack")
    seeded_rec = client.get(f"/api/attempts/{seeded['id']}", headers=lecturer).json()["recommendation"]
    assert seeded_rec["activityId"] == need["terapan"]["activity"]


def test_decision_recomputes_score(client, lecturer, db):
    nadia = next(a for a in db.tables["attempts"] if a["student_id"] == "nadia")
    assert nadia["score"] == 68
    res = client.post(f"/api/attempts/{nadia['id']}/decisions", headers=lecturer,
                      json={"indicator": "i4", "decision": "correct", "status": "terpenuhi"}).json()
    # i1 terpenuhi 30, i2 terpenuhi 25, i3 sebagian 25, i4 terpenuhi 20 -> 87.5 -> 88
    assert res["score"] == 88


# ---- demo dan P1 ----

def test_demo_reset_restores_seed(client, student, lecturer, db):
    submitted_attempt(client, student)
    assert client.post("/api/demo/reset", headers=student).status_code == 403
    res = client.post("/api/demo/reset", headers=lecturer).json()
    assert res["counts"]["attempts"] == 30
    assert not [a for a in db.tables["attempts"] if a["session_id"] == QUEUE]


def test_trend_matches_seed_trend(client, lecturer):
    from app.seed import load_seed
    assert client.get("/api/classes/if203b/trend", headers=lecturer).json() == load_seed()["trend"]


def test_running_session_stays_out_of_trend(client, student, lecturer):
    from app.seed import load_seed
    submitted_attempt(client, student)
    assert client.get("/api/classes/if203b/trend", headers=lecturer).json() == load_seed()["trend"]


def test_lecturer_correction_moves_trend(client, lecturer, db):
    nadia = next(a for a in db.tables["attempts"] if a["student_id"] == "nadia")
    client.post(f"/api/attempts/{nadia['id']}/decisions", headers=lecturer,
                json={"indicator": "i4", "decision": "correct", "status": "terpenuhi"})
    values = client.get("/api/classes/if203b/trend", headers=lecturer).json()["values"]
    assert values[:4] == [58, 63, 61, 67] and values[4] >= 71


def test_assignments_list_and_create(client, lecturer):
    assert len(client.get("/api/assignments", headers=lecturer).json()) == 3
    res = client.post("/api/assignments", headers=lecturer, json={
        "activityId": "mi-telusur", "studentIds": ["nadia", "bagas"], "start": "2 Nov 2026, 08.00",
        "due": "5 Nov 2026, 23.59", "mode": "Mandiri"}).json()
    assert res["activityId"] == "mi-telusur" and res["studentIds"] == ["nadia", "bagas"] and res["state"] == "pelaksanaan"
    assert res["id"] == "pd-13"
    bad = client.post("/api/assignments", headers=lecturer, json={
        "activityId": "mi-telusur", "studentIds": ["siapa"], "start": "a", "due": "b", "mode": "Mandiri"})
    assert bad.json()["error"]["code"] == "unknown_students"


def test_activities_are_camel_case(client, student):
    from app.seed import load_seed
    acts = client.get("/api/activities", headers=student).json()
    assert len(acts) == sum(a["active"] for a in load_seed()["activities"])
    assert {"id", "title", "concepts", "steps"} <= set(acts[0])


def test_rate_limit_returns_uniform_error(client, lecturer):
    limiter.enabled = True
    try:
        codes = [client.post("/api/demo/reset", headers=lecturer).status_code for _ in range(6)]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codes[:5] == [200] * 5 and codes[5] == 429
