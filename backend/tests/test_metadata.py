"""Busca automática de dados do jogo: IGDB, Steam, HowLongToBeat e endpoints /metadata."""
import asyncio
import types

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.developer import Developer
from backend.app.models.franchise import Franchise
from backend.app.models.genre import Genre
from backend.app.models.platform import Platform
from backend.app.services import metadata_service as ms

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

CREDS = {"igdb_client_id": "cid", "igdb_client_secret": "secret"}

HOLLOW = {
    "id": 1, "name": "Hollow Knight", "first_release_date": 1487894400,
    "platforms": [{"name": "PC (Microsoft Windows)"}, {"name": "Nintendo Switch"}, {"name": "Xbox One"}],
    "genres": [{"name": "Platform"}, {"name": "Adventure"}, {"name": "Indie"}],
    "themes": [{"name": "Action"}, {"name": "Fantasy"}],
    "keywords": [{"name": "metroidvania"}, {"name": "2d"}],
    "involved_companies": [{"developer": False, "company": {"name": "Publisher Co"}},
                           {"developer": True, "company": {"name": "Team Cherry Pty Ltd"}}],
    "franchises": [], "collections": [{"name": "hollow knight"}],
}


@pytest.fixture
def db():
    Base.metadata.create_all(bind=_engine)
    session = _Session()
    app.dependency_overrides[get_db] = lambda: session
    yield session
    app.dependency_overrides.pop(get_db, None)
    session.close()
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    """Sem credenciais do .env, sem token em cache e sem HowLongToBeat de verdade."""
    monkeypatch.setattr(settings, "IGDB_CLIENT_ID", "")
    monkeypatch.setattr(settings, "IGDB_CLIENT_SECRET", "")
    ms._token_cache.clear()

    async def no_hltb(title):
        return None
    monkeypatch.setattr(ms, "hltb_main_story", no_hltb)


def _transport(igdb_games=None, ttb=None, token_status=200, igdb_status=200, steam_search=None, steam_app=None,
               calls=None):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if calls is not None:
            calls.append(url)
        if url.startswith(ms.TWITCH_TOKEN_URL):
            return httpx.Response(token_status, json={"access_token": "tok", "expires_in": 3600})
        if url.startswith(f"{ms.IGDB_URL}/games"):
            return httpx.Response(igdb_status, json=igdb_games or [])
        if url.startswith(f"{ms.IGDB_URL}/game_time_to_beats"):
            return httpx.Response(200, json=ttb or [])
        if url.startswith(ms.STEAM_SEARCH_URL):
            return httpx.Response(200, json={"items": steam_search or []})
        if url.startswith(ms.APP_DETAILS_URL):
            return httpx.Response(200, json=steam_app or {})
        return httpx.Response(404)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _run(coro):
    return asyncio.run(coro)


# --- mapeamento de gêneros ---

@pytest.mark.parametrize("kwargs, expected", [
    ({"genres": ["Platform", "Adventure"], "themes": ["Action"], "keywords": ["metroidvania"]},
     ["Metroidvania", "Plataforma"]),
    ({"genres": ["Role-playing (RPG)", "Adventure"], "themes": ["Action"]}, ["RPG de Ação", "Ação e Aventura"]),
    ({"genres": ["Role-playing (RPG)", "Turn-based strategy (TBS)"]}, ["RPG por Turnos", "Estratégia"]),
    ({"genres": ["Shooter"], "perspectives": ["First person"], "themes": ["Horror"]}, ["FPS", "Terror"]),
    ({"genres": ["Hack and slash/Beat 'em up"], "keywords": ["roguelite"]}, ["Roguelike", "Hack and Slash"]),
    ({"genres": ["Action", "Adventure"]}, ["Ação e Aventura"]),  # Steam: o composto cobre os dois
    ({"genres": ["Indie", "Casual"]}, []),
])
def test_map_genres(kwargs, expected):
    assert ms.map_genres(kwargs.pop("genres"), **kwargs) == expected


def test_known_names_matching(db):
    db.add_all([Developer(name="Team Cherry"), Franchise(name="Hollow Knight"),
                Genre(name="Metroidvania"), Platform(name="PC"), Platform(name="Switch")])
    db.commit()
    known = ms.load_known_names(db)
    assert ms._known_platforms(["Nintendo Switch", "PC (Microsoft Windows)", "Linux", "Xbox One"], known) == \
        ["Switch", "PC"]
    assert ms._known_franchise("hollow knight", known) == "Hollow Knight"
    assert ms._known_franchise("Celeste", known) == "Celeste"
    assert ms._known_franchise(None, known) is None
    assert ms._known_genres(["metroidvania", "Plataforma"], known) == ["Metroidvania", "Plataforma"]


# --- busca de candidatos ---

def test_search_uses_igdb_with_credentials():
    calls = []
    client = _transport(igdb_games=[HOLLOW, {"id": 2, "name": "Hollow Knight: Silksong"}], calls=calls)
    res = _run(ms.search_candidates("Hollow Knight", "cid", "secret", client=client))
    assert res.warning is None
    assert [(c.source, c.source_id, c.year) for c in res.candidates] == [("igdb", "1", 2017), ("igdb", "2", None)]
    assert res.candidates[0].platforms[0] == "PC (Microsoft Windows)"
    # token reaproveitado na segunda busca
    _run(ms.search_candidates("Hollow Knight", "cid", "secret", client=_transport(igdb_games=[HOLLOW], calls=calls)))
    assert sum(ms.TWITCH_TOKEN_URL in c for c in calls) == 1


def test_search_without_credentials_uses_steam():
    client = _transport(steam_search=[{"id": 367520, "name": "Hollow Knight"},
                                      {"id": 598190, "name": "Hollow Knight - Official Soundtrack"}])
    res = _run(ms.search_candidates("Hollow Knight", client=client))
    assert [(c.source, c.source_id, c.platforms) for c in res.candidates] == [("steam", "367520", ["PC"])]


def test_search_falls_back_to_steam_with_warning_when_credentials_rejected():
    client = _transport(token_status=400, steam_search=[{"id": 10, "name": "Celeste"}])
    res = _run(ms.search_candidates("Celeste", "cid", "bad", client=client))
    assert res.candidates[0].source == "steam" and "credenciais" in res.warning


def test_search_falls_back_to_steam_when_igdb_finds_nothing():
    client = _transport(igdb_games=[], steam_search=[{"id": 10, "name": "Celeste"}])
    res = _run(ms.search_candidates("Celeste", "cid", "secret", client=client))
    assert res.candidates[0].source == "steam" and res.warning is None


def test_search_not_found():
    with pytest.raises(ms.MetadataNotFoundError):
        _run(ms.search_candidates("Nada", client=_transport()))


def test_igdb_search_escapes_quotes():
    assert ms._igdb_search_body('Say "hi"').startswith('search "Say \\"hi\\""')


def test_resolve_credentials_from_env(monkeypatch):
    assert ms.resolve_credentials(None, None) is None
    monkeypatch.setattr(settings, "IGDB_CLIENT_ID", "env-id")
    monkeypatch.setattr(settings, "IGDB_CLIENT_SECRET", "env-secret")
    assert ms.resolve_credentials(None, " ") == ("env-id", "env-secret")
    assert ms.resolve_credentials("mine", "s") == ("mine", "s")


# --- detalhes ---

def test_igdb_details_with_ttb_fallback(db):
    db.add_all([Developer(name="Team Cherry"), Platform(name="PC"), Platform(name="Switch"),
                Franchise(name="Hollow Knight")])
    db.commit()
    client = _transport(igdb_games=[HOLLOW], ttb=[{"normally": 97200}])
    p = _run(ms.fetch_details("igdb", "1", "Hollow Knight", ms.load_known_names(db), "cid", "secret", client=client))
    assert p.developer == "Team Cherry"  # sufixo jurídico removido e grafia do cadastro
    assert p.franchise == "Hollow Knight" and p.year == 2017
    assert p.genres == ["Metroidvania", "Plataforma"]
    assert p.platforms == ["PC", "Switch"]
    assert (p.hltb_hours, p.hltb_source) == (27.0, "IGDB")


def test_hltb_takes_priority(monkeypatch):
    async def hltb(title):
        return 26.9 if title == "Hollow Knight" else None
    monkeypatch.setattr(ms, "hltb_main_story", hltb)
    client = _transport(igdb_games=[HOLLOW], ttb=[{"normally": 97200}])
    p = _run(ms.fetch_details("igdb", "1", "Hollow Knight", ms.KnownNames(), "cid", "secret", client=client))
    assert (p.hltb_hours, p.hltb_source) == (26.9, "HowLongToBeat")


def test_igdb_details_errors():
    with pytest.raises(ms.MetadataSourceError):  # sem credenciais
        _run(ms.fetch_details("igdb", "1", "X", ms.KnownNames(), client=_transport()))
    with pytest.raises(ms.MetadataNotFoundError):
        _run(ms.fetch_details("igdb", "1; fields *", "X", ms.KnownNames(), "c", "s", client=_transport()))
    with pytest.raises(ms.MetadataNotFoundError):
        _run(ms.fetch_details("igdb", "1", "X", ms.KnownNames(), "c", "s", client=_transport(igdb_games=[])))
    with pytest.raises(ms.MetadataSourceError):
        _run(ms.fetch_details("igdb", "1", "X", ms.KnownNames(), "c", "s", client=_transport(igdb_status=429)))


def test_steam_details(db):
    db.add_all([Platform(name="PC"), Genre(name="Ação e Aventura")])
    db.commit()
    app_data = {"367520": {"success": True, "data": {
        "name": "Hollow Knight", "developers": ["Team Cherry"], "release_date": {"date": "24 Feb, 2017"},
        "genres": [{"description": "Action"}, {"description": "Adventure"}, {"description": "Indie"}]}}}
    p = _run(ms.fetch_details("steam", "367520", "Hollow Knight", ms.load_known_names(db),
                              client=_transport(steam_app=app_data)))
    assert (p.developer, p.year, p.genres, p.platforms) == ("Team Cherry", 2017, ["Ação e Aventura"], ["PC"])
    assert p.hltb_hours is None and p.franchise is None


def test_steam_details_not_found():
    with pytest.raises(ms.MetadataNotFoundError):
        _run(ms.fetch_details("steam", "1", "X", ms.KnownNames(), client=_transport(steam_app={"1": {"success": False}})))
    with pytest.raises(ms.MetadataNotFoundError):
        _run(ms.fetch_details("steam", "abc", "X", ms.KnownNames(), client=_transport()))


def test_network_error_becomes_source_error():
    def boom(request):
        raise httpx.ConnectError("offline")
    client = httpx.AsyncClient(transport=httpx.MockTransport(boom))
    with pytest.raises(ms.MetadataSourceError):
        _run(ms.fetch_details("steam", "1", "X", ms.KnownNames(), client=client))
    with pytest.raises(ms.MetadataSourceError):
        _run(ms.search_candidates("X", client=httpx.AsyncClient(transport=httpx.MockTransport(boom))))


# --- HowLongToBeat (lib simulada) ---

def _fake_hltb(monkeypatch, results=None, error=None):
    import sys

    class FakeHLTB:
        async def async_search(self, title):
            if error:
                raise error
            return results

    monkeypatch.setitem(sys.modules, "howlongtobeatpy", types.SimpleNamespace(HowLongToBeat=FakeHLTB))


def _entry(main, sim):
    return types.SimpleNamespace(main_story=main, similarity=sim)


def test_hltb_main_story(monkeypatch):
    monkeypatch.undo()  # volta a função real (a fixture autouse a desliga)
    _fake_hltb(monkeypatch, [_entry(12.57, 0.7), _entry(26.98, 1.0), _entry(0, 1.0)])
    assert _run(ms.hltb_main_story("Hollow Knight")) == 27.0
    _fake_hltb(monkeypatch, [_entry(10, 0.3)])
    assert _run(ms.hltb_main_story("X")) is None
    _fake_hltb(monkeypatch, None)
    assert _run(ms.hltb_main_story("X")) is None
    _fake_hltb(monkeypatch, error=ValueError("site mudou"))
    assert _run(ms.hltb_main_story("X")) is None


# --- endpoints ---

def test_endpoints(monkeypatch, db):
    client = TestClient(app)
    seen = {}

    async def fake_search(title, client_id=None, secret=None):
        seen["creds"] = (client_id, secret)
        if title == "Nada":
            raise ms.MetadataNotFoundError()
        if title == "Erro":
            raise ms.MetadataSourceError("A IGDB respondeu com erro 429.")
        return ms.MetadataSearchResponse(candidates=[ms.MetadataCandidate(
            source="igdb", source_id="1", name="Hollow Knight", year=2017)])

    async def fake_details(source, source_id, title, known, client_id=None, secret=None):
        if source_id == "404":
            raise ms.MetadataNotFoundError()
        if source_id == "502":
            raise ms.MetadataSourceError("A fonte de dados não respondeu.")
        return ms.MetadataProposal(source=source, name=title, developer="Team Cherry", genres=["Metroidvania"])

    monkeypatch.setattr("backend.app.api.v1.endpoints.metadata.search_candidates", fake_search)
    monkeypatch.setattr("backend.app.api.v1.endpoints.metadata.fetch_details", fake_details)

    ok = client.post("/api/v1/metadata/search", json={"title": "Hollow Knight", **CREDS})
    assert ok.status_code == 200 and ok.json()["candidates"][0]["year"] == 2017
    assert seen["creds"] == ("cid", "secret")
    assert client.post("/api/v1/metadata/search", json={"title": "Nada"}).status_code == 404
    err = client.post("/api/v1/metadata/search", json={"title": "Erro"})
    assert err.status_code == 502 and "429" in err.json()["detail"]
    assert client.post("/api/v1/metadata/search", json={"title": "  "}).status_code == 400
    assert client.post("/api/v1/metadata/search", json={}).status_code == 422

    body = {"source": "igdb", "source_id": "1", "title": "Hollow Knight"}
    det = client.post("/api/v1/metadata/details", json=body)
    assert det.status_code == 200 and det.json()["developer"] == "Team Cherry"
    assert client.post("/api/v1/metadata/details", json={**body, "source_id": "404"}).status_code == 404
    assert client.post("/api/v1/metadata/details", json={**body, "source": "gog"}).status_code == 422
    assert client.post("/api/v1/metadata/details", json={**body, "title": ""}).status_code == 400
    assert client.post("/api/v1/metadata/details", json={**body, "source_id": "502"}).status_code == 502
