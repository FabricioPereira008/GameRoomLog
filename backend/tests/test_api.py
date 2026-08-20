import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.main import app
from backend.app.core.database import Base, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["version"] == "0.1.0"

def test_create_and_list_genre_details():
    res = client.post("/api/v1/genres/", json={"name": "RPG", "color": "#E53E3E"})
    assert res.status_code == 201
    genre_id = res.json()["id"]

    # Criar um jogo nesse gênero
    client.post("/api/v1/games/", json={
        "title": "Chrono Trigger",
        "genre_ids": [genre_id],
        "status": "Zerado",
        "played_hours": 25.0
    })

    # Testar detalhes do gênero
    detail_res = client.get(f"/api/v1/genres/{genre_id}/details")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["name"] == "RPG"
    assert detail["total_games"] == 1
    assert detail["total_hours_played"] == 25.0

def test_create_and_list_platform():
    res = client.post("/api/v1/platforms/", json={"name": "Switch 2", "icon_name": "switch"})
    assert res.status_code == 201
    plat_id = res.json()["id"]

    put_res = client.put(f"/api/v1/platforms/{plat_id}", json={"name": "Nintendo Switch 2"})
    assert put_res.status_code == 200
    assert put_res.json()["name"] == "Nintendo Switch 2"

def test_developer_crud():
    res = client.post("/api/v1/developers/", json={"name": "Nintendo"})
    assert res.status_code == 201
    dev_id = res.json()["id"]

    list_res = client.get("/api/v1/developers/")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

def test_create_game_and_verify_yearbook():
    p_res = client.post("/api/v1/platforms/", json={"name": "PC"})
    plat_id = p_res.json()["id"]

    g_res = client.post("/api/v1/genres/", json={"name": "Ação/Aventura"})
    genre_id = g_res.json()["id"]

    game_payload = {
        "title": "Mortal Shell",
        "developer": "Cold Symmetry",
        "platform_id": plat_id,
        "genre_ids": [genre_id],
        "status": "Zerado",
        "hltb_hours": 8.0,
        "played_hours": 8.0,
        "score": 7.5,
        "difficulty": 7.0,
        "finish_date": "2026-02-15",
        "completion_year": 2026,
        "play_type": "Primeira Jogada"
    }
    game_res = client.post("/api/v1/games/", json=game_payload)
    assert game_res.status_code == 201

    game2_payload = {
        "title": "Zelda: Ocarina of Time",
        "developer": "Nintendo",
        "status": "Platinado",
        "hltb_hours": 30.0,
        "played_hours": 31.0,
        "score": 9.5,
        "difficulty": 6.0,
        "finish_date": "2026-01-20",
        "completion_year": 2026
    }
    client.post("/api/v1/games/", json=game2_payload)

    yb_res = client.get("/api/v1/stats/yearbook/2026")
    assert yb_res.status_code == 200
    yb = yb_res.json()
    assert yb["total_games_finished"] == 2
    assert yb["total_platinums"] == 1
    assert yb["total_hours_played"] == 39.0
