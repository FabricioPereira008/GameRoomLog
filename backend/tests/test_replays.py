"""Rejogadas: registros separados vinculados ao registro original (1ª jogada)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.core.database import Base, get_db, _enable_sqlite_foreign_keys

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
event.listen(_engine, "connect", _enable_sqlite_foreign_keys)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture
def client():
    Base.metadata.create_all(bind=_engine)
    session = _Session()
    app.dependency_overrides[get_db] = lambda: session
    yield TestClient(app)
    session.close()
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=_engine)


def _new(client, title="Hades", **extra):
    r = client.post("/api/v1/games/", json={"title": title, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _get(client, game_id):
    return client.get(f"/api/v1/games/{game_id}").json()


def test_replay_links_to_original_and_counts(client):
    original = _new(client, status="Zerado", finish_date="2020-05-01")
    assert original["replay_of_id"] is None and original["replays_count"] == 0
    replay = _new(client, replay_of_id=original["id"], play_count=2)
    assert replay["replay_of_id"] == original["id"] and replay["play_type"] == "Rejogada"
    assert _get(client, original["id"])["replays_count"] == 1
    listed = {g["id"]: g for g in client.get("/api/v1/games/").json()}
    assert listed[original["id"]]["replays_count"] == 1 and listed[replay["id"]]["replays_count"] == 0


def test_link_to_a_replay_points_to_the_original(client):
    original = _new(client)
    second = _new(client, replay_of_id=original["id"])
    third = _new(client, replay_of_id=second["id"])
    assert third["replay_of_id"] == original["id"]
    assert _get(client, original["id"])["replays_count"] == 2


def test_invalid_links_are_422(client):
    original = _new(client)
    replay = _new(client, replay_of_id=original["id"])
    assert client.post("/api/v1/games/", json={"title": "X", "replay_of_id": 999}).status_code == 422
    assert client.put(f"/api/v1/games/{original['id']}", json={"replay_of_id": original["id"]}).status_code == 422
    # o original não pode virar rejogada de uma das próprias rejogadas
    r = client.put(f"/api/v1/games/{original['id']}", json={"replay_of_id": replay["id"]})
    assert r.status_code == 422 and "original" in r.json()["detail"]


def test_unlink_by_marking_first_play(client):
    original = _new(client)
    replay = _new(client, replay_of_id=original["id"])
    r = client.put(f"/api/v1/games/{replay['id']}", json={"play_type": "Primeira Jogada"})
    assert r.json()["replay_of_id"] is None
    assert _get(client, original["id"])["replays_count"] == 0
    other = client.put(f"/api/v1/games/{replay['id']}", json={"title": "Só renomeado"}).json()
    assert other["replay_of_id"] is None                    # update parcial não mexe no vínculo


def test_merging_groups_moves_the_replays(client):
    a, b = _new(client, "Hades"), _new(client, "Hades (cópia)")
    b_replay = _new(client, replay_of_id=b["id"])
    moved = client.put(f"/api/v1/games/{b['id']}", json={"replay_of_id": a["id"]}).json()
    assert moved["replay_of_id"] == a["id"]
    assert _get(client, b_replay["id"])["replay_of_id"] == a["id"]
    assert _get(client, a["id"])["replays_count"] == 2


def test_deleting_the_original_promotes_the_oldest_replay(client):
    original = _new(client)
    second = _new(client, replay_of_id=original["id"])
    third = _new(client, replay_of_id=original["id"])
    assert client.delete(f"/api/v1/games/{original['id']}").status_code == 204
    assert _get(client, second["id"])["replay_of_id"] is None
    assert _get(client, third["id"])["replay_of_id"] == second["id"]
    assert _get(client, second["id"])["replays_count"] == 1


def test_deleting_a_replay_keeps_the_original(client):
    original = _new(client)
    replay = _new(client, replay_of_id=original["id"])
    client.delete(f"/api/v1/games/{replay['id']}")
    assert _get(client, original["id"])["replays_count"] == 0


def test_brief_list(client):
    plat = client.post("/api/v1/platforms/", json={"name": "PC"}).json()
    original = _new(client, "Hades", platform_id=plat["id"], status="Zerado", finish_date="2020-05-01", score=9)
    _new(client, "Celeste")
    _new(client, "Hades", replay_of_id=original["id"], play_count=2)
    briefs = client.get("/api/v1/games/brief").json()
    assert [b["title"] for b in briefs] == ["Celeste", "Hades", "Hades"]
    first = briefs[1]
    assert first["platform"] == "PC" and first["completion_year"] == 2020 and first["score"] == 9
    assert briefs[2]["replay_of_id"] == original["id"] and briefs[2]["play_count"] == 2


def test_replay_root_survives_cycles(client):
    from backend.app.models.game import Game
    from backend.app.services.game_service import GameService
    session = _Session()
    a, b = Game(title="A"), Game(title="B")
    session.add_all([a, b])
    session.flush()
    a.replay_of_id, b.replay_of_id = b.id, a.id             # dado corrompido
    session.flush()
    assert GameService.replay_root(session, a) in (a, b)
    session.rollback()
    session.close()
