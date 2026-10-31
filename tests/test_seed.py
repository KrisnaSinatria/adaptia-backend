from collections import defaultdict

from app.seed import build_rows, load_seed

SEED = load_seed()
ROWS = build_rows(SEED)


def test_every_rubric_weighs_100():
    total = defaultdict(int)
    for ind in ROWS["indicators"]:
        total[ind["session_id"]] += ind["weight"]
    assert dict(total) == {"operasi-stack": 100, "antrean-queue": 100}


def test_demo_session_has_task_fallback_script_and_rubric():
    queue = next(s for s in ROWS["sessions"] if s["id"] == "antrean-queue")
    assert queue["instruction"] and len(queue["penerapan"]) == 2 and len(queue["boby_script"]) == 3
    assert [i["id"] for i in ROWS["indicators"] if i["session_id"] == "antrean-queue"] == ["q1", "q2", "q3", "q4"]


def test_demo_session_has_a_trap_with_correction_key():
    queue_ids = {i["id"] for i in ROWS["indicators"] if i["session_id"] == "antrean-queue"}
    traps = [t for t in ROWS["traps"] if t["indicator"] in queue_ids]
    assert traps and all(t["correction_key"] for t in traps)


def test_trap_indicators_exist():
    ids = {i["id"] for i in ROWS["indicators"]}
    assert all(t["indicator"] in ids for t in ROWS["traps"] if t["indicator"])


def test_seed_values_win_over_drafts():
    seed = {**SEED, "traps": [{**SEED["traps"][0], "indicator": "i1"}]}
    assert build_rows(seed)["traps"][0]["indicator"] == "i1"


def test_without_drafts_queue_session_has_no_rubric():
    rows = build_rows(SEED, drafts={})
    assert all(i["session_id"] == "operasi-stack" for i in rows["indicators"])


def test_assignments_reference_existing_students():
    ids = {s["id"] for s in ROWS["students"]}
    assert all(set(a["student_ids"]) <= ids for a in ROWS["assignments"])
