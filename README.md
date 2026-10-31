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

- `seed/seed.json` dan `seed/golden.json` diekspor dari `data.ts` frontend dan belum ada di repo ini.
  `app/seed.py` mengasumsikan tiap `students[].evidence` memuat `sessionId`, `state`, `code`, `explain`,
  `dialog`, `answers`, dan `findings_raw`. Sesuaikan bila bentuk ekspornya berbeda.
- Skor seed dihitung ulang oleh server dari `findings_raw` (server adalah satu sumber kebenaran);
  tes emas memastikan hasilnya sama dengan frontend.
- Temuan yang belum diputuskan dosen tetap memakai status AI, sehingga skor masih sementara
  sampai finalisasi.
- `POST /api/demo/reset` mempertahankan `analysis_cache` supaya demo berulang tidak memakai kuota LLM.
- Tabel `indicators` punya kolom tambahan `position` untuk menjaga urutan rubrik seperti di `data.ts`.
- Prototipe frontend dibuat sebelum sprint; status izinnya masih ditanyakan ke panitia.
