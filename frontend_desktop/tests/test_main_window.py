import pytest
from frontend_desktop.views import game_status as gs
from frontend_desktop.views.main_window import MainWindow


def _game(gid, status, title=None):
    return {"id": gid, "title": title or f"Jogo {gid}", "status": status, "genres": []}


@pytest.fixture
def window(qapp, monkeypatch):
    games = [_game(1, "Fila"), _game(2, "Zerado"), _game(3, "Platinado"), _game(4, "Jogando")]
    from frontend_desktop.views import main_window as mw
    monkeypatch.setattr(mw.api_client, "get_games", lambda **kw: list(games))
    for name in ("get_genres", "get_developers", "get_platforms", "get_franchises"):
        monkeypatch.setattr(mw.api_client, name, lambda: [])
    # Views criadas sob demanda disparam workers; sem rede real (e sem log de falha) em threads de fundo
    monkeypatch.setattr(mw.api_client, "get_library_settings", lambda: {"steam_api_key_set": False, "steam_id": "", "heroic_path": ""})
    monkeypatch.setattr(mw.api_client, "inbox_pending", lambda threshold=None: {"total_events": 0, "groups": []})
    w = MainWindow(auto_load=False)
    w.refresh_all_data_sync()
    yield w
    w.close()
    # Nenhuma QThread pode sobreviver à janela (crash no PySide 6.12)
    for owner in [w, *w._views.values()]:
        for worker in list(owner.__dict__.get("_workers", ())):
            worker.wait(5000)


def _ids(grid):
    return {g["id"] for g in grid.all_games_source}


def test_status_lists_membership():
    assert gs.in_list("zerados", "Platinado") and gs.in_list("platinados", "Platinado")
    assert not gs.in_list("platinados", "Zerado")
    assert [g["id"] for g in gs.filter_games("queue", [_game(1, "Fila"), _game(2, "Pausado"), _game(3, "Zerado")])] == [1, 2]


def test_refresh_distributes_games_by_status(window):
    assert _ids(window.view_queue_grid) == {1}
    assert _ids(window.view_zerados_grid) == {2, 3}
    assert _ids(window.view_platinados_grid) == {3}


def test_new_game_is_inserted_in_matching_lists_only(window):
    window.apply_game_mutation(_game(10, "Platinado"), is_new=True)
    assert 10 in _ids(window.view_zerados_grid) and 10 in _ids(window.view_platinados_grid)
    assert 10 not in _ids(window.view_queue_grid)
    assert window.all_games[0]["id"] == 10


def test_status_change_moves_game_between_lists(window):
    window.apply_game_mutation(_game(1, "Zerado"), old_status="Fila")
    assert 1 not in _ids(window.view_queue_grid)
    assert 1 in _ids(window.view_zerados_grid)
    window.apply_game_mutation(_game(1, "Platinado"), old_status="Zerado")
    assert 1 in _ids(window.view_zerados_grid) and 1 in _ids(window.view_platinados_grid)
    window.apply_game_mutation(_game(1, "Zerado"), old_status="Platinado")
    assert 1 not in _ids(window.view_platinados_grid) and 1 in _ids(window.view_zerados_grid)


def test_same_status_edit_updates_in_place(window):
    window.apply_game_mutation(_game(1, "Fila", "Novo Título"), old_status="Fila")
    assert [g["title"] for g in window.view_queue_grid.all_games_source if g["id"] == 1] == ["Novo Título"]
    assert [g["title"] for g in window.all_games if g["id"] == 1] == ["Novo Título"]


def test_deletion_removes_from_all_lists(window):
    window.apply_game_deletion(3)
    assert all(3 not in _ids(g) for _, g in window._list_grids())
    assert all(g["id"] != 3 for g in window.all_games)


def test_async_refresh_loads_in_background_and_coalesces(qapp, monkeypatch):
    from PySide6.QtCore import QEventLoop, QTimer
    from frontend_desktop.views import main_window as mw
    calls = []
    monkeypatch.setattr(mw.api_client, "get_games", lambda **kw: calls.append(1) or [_game(1, "Fila")])
    for name in ("get_genres", "get_developers", "get_platforms", "get_franchises"):
        monkeypatch.setattr(mw.api_client, name, lambda: [])
    w = MainWindow(auto_load=False)
    w.refresh_all_data()
    w.refresh_all_data()  # coalescido: roda no máximo mais uma vez depois da primeira
    loop = QEventLoop()
    QTimer.singleShot(1500, loop.quit)
    w._loader.finished.connect(lambda: QTimer.singleShot(300, loop.quit))
    loop.exec()
    assert 1 <= len(calls) <= 2
    assert {g["id"] for g in w.view_queue_grid.all_games_source} == {1}
    w.close()


def test_async_refresh_reports_failure(qapp, monkeypatch):
    from PySide6.QtCore import QEventLoop, QTimer
    from frontend_desktop.views import main_window as mw
    def boom(**kw):
        raise ConnectionError("offline")
    monkeypatch.setattr(mw.api_client, "get_games", boom)
    w = MainWindow(auto_load=False)
    w.refresh_all_data()
    loop = QEventLoop()
    w._loader.finished.connect(loop.quit)
    QTimer.singleShot(2000, loop.quit)
    loop.exec()
    assert "offline" in w.statusBar().currentMessage()
    w.close()


def test_lazy_views_are_created_on_first_visit(window):
    from frontend_desktop.views.view_ids import ViewId
    assert ViewId.YEARBOOK not in window._views and ViewId.SETTINGS not in window._views
    window.switch_view(int(ViewId.SETTINGS))
    assert ViewId.SETTINGS in window._views and window.current_view_id == ViewId.SETTINGS
    assert window.view_title_label.text() == "Configurações"
    window.switch_view(int(ViewId.QUEUE))
    assert window.current_view_id == ViewId.QUEUE
    assert ViewId.YEARBOOK not in window._views  # nunca visitada


def test_every_view_id_has_metadata_and_icon(qapp):
    from frontend_desktop import icons
    from frontend_desktop.views.view_ids import ViewId, VIEW_META
    assert set(VIEW_META) == set(ViewId)
    for meta in VIEW_META.values():
        assert (icons.icons_dir() / f"{meta.icon}.svg").exists(), meta.icon


def test_sidebar_has_a_button_for_each_nav_view(window):
    from frontend_desktop.views.view_ids import NAV_SECTIONS
    expected = {int(v) for _, ids in NAV_SECTIONS for v in ids} | {11}
    assert {window.sidebar.button_group.id(b) for b in window.sidebar.button_group.buttons()} == expected


def test_sync_view_is_lazy_and_imports_in_place(window):
    from frontend_desktop.views.view_ids import ViewId
    assert ViewId.SYNC not in window._views
    window.switch_view(int(ViewId.SYNC))
    assert window.current_view_id == ViewId.SYNC
    assert window.view_title_label.text() == "Sincronizar bibliotecas"
    before = len(window.all_games)
    new = {"id": 9001, "title": "Importado", "status": "Disponível"}
    window._views[ViewId.SYNC].games_imported.emit([new])
    assert len(window.all_games) == before + 1 and window.all_games[0]["id"] == 9001
    window._views[ViewId.SYNC].games_updated.emit([dict(new, cover_image="c.jpg")])
    assert next(g for g in window.all_games if g["id"] == 9001)["cover_image"] == "c.jpg"
