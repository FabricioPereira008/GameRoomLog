import json

import pytest

from backend.app.core.config import settings
from backend.app.services.library import PROVIDERS, LibraryProviderError, heroic
from backend.app.services.library.heroic import HeroicProvider, find_heroic_dir
from backend.app.services.library.settings_store import LibrarySettings, save_settings


@pytest.fixture
def env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(settings, "BASE_DIR", data)
    home = tmp_path / "heroic"
    home.mkdir()
    save_settings(LibrarySettings(heroic_path=str(home)))
    return home


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")


def epic(home, _n, app_id, title, categories=("games",), main=None):
    meta = {"categories": [{"path": c} for c in categories], "mainGameItem": main}
    write(home / "legendaryConfig/legendary/metadata" / f"{app_id}.json",
          {"app_name": app_id, "app_title": title, "metadata": meta})


def by_store(entries):
    out = {}
    for e in entries:
        out.setdefault(e.store, []).append(e)
    return out


def test_registered():
    assert PROVIDERS["heroic"] is HeroicProvider


def test_reads_epic_gog_and_amazon(env):
    epic(env, "a", "e1", "Fall Guys", ("applications", "games"))
    epic(env, "b", "e2", "Some DLC", ("applications", "games"), main={"id": "x"})
    epic(env, "c", "e3", "Outfit", ("addons",))
    epic(env, "d", "e4", "Extras", ("digitalextras", "games"))
    write(env / "legendaryConfig/legendary/metadata/broken.json", "{nope")
    write(env / "legendaryConfig/legendary/metadata/list.json", "[1]")
    write(env / "legendaryConfig/legendary/metadata/noname.json", {"app_name": "z"})
    write(env / "store_cache/gog_library.json", {"games": [
        {"app_name": "100", "title": "Prey", "install": {}},
        {"app_name": "101", "title": "Redist", "install": {"is_dlc": True}},
        {"app_name": "", "title": "Sem id"}, "lixo"]})
    write(env / "store_cache/nile_library.json", {"library": [
        {"id": "a1", "product": {"title": "Amazon Game"}}, {"app_name": "a2", "title": "Outro"}, 5, {"id": "a3"}]})
    groups = by_store(HeroicProvider().fetch())
    assert {e.title: e.is_game for e in groups["epic"]} == {
        "Fall Guys": True, "Some DLC": False, "Outfit": False, "Extras": False}
    assert {e.title: e.is_game for e in groups["gog"]} == {"Prey": True, "Redist": False}
    assert [(e.external_id, e.title) for e in groups["amazon"]] == [("a1", "Amazon Game"), ("a2", "Outro")]
    assert all(e.played_hours is None for e in groups["epic"] + groups["gog"])


def test_partial_stores_are_ok(env):
    write(env / "store_cache/gog_library.json", [{"app_name": "1", "title": "Solo GOG"}])
    entries = HeroicProvider().fetch()
    assert [(e.store, e.title) for e in entries] == [("gog", "Solo GOG")]


def test_unusual_formats_yield_no_entries_not_errors(env):
    write(env / "store_cache/gog_library.json", {"games": "x"})
    write(env / "store_cache/nile_library.json", {"library": None})
    assert HeroicProvider().fetch() == []


def test_missing_heroic_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "BASE_DIR", tmp_path)
    save_settings(LibrarySettings(heroic_path=str(tmp_path / "nao-existe")))
    with pytest.raises(LibraryProviderError, match="Heroic não encontrado"):
        HeroicProvider().fetch()


def test_heroic_without_libraries(env):
    with pytest.raises(LibraryProviderError, match="Nenhuma biblioteca"):
        HeroicProvider().fetch()


def test_autodetect_uses_candidates(tmp_path, monkeypatch):
    first, second = tmp_path / "a", tmp_path / "b"
    second.mkdir()
    monkeypatch.setattr(heroic, "candidate_dirs", lambda: [first, second])
    assert find_heroic_dir() == second
    monkeypatch.setattr(heroic, "candidate_dirs", lambda: [first])
    assert find_heroic_dir() is None


@pytest.mark.parametrize("platform,env_key", [("linux", "XDG_CONFIG_HOME"), ("win32", "APPDATA")])
def test_candidate_dirs_per_platform(tmp_path, monkeypatch, platform, env_key):
    monkeypatch.setattr(heroic.sys, "platform", platform)
    monkeypatch.setenv(env_key, str(tmp_path))
    dirs = heroic.candidate_dirs()
    assert dirs[0] == tmp_path / "heroic"
    assert (len(dirs) == 2) == (platform == "linux")
