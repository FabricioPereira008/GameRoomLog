import pytest
from PySide6.QtCore import Qt
from frontend_desktop.views.components import library_sync_view as lsv
from frontend_desktop.views.components.library_sync_view import COL_TITLE, LibrarySyncView, fetch_covers


@pytest.fixture(autouse=True)
def sync_workers(monkeypatch):
    """Executa os workers de forma síncrona e determinística."""
    def run_async(owner, func, on_success, on_error=None, *args, **kwargs):
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            if on_error:
                on_error(str(exc))
            return None
        on_success(result)
    monkeypatch.setattr(lsv, "run_async", run_async)
    monkeypatch.setattr(lsv.api_client, "get_library_settings", lambda: {"steam_api_key_set": True, "steam_id": "42"})


CANDS = [
    {"store": "steam", "external_id": "1", "title": "Hades", "played_hours": 12.0, "ambiguous": False},
    {"store": "steam", "external_id": "2", "title": "Celeste", "played_hours": 0.0, "ambiguous": False},
    {"store": "steam", "external_id": "3", "title": "Doom", "played_hours": None, "ambiguous": True},
]


def scanned(view, monkeypatch, data=None):
    monkeypatch.setattr(lsv.api_client, "library_scan", lambda include_all=False: data or {
        "candidates": CANDS, "auto_linked": 2, "errors": []})
    view.start_scan()


def titles(view, visible_only=True):
    return sorted(i.text(0) for i in view._items() if not (visible_only and i.isHidden()))


def test_loads_saved_settings(qapp):
    view = LibrarySyncView()
    assert view.input_steam_id.text() == "42"
    assert "já salva" in view.input_steam_key.placeholderText()


def test_save_settings_omits_empty_key(qapp, monkeypatch):
    sent = []
    monkeypatch.setattr(lsv.api_client, "save_library_settings",
                        lambda p: sent.append(p) or {"steam_api_key_set": True, "steam_id": p["steam_id"]})
    view = LibrarySyncView()
    view.input_steam_id.setText(" 99 ")
    view.save_settings()
    assert sent[-1] == {"steam_id": "99"}
    view.input_steam_key.setText("KEY")
    view.save_settings()
    assert sent[-1] == {"steam_id": "99", "steam_api_key": "KEY"}
    assert view.input_steam_key.text() == "" and "salvas" in view.config_status.text()


def test_save_settings_error(qapp, monkeypatch):
    def boom(_p):
        raise RuntimeError("offline")
    monkeypatch.setattr(lsv.api_client, "save_library_settings", boom)
    view = LibrarySyncView()
    view.save_settings()
    assert "offline" in view.config_status.text()


def test_scan_lists_candidates_unchecked(qapp, monkeypatch):
    view = LibrarySyncView()
    scanned(view, monkeypatch)
    assert len(view._items()) == 3
    assert view.checked_items() == []
    assert not view.btn_import.isEnabled()
    assert "3 jogo(s)" in view.status_label.text() and "2 já cadastrado" in view.status_label.text()
    doom = next(i for i in view._items() if i.text(0).startswith("Doom"))
    assert "ambíguo" in doom.text(0)
    assert view.store_filter.count() == 2


def test_scan_shows_store_errors(qapp, monkeypatch):
    view = LibrarySyncView()
    scanned(view, monkeypatch, {"candidates": [], "auto_linked": 0,
                                "errors": [{"store": "steam", "message": "Perfil privado"}]})
    assert "Steam: Perfil privado" in view.status_label.text()


def test_scan_failure_reenables_button(qapp, monkeypatch):
    def boom(include_all=False):
        raise RuntimeError("sem rede")
    monkeypatch.setattr(lsv.api_client, "library_scan", boom)
    view = LibrarySyncView()
    view.start_scan()
    assert view.btn_scan.isEnabled() and "sem rede" in view.status_label.text()


def test_filters_and_select_visible(qapp, monkeypatch):
    view = LibrarySyncView()
    scanned(view, monkeypatch)
    view.search_input.setText("had")
    assert titles(view) == ["Hades"]
    view.search_input.clear()
    view.chk_played.setChecked(True)
    assert titles(view) == ["Hades"]
    view._set_visible_checked(True)
    assert [i.text(0) for i in view.checked_items()] == ["Hades"]
    assert view.btn_import.text() == "Importar selecionados (1)" and view.btn_import.isEnabled()
    view.chk_played.setChecked(False)
    view.store_filter.setCurrentIndex(0)
    assert len(titles(view)) == 3
    view._set_all_checked(False)
    assert view.checked_items() == []


def test_import_removes_items_and_emits(qapp, monkeypatch):
    view = LibrarySyncView()
    scanned(view, monkeypatch)
    sent, imported, updated = [], [], []
    game = {"id": 7, "title": "Hades", "status": "Disponível"}
    monkeypatch.setattr(lsv.api_client, "library_import",
                        lambda items: sent.append(items) or {"imported": [game], "skipped": 0})
    monkeypatch.setattr(lsv, "fetch_covers", lambda games, key: [dict(game, cover_image="x.jpg")])
    view.games_imported.connect(imported.append)
    view.games_updated.connect(updated.append)
    next(i for i in view._items() if i.text(0) == "Hades").setCheckState(COL_TITLE, Qt.Checked)
    view.import_selected()
    assert sent[0] == [{"store": "steam", "external_id": "1", "title": "Hades", "played_hours": 12.0}]
    assert titles(view) == ["Celeste", "Doom  (título ambíguo)"]
    assert imported == [[game]] and updated[0][0]["cover_image"] == "x.jpg"
    assert "concluída" in view.status_label.text()


def test_import_without_selection_does_nothing(qapp, monkeypatch):
    view = LibrarySyncView()
    scanned(view, monkeypatch)
    view.import_selected()
    view.ignore_selected()
    assert len(view._items()) == 3


def test_import_with_no_new_games(qapp, monkeypatch):
    view = LibrarySyncView()
    scanned(view, monkeypatch)
    monkeypatch.setattr(lsv.api_client, "library_import", lambda items: {"imported": [], "skipped": 1})
    emitted = []
    view.games_imported.connect(emitted.append)
    view._items()[0].setCheckState(COL_TITLE, Qt.Checked)
    view.import_selected()
    assert emitted == []


def test_ignore_selected_and_manage_ignored_tab(qapp, monkeypatch):
    view = LibrarySyncView()
    scanned(view, monkeypatch)
    sent = []
    monkeypatch.setattr(lsv.api_client, "library_ignore", lambda items: sent.append(items) or {"ignored": 1})
    next(i for i in view._items() if i.text(0) == "Celeste").setCheckState(COL_TITLE, Qt.Checked)
    view.ignore_selected()
    assert sent[0][0]["external_id"] == "2" and len(view._items()) == 2

    monkeypatch.setattr(lsv.api_client, "library_ignored",
                        lambda: [{"id": 5, "store": "steam", "external_id": "2", "title": "Celeste"}])
    removed = []
    monkeypatch.setattr(lsv.api_client, "library_unignore", lambda i: removed.append(i) or True)
    view.tabs.setCurrentIndex(2)
    assert view.ignored_list.count() == 1
    view.ignored_list.selectAll()
    view.unignore_selected()
    assert removed == [5] and view.ignored_list.count() == 0


def test_import_error_reenables(qapp, monkeypatch):
    view = LibrarySyncView()
    scanned(view, monkeypatch)

    def boom(items):
        raise RuntimeError("falhou")
    monkeypatch.setattr(lsv.api_client, "library_import", boom)
    view._items()[0].setCheckState(COL_TITLE, Qt.Checked)
    view.import_selected()
    assert view.btn_scan.isEnabled() and "falhou" in view.status_label.text()
    assert len(view._items()) == 3


def test_fetch_covers_collects_only_successes(monkeypatch):
    def auto(gid, key):
        if gid == 2:
            raise RuntimeError("x")
        return {"success": gid == 1}
    monkeypatch.setattr(lsv.api_client, "auto_cover_game", auto)
    monkeypatch.setattr(lsv.api_client, "get_game", lambda gid: {"id": gid, "cover_image": "c.jpg"})
    games = [{"id": 1}, {"id": 2}, {"id": 3}]
    assert fetch_covers(games, "") == [{"id": 1, "cover_image": "c.jpg"}]
