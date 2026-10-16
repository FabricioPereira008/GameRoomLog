import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import Base, get_db
from backend.app.models.game import Game
from backend.app.services import cover_service
from backend.app.services.notion_importer import NotionImporterService

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=_engine)
    session = _Session()
    app.dependency_overrides[get_db] = lambda: session
    yield session
    session.close()
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture(autouse=True)
def tmp_covers(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "COVERS_DIR", tmp_path)
    return tmp_path


def _img(size):
    buf = io.BytesIO()
    Image.new("RGB", size, "blue").save(buf, format="PNG")
    return buf.getvalue()


def test_process_cover_keeps_portrait_and_letterboxes_landscape():
    out, ext = cover_service.process_cover_image(_img((300, 450)))
    assert ext == ".jpg" and Image.open(io.BytesIO(out)).size == (300, 450)
    out, _ = cover_service.process_cover_image(_img((460, 215)))
    assert Image.open(io.BytesIO(out)).size == (600, 900)


def test_process_cover_invalid_bytes_returns_original():
    assert cover_service.process_cover_image(b"junk") == (b"junk", ".jpg")


def test_steam_candidate_urls_contains_app_id():
    urls = cover_service.steam_candidate_urls(123)
    assert urls and all("/123/" in u for u in urls)


def test_save_cover_bytes_writes_file(tmp_covers):
    name = cover_service.save_cover_bytes(_img((300, 450)))
    assert (tmp_covers / name).exists()


def test_auto_cover_endpoint(monkeypatch, db):
    client = TestClient(app)

    async def fake_find(title, api_key=None):
        return ("x.jpg", "Fake") if title == "Zelda" else None

    monkeypatch.setattr("backend.app.api.v1.endpoints.uploads.find_cover", fake_find)
    ok = client.post("/api/v1/uploads/auto-cover", json={"title": "Zelda"})
    assert ok.status_code == 200 and ok.json()["source"] == "Fake"
    assert client.post("/api/v1/uploads/auto-cover", json={"title": "Nada"}).status_code == 404
    assert client.post("/api/v1/uploads/auto-cover", json={"title": "  "}).status_code == 400

    game = client.post("/api/v1/games/", json={"title": "Zelda"}).json()
    res = client.post(f"/api/v1/uploads/auto-cover-game/{game['id']}", json={}).json()
    assert res["success"] is True and res["filename"] == "x.jpg"
    miss = client.post("/api/v1/games/", json={"title": "Nada"}).json()
    assert client.post(f"/api/v1/uploads/auto-cover-game/{miss['id']}", json={}).json()["success"] is False


def test_import_notion_folder_creates_then_updates(tmp_path, db):
    csv_file = tmp_path / "Jogos_all.csv"
    csv_file.write_text(
        "Jogo,Status,Plataforma,Gênero,Nota,Horas Jogadas\n"
        "Hades,Zerado,PC,Roguelike,9,30\n"
        ",Zerado,PC,RPG,5,1\n",
        encoding="utf-8",
    )
    first = NotionImporterService.import_notion_folder(db, str(tmp_path), auto_fetch_covers=False)
    assert first["imported"] == 1 and first["updated"] == 0
    csv_file.write_text("Jogo,Status,Plataforma,Nota\nHades,Platinado,PC,10\n", encoding="utf-8")
    second = NotionImporterService.import_notion_folder(db, str(tmp_path), auto_fetch_covers=False)
    assert second["updated"] == 1
    game = db.query(Game).filter(Game.title == "Hades").one()
    assert game.score == 10


def test_import_endpoint_errors(db, tmp_path):
    client = TestClient(app)
    assert client.post("/api/v1/imports/notion", json={"folder_path": "/nao/existe"}).status_code == 400
    assert client.post("/api/v1/imports/notion", json={"folder_path": str(tmp_path)}).status_code == 400
