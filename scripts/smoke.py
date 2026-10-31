"""Smoke test lewat HTTP terhadap server yang berjalan (lokal atau URL publik), seperti latihan demo.

    python -m scripts.smoke http://localhost:8000
    python -m scripts.smoke https://adaptia-api.onrender.com --rounds 3

Menjalankan POST /api/demo/reset lalu alur penuh mahasiswa -> dosen. Database akan dikembalikan ke seed
di awal setiap putaran. Keluar dengan kode 1 bila ada pemeriksaan yang gagal.
"""

import argparse
import sys
import time

import httpx

PRACTICE = {
    "code": 'from collections import deque\n\nantrean = deque()\nantrean.append("Ani")\nantrean.append("Budi")\n'
            'antrean.popleft()      # Ani dilayani\nantrean.append("Cici")\nantrean.popleft()      # Budi dilayani\n'
            "print(antrean)         # deque(['Cici'])",
    "explain": "Yang dilayani Ani lalu Budi, dan tersisa Cici, karena queue melayani yang datang lebih dulu.",
}
REPLIES = [
    {"text": "popleft() mengambil dari kiri, yaitu Ani yang datang pertama."},
    {"text": "Queue mengeluarkan yang paling awal masuk, stack yang paling akhir masuk.", "choice": "Tidak setuju"},
    {"text": "Undo pakai stack, karena yang dibatalkan dulu perubahan terakhir."},
]
ANSWERS = ["Queue, karena telepon yang masuk lebih dulu harus dijawab lebih dulu.",
           "Stack. Kembali dua kali membuka halaman terakhir lalu halaman sebelumnya."]
SEED_SUMMARY = {"perlu": 8, "selesai": 20, "kurang": 2, "belum": 5, "submitted": 30, "pendingFindings": 32,
                "avg": 71, "scoredCount": 28}


class Run:
    def __init__(self, base: str):
        self.http = httpx.Client(base_url=base.rstrip("/") + "/api", timeout=30)
        self.failures: list[str] = []
        self.timings: dict[str, list[float]] = {}

    def check(self, name: str, ok: bool, detail: object = "") -> None:
        print(("  OK    " if ok else "  GAGAL ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
        if not ok:
            self.failures.append(name)

    def call(self, label: str, method: str, path: str, headers=None, **kw):
        start = time.monotonic()
        res = self.http.request(method, path, headers=headers, **kw)
        self.timings.setdefault(label, []).append((time.monotonic() - start) * 1000)
        return res

    def login(self, role: str) -> dict:
        res = self.call("login", "POST", "/auth/demo", json={"role": role})
        return {"Authorization": "Bearer " + res.json()["token"]}

    def rehearsal(self) -> None:
        health = self.call("health", "GET", "/health").json()
        self.check("health ok", health.get("ok") is True, health)
        print(f"        llmMode={health.get('llmMode')}")
        S, D = self.login("mahasiswa"), self.login("dosen")

        res = self.call("reset", "POST", "/demo/reset", D)
        self.check("demo/reset", res.status_code == 200, res.text)
        summary = self.call("roster", "GET", "/sessions/operasi-stack/roster", D).json().get("summary")
        self.check("roster seed sama dengan golden", summary == SEED_SUMMARY, summary)

        active = self.call("me/sessions", "GET", "/me/sessions", S).json()["active"]
        self.check("sesi berjalan antrean-queue", [s["id"] for s in active] == ["antrean-queue"], active)
        detail = self.call("session", "GET", "/sessions/antrean-queue", S).json()
        self.check("rubrik sesi demo ada", len(detail.get("indicators", [])) > 0, detail)

        aid = self.call("start", "POST", "/sessions/antrean-queue/attempts", S).json()["attemptId"]
        res = self.call("practice", "PUT", f"/attempts/{aid}/practice", S, json=PRACTICE)
        self.check("praktik tersimpan", res.json() == {"ok": True}, res.text)

        turns = [self.call(f"boby{i}", "POST", f"/attempts/{aid}/boby/turn", S, json=b).json()
                 for i, b in enumerate([{}] + REPLIES, start=1)]
        self.check("tiga giliran Boby lalu selesai", [t.get("index") for t in turns] == [1, 2, 3, 3]
                   and turns[-1].get("done") is True, turns)
        self.check("giliran 2 jebakan dari bank", turns[1].get("turn", {}).get("trap") is True, turns[1])
        for t in turns[:3]:
            print(f"        Boby[{t.get('index')}] fallback={t.get('usedFallback')}: {t.get('turn', {}).get('text')}")

        res = self.call("application", "PUT", f"/attempts/{aid}/application", S, json={"answers": ANSWERS})
        self.check("jawaban penerapan tersimpan", res.json() == {"ok": True}, res.text)
        sub = self.call("submit", "POST", f"/attempts/{aid}/submit", S).json()
        self.check("submit menghasilkan temuan", len(sub.get("findings", [])) == len(detail["indicators"]), sub)
        print(f"        analyst={sub.get('analyst')} score={sub.get('score')} mode={sub.get('mode')}")

        roster = self.call("roster", "GET", "/sessions/antrean-queue/roster", D).json()
        row = next((r for r in roster["rows"] if r["attemptId"] == aid), {})
        self.check("roster dosen memuat percobaan baru", row.get("state") == "perlu", row)
        evidence = self.call("attempt", "GET", f"/attempts/{aid}", D).json()
        self.check("kartu bukti berisi transkrip", bool(evidence.get("transcript")), evidence)

        decisions = ["accept", "correct", "accept", "reject"]
        last = {}
        for ind, dec in zip([i["id"] for i in detail["indicators"]], decisions):
            body = {"indicator": ind, "decision": dec, **({"status": "terpenuhi"} if dec == "correct" else {})}
            last = self.call("decision", "POST", f"/attempts/{aid}/decisions", D, json=body).json()
        self.check("semua temuan diputuskan", last.get("pending") == 0, last)
        fin = self.call("finalize", "POST", f"/attempts/{aid}/finalize", D, json={"note": "Smoke test."}).json()
        self.check("finalisasi", fin.get("ok") is True, fin)
        again = self.call("attempt", "GET", f"/attempts/{aid}", D).json()
        self.check("keputusan tersimpan setelah dibaca ulang",
                   again.get("state") == "selesai" and len(again.get("decisions", {})) == len(decisions), again)
        mine = self.call("attempt", "GET", f"/attempts/{aid}", S).json()
        self.check("mahasiswa melihat hasil tinjauan", mine.get("note") == "Smoke test.", mine)
        trend = self.call("trend", "GET", "/classes/if203b/trend", D).json()
        self.check("tren kelas", trend.get("values") == [58, 63, 61, 67, 71], trend)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("base_url")
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--pause", type=float, default=0, help="jeda antarputaran (detik), mis. untuk kuota LLM")
    args = parser.parse_args(argv)

    run = Run(args.base_url)
    for n in range(1, args.rounds + 1):
        print(f"--- putaran {n}")
        run.rehearsal()
        if n < args.rounds and args.pause:
            time.sleep(args.pause)
    print("--- latensi (ms, maks)")
    for label in ("boby1", "boby2", "boby3", "submit", "reset"):
        if label in run.timings:
            print(f"  {label:8} {max(run.timings[label]):7.0f}")
    print("HASIL:", "SEMUA LULUS" if not run.failures else f"{len(run.failures)} GAGAL: {run.failures}")
    return 1 if run.failures else 0


if __name__ == "__main__":
    sys.exit(main())
