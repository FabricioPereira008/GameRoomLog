import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.main import app
from backend.app.core.database import Base, get_db

# Criar banco SQLite em memória compartilhada com StaticPool para testes
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

    list_res = client.get("/api/v1/genres/")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

def test_create_and_list_platform():
    res = client.post("/api/v1/platforms/", json={"name": "Switch 2", "icon_name": "switch"})
    assert res.status_code == 201
    assert res.json()["name"] == "Switch 2"

def test_create_game_and_verify_yearbook():
    # 1. Criar plataforma e gênero
    p_res = client.post("/api/v1/platforms/", json={"name": "PC"})
    plat_id = p_res.json()["id"]

    g_res = client.post("/api/v1/genres/", json={"name": "Ação/Aventura"})
    genre_id = g_res.json()["id"]

    # 2. Criar jogo Zerado em 2026
    game_payload = {
        "title": "Mortal Shell",
        "developer": "Cold Symmetry",
        "platform_id": plat_id,
        "genre_ids": [genre_id],
        "status": "Zerado",
        "hltb_hours": 8.0,
        "played_hours": 8.0,
        "score": 7.0,
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
    assert len(created["genres"]) == 1

    # 3. Criar segundo jogo Platinado em 2026
    game2_payload = {
        "title": "Zelda: Ocarina of Time",
        "developer": "Nintendo",
        "status": "Platinado",
        "hltb_hours": 30.0,
        "played_hours": 31.0,
        "score": 10.0,
        "difficulty": 6.0,
        "finish_date": "2026-01-20",
        "completion_year": 2026
    }
    client.post("/api/v1/games/", json=game2_payload)

    # 4. Criar terceiro jogo na Fila (não zerado)
    game3_payload = {
        "title": "Super Mario Odyssey",
        "status": "Fila",
        "hltb_hours": 20.0
    }
    client.post("/api/v1/games/", json=game3_payload)

    # 5. Testar Anuário de 2026
    yb_res = client.get("/api/v1/stats/yearbook/2026")
    assert yb_res.status_code == 200
    yb = yb_res.json()
    assert yb["year"] == 2026
    assert yb["total_games_finished"] == 2
    assert yb["total_platinums"] == 1
    assert yb["total_hours_played"] == 39.0  # 8 + 31
    assert yb["average_score"] == 8.5  # (7 + 10) / 2

    # 6. Testar Overall Stats
    overall_res = client.get("/api/v1/stats/overall")
    assert overall_res.status_code == 200
    overall = overall_res.json()
    assert overall["status_counts"]["zerados"] == 1
    assert overall["status_counts"]["platinados"] == 1
    assert overall["status_counts"]["fila"] == 1
    assert overall["status_counts"]["total"] == 3
    assert 2026 in overall["available_years"]
