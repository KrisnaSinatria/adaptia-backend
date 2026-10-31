-- ADAPTIA skema awal. Data berbentuk dokumen disimpan sebagai jsonb supaya cepat dibangun dalam sprint.
-- Tanggal dan tenggat dari data.ts disimpan apa adanya (text) agar respons identik dengan frontend.

create extension if not exists pgcrypto;

create table classes (
  id text primary key,
  code text not null,
  name text not null,
  "group" text,
  join_code text,
  material text,
  enrolled int
);

create table students (
  id text primary key,
  name text not null,
  nim text not null,
  initials text,
  class_id text references classes(id) on delete cascade,
  prev int,          -- skor sesi sebelumnya, untuk tren per mahasiswa
  archetype text     -- kunci ke peta `need` untuk rekomendasi kegiatan pada data seed
);

create table sessions (
  id text primary key,
  title text not null,
  class_id text references classes(id) on delete cascade,
  type text,
  format text,
  due text,
  state text,
  instruction text,
  goal text,
  penerapan jsonb not null default '[]',
  boby_script jsonb not null default '[]',  -- skrip cadangan Boby bila LLM gagal
  -- Ringkasan statis untuk sesi riwayat; roster sesi aktif dihitung langsung dari attempts.
  submitted int,
  enrolled int,
  avg int,
  pending int
);

create table indicators (
  id text primary key,
  session_id text references sessions(id) on delete cascade,
  name text not null,
  concept text,
  weight int not null check (weight >= 0),
  position int not null default 0  -- urutan rubrik seperti di data.ts
);

create table attempts (
  id uuid primary key default gen_random_uuid(),
  session_id text not null references sessions(id) on delete cascade,
  student_id text not null references students(id) on delete cascade,
  state text not null default 'berlangsung',
  code text not null default '',
  explain text not null default '',
  dialog jsonb not null default '[]',
  answers jsonb not null default '[]',
  findings jsonb not null default '[]',
  misconception text,
  summary text not null default '',
  score int,
  decisions jsonb not null default '{}',
  corrections jsonb not null default '{}',
  note text not null default '',
  reviewed_at timestamptz,
  analyst text check (analyst in ('llm', 'fallback')),
  created_at timestamptz not null default now()
);
create index attempts_session_idx on attempts(session_id);
create index attempts_student_idx on attempts(student_id);

create table traps (
  id text primary key,
  topic text,
  statement text not null,
  misconception text,
  correction_key text,
  indicator text,
  active boolean not null default true
);

create table activities (
  id text primary key,
  title text not null,
  kind text,
  concepts jsonb not null default '[]',
  minutes int,
  level text,
  goal text,
  steps jsonb not null default '[]',
  outcome text,
  active boolean not null default true
);

create table assignments (
  id text primary key,
  title text,
  activity_id text references activities(id) on delete cascade,
  student_ids jsonb not null default '[]',
  start text,
  due text,
  mode text,
  state text,
  done int not null default 0
);

create table analysis_cache (
  transcript_hash text primary key,
  result jsonb not null,
  created_at timestamptz not null default now()
);

-- RLS aktif tanpa policy: anon/authenticated tidak bisa membaca apa pun.
-- Hanya server (service role) yang mengakses tabel.
alter table classes enable row level security;
alter table students enable row level security;
alter table sessions enable row level security;
alter table indicators enable row level security;
alter table attempts enable row level security;
alter table traps enable row level security;
alter table activities enable row level security;
alter table assignments enable row level security;
alter table analysis_cache enable row level security;
