import json
import logging
import os
import stat
import sys

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.main import app
from backend.app.services.library import PROVIDERS, LibraryProviderError
from backend.app.services.library import steam as steam_mod
from backend.app.services.library.settings_store import LibrarySettings, load_settings, save_settings
from backend.app.services.library.steam import SteamProvider

client = TestClient(app)


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "BASE_DIR", tmp_path)
    return tmp_path


def configure(key="SEGREDO123", steam_id="7656"):
    save_settings(LibrarySettings(steam_api_key=key, steam_id=steam_id))


def fake_get(monkeypatch, status=200, payload=None, exc=None):
    seen = {}

    def _get(url, params=None, timeout=None):
        seen["params"] = params
        if exc:
            raise exc
        return httpx.Response(status, json=payload if payload is not None else {}, request=httpx.Request("GET", url))

    monkeypatch.setattr(steam_mod.httpx, "get", _get)
    return seen


def test_steam_is_registered():
    assert PROVIDERS["steam"] is SteamProvider


def test_fetch_maps_games_and_hours(monkeypatch):
    configure()
    seen = fake_get(monkeypatch, payload={"response": {"games": [
        {"appid": 1145360, "name": "Hades", "playtime_forever": 90},
        {"appid": 5, "name": "  ", "playtime_forever": 1},
        {"name": "Sem id"},
        {"appid": 6, "name": "Nunca jogado"},
    ]}})
    entries = SteamProvider().fetch()
    assert [(e.store, e.external_id, e.title, e.played_hours) for e in entries] == [
        ("steam", "1145360", "Hades", 1.5), ("steam", "6", "Nunca jogado", 0.0)]
    assert seen["params"]["steamid"] == "7656"


def test_fetch_requires_configuration():
    with pytest.raises(LibraryProviderError, match="Informe"):
        SteamProvider().fetch()


@pytest.mark.parametrize("status,text", [(403, "inválida"), (500, "erro 500")])
def test_fetch_http_errors(monkeypatch, status, text):
    configure()
    fake_get(monkeypatch, status=status)
    with pytest.raises(LibraryProviderError, match=text):
        SteamProvider().fetch()


def test_fetch_private_profile(monkeypatch):
    configure()
    fake_get(monkeypatch, payload={"response": {}})
    with pytest.raises(LibraryProviderError, match="públicos"):
        SteamProvider().fetch()


def test_network_error_does_not_leak_key(monkeypatch, caplog):
    configure()
    fake_get(monkeypatch, exc=httpx.ConnectError("GET https://x/?key=SEGREDO123 failed"))
    with caplog.at_level(logging.DEBUG), pytest.raises(LibraryProviderError) as err:
        SteamProvider().fetch()
    assert "SEGREDO123" not in str(err.value) and "SEGREDO123" not in caplog.text
    assert err.value.__cause__ is None


def test_invalid_json(monkeypatch):
    configure()

    def _get(url, params=None, timeout=None):
        return httpx.Response(200, content=b"<html>", request=httpx.Request("GET", url))

    monkeypatch.setattr(steam_mod.httpx, "get", _get)
    with pytest.raises(LibraryProviderError, match="inesperada"):
        SteamProvider().fetch()


def test_settings_api_never_returns_key_and_supports_partial_update():
    res = client.get("/api/v1/library/settings").json()
    assert res == {"steam_api_key_set": False, "steam_id": ""}
    res = client.put("/api/v1/library/settings", json={"steam_api_key": " K ", "steam_id": "123"}).json()
    assert res == {"steam_api_key_set": True, "steam_id": "123"}
    assert "K" not in json.dumps(client.get("/api/v1/library/settings").json()).replace("steam_api_key_set", "")
    # None mantém a key; "" apaga
    client.put("/api/v1/library/settings", json={"steam_id": "456"})
    assert load_settings().steam_api_key == "K" and load_settings().steam_id == "456"
    assert client.put("/api/v1/library/settings", json={"steam_api_key": ""}).json()["steam_api_key_set"] is False


@pytest.mark.skipif(sys.platform == "win32", reason="permissões POSIX")
def test_settings_file_is_private(data_dir):
    configure()
    mode = stat.S_IMODE(os.stat(data_dir / "library_settings.json").st_mode)
    assert mode == 0o600


def test_load_settings_tolerates_corrupt_file(data_dir):
    (data_dir / "library_settings.json").write_text("{nope")
    assert load_settings() == LibrarySettings()
    (data_dir / "library_settings.json").write_text("[1]")
    assert load_settings() == LibrarySettings()
