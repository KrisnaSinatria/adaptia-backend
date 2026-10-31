# ADAPTIA Backend

API untuk ADAPTIA (Hackathon INCEPTION 2026, subtema 1 *Inclusive Education and Future Skills*).
Mahasiswa mengajari **Boby**, murid AI yang sengaja keliru; cara mereka membetulkannya menjadi bukti
pemahaman yang dibaca dosen, kalimat demi kalimat.

Prinsip: **AI mengusulkan, aturan memverifikasi, dosen memutuskan.** AI tidak pernah memberi nilai final.

Stack: Python 3.10, FastAPI, Supabase (Postgres), Anthropic API. Dokumentasi interaktif ada di `/docs`.

## Menjalankan (kurang dari 5 menit)

```bash
python -m venv .venv
.venv/Scripts/activate              # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                # isi nilainya
```

1. Buat proyek Supabase, jalankan `migrations/001_init.sql` di SQL Editor.
2. Muat seed: `python -m app.seed`
3. Jalankan: `uvicorn app.main:app --reload`, buka `http://localhost:8000/docs`.
4. Tes: `pytest` (tanpa jaringan: DB palsu berisi seed asli, model selalu dipalsukan).

Tanpa internet atau tanpa kunci model: `LLM_MODE=scripted`. Seluruh alur tetap berjalan; Boby memakai
skrip dan analis memakai aturan kata kunci, dan setiap respons membawa `"mode": "scripted"`.

### Deploy

`render.yaml` (Render Blueprint) membuat satu web service dengan URL HTTPS publik dan health check
`/api/health`. Isi `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`, `LLM_MODEL`, dan
`ALLOWED_ORIGINS` di dashboard; `JWT_SECRET` dibuat otomatis.

## Arsitektur

```
Frontend (React + Vite)
   │  Authorization: Bearer <token mode demo>
   ▼
FastAPI  /api/*
   ├─ routers/       tipis: validasi, peran, urutan alur
   ├─ boby.py        penjadwal jebakan (aturan) + pertanyaan Boby (LLM, cadangan skrip)
   ├─ analyst.py     analis bukti (LLM JSON, cadangan aturan kata kunci) + cache SHA-256
   ├─ logic.py       MURNI: verify_quote, score_of, transcript_of, roster, rekomendasi
   ├─ llm.py         satu pintu ke model: batas waktu 6 detik, tanpa retry otomatis, log latensi
   └─ repo.py        semua query Supabase (service role)
   ▼
Supabase Postgres: RLS aktif di semua tabel tanpa policy; frontend tidak pernah bicara ke Supabase.
```

LLM hanya di dua titik: pertanyaan lanjutan Boby (giliran 1 dan 3) dan analis bukti. Yang lain
deterministik:

| Pekerjaan | Oleh | Alasan |
|---|---|---|
| Memilih dan membacakan jebakan (giliran 2) | Penjadwal dari bank | Jebakan harus pasti keliru dan punya kunci koreksi |
| Pertanyaan lanjutan Boby | LLM | Harus merujuk kode dan kalimat mahasiswa |
| Menunjuk bukti per indikator | LLM, JSON terstruktur | Membaca bahasa bebas |
| Memeriksa kutipan ada di transkrip | Kode | Mencegah kutipan karangan; gagal → `ambigu` |
| Skor, ringkasan, miskonsepsi dari jebakan | Kode | Bisa diaudit ulang |
| Rekomendasi kegiatan penguatan | Kode (peta `need`) | Konsisten, tanpa LLM |
| Keputusan akhir | Dosen | Finalisasi ditolak selama ada temuan yang belum diputuskan |

Skor = rata-rata berbobot (terpenuhi 1, sebagian 0,5, belum 0, ambigu tidak dihitung), dibulatkan
setengah ke atas seperti frontend. Tes emas (`tests/test_golden.py`) memastikan status, skor, dan
ringkasan roster 35 mahasiswa sama persis dengan `src/lib/data.ts`.

## Endpoint

Semua di bawah `/api`, JSON camelCase seperti `data.ts`. Galat: `{ "error": { "code", "message" } }`.

| Metode dan jalur | Peran | Fungsi |
|---|---|---|
| `POST /auth/demo` | – | `{ role }` → `{ token, user }` (Nadia / Dr. Rina). Mode demo, bukan autentikasi |
| `GET /me/sessions` | keduanya | `{ active, history }`; untuk mahasiswa tiap sesi membawa `attempt` terakhirnya |
| `GET /sessions/:id` | keduanya | `{ id, title, instruction, goal, indicators, penerapan }` |
| `POST /sessions/:id/attempts` | mahasiswa | `{ attemptId, resumed }`; melanjutkan percobaan yang belum dikirim |
| `PUT /attempts/:id/practice` | mahasiswa | `{ code, explain }` |
| `POST /attempts/:id/boby/turn` | mahasiswa | `{}` → giliran 1; `{ text }` → giliran 2 (jebakan); `{ text, choice }` → giliran 3; `{ text }` → `done` |
| `PUT /attempts/:id/application` | mahasiswa | `{ answers }` |
| `POST /attempts/:id/submit` | mahasiswa | `{ findings, score, summary, misconception, analyst: "llm"\|"fallback", mode }` |
| `GET /sessions/:id/roster` | dosen | `{ summary, rows }` 35 baris |
| `GET /attempts/:id` | dosen, pemilik | Percobaan lengkap + `transcript`, `student`, `indicators`, `recommendation` |
| `POST /attempts/:id/decisions` | dosen | `{ indicator, decision, status? }` → skor dihitung ulang |
| `POST /attempts/:id/finalize` | dosen | `{ note }`; kunci skor, tandai ditinjau |
| `POST /demo/reset` | dosen | Kembalikan seed ke kondisi awal (cache analisis dipertahankan) |
| `GET /health` | – | `{ ok, db, llmMode }` |
| `GET /activities` | keduanya | P1: bank kegiatan aktif |
| `GET /assignments`, `POST /assignments` | dosen | P1: penugasan `{ activityId, studentIds, start, due, mode }` |
| `GET /classes/:id/trend` | dosen | P1: rata-rata kelas per sesi yang sudah ditutup |

Tiap temuan di respons membawa `status` (setelah pemverifikasi), `aiStatus` (usulan asli model), dan
`verified`, supaya dosen melihat kutipan yang ditolak pemverifikasi.

Batas laju per token: 120/menit umum, 20/menit untuk giliran Boby dan submit, 5/menit untuk reset.
Masukan dibatasi 4.000 karakter per jawaban.

## Persiapan demo

1. `POST /api/demo/reset` (token dosen) sebelum setiap latihan.
2. Pastikan `GET /api/health` → `"ok": true` dan `llmMode` sesuai harapan.
3. Latihan penuh tiga kali berturut-turut tanpa menyentuh kode.
4. Bila jaringan atau model bermasalah: set `LLM_MODE=scripted`. Tampilan wajib menunjukkan penanda
   `mode: "scripted"`; jangan pernah ditampilkan seolah AI sungguhan.

Log tiap panggilan model (`adaptia.llm`): jenis, latensi, timeout atau galat. Isi transkrip dan kunci
tidak pernah ditulis ke log.

## Uji akurasi analis

```bash
python -m scripts.accuracy seed/labeled.json            # analis LLM
python -m scripts.accuracy seed/labeled.json --fallback # pembanding: aturan kata kunci
```

Butuh penjelasan yang dilabeli dosen (format di `scripts/accuracy.py`). Lima arketipe di `data.ts`
adalah data karangan, bukan gold set. **Belum ada angka akurasi**: set berlabel dosen belum tersedia,
dan angka hanya boleh disebut beserta jumlah sampelnya setelah skrip dijalankan.

## Yang masih disimulasikan atau belum selesai

- **Login** adalah mode demo dengan dua akun tetap; bukan autentikasi.
- **Data** seluruhnya fiktif (`seed/seed.json`, ekspor `data.ts`). Tidak ada data mahasiswa sungguhan.
- **Rubrik sesi Queue dan isi bank jebakan** (`misconception`, `correction_key`, `indicator`) adalah
  draf backend di `seed/drafts.json`, belum disetujui dosen. Jebakan Peluang belum punya indikator.
- **Analis cadangan** adalah aturan kata kunci buatan backend, sengaja konservatif (status tertinggi
  "sebagian"). Pada data seed, kesepakatannya dengan status golden hanya sekitar sepertiga; ia jaring
  pengaman agar alur tidak mati, bukan pengganti analis LLM.
- **Ringkasan** temuan dibuat aturan dari status per indikator, bukan oleh model.
- **Riwayat sesi** selain `operasi-stack` hanya ringkasan statis dari seed (tanpa percobaan per mahasiswa).
- Belum dikerjakan (P2): suara/STT, sinyal tempel teks, Peta Kelas langsung.

## Asumsi yang dicatat

- Roster 35 mahasiswa dan rubrik i1–i4 di `data.ts` milik sesi `operasi-stack`. `stackTask` mengisi
  instruksinya; `queueTask` mengisi sesi demo `antrean-queue` termasuk skrip cadangan Boby.
- Mahasiswa `kurang` punya percobaan tanpa bukti; mahasiswa `belum` tidak punya percobaan.
- Temuan "menunggu" hanya dihitung pada percobaan `perlu`; percobaan `selesai` di seed dianggap sudah ditinjau.
- Temuan yang belum diputuskan memakai status AI, jadi skor masih sementara sampai finalisasi.
- Finalisasi mensyaratkan semua temuan sudah diputuskan dosen.
- Penjadwal jebakan: jebakan aktif pertama (urut id) yang indikatornya ada di rubrik sesi dan belum pernah
  diterima mahasiswa itu di sesi yang sama.
- Miskonsepsi tercatat hanya bila mahasiswa memilih "Setuju" pada jebakan (diambil dari bank).
- SDK Anthropic 2.x tidak lagi menerima parameter `temperature`; konsistensi analis dijaga lewat
  keluaran JSON terstruktur, validasi skema, dan cache, bukan suhu rendah.
- Kolom tambahan di luar skema awal: `students.prev`, `students.archetype`, `sessions.boby_script`,
  ringkasan statis sesi riwayat, `assignments.title`, `indicators.position`.
- Penugasan di seed merujuk mahasiswa lewat nama; `seed.py` memetakannya ke id. Inisial diturunkan dari nama.
- Hosting: Render, karena memberi URL HTTPS publik dan variabel lingkungan tanpa konfigurasi tambahan.
- Prototipe frontend dibuat sebelum sprint; izin pemakaiannya masih dikonfirmasi ke panitia
  [PERLU VERIFIKASI].

## AI Use and Third-Party Declaration

**Penggunaan AI**
- **Claude (Anthropic) di dalam produk**: model yang dikunci lewat `LLM_MODEL` berperan sebagai Boby
  (pertanyaan lanjutan giliran 1 dan 3) dan sebagai analis bukti (menunjuk kutipan per indikator).
  Keluarannya selalu divalidasi kode dan diputuskan dosen; model tidak pernah memberi nilai final.
- **Claude Code sebagai asisten coding**: membantu menulis kode backend, tes, dan dokumentasi ini.
  Tim meninjau, menjalankan tes, dan bertanggung jawab atas seluruh kode.

**Pustaka pihak ketiga**: FastAPI, Uvicorn, Pydantic, pydantic-settings, supabase-py, Anthropic Python
SDK, PyJWT, SlowAPI, HTTPX, pytest. Layanan: Supabase (Postgres), Anthropic API, Render.
