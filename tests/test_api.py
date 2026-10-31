from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import sessions


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_):
        return self

    def eq(self, col, val):
        return FakeQuery([r for r in self.rows if r.get(col) == val])

    def order(self, col):
        return FakeQuery(sorted(self.rows, key=lambda r: r[col]))

    def limit(self, n):
        return FakeQuery(self.rows[:n])

    def execute(self):
        return SimpleNamespace(data=self.rows)


class FakeDB:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return FakeQuery(self.tables.get(name, []))


@pytest.fixture
def client(monkeypatch):
    db = FakeDB({
        "sessions": [{
            "id": "s-queue", "title": "Antrean dengan Queue", "instruction": "Buat antrean loket.",
            "goal": "Paham FIFO", "penerapan": ["Soal 1", "Soal 2"], "class_id": "c1",
        }],
        "indicators": [
            {"id": "i2", "session_id": "s-queue", "name": "Operasi", "concept": "enqueue", "weight": 40, "position": 1},
            {"id": "i1", "session_id": "s-queue", "name": "Urutan", "concept": "fifo", "weight": 60, "position": 0},
        ],
    })
    monkeypatch.setattr(sessions, "get_db", lambda: db)
    return TestClient(app, raise_server_exceptions=False)


def test_session_detail_is_camel_case_and_keeps_rubric_order(client):
    res = client.get("/api/sessions/s-queue")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"id", "title", "instruction", "goal", "indicators", "penerapan"}
    assert [i["id"] for i in body["indicators"]] == ["i1", "i2"]
    assert sum(i["weight"] for i in body["indicators"]) == 100


def test_unknown_session_uses_uniform_error_shape(client):
    res = client.get("/api/sessions/tidak-ada")
    assert res.status_code == 404
    assert res.json() == {"error": {"code": "session_not_found", "message": "Sesi tidak-ada tidak ditemukan."}}


def test_unknown_route_uses_uniform_error_shape(client):
    res = client.get("/api/tidak-ada")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


def test_health_reports_db_error_without_crashing(client, monkeypatch):
    from app.routers import health

    def broken():
        raise RuntimeError("tidak ada koneksi")

    monkeypatch.setattr(health, "get_db", broken)
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["ok"] is False
