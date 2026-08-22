import pytest
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
        json={"app": "GameRoomLog", "version": "0.2.2"},
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
