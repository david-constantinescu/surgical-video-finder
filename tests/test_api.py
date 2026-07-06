"""Flask API tests."""

from __future__ import annotations

import pytest

from app.server import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_batch_invalid_ids_returns_400(client):
    res = client.post("/api/terms/batch", json={"ids": ["abc"]})
    assert res.status_code == 400


def test_search_invalid_limit_returns_400(client):
    res = client.get("/api/terms/search?q=test&limit=abc")
    assert res.status_code == 400


def test_health_without_db_is_graceful(monkeypatch, tmp_path):
    from app import config

    empty_db = tmp_path / "empty.db"
    monkeypatch.setattr(config, "DB_PATH", empty_db)
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        res = c.get("/api/health")
        assert res.status_code == 503
        assert res.json["status"] == "empty_database"
