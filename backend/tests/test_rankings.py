import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base, get_db
from backend.app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


@event.listens_for(engine, "connect")
def _fk_on(dbapi_connection, _):
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


Session = sessionmaker(bind=engine)
client = TestClient(app)
API = "/api/v1/rankings/"


@pytest.fixture(autouse=True)
def db():
    previous = app.dependency_overrides.get(get_db)

    def override():
        s = Session()
        try:
            yield s
        finally:
            s.close()
    app.dependency_overrides[get_db] = override
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


def game(title, **fields):
    res = client.post("/api/v1/games/", json={"title": title, **fields})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def ranking(name, **fields):
    res = client.post(API, json={"name": name, **fields})
    assert res.status_code == 201, res.text
    return res.json()


def set_entries(rid, ids):
    return client.put(f"{API}{rid}/entries", json={"game_ids": ids})


@pytest.fixture
def library():
    soul = client.post("/api/v1/genres/", json={"name": "Soulslike", "color": "#00ff00"}).json()["id"]
    rpg = client.post("/api/v1/genres/", json={"name": "RPG", "color": "#ff0000"}).json()["id"]
    zelda = client.post("/api/v1/franchises/", json={"name": "Zelda"}).json()["id"]
    pc = client.post("/api/v1/platforms/", json={"name": "PC"}).json()["id"]
    return {
        "soul": soul, "rpg": rpg, "zelda": zelda, "pc": pc,
        "elden": game("Elden Ring", genre_ids=[rpg, soul], platform_id=pc, is_favorite=True),
        "ds": game("Dark Souls", genre_ids=[soul]),
        "botw": game("Breath of the Wild", franchise_id=zelda),
        "mario": game("Mario"),
    }


def test_create_list_and_get(library):
    top = ranking("Top de todos os tempos")
    souls = ranking("Top Soulslike", max_size=5, genre_id=library["soul"])
    assert top["max_size"] == 10 and top["filter_type"] is None and top["entries"] == []
    assert souls["filter_type"] == "genre" and souls["filter_label"] == "Soulslike"
    assert [r["name"] for r in client.get(API).json()] == ["Top de todos os tempos", "Top Soulslike"]
    assert client.get(f"{API}{souls['id']}").json()["max_size"] == 5


def test_filter_labels_for_franchise_and_platform(library):
    assert ranking("Zelda", franchise_id=library["zelda"])["filter_label"] == "Zelda"
    assert ranking("PC", platform_id=library["pc"])["filter_type"] == "platform"


@pytest.mark.parametrize("payload", [
    {"name": ""},
    {"name": "x", "max_size": 0},
    {"name": "x", "max_size": 51},
    {"name": "x", "genre_id": 1, "franchise_id": 1},
])
def test_create_validation(payload, library):
    assert client.post(API, json=payload).status_code == 422


def test_create_with_missing_filter_is_rejected():
    assert client.post(API, json={"name": "x", "genre_id": 999}).status_code == 422


def test_duplicate_name_conflicts_case_insensitive():
    ranking("Top 10")
    assert client.post(API, json={"name": " top 10 "}).status_code == 409
    other = ranking("Outro")
    assert client.put(f"{API}{other['id']}", json={"name": "TOP 10"}).status_code == 409


def test_missing_ranking_is_404():
    assert client.get(f"{API}999").status_code == 404
    assert client.put(f"{API}999", json={"name": "x"}).status_code == 404
    assert client.delete(f"{API}999").status_code == 404
    assert set_entries(999, []).status_code == 404


def test_set_entries_keeps_order_and_reports_rankings_by_game(library):
    top = ranking("Top")
    res = set_entries(top["id"], [library["mario"], library["elden"], library["ds"]])
    assert res.status_code == 200
    assert [g["title"] for g in res.json()["entries"]] == ["Mario", "Elden Ring", "Dark Souls"]
    souls = ranking("Souls", genre_id=library["soul"])
    set_entries(souls["id"], [library["elden"]])
    positions = client.get(f"{API}by-game/{library['elden']}").json()
    assert [(p["name"], p["position"]) for p in positions] == [("Top", 2), ("Souls", 1)]
    assert client.get(f"{API}by-game/{library['botw']}").json() == []


def test_set_entries_validation(library):
    small = ranking("Top 2", max_size=2)
    assert set_entries(small["id"], [library["elden"], library["elden"]]).status_code == 422
    assert set_entries(small["id"], [library["elden"], library["ds"], library["mario"]]).status_code == 422
    assert set_entries(small["id"], [999]).status_code == 422
    souls = ranking("Souls", genre_id=library["soul"])
    assert set_entries(souls["id"], [library["mario"]]).status_code == 422
    zelda = ranking("Zelda", franchise_id=library["zelda"])
    assert set_entries(zelda["id"], [library["botw"]]).status_code == 200
    assert set_entries(zelda["id"], [library["elden"]]).status_code == 422
    pc = ranking("PC", platform_id=library["pc"])
    assert set_entries(pc["id"], [library["elden"]]).status_code == 200
    assert set_entries(pc["id"], [library["ds"]]).status_code == 422
    assert set_entries(small["id"], []).json()["entries"] == []


def test_game_leaving_filter_stays_and_is_flagged(library):
    souls = ranking("Souls", genre_id=library["soul"])
    set_entries(souls["id"], [library["ds"], library["elden"]])
    client.put(f"/api/v1/games/{library['ds']}", json={"genre_ids": [library["rpg"]]})
    data = client.get(f"{API}{souls['id']}").json()
    assert data["out_of_filter_ids"] == [library["ds"]]
    # reordenar ainda funciona com o jogo que saiu do filtro
    assert set_entries(souls["id"], [library["elden"], library["ds"]]).status_code == 200


def test_update_shrinks_and_changes_filter(library):
    top = ranking("Top")
    set_entries(top["id"], [library["elden"], library["ds"], library["mario"]])
    res = client.put(f"{API}{top['id']}", json={"name": "Top 2", "max_size": 2})
    assert res.status_code == 200
    assert [g["title"] for g in res.json()["entries"]] == ["Elden Ring", "Dark Souls"]
    res = client.put(f"{API}{top['id']}", json={"genre_id": library["soul"]})
    assert res.json()["filter_type"] == "genre"
    res = client.put(f"{API}{top['id']}", json={"genre_id": None, "franchise_id": library["zelda"],
                                                "platform_id": None})
    body = res.json()
    assert body["genre_id"] is None and body["filter_label"] == "Zelda"
    assert set(body["out_of_filter_ids"]) == {library["elden"], library["ds"]}
    res = client.put(f"{API}{top['id']}", json={"name": None, "max_size": None})
    assert res.status_code == 200 and res.json()["name"] == "Top 2"
    assert client.put(f"{API}{top['id']}", json={"platform_id": 999}).status_code == 422


def test_reorder_and_delete(library):
    a, b, c = ranking("A"), ranking("B"), ranking("C")
    res = client.put(f"{API}order", json={"ranking_ids": [c["id"], a["id"], b["id"]]})
    assert [r["name"] for r in res.json()] == ["C", "A", "B"]
    assert client.put(f"{API}order", json={"ranking_ids": [a["id"]]}).status_code == 422
    assert client.delete(f"{API}{a['id']}").status_code == 204
    assert [r["name"] for r in client.get(API).json()] == ["C", "B"]
    assert ranking("D")["position"] == 3


def test_deleting_game_compacts_positions(library):
    top = ranking("Top")
    set_entries(top["id"], [library["mario"], library["elden"], library["ds"]])
    assert client.delete(f"/api/v1/games/{library['elden']}").status_code == 204
    data = client.get(f"{API}{top['id']}").json()
    assert [g["title"] for g in data["entries"]] == ["Mario", "Dark Souls"]
    assert client.get(f"{API}by-game/{library['ds']}").json()[0]["position"] == 2


def test_deleting_genre_removes_filter(library):
    souls = ranking("Souls", genre_id=library["soul"])
    set_entries(souls["id"], [library["ds"]])
    assert client.delete(f"/api/v1/genres/{library['soul']}").status_code in (200, 204)
    data = client.get(f"{API}{souls['id']}").json()
    assert data["genre_id"] is None and data["filter_type"] is None
    assert [g["title"] for g in data["entries"]] == ["Dark Souls"]


def test_ranking_entries_include_replay_counts(library):
    game("Dark Souls", play_type="Rejogada", replay_of_id=library["ds"])
    top = ranking("Top")
    data = set_entries(top["id"], [library["ds"]]).json()
    assert data["entries"][0]["replays_count"] == 1
