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
    assert response.json()["version"] == "0.2.2"

def test_genre_crud_and_details():
    # 1. Create
    res = client.post("/api/v1/genres/", json={"name": "RPG", "color": "#E53E3E"})
    assert res.status_code == 201
    genre_id = res.json()["id"]

    # 2. Read list
    list_res = client.get("/api/v1/genres/")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    # 3. Read details
    single_res = client.get(f"/api/v1/genres/{genre_id}/details")
    assert single_res.status_code == 200
    assert single_res.json()["name"] == "RPG"
    assert single_res.json()["total_games"] == 0

    # 4. Update
    put_res = client.put(f"/api/v1/genres/{genre_id}", json={"name": "JRPG", "color": "#C53030"})
    assert put_res.status_code == 200
    assert put_res.json()["name"] == "JRPG"

    # 5. Delete
    del_res = client.delete(f"/api/v1/genres/{genre_id}")
    assert del_res.status_code == 204

    # 6. Verify Not Found after deletion
    not_found = client.get(f"/api/v1/genres/{genre_id}/details")
    assert not_found.status_code == 404

def test_platform_crud():
    res = client.post("/api/v1/platforms/", json={"name": "Switch 2", "icon_name": "switch"})
    assert res.status_code == 201
    plat_id = res.json()["id"]

    # Read details
    detail_res = client.get(f"/api/v1/platforms/{plat_id}/details")
    assert detail_res.status_code == 200
    assert detail_res.json()["name"] == "Switch 2"

    # Update
    put_res = client.put(f"/api/v1/platforms/{plat_id}", json={"name": "Nintendo Switch 2", "icon_name": "switch"})
    assert put_res.status_code == 200
    assert put_res.json()["name"] == "Nintendo Switch 2"

    # Delete
    del_res = client.delete(f"/api/v1/platforms/{plat_id}")
    assert del_res.status_code == 204

    # Verify Not Found
    not_found = client.get(f"/api/v1/platforms/{plat_id}/details")
    assert not_found.status_code == 404

def test_franchise_crud_and_details():
    res = client.post("/api/v1/franchises/", json={"name": "Final Fantasy"})
    assert res.status_code == 201
    f_id = res.json()["id"]

    put_res = client.put(f"/api/v1/franchises/{f_id}", json={"name": "Final Fantasy Series"})
    assert put_res.status_code == 200
    assert put_res.json()["name"] == "Final Fantasy Series"

    detail_res = client.get(f"/api/v1/franchises/{f_id}/details")
    assert detail_res.status_code == 200
    assert detail_res.json()["total_games"] == 0

    del_res = client.delete(f"/api/v1/franchises/{f_id}")
    assert del_res.status_code == 204

    not_found = client.get(f"/api/v1/franchises/{f_id}/details")
    assert not_found.status_code == 404

def test_developer_crud():
    res = client.post("/api/v1/developers/", json={"name": "Nintendo"})
    assert res.status_code == 201
    dev_id = res.json()["id"]

    list_res = client.get("/api/v1/developers/")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    del_res = client.delete(f"/api/v1/developers/{dev_id}")
    assert del_res.status_code == 204

def test_game_full_crud_and_negative_cases():
    # 1. Negative: Game 9999 not found
    assert client.get("/api/v1/games/9999").status_code == 404
    assert client.put("/api/v1/games/9999", json={"title": "Ghost"}).status_code == 404
    assert client.delete("/api/v1/games/9999").status_code == 404

    # 2. Create valid game
    game_payload = {
        "title": "Metroid Prime",
        "developer": "Retro Studios",
        "status": "Zerado",
        "score": 9.5,
        "played_hours": 14.0
    }
    create_res = client.post("/api/v1/games/", json=game_payload)
    assert create_res.status_code == 201
    game_id = create_res.json()["id"]
    assert create_res.json()["title"] == "Metroid Prime"

    # 3. Get single game
    get_res = client.get(f"/api/v1/games/{game_id}")
    assert get_res.status_code == 200
    assert get_res.json()["score"] == 9.5

    # 4. Update game
    update_res = client.put(f"/api/v1/games/{game_id}", json={
        "status": "Platinado",
        "score": 10.0,
        "played_hours": 20.0
    })
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "Platinado"
    assert update_res.json()["score"] == 10.0

    # 5. Delete game
    del_res = client.delete(f"/api/v1/games/{game_id}")
    assert del_res.status_code == 204

    # 6. Verify 404 after deletion
    assert client.get(f"/api/v1/games/{game_id}").status_code == 404

def test_overall_stats_and_yearbook():
    p_res = client.post("/api/v1/platforms/", json={"name": "PC"})
    plat_id = p_res.json()["id"]

    client.post("/api/v1/games/", json={
        "title": "Mortal Shell",
        "platform_id": plat_id,
        "status": "Zerado",
        "played_hours": 8.0,
        "score": 7.5,
        "finish_date": "2026-02-15",
        "completion_year": 2026
    })

    client.post("/api/v1/games/", json={
        "title": "Zelda: Ocarina of Time",
        "status": "Platinado",
        "played_hours": 31.0,
        "score": 9.5,
        "finish_date": "2026-01-20",
        "completion_year": 2026
    })

    # Test Yearbook
    yb_res = client.get("/api/v1/stats/yearbook/2026")
    assert yb_res.status_code == 200
    yb = yb_res.json()
    assert yb["total_games_finished"] == 2
    assert yb["total_platinums"] == 1
    assert yb["total_hours_played"] == 39.0

    # Test Overall stats
    overall_res = client.get("/api/v1/stats/overall")
    assert overall_res.status_code == 200
    overall = overall_res.json()
    assert overall["status_counts"]["total"] == 2
    assert overall["status_counts"]["zerados"] == 1
    assert overall["status_counts"]["platinados"] == 1
    assert overall["total_hours"] == 39.0
