import pytest
from PySide6.QtCore import Qt
from frontend_desktop.views.components import library_sync_view as lsv
from frontend_desktop.views.components.library_sync_view import (
    COL_TITLE, LibrarySyncView, finish_import, import_prefill,
)


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
    monkeypatch.setattr(lsv.api_client, "get_library_settings", lambda: {"steam_api_key_set": True, "steam_id": "42", "heroic_path": "/h"})


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
    assert view.input_heroic_path.text() == "/h"
    assert "já salva" in view.input_steam_key.placeholderText()


def test_save_settings_omits_empty_key(qapp, monkeypatch):
    sent = []
    monkeypatch.setattr(lsv.api_client, "save_library_settings",
                        lambda p: sent.append(p) or {"steam_api_key_set": True, "steam_id": p["steam_id"], "heroic_path": "/h"})
    view = LibrarySyncView()
    view.input_steam_id.setText(" 99 ")
    view.save_settings()
    assert sent[-1] == {"steam_id": "99", "heroic_path": "/h"}
    view.input_steam_key.setText("KEY")
    view.save_settings()
    assert sent[-1] == {"steam_id": "99", "heroic_path": "/h", "steam_api_key": "KEY"}
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
    assert list(view.store_buttons) == ["", "steam"]  # "Todas" + uma loja
    assert view.store_buttons[""].text() == "Todas  3" and view.store_buttons[""].isChecked()
    assert view.stack.currentWidget() is view.tree


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
    assert view.selection_label.text() == "1 de 1 selecionado(s)"
    view.chk_played.setChecked(False)
    view.set_store_filter("")
    assert len(titles(view)) == 3
    view._set_all_checked(False)
    assert view.checked_items() == []


def check(view, *names):
    for item in view._items():
        if any(item.text(0).startswith(n) for n in names):
            item.setCheckState(COL_TITLE, Qt.Checked)


def test_import_opens_editor_then_links_and_emits(qapp, monkeypatch):
    view = LibrarySyncView()
    scanned(view, monkeypatch)
    opened, linked, imported, updated = [], [], [], []
    game = {"id": 7, "title": "Hades", "status": "Fila", "cover_image": None}
    monkeypatch.setattr(view, "edit_before_import",
                        lambda cand, i, n: opened.append((cand["title"], i, n)) or game)
    monkeypatch.setattr(lsv.api_client, "library_link", lambda *a: linked.append(a) or {"id": 1})
    monkeypatch.setattr(lsv.api_client, "auto_cover_game", lambda gid, key: {"success": True})
    monkeypatch.setattr(lsv.api_client, "get_game", lambda gid: dict(game, cover_image="x.jpg"))
    view.games_imported.connect(imported.append)
    view.games_updated.connect(updated.append)
    check(view, "Hades")
    view.import_selected()
    assert opened == [("Hades", 1, 1)]
    assert linked == [(7, "steam", "1")]
    assert titles(view) == ["Celeste", "Doom  (título ambíguo)"]
    assert imported == [[game]] and updated[0][0]["cover_image"] == "x.jpg"
    assert "1 jogo(s) importado(s)" in view.status_label.text() and view.btn_scan.isEnabled()


def test_cancelled_editor_keeps_item_and_can_stop_batch(qapp, monkeypatch):
    view = LibrarySyncView()
    scanned(view, monkeypatch)
    opened, asked = [], []
    monkeypatch.setattr(view, "edit_before_import", lambda cand, i, n: opened.append(cand["title"]) or None)
    monkeypatch.setattr(view, "confirm_continue", lambda remaining: asked.append(remaining) or False)
    emitted = []
    view.games_imported.connect(emitted.append)
    check(view, "Hades", "Celeste", "Doom")
    view.import_selected()
    assert len(opened) == 1 and asked == [2]  # parou após o primeiro cancelamento
    assert emitted == [] and len(view._items()) == 3
    assert "0 jogo(s)" in view.status_label.text() and view.btn_import.isEnabled()


def test_cancel_one_and_continue_with_next(qapp, monkeypatch):
    view = LibrarySyncView()
    scanned(view, monkeypatch)
    results = iter([None, {"id": 9, "title": "Hades", "cover_image": "c.jpg"}])
    monkeypatch.setattr(view, "edit_before_import", lambda cand, i, n: next(results))
    monkeypatch.setattr(view, "confirm_continue", lambda remaining: True)
    monkeypatch.setattr(lsv.api_client, "library_link", lambda *a: {"id": 1})
    updated = []
    view.games_updated.connect(updated.append)
    check(view, "Hades", "Celeste")
    view.import_selected()
    assert titles(view) == ["Celeste", "Doom  (título ambíguo)"]  # ordem alfabética: Celeste veio 1º
    assert updated == []  # já tinha capa


def test_link_failure_is_reported(qapp, monkeypatch):
    view = LibrarySyncView()
    scanned(view, monkeypatch)
    monkeypatch.setattr(view, "edit_before_import", lambda cand, i, n: {"id": 7, "title": "Hades"})

    def boom(*a):
        raise RuntimeError("conflito")
    monkeypatch.setattr(lsv.api_client, "library_link", boom)
    emitted = []
    view.games_imported.connect(emitted.append)
    check(view, "Hades")
    view.import_selected()
    assert emitted == [[{"id": 7, "title": "Hades"}]]  # o jogo foi salvo mesmo sem o vínculo
    view._on_link_failed({"title": "Hades"}, "conflito")
    assert "não foi vinculado" in view.status_label.text() and "conflito" in view.status_label.text()


def test_edit_before_import_uses_prefilled_dialog(qapp, monkeypatch):
    view = LibrarySyncView()
    created = []

    class FakeDialog:
        def __init__(self, data, parent):
            created.append(data)
            self.saved_game, self.is_deleted = {"id": 1}, False

        def setWindowTitle(self, text):
            created.append(text)

        def exec(self):
            return lsv.QDialog.Accepted
    monkeypatch.setattr(lsv, "GameDialog", FakeDialog)
    assert view.edit_before_import(CANDS[0], 2, 3) == {"id": 1}
    assert created[0]["platform"] == {"name": "PC"} and created[0]["played_hours"] == 12.0
    assert created[1] == "Importar jogo (2 de 3) — Steam"
    FakeDialog.exec = lambda self: lsv.QDialog.Rejected
    assert view.edit_before_import(CANDS[0], 1, 1) is None


def test_import_prefill_defaults():
    data = import_prefill({"store": "gog", "external_id": "x", "title": "Doom", "played_hours": None})
    assert data == {"title": "Doom", "status": "Disponível", "format": "Digital",
                    "played_hours": 0, "platform": {"name": "PC"}}


def test_import_without_selection_does_nothing(qapp, monkeypatch):
    view = LibrarySyncView()
    scanned(view, monkeypatch)
    view.import_selected()
    view.ignore_selected()
    assert len(view._items()) == 3


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


def test_finish_import_links_and_fetches_cover_only_when_missing(monkeypatch):
    linked, covers = [], []
    monkeypatch.setattr(lsv.api_client, "library_link", lambda *a: linked.append(a))
    monkeypatch.setattr(lsv.api_client, "auto_cover_game", lambda gid, key: covers.append(key) or {"success": False})
    cand = {"store": "epic", "external_id": "abc"}
    assert finish_import({"id": 1, "cover_image": "a.jpg"}, cand) is None
    assert finish_import({"id": 2}, cand, "k") is None
    assert linked == [(1, "epic", "abc"), (2, "epic", "abc")] and covers == ["k"]

    def boom(gid, key):
        raise RuntimeError("x")
    monkeypatch.setattr(lsv.api_client, "auto_cover_game", boom)
    assert finish_import({"id": 3}, cand) is None


def test_confirm_continue_asks_user(qapp, monkeypatch):
    view = LibrarySyncView()
    monkeypatch.setattr(lsv.QMessageBox, "question", lambda *a, **k: lsv.QMessageBox.Yes)
    assert view.confirm_continue(2) is True
    monkeypatch.setattr(lsv.QMessageBox, "question", lambda *a, **k: lsv.QMessageBox.No)
    assert view.confirm_continue(2) is False


def test_store_chips_filter_and_developer_column(qapp, monkeypatch):
    view = LibrarySyncView()
    scanned(view, monkeypatch, {"candidates": [
        {"store": "steam", "external_id": "1", "title": "Hades", "played_hours": 3.0, "developer": None},
        {"store": "gog", "external_id": "g1", "title": "Prey", "played_hours": None, "developer": "Arkane Studios"},
        {"store": "gog", "external_id": "g2", "title": "Thief", "played_hours": None, "developer": "Looking Glass"},
    ], "auto_linked": 0, "errors": []})
    assert view.store_buttons["gog"].text() == "GOG  2"
    view.store_buttons["gog"].click()
    assert titles(view) == ["Prey", "Thief"] and view._store == "gog"
    view.search_input.setText("arkane")  # busca também pela desenvolvedora
    assert titles(view) == ["Prey"]
    prey = next(i for i in view._items() if i.text(0) == "Prey")
    assert prey.text(2) == "Arkane Studios" and prey.data(1, Qt.UserRole + 1) == "gog"
    view._toggle_item(prey)
    assert view.checked_items() == [prey]
    view._toggle_item(prey)
    assert view.checked_items() == []
    view.set_store_filter("amazon")  # loja que não está na lista: volta para "Todas"
    assert view._store == ""

    scanned(view, monkeypatch, {"candidates": [], "auto_linked": 0, "errors": []})
    assert view.stack.currentIndex() == 0 and "Nenhum jogo novo" in view.empty_label.text()


def test_steam_import_fetches_developer_while_dialog_is_open(qapp, monkeypatch):
    view = LibrarySyncView()
    events = []

    class FakeDialog:
        def __init__(self, data, parent):
            self.data, self.saved_game, self.is_deleted = data, None, False
            events.append(("open", data.get("developer")))

        def setWindowTitle(self, text):
            pass

        def suggest_developer(self, name):
            events.append(("suggest", name))

        def exec(self):
            return lsv.QDialog.Rejected
    monkeypatch.setattr(lsv, "GameDialog", FakeDialog)
    monkeypatch.setattr(lsv, "run_async", lambda owner, fn, ok, err, *args: ok(fn(*args)))
    monkeypatch.setattr(lsv.api_client, "library_details", lambda store, ext: events.append(("ask", ext)) or {"developer": "Valve"})
    view.edit_before_import({"store": "steam", "external_id": "220", "title": "Half-Life 2"}, 1, 1)
    view.edit_before_import({"store": "gog", "external_id": "g", "title": "Prey", "developer": "Arkane"}, 1, 1)
    assert events == [("open", None), ("ask", "220"), ("suggest", "Valve"), ("open", "Arkane")]


def test_settings_state_and_ignored_placeholder(qapp, monkeypatch):
    view = LibrarySyncView()
    view._on_settings_loaded({"steam_api_key_set": True, "steam_id": "1", "heroic_path": ""})
    assert view.steam_state.text() == "Configurada"
    view._on_settings_loaded({"steam_api_key_set": False, "steam_id": ""})
    assert "Falta" in view.steam_state.text()
    view._on_ignored_loaded([])
    assert view.ignored_list.count() == 1 and view.ignored_list.item(0).flags() == Qt.NoItemFlags
    view.ignored_list.selectAll()
    view.unignore_selected()  # o aviso "Nenhum jogo ignorado" não vira chamada à API
