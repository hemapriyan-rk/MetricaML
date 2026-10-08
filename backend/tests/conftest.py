import os
import tempfile
import time

import pytest

_tmp = tempfile.mkdtemp(prefix="metrica-test-")
os.environ["METRICA_DATA_DIR"] = _tmp

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def make_client():
    clients = []

    def _make(email, name="Test User", password="correct-horse"):
        c = TestClient(app)
        c.__enter__()
        clients.append(c)
        r = c.post("/api/auth/register", json={"name": name, "email": email, "password": password})
        assert r.status_code == 200, r.text
        return c

    yield _make
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture(scope="session")
def client(make_client):
    return make_client("main@example.com")


def wait_for(client, exp_id, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        data = client.get(f"/api/experiments/{exp_id}").json()
        if data["status"] != "running":
            return data
        time.sleep(0.4)
    raise AssertionError("experiment did not finish")
