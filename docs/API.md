# Kontrak API ADAPTIA untuk frontend

Dokumen ini untuk menyambungkan frontend (React + Vite) ke backend. Bentuk JSON mengikuti
`src/lib/data.ts`: camelCase, dan nama enum persis sama. Dokumentasi interaktif ada di `/docs` (OpenAPI).

- Basis URL: `https://<host>/api`
- Semua permintaan selain `POST /auth/demo` dan `GET /health` memerlukan header
  `Authorization: Bearer <token>`.
- Semua contoh di bawah diambil dari respons API yang berjalan (mode skrip), dan sebagian dipotong.

## Enum

```ts
type Status   = 'terpenuhi' | 'sebagian' | 'belum' | 'ambigu'
type Stage    = 'praktik' | 'reverse_tutor' | 'penerapan'
type Decision = 'accept' | 'correct' | 'reject'
type AttemptState = 'berlangsung' | 'perlu' | 'selesai' | 'kurang' | 'belum'
type Mode     = 'live' | 'scripted'   // scripted = tanpa LLM; WAJIB ditandai di tampilan
```

## Galat

Selalu berbentuk:

```json
{ "error": { "code": "findings_pending", "message": "Masih ada 3 temuan yang belum diputuskan." } }
```

`message` sudah berbahasa Indonesia dan aman ditampilkan apa adanya. Gunakan `code` untuk logika.

| HTTP | code | Kapan |
|---|---|---|
| 401 | `unauthorized`, `token_expired` | Tanpa token, token rusak, atau kedaluwarsa (12 jam). Arahkan ke login demo |
| 403 | `forbidden` | Peran salah, atau membuka percobaan milik mahasiswa lain |
| 404 | `not_found`, `session_not_found`, `attempt_not_found`, `student_not_found`, `activity_not_found`, `class_not_found` | Sumber tidak ada |
| 409 | `session_closed` | Memulai percobaan di sesi yang bukan `berlangsung` |
| 409 | `attempt_submitted` | Mengubah percobaan yang sudah dikirim |
| 409 | `practice_missing` | Mengajari Boby atau submit sebelum kode/penjelasan disimpan |
| 409 | `turn_order` | Mengirim balasan padahal Boby belum bertanya |
| 409 | `dialog_incomplete`, `answers_incomplete` | Submit sebelum tiga giliran Boby atau semua soal penerapan selesai |
| 409 | `rubric_missing` | Sesi belum punya rubrik |
| 409 | `nothing_to_review`, `attempt_finalized`, `findings_pending` | Tinjauan dosen tidak bisa dilakukan |
| 422 | `invalid_input`, `text_required`, `choice_required`, `status_required`, `unknown_indicator`, `unknown_students` | Isi permintaan tidak valid (mis. lebih dari 4.000 karakter) |
| 429 | `rate_limited` | Lebih dari 120/menit umum, 20/menit untuk Boby dan submit, 5/menit untuk reset |
| 503 | `db_unconfigured`, `auth_unconfigured`, `seed_missing` | Server belum dikonfigurasi |
| 500 | `internal_error` | Galat tak terduga (detail hanya di log server) |

## Mode demo

### `POST /auth/demo`

Mode demo dengan dua akun tetap, tanpa kata sandi. **Jangan disebut autentikasi di presentasi.**

```json
// permintaan
{ "role": "mahasiswa" }      // atau "dosen"
// respons
{ "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": { "id": "nadia", "name": "Nadia Rahmawati", "nim": "2410512031", "initials": "NR", "role": "mahasiswa" } }
```

Untuk dosen: `user = { id: "rina", name: "Dr. Rina Anggraini", initials: "RA", title: "Dosen · Informatika", role: "dosen" }`.

## Alur mahasiswa

### `GET /me/sessions` (keduanya)

```json
{ "active": [ { "id": "antrean-queue", "title": "Antrean dengan Queue", "classId": "if203b", "type": "Formatif",
                "format": "Teks / Kode", "due": "6 Nov 2026", "state": "berlangsung", "submitted": 12,
                "enrolled": 35, "avg": null, "pending": 0, "attempt": null } ],
  "history": [ { "id": "operasi-stack", "...": "...", "state": "perlu", "avg": 71,
                 "attempt": { "id": "acfd93c3-…", "state": "perlu", "score": 68 } } ] }
```

`attempt` adalah percobaan terakhir mahasiswa di sesi itu (selalu `null` untuk dosen). Urutan: tenggat terbaru dulu.

### `GET /sessions/:id` (keduanya)

```json
{ "id": "antrean-queue", "title": "Antrean dengan Queue",
  "instruction": "Simulasikan antrean loket: …", "goal": "Menjelaskan urutan FIFO …",
  "indicators": [ { "id": "q1", "name": "Menjelaskan urutan FIFO", "concept": "fifo", "weight": 30 }, "…" ],
  "penerapan": [ "Pusat panggilan kampus …", "Tombol Kembali di peramban …" ] }
```

Bobot satu rubrik berjumlah 100. Konsep `enqdeq` (q2) belum ada di `concepts` milik `data.ts`; tambahkan labelnya,
misalnya "Operasi enqueue & dequeue".

### `POST /sessions/:id/attempts` (mahasiswa)

```json
{ "attemptId": "defa0aa8-af27-4ea2-b147-f21c046ff875", "resumed": false }
```

Bila masih ada percobaan `berlangsung` di sesi itu, percobaan tersebut dilanjutkan (`resumed: true`).
Simpan `attemptId` (misalnya di state halaman) untuk langkah berikutnya.

### `PUT /attempts/:id/practice` (mahasiswa)

```json
{ "code": "from collections import deque …", "explain": "Yang dilayani Ani lalu Budi …" }   // → { "ok": true }
```

Boleh dipanggil berkali-kali (autosave) selama percobaan belum dikirim.

### `POST /attempts/:id/boby/turn` (mahasiswa)

Empat panggilan berurutan:

| Panggilan | Isi permintaan | Respons |
|---|---|---|
| 1 | `{}` | giliran 1: pertanyaan tentang kode |
| 2 | `{ "text": "balasan mahasiswa" }` | giliran 2: **jebakan** (`turn.trap: true`) |
| 3 | `{ "text": "alasan", "choice": "Setuju" \| "Tidak setuju" }` | giliran 3: pertanyaan penerapan |
| 4 | `{ "text": "balasan mahasiswa" }` | `done: true`, `turn: null` |

```json
{ "turn": { "who": "boby", "text": "Queue mengeluarkan elemen yang terakhir masuk.", "trap": true,
            "trapId": "t5", "time": "01.13" },
  "index": 2, "done": false, "usedFallback": false, "mode": "live" }
```

- Saat `turn.trap` bernilai `true`, tampilkan tombol **Setuju / Tidak setuju** dan kolom alasan; `choice` wajib
  pada panggilan berikutnya.
- Balasan mahasiswa tidak dikembalikan di respons; frontend menambahkannya sendiri ke tampilan dialog
  (bentuknya `{ who: "mhs", text, choice?, time }` dan sudah tersimpan di server).
- `usedFallback: true` berarti Boby memakai skrip karena model gagal, lambat (> 6 detik), atau menulis sesuatu
  yang dilarang. `mode: "scripted"` berarti server sengaja berjalan tanpa LLM: **tampilkan penanda mode skrip**.
- Target latensi: di bawah 3 detik. Tampilkan indikator "Boby sedang berpikir"; jangan biarkan layar menggantung.

### `PUT /attempts/:id/application` (mahasiswa)

```json
{ "answers": [ "Queue, karena …", "Stack. Kembali dua kali …" ] }   // → { "ok": true }
```

Jumlah jawaban harus sama dengan jumlah soal `penerapan`.

### `POST /attempts/:id/submit` (mahasiswa)

```json
{ "findings": [ { "indicator": "q1", "status": "terpenuhi", "stage": "praktik",
                  "quote": "Yang dilayani Ani lalu Budi …", "reason": "Mahasiswa menjelaskan urutan FIFO.",
                  "aiStatus": "terpenuhi", "verified": true } ],
  "score": 100, "summary": "4 dari 4 indikator terpenuhi.", "misconception": null,
  "analyst": "llm", "mode": "live" }
```

- `status` sudah melewati pemverifikasi. `aiStatus` adalah usulan asli model; bila berbeda, tampilkan bahwa
  pemverifikasi menurunkannya. `verified: false` berarti kutipan tidak ditemukan di transkrip.
- `analyst: "fallback"` berarti analis aturan kata kunci dipakai (model gagal). **Tampilkan penanda "analis cadangan".**
- `misconception` hanya terisi bila mahasiswa memilih "Setuju" pada jebakan.
- Skor masih sementara sampai dosen memfinalkan. Target latensi: di bawah 10 detik.

## Alur dosen

### `GET /sessions/:id/roster` (dosen)

```json
{ "summary": { "perlu": 8, "selesai": 20, "kurang": 2, "belum": 5, "submitted": 30,
               "pendingFindings": 32, "avg": 71, "scoredCount": 28 },
  "rows": [ { "id": "nadia", "name": "Nadia Rahmawati", "nim": "2410512031", "state": "perlu", "score": 68,
              "summary": "Menelusuri push dan pop dengan benar, …", "pending": 4,
              "statuses": { "i1": "terpenuhi", "i2": "terpenuhi", "i3": "sebagian", "i4": "belum" },
              "attemptId": "acfd93c3-…", "prev": 70 } ] }
```

Satu baris per mahasiswa di kelas sesi itu (35). Mahasiswa yang belum mengerjakan: `state: "belum"`,
`attemptId: null`. `statuses` sudah memperhitungkan keputusan dosen (temuan ditolak tidak muncul).

### `GET /attempts/:id` (dosen, atau mahasiswa pemilik)

Percobaan lengkap (`Attempt` di `data.ts`) ditambah:

```json
{ "id": "…", "sessionId": "antrean-queue", "studentId": "nadia", "state": "perlu",
  "code": "…", "explain": "…", "dialog": [ "…Turn" ], "answers": [ "…" ],
  "findings": [ "…seperti di submit" ], "misconception": null, "summary": "…", "score": 50,
  "decisions": {}, "corrections": {}, "note": "", "reviewedAt": null, "analyst": "fallback",
  "statuses": { "q1": "sebagian", "…": "…" }, "pending": 4,
  "transcript": "antrean.popleft()\nQueue itu FIFO.\n…",
  "student": { "id": "nadia", "name": "Nadia Rahmawati", "nim": "2410512031" },
  "indicators": [ { "id": "q1", "name": "…", "concept": "fifo", "weight": 30 } ],
  "recommendation": { "need": "pemantauan", "concepts": ["pushpop"], "activityId": "mi-telusur" } }
```

`recommendation` dipilih aturan dari peta `need` di `data.ts`. Peta itu baru memuat konsep Stack, jadi untuk
sesi Queue rekomendasinya masih kasar sampai peta `need` diperluas.

Untuk menyorot kutipan di transkrip: cari `quote` di `transcript` tanpa membedakan huruf besar-kecil dan spasi
ganda (aturan sama dengan `verifyQuote`).

### `POST /attempts/:id/decisions` (dosen)

```json
// permintaan
{ "indicator": "q1", "decision": "correct", "status": "terpenuhi" }   // status wajib hanya untuk "correct"
// respons
{ "score": 65, "decisions": { "q1": "correct" }, "corrections": { "q1": "terpenuhi" }, "pending": 3 }
```

Skor dihitung ulang: koreksi memakai status dosen, terima memakai status AI, tolak tidak dihitung. Keputusan
bisa diubah sampai finalisasi.

### `POST /attempts/:id/finalize` (dosen)

```json
{ "note": "Perjelas operasi dequeue." }   // → { "ok": true, "score": <skor akhir>, "reviewedAt": "<ISO 8601 UTC>" }
```

Ditolak (`409 findings_pending`) selama masih ada temuan yang belum diputuskan: AI tidak pernah memberi nilai
final. Setelah final, `state` menjadi `selesai` dan skor terkunci.

## P1

| Endpoint | Peran | Isi |
|---|---|---|
| `GET /activities` | keduanya | Kegiatan aktif, bentuk sama dengan `activities` di `data.ts` |
| `GET /assignments` | dosen | Penugasan: `{ id, title, activityId, studentIds, start, due, mode, state, done }` |
| `POST /assignments` | dosen | `{ activityId, studentIds, start, due, mode }` → penugasan baru (`state: "pelaksanaan"`) |
| `GET /classes/:id/trend` | dosen | `{ labels: ["9 Sep", …], values: [58, …] }` rata-rata kelas per sesi yang sudah ditutup |

Catatan: penugasan di `data.ts` memakai `students` (nama) dan `activity`; API memakai `studentIds` dan `activityId`.

## Demo

| Endpoint | Peran | Isi |
|---|---|---|
| `POST /demo/reset` | dosen | Kembalikan data ke seed. Jalankan sebelum setiap latihan demo |
| `GET /health` | – | `{ "ok": true, "db": "ok", "llmMode": "live" }` |

## Contoh pemanggilan dari frontend

```ts
const API = import.meta.env.VITE_API_URL  // mis. https://adaptia-api.onrender.com/api

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = sessionStorage.getItem('adaptia-token')
  const res = await fetch(API + path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  })
  const body = await res.json()
  if (!res.ok) throw Object.assign(new Error(body.error.message), { code: body.error.code, status: res.status })
  return body as T
}
```

Frontend harus terdaftar di `ALLOWED_ORIGINS` backend (dipisah koma), misalnya
`https://adaptia.vercel.app,http://localhost:5173`.
