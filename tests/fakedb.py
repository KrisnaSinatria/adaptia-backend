"""Pengganti Supabase di memori untuk tes. Hanya mendukung bagian API yang dipakai app/repo.py dan app/seed.py."""

import copy
import itertools
import uuid
from types import SimpleNamespace

ATTEMPT_DEFAULTS = {
    "state": "berlangsung", "code": "", "explain": "", "dialog": [], "answers": [], "findings": [],
    "misconception": None, "summary": "", "score": None, "decisions": {}, "corrections": {}, "note": "",
    "reviewed_at": None, "analyst": None,
}
_clock = itertools.count()


class Query:
    def __init__(self, db, table):
        self.db, self.table = db, table
        self.filters, self.op, self.payload = [], "select", None
        self.order_by, self.limit_n = None, None

    # Pembangun query
    def select(self, *_):
        return self

    def eq(self, col, val):
        self.filters.append(lambda r: r.get(col) == val)
        return self

    def neq(self, col, val):
        self.filters.append(lambda r: r.get(col) != val)
        return self

    def in_(self, col, vals):
        self.filters.append(lambda r: r.get(col) in vals)
        return self

    def order(self, col, desc=False):
        self.order_by = (col, desc)
        return self

    def limit(self, n):
        self.limit_n = n
        return self

    def insert(self, rows):
        self.op, self.payload = "insert", rows if isinstance(rows, list) else [rows]
        return self

    def upsert(self, row):
        self.op, self.payload = "upsert", row
        return self

    def update(self, fields):
        self.op, self.payload = "update", fields
        return self

    def delete(self):
        self.op = "delete"
        return self

    def execute(self):
        rows = self.db.tables.setdefault(self.table, [])
        if self.op == "insert":
            out = []
            for r in self.payload:
                r = copy.deepcopy(r)
                if self.table == "attempts":
                    r = {**copy.deepcopy(ATTEMPT_DEFAULTS), "id": str(uuid.uuid4()), **r}
                    r["created_at"] = next(_clock)
                rows.append(r)
                out.append(copy.deepcopy(r))
            return SimpleNamespace(data=out)
        if self.op == "upsert":
            key = "transcript_hash" if self.table == "analysis_cache" else "id"
            rows[:] = [r for r in rows if r.get(key) != self.payload[key]]
            rows.append(copy.deepcopy(self.payload))
            return SimpleNamespace(data=[self.payload])
        matched = [r for r in rows if all(f(r) for f in self.filters)]
        if self.op == "update":
            for r in matched:
                r.update(copy.deepcopy(self.payload))
            return SimpleNamespace(data=copy.deepcopy(matched))
        if self.op == "delete":
            rows[:] = [r for r in rows if r not in matched]
            return SimpleNamespace(data=matched)
        if self.order_by:
            col, desc = self.order_by
            matched = sorted(matched, key=lambda r: r[col], reverse=desc)
        if self.limit_n is not None:
            matched = matched[: self.limit_n]
        return SimpleNamespace(data=copy.deepcopy(matched))


class FakeDB:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {}

    def table(self, name):
        return Query(self, name)
