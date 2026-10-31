# ADAPTIA Backend

API untuk ADAPTIA: mahasiswa mengajari Boby, murid AI yang sengaja keliru, dan cara mereka
membetulkannya menjadi bukti pemahaman yang dibaca dosen kalimat demi kalimat.

Prinsip: **AI mengusulkan, aturan memverifikasi, dosen memutuskan.** AI tidak pernah memberi nilai final.

Stack: Python 3.10+, FastAPI, Supabase (Postgres).

## Menjalankan lokal

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows; di macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # isi nilainya
```

1. Buat proyek Supabase, lalu jalankan `migrations/001_init.sql` di SQL Editor.
2. Muat seed: `python -m app.seed`
3. Jalankan: `uvicorn app.main:app --reload`, lalu buka `http://localhost:8000/docs`.
4. Tes: `pytest`

## Arsitektur

- `app/logic.py`: logika deterministik, murni tanpa I/O. Terjemahan langsung `verifyQuote`,
  `scoreOf`, dan `transcriptOf` dari frontend `src/lib/data.ts`.
- `app/seed.py`: memuat `seed/seed.json`; dipakai juga oleh `POST /api/demo/reset`.
- `app/routers/`: endpoint di bawah `/api`. Semua galat berbentuk
  `{ "error": { "code": string, "message": string } }`.
- Semua tabel memakai RLS tanpa policy. Frontend tidak pernah bicara langsung ke Supabase;
  hanya server (service role) yang mengakses database.

## Status

Sudah: kerangka API, galat seragam, `/api/health`, `/api/demo/reset`, `GET /api/sessions/:id`,
skema database, logika skor dan pemverifikasi kutipan beserta tesnya.

Belum: login demo, alur mahasiswa, Boby, analis, endpoint dosen, deploy.

## Asumsi yang dicatat

- `seed/seed.json` dan `seed/golden.json` diekspor dari `data.ts` frontend. Semua nama fiktif.
- Roster 35 mahasiswa dan rubrik i1–i4 di `data.ts` dimuat sebagai milik sesi `operasi-stack`
  (asesmen awal, berstatus "perlu"). `stackTask` mengisi instruksi sesi itu; `queueTask` mengisi
  sesi `antrean-queue` termasuk skrip cadangan Boby.
- Mahasiswa berstatus `kurang` (mengumpulkan tetapi tidak lengkap) tetap punya percobaan tanpa bukti;
  mahasiswa `belum` tidak punya percobaan.
- Temuan "menunggu" hanya dihitung pada percobaan berstatus `perlu`; percobaan `selesai` di seed
  dianggap sudah ditinjau.
- Skor seed dihitung ulang oleh server dari `findings_raw` (server adalah satu sumber kebenaran);
  tes emas (`tests/test_golden.py`) memastikan status, skor, dan ringkasan roster sama persis dengan frontend.
- Kolom tambahan di luar skema awal: `students.prev`, `students.archetype`, `sessions.boby_script`,
  ringkasan statis sesi riwayat (`submitted`, `enrolled`, `avg`, `pending`), dan `assignments.title`.
- Penugasan di seed merujuk mahasiswa lewat nama; `seed.py` memetakannya ke id.
- Inisial mahasiswa diturunkan dari dua kata pertama nama.
- Temuan yang belum diputuskan dosen tetap memakai status AI, sehingga skor masih sementara
  sampai finalisasi.
- `POST /api/demo/reset` mempertahankan `analysis_cache` supaya demo berulang tidak memakai kuota LLM.
- Tabel `indicators` punya kolom tambahan `position` untuk menjaga urutan rubrik seperti di `data.ts`.
- Prototipe frontend dibuat sebelum sprint; status izinnya masih ditanyakan ke panitia.
