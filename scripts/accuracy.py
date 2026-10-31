"""Uji akurasi analis terhadap label dosen.

    python -m scripts.accuracy seed/labeled.json            # analis LLM (butuh GROQ_API_KEY, LLM_MODEL)
    python -m scripts.accuracy seed/labeled.json --fallback # pembanding: analis aturan kata kunci

Format berkas (daftar penjelasan yang sudah dilabeli dosen, BUKAN lima arketipe karangan di data.ts):
    [{"id": "...", "sessionId": "antrean-queue",
      "code": "...", "explain": "...", "dialog": [Turn...], "answers": ["..."],
      "labels": {"q1": "terpenuhi", "q2": "belum", ...}}]

Laporkan angka beserta jumlah sampelnya. Jangan menyebut angka apa pun sebelum skrip ini dijalankan.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from app import analyst
from app.logic import shown_statuses, transcript_of
from app.seed import build_rows, load_seed

STATUSES = ["terpenuhi", "sebagian", "belum", "ambigu"]


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    n = len(pairs)
    if n == 0:
        return None
    observed = sum(a == b for a, b in pairs) / n
    left, right = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(left[s] * right[s] for s in STATUSES) / (n * n)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def evaluate(items: list[dict], indicators_by_session: dict, use_fallback: bool,
             sessions: dict | None = None) -> dict:
    pairs, per_indicator, llm_failed, confusion = [], {}, 0, Counter()
    for item in items:
        indicators = indicators_by_session[item["sessionId"]]
        transcript = transcript_of(item)
        session = (sessions or {}).get(item["sessionId"])
        findings = None if use_fallback else analyst.llm_findings(item, indicators, session=session)
        if findings is None:
            if not use_fallback:
                llm_failed += 1
                continue  # kegagalan LLM dilaporkan terpisah, tidak dihitung sebagai ketidaksepakatan
            findings = analyst.keyword_findings(item, indicators)
        predicted = shown_statuses(findings, transcript)
        for ind_id, label in item["labels"].items():
            got = predicted.get(ind_id, "ambigu")
            pairs.append((label, got))
            per_indicator.setdefault(ind_id, []).append(label == got)
            confusion[f"{label}->{got}"] += 1
    agree = sum(a == b for a, b in pairs)
    return {
        "analyst": "fallback" if use_fallback else "llm",
        "explanations": len(items),
        "llmFailed": llm_failed,
        "judgments": len(pairs),
        "agreementPct": round(100 * agree / len(pairs), 1) if pairs else None,
        "cohenKappa": None if not pairs else round(cohen_kappa(pairs), 3),
        "perIndicatorPct": {k: round(100 * sum(v) / len(v), 1) for k, v in sorted(per_indicator.items())},
        "confusion": dict(sorted(confusion.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path)
    parser.add_argument("--fallback", action="store_true", help="ukur analis aturan kata kunci")
    args = parser.parse_args(argv)

    items = json.loads(args.path.read_text(encoding="utf-8"))
    rows = build_rows(load_seed())
    by_session: dict[str, list[dict]] = {}
    for ind in rows["indicators"]:
        by_session.setdefault(ind["session_id"], []).append(ind)
    unknown = {i["sessionId"] for i in items} - set(by_session)
    if unknown:
        print(f"Sesi tanpa rubrik: {sorted(unknown)}", file=sys.stderr)
        return 1
    sessions = {s["id"]: s for s in rows["sessions"]}
    print(json.dumps(evaluate(items, by_session, args.fallback, sessions), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
