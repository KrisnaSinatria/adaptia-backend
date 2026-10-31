import pytest

from app.seed import build_rows, load_seed
from scripts.accuracy import cohen_kappa, evaluate


def test_kappa_perfect_and_chance():
    assert cohen_kappa([("belum", "belum"), ("terpenuhi", "terpenuhi")]) == 1.0
    assert cohen_kappa([("belum", "terpenuhi"), ("terpenuhi", "belum")]) == -1.0
    assert cohen_kappa([]) is None


def test_evaluate_reports_sample_size_and_agreement():
    # Struktur saja: memakai bukti seed dengan label = status golden, BUKAN gold set dosen.
    seed = load_seed()
    rows = build_rows(seed)
    stack = [i for i in rows["indicators"] if i["session_id"] == "operasi-stack"]
    items = [{**s["evidence"], "sessionId": "operasi-stack",
              "labels": {f["indicator"]: f["status"] for f in s["evidence"]["findings_raw"]}}
             for s in seed["students"][:3] if s["evidence"]]
    report = evaluate(items, {"operasi-stack": stack}, use_fallback=True)
    assert report["explanations"] == 3 and report["judgments"] == 12
    assert 0 <= report["agreementPct"] <= 100
    assert set(report["perIndicatorPct"]) == {"i1", "i2", "i3", "i4"}


def test_llm_failures_are_counted_separately(monkeypatch):
    from app import analyst
    monkeypatch.setattr(analyst, "llm_findings", lambda *a: None)
    item = {"code": "", "explain": "", "dialog": [], "answers": [], "sessionId": "s", "labels": {"i1": "belum"}}
    report = evaluate([item], {"s": [{"id": "i1", "concept": "lifo", "name": "x", "weight": 100}]}, False)
    assert report["llmFailed"] == 1 and report["judgments"] == 0 and report["agreementPct"] is None


@pytest.mark.parametrize("bad", [[("x", "y")]])
def test_kappa_handles_unknown_categories(bad):
    assert cohen_kappa(bad) == 0.0
