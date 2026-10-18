import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base, get_db
from backend.app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Session = sessionmaker(bind=engine)
client = TestClient(app)


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
    return res.json()


def setup_year():
    rpg = client.post("/api/v1/genres/", json={"name": "RPG", "color": "#ff0000"}).json()["id"]
    soul = client.post("/api/v1/genres/", json={"name": "Soulslike", "color": "#00ff00"}).json()["id"]
    pc = client.post("/api/v1/platforms/", json={"name": "PC"}).json()["id"]
    sw = client.post("/api/v1/platforms/", json={"name": "Switch"}).json()["id"]
    saga = client.post("/api/v1/franchises/", json={"name": "Souls"}).json()["id"]
    a = game("Elden Ring", status="Platinado", finish_date="2026-03-10", platinum_date="2026-04-01", played_hours=120,
             score=10, difficulty=9, genre_ids=[rpg, soul], platform_id=pc, developer="FromSoftware", franchise_id=saga)
    b = game("Hades", status="Zerado", finish_date="2026-03-20", played_hours=40, score=9, difficulty=6,
             genre_ids=[soul], platform_id=pc, developer="Supergiant", play_type="Rejogada", play_count=2)
    c = game("Mario", status="Zerado", finish_date="2026-07-02", played_hours=15, score=8, platform_id=sw,
             developer="Nintendo")
    d = game("Sem nota", status="Zerado", completion_year=2026, hltb_hours=10, developer="FromSoftware")
    game("Ano passado", status="Zerado", finish_date="2025-12-31", played_hours=5)
    game("Na fila", status="Fila", finish_date="2026-05-05")
    return a, b, c, d


def test_yearbook_details():
    a, b, c, d = setup_year()
    yb = client.get("/api/v1/stats/yearbook/2026").json()
    assert yb["total_games_finished"] == 4 and yb["previous_year_finished"] == 1
    assert yb["monthly_finished"] == [0, 0, 2, 0, 0, 0, 1, 0, 0, 0, 0, 0]  # "Sem nota" não tem data
    assert [(g["name"], g["count"], g["color"]) for g in yb["genres"]] == [("Soulslike", 2, "#00ff00"), ("RPG", 1, "#ff0000")]
    assert [(p["name"], p["count"], p["hours"]) for p in yb["platforms"]] == [
        ("PC", 2, 160.0), ("Switch", 1, 15.0), ("Sem plataforma", 1, 10.0)]
    assert yb["developers"][0] == {"name": "FromSoftware", "count": 2, "hours": 0.0, "color": None}
    assert yb["franchises"] == [{"name": "Souls", "count": 1, "hours": 0.0, "color": None}]
    assert yb["average_difficulty"] == 7.5 and yb["average_hours"] == 46.2 and yb["replays"] == 1
    assert yb["longest_game"]["title"] == "Elden Ring"
    assert yb["best_game"]["title"] == "Elden Ring" and yb["hardest_game"]["title"] == "Elden Ring"
    # Sem escolha: pódio sugerido pela nota (sem nota fica por último)
    assert [g["title"] for g in yb["top3"]] == ["Elden Ring", "Hades", "Mario"] and yb["top3_custom"] is False


def test_empty_year():
    yb = client.get("/api/v1/stats/yearbook/1999").json()
    assert yb["total_games_finished"] == 0 and yb["top3"] == [] and yb["average_hours"] is None
    assert yb["longest_game"] is None and yb["monthly_finished"] == [0] * 12


def test_choose_top3_and_validation():
    a, b, c, d = setup_year()
    res = client.put("/api/v1/stats/yearbook/2026/top3", json={"game_ids": [d["id"], c["id"]]})
    assert res.status_code == 200
    assert [g["title"] for g in res.json()["top3"]] == ["Sem nota", "Mario"] and res.json()["top3_custom"] is True
    assert [g["title"] for g in client.get("/api/v1/stats/yearbook/2026").json()["top3"]] == ["Sem nota", "Mario"]

    other = client.get("/api/v1/games/").json()
    last_year = next(g for g in other if g["title"] == "Ano passado")
    assert client.put("/api/v1/stats/yearbook/2026/top3", json={"game_ids": [last_year["id"]]}).status_code == 422
    assert client.put("/api/v1/stats/yearbook/2026/top3", json={"game_ids": [a["id"], a["id"]]}).status_code == 422
    assert client.put("/api/v1/stats/yearbook/2026/top3", json={"game_ids": [1, 2, 3, 4]}).status_code == 422

    # Um jogo escolhido que deixa de valer para o ano some do pódio; se nenhum sobra, volta a sugestão
    client.put(f"/api/v1/games/{d['id']}", json={"status": "Fila"})
    assert [g["title"] for g in client.get("/api/v1/stats/yearbook/2026").json()["top3"]] == ["Mario"]
    client.delete(f"/api/v1/games/{c['id']}")
    yb = client.get("/api/v1/stats/yearbook/2026").json()
    assert yb["top3_custom"] is False and [g["title"] for g in yb["top3"]] == ["Elden Ring", "Hades"]

    cleared = client.put("/api/v1/stats/yearbook/2026/top3", json={"game_ids": []}).json()
    assert cleared["top3_custom"] is False
