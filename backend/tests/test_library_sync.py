import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.models.game import Game
from backend.app.models.store_link import GameStoreLink
from backend.app.services.library import PROVIDERS, LibraryEntry, LibraryProviderError, register_provider
from backend.app.services.library_service import looks_like_non_game, normalize_title

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


class FakeProvider:
    store = "fake"

    def __init__(self, entries):
        self._entries = entries

    def fetch(self):
        return self._entries


class BrokenProvider:
    store = "broken"

    def fetch(self):
        raise LibraryProviderError("Perfil privado")


class CrashingProvider:
    store = "crash"

    def fetch(self):
        raise RuntimeError("key=SEGREDO")


@pytest.fixture(autouse=True)
def setup():
    # Override só durante este módulo: não pode vazar para os demais testes de API
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    saved = dict(PROVIDERS)
    PROVIDERS.clear()
    yield
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
    PROVIDERS.clear()
    PROVIDERS.update(saved)
    Base.metadata.drop_all(bind=engine)


def use(*entries):
    register_provider("fake", lambda: FakeProvider(list(entries)))


def e(ext, title, hours=None, is_game=True):
    return LibraryEntry("fake", ext, title, hours, is_game)


def scan(**body):
    res = client.post("/api/v1/library/scan", json=body)
    assert res.status_code == 200, res.text
    return res.json()


def test_normalize_title():
    assert normalize_title("  Pokémon™: Edição – Vermelha!® ") == "pokemon edicao vermelha"
    assert normalize_title("™®") == ""


def test_normalize_title_ignores_apostrophes_and_ampersand():
    assert normalize_title("Dragon's Dogma 2") == normalize_title("Dragons Dogma 2") == normalize_title("Dragon’s Dogma 2")
    assert normalize_title("Ratchet & Clank") == normalize_title("Ratchet and Clank")


def test_non_game_heuristic():
    assert looks_like_non_game("Proton 9.0")
    assert looks_like_non_game("Hades Soundtrack")
    assert not looks_like_non_game("Hades")


def test_scan_lists_new_games_sorted_and_filters_non_games():
    use(e("2", "Zelda"), e("1", "Hades", 12.5), e("3", "Proton 9"), e("4", "Some DLC", is_game=False))
    data = scan()
    assert [c["title"] for c in data["candidates"]] == ["Hades", "Zelda"]
    assert data["candidates"][0]["played_hours"] == 12.5
    all_data = scan(include_all=True)
    assert len(all_data["candidates"]) == 4


def test_scan_dedups_repeated_entries():
    use(e("1", "Hades"), e("1", "Hades"))
    assert len(scan()["candidates"]) == 1


def test_scan_unknown_store_is_422():
    use(e("1", "Hades"))
    res = client.post("/api/v1/library/scan", json={"stores": ["nope"]})
    assert res.status_code == 422


def test_scan_store_errors_do_not_block_other_stores():
    use(e("1", "Hades"))
    register_provider("broken", BrokenProvider)
    register_provider("crash", CrashingProvider)
    data = scan()
    assert [c["title"] for c in data["candidates"]] == ["Hades"]
    msgs = {x["store"]: x["message"] for x in data["errors"]}
    assert msgs["broken"] == "Perfil privado"
    assert "SEGREDO" not in msgs["crash"]


def test_scan_only_selected_stores():
    use(e("1", "Hades"))
    register_provider("broken", BrokenProvider)
    data = scan(stores=["fake"])
    assert data["errors"] == []


def test_import_creates_game_with_defaults_and_link_then_scan_hides_it():
    use(e("1", "Hades", 12.5))
    item = {"store": "fake", "external_id": "1", "title": "Hades", "played_hours": 12.5}
    res = client.post("/api/v1/library/import", json={"items": [item]})
    assert res.status_code == 201
    body = res.json()
    game = body["imported"][0]
    assert game["title"] == "Hades"
    assert game["platform"]["name"] == "PC"
    assert game["format"] == "Digital"
    assert game["status"] == "Disponível"
    assert game["played_hours"] == 12.5
    assert body["skipped"] == 0
    assert scan()["candidates"] == []
    # idempotente
    again = client.post("/api/v1/library/import", json={"items": [item]}).json()
    assert again["imported"] == [] and again["skipped"] == 1


def test_import_reuses_existing_pc_platform_and_defaults_hours():
    client.post("/api/v1/platforms/", json={"name": "pc"})
    item = {"store": "fake", "external_id": "9", "title": "Celeste"}
    res = client.post("/api/v1/library/import", json={"items": [item]}).json()
    assert res["imported"][0]["played_hours"] == 0
    assert len(client.get("/api/v1/platforms/").json()) == 1


def test_import_validation_errors():
    assert client.post("/api/v1/library/import", json={"items": []}).status_code == 422
    bad = {"store": "fake", "external_id": "1", "title": ""}
    assert client.post("/api/v1/library/import", json={"items": [bad]}).status_code == 422


def test_link_existing_game_hides_candidate_and_clears_ignored():
    use(e("1", "Hades"), e("2", "Zelda"))
    item = {"store": "fake", "external_id": "1", "title": "Hades"}
    client.post("/api/v1/library/ignored", json={"items": [item]})
    game_id = client.post("/api/v1/games/", json={"title": "Hades (meu título)"}).json()["id"]
    link = {"game_id": game_id, "store": "fake", "external_id": "1"}
    res = client.post("/api/v1/library/link", json=link)
    assert res.status_code == 201
    assert res.json()["game_id"] == game_id and res.json()["id"]
    assert client.get("/api/v1/library/ignored").json() == []
    assert [c["title"] for c in scan()["candidates"]] == ["Zelda"]
    # idempotente para o mesmo jogo
    assert client.post("/api/v1/library/link", json=link).status_code == 201
    db = TestingSessionLocal()
    assert db.query(GameStoreLink).filter_by(external_id="1").count() == 1
    db.close()


def test_link_errors():
    game_id = client.post("/api/v1/games/", json={"title": "Hades"}).json()["id"]
    other_id = client.post("/api/v1/games/", json={"title": "Celeste"}).json()["id"]
    link = {"game_id": game_id, "store": "fake", "external_id": "1"}
    assert client.post("/api/v1/library/link", json={**link, "game_id": 9999}).status_code == 404
    assert client.post("/api/v1/library/link", json=link).status_code == 201
    assert client.post("/api/v1/library/link", json={**link, "game_id": other_id}).status_code == 409
    assert client.post("/api/v1/library/link", json={**link, "store": ""}).status_code == 422
    assert client.post("/api/v1/library/link", json={"store": "fake", "external_id": "1"}).status_code == 422


def test_manual_game_is_auto_linked_by_normalized_title():
    client.post("/api/v1/games/", json={"title": "Pokémon Vermelho"})
    use(e("7", "POKEMON vermelho™"))
    data = scan()
    assert data["candidates"] == [] and data["auto_linked"] == 1
    db = TestingSessionLocal()
    assert db.query(GameStoreLink).filter_by(external_id="7").count() == 1
    db.close()
    assert scan()["auto_linked"] == 0  # já vinculado


def test_ambiguous_title_is_listed_and_not_linked():
    client.post("/api/v1/games/", json={"title": "Doom"})
    client.post("/api/v1/games/", json={"title": "DOOM!"})
    use(e("5", "Doom"))
    data = scan()
    assert data["auto_linked"] == 0
    assert data["candidates"][0]["ambiguous"] is True


def test_ignore_flow():
    use(e("1", "Hades"), e("2", "Zelda"))
    item = {"store": "fake", "external_id": "1", "title": "Hades"}
    assert client.post("/api/v1/library/ignored", json={"items": [item]}).json() == {"ignored": 1}
    assert client.post("/api/v1/library/ignored", json={"items": [item]}).json() == {"ignored": 0}
    assert [c["title"] for c in scan()["candidates"]] == ["Zelda"]

    ignored = client.get("/api/v1/library/ignored").json()
    assert len(ignored) == 1 and ignored[0]["title"] == "Hades"
    assert client.delete(f"/api/v1/library/ignored/{ignored[0]['id']}").status_code == 204
    assert len(scan()["candidates"]) == 2
    assert client.delete("/api/v1/library/ignored/999").status_code == 404
    assert client.post("/api/v1/library/ignored", json={"items": []}).status_code == 422


def test_importing_an_ignored_game_removes_it_from_ignored():
    item = {"store": "fake", "external_id": "1", "title": "Hades"}
    client.post("/api/v1/library/ignored", json={"items": [item]})
    client.post("/api/v1/library/import", json={"items": [item]})
    assert client.get("/api/v1/library/ignored").json() == []


def test_deleting_game_removes_its_links():
    item = {"store": "fake", "external_id": "1", "title": "Hades"}
    game_id = client.post("/api/v1/library/import", json={"items": [item]}).json()["imported"][0]["id"]
    assert client.delete(f"/api/v1/games/{game_id}").status_code in (200, 204)
    db = TestingSessionLocal()
    assert db.query(GameStoreLink).count() == 0
    assert db.query(Game).count() == 0
    db.close()
