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
    assert "GameRoomLog API" in response.json()["message"]

def test_create_and_list_genre():
    res = client.post("/api/v1/genres/", json={"name": "RPG", "color": "#E53E3E"})
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "RPG"
    assert data["id"] is not None

    # Testar update PUT
    put_res = client.put(f"/api/v1/genres/{data['id']}", json={"name": "JRPG", "color": "#9F7AEA"})
    assert put_res.status_code == 200
    assert put_res.json()["name"] == "JRPG"

    list_res = client.get("/api/v1/genres/")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

def test_create_and_list_platform():
    res = client.post("/api/v1/platforms/", json={"name": "Switch 2", "icon_name": "switch"})
    assert res.status_code == 201
    plat_id = res.json()["id"]

    # Testar update PUT
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

    put_res = client.put(f"/api/v1/developers/{dev_id}", json={"name": "Nintendo EPD"})
    assert put_res.status_code == 200
    assert put_res.json()["name"] == "Nintendo EPD"

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
    created = game_res.json()
    assert created["title"] == "Mortal Shell"
    assert created["platform"]["name"] == "PC"
    assert created["score"] == 7.5

    # Criar segundo jogo Platinado
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

    # Verificar Anuário de 2026
    yb_res = client.get("/api/v1/stats/yearbook/2026")
    assert yb_res.status_code == 200
    yb = yb_res.json()
    assert yb["year"] == 2026
    assert yb["total_games_finished"] == 2
    assert yb["total_platinums"] == 1
    assert yb["total_hours_played"] == 39.0
    assert yb["average_score"] == 8.5  # (7.5 + 9.5) / 2
