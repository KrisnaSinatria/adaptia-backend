import os
import sys
from pathlib import Path

# Lingkungan tes: tanpa kunci asli, LLM mode skrip, batas laju dimatikan (dites terpisah).
os.environ.update({
    "JWT_SECRET": "tes-rahasia-yang-cukup-panjang-untuk-hs256",
    "LLM_MODE": "scripted",
    "GROQ_API_KEY": "",
    "LLM_MODEL": "",
    "SUPABASE_URL": "",
    "SUPABASE_SERVICE_ROLE_KEY": "",
    "RATE_LIMIT_ENABLED": "false",
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import reset_database  # noqa: E402
from tests.fakedb import FakeDB  # noqa: E402


@pytest.fixture
def db():
    fake = FakeDB()
    reset_database(fake)
    return fake


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _token(client, role):
    return {"Authorization": "Bearer " + client.post("/api/auth/demo", json={"role": role}).json()["token"]}


@pytest.fixture
def student(client):
    return _token(client, "mahasiswa")


@pytest.fixture
def lecturer(client):
    return _token(client, "dosen")
