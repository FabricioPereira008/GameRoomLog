import pytest
from app_version import __version__
import responses
from frontend_desktop.api_client.client import ApiClient

@pytest.fixture
def client():
    return ApiClient(base_url="http://test-server:8000/api/v1")

@responses.activate
def test_is_backend_online(client):
    responses.add(
        responses.GET,
        "http://test-server:8000/",
        json={"app": "GameRoomLog", "version": __version__},
        status=200
    )
    assert client.is_backend_online() is True

@responses.activate
def test_is_backend_offline(client):
    responses.add(
        responses.GET,
        "http://test-server:8000/",
        status=500
    )
    assert client.is_backend_online() is False

@responses.activate
def test_get_games_with_params(client):
    responses.add(
        responses.GET,
        "http://test-server:8000/api/v1/games/",
        json=[{"id": 1, "title": "Zelda BOTW", "status": "Zerado"}],
        status=200
    )

    games = client.get_games(status="Zerado", sort_by="score_desc")
    assert len(games) == 1
    assert games[0]["title"] == "Zelda BOTW"
    assert "status=Zerado" in responses.calls[0].request.url
    assert "sort_by=score_desc" in responses.calls[0].request.url

@responses.activate
def test_create_and_update_game(client):
    responses.add(
        responses.POST,
        "http://test-server:8000/api/v1/games/",
        json={"id": 10, "title": "Super Mario Odyssey", "status": "Fila"},
        status=201
    )
    responses.add(
        responses.PUT,
        "http://test-server:8000/api/v1/games/10",
        json={"id": 10, "title": "Super Mario Odyssey", "status": "Jogando"},
        status=200
    )

    created = client.create_game({"title": "Super Mario Odyssey", "status": "Fila"})
    assert created["id"] == 10

    updated = client.update_game(10, {"status": "Jogando"})
    assert updated["status"] == "Jogando"

@responses.activate
def test_delete_game(client):
    responses.add(
        responses.DELETE,
        "http://test-server:8000/api/v1/games/10",
        status=204
    )
    assert client.delete_game(10) is True

@responses.activate
def test_get_stats_and_yearbook(client):
    responses.add(
        responses.GET,
        "http://test-server:8000/api/v1/stats/yearbook/2026",
        json={"year": 2026, "total_games_finished": 5, "total_hours_played": 120.0},
        status=200
    )
    responses.add(
        responses.GET,
        "http://test-server:8000/api/v1/stats/overall",
        json={"status_counts": {"total": 50}, "total_hours": 850.0},
        status=200
    )

    yb = client.get_yearbook(2026)
    assert yb["year"] == 2026
    assert yb["total_games_finished"] == 5

    overall = client.get_overall_stats()
    assert overall["total_hours"] == 850.0


@responses.activate
def test_auto_cover_game_sends_key_in_body(client):
    responses.add(responses.POST, "http://test-server:8000/api/v1/uploads/auto-cover-game/3",
                  json={"success": True}, status=200)
    client.auto_cover_game(3, "secret")
    req = responses.calls[0].request
    assert b"secret" in req.body
    assert "secret" not in req.url


@responses.activate
def test_get_cover_path_downloads_once_and_caches(tmp_path):
    api = ApiClient(base_url="http://test-server:8000/api/v1", cover_cache_dir=tmp_path)
    responses.add(responses.GET, "http://test-server:8000/static/covers/a.jpg", body=b"img", status=200)
    path = api.get_cover_path("a.jpg")
    assert path and open(path, "rb").read() == b"img"
    api.get_cover_path("a.jpg")
    assert len(responses.calls) == 1


@responses.activate
def test_get_cover_path_missing_and_traversal(tmp_path):
    api = ApiClient(base_url="http://test-server:8000/api/v1", cover_cache_dir=tmp_path)
    responses.add(responses.GET, "http://test-server:8000/static/covers/none.jpg", status=404)
    assert api.get_cover_path("none.jpg") is None
    responses.add(responses.GET, "http://test-server:8000/static/covers/passwd", body=b"x", status=200)
    assert api.get_cover_path("../../etc/passwd") is not None
    assert not (tmp_path.parent / "etc").exists()


@responses.activate
def test_error_status_raises_and_delete_returns_bool(client):
    import requests
    responses.add(responses.PUT, "http://test-server:8000/api/v1/genres/1", status=409)
    with pytest.raises(requests.HTTPError):
        client.update_genre(1, "x", "#fff")
    responses.add(responses.DELETE, "http://test-server:8000/api/v1/genres/1", status=204)
    assert client.delete_genre(1) is True
    responses.add(responses.DELETE, "http://test-server:8000/api/v1/genres/2", status=404)
    assert client.delete_genre(2) is False


def test_base_url_from_env(monkeypatch):
    monkeypatch.setenv("GAMEROOM_API_URL", "http://example:9000/api/v1/")
    assert ApiClient().base_url == "http://example:9000/api/v1"


@responses.activate
def test_is_backend_online_rejects_foreign_service(client):
    responses.add(responses.GET, "http://test-server:8000/", body="<html>other service</html>", status=200)
    assert client.is_backend_online() is False


@responses.activate
def test_library_endpoints(client):
    base = "http://test-server:8000/api/v1/library"
    responses.add(responses.POST, f"{base}/scan", json={"candidates": [], "auto_linked": 0, "errors": []})
    responses.add(responses.POST, f"{base}/import", json={"imported": [], "skipped": 0}, status=201)
    responses.add(responses.POST, f"{base}/ignored", json={"ignored": 1}, status=201)
    responses.add(responses.GET, f"{base}/ignored", json=[{"id": 3}])
    responses.add(responses.DELETE, f"{base}/ignored/3", status=204)
    responses.add(responses.DELETE, f"{base}/ignored/9", status=404)
    responses.add(responses.GET, f"{base}/settings", json={"steam_api_key_set": False, "steam_id": ""})
    responses.add(responses.PUT, f"{base}/settings", json={"steam_api_key_set": True, "steam_id": "1"})

    assert client.library_scan(include_all=True)["errors"] == []
    assert responses.calls[0].request.body == b'{"include_all": true, "stores": null}'
    assert client.library_import([{"store": "steam"}])["skipped"] == 0
    assert client.library_ignore([{"store": "steam"}])["ignored"] == 1
    assert client.library_ignored() == [{"id": 3}]
    assert client.library_unignore(3) is True
    assert client.library_unignore(9) is False
    assert client.get_library_settings()["steam_id"] == ""
    assert client.save_library_settings({"steam_id": "1"})["steam_api_key_set"] is True
