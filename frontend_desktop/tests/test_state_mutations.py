import pytest
from PySide6.QtCore import Qt
from frontend_desktop.views.components.game_grid import GameGrid, ScrollableGameGrid
from frontend_desktop.views.components.game_room_view import GameRoomView
from frontend_desktop.views.components.filter_panel import FilterPanel
from frontend_desktop.views.dialogs.game_dialog import GameDialog

def test_scrollable_game_grid_search_filter(qapp):
    scroll_grid = ScrollableGameGrid()
    games = [
        {"id": 1, "title": "Chrono Trigger", "status": "Zerado"},
        {"id": 2, "title": "Final Fantasy VII", "status": "Zerado"},
        {"id": 3, "title": "Dark Souls III", "status": "Zerado"},
        {"id": 4, "title": "Elden Ring", "status": "Zerado"},
    ]
    scroll_grid.set_games(games)
    assert len(scroll_grid.grid.games) == 4

    # 1. Busca case-insensitive
    scroll_grid.search_input.setText("chrono")
    assert len(scroll_grid.grid.games) == 1
    assert scroll_grid.grid.games[0]["title"] == "Chrono Trigger"

    # 2. Busca por termo parcial
    scroll_grid.search_input.setText("souls")
    assert len(scroll_grid.grid.games) == 1
    assert scroll_grid.grid.games[0]["title"] == "Dark Souls III"

    # 3. Busca sem correspondência
    scroll_grid.search_input.setText("Zelda")
    assert len(scroll_grid.grid.games) == 0

    # 4. Limpar busca restaura todos os itens
    scroll_grid.clear_search()
    assert len(scroll_grid.grid.games) == 4
    assert scroll_grid.search_input.text() == ""

def test_game_room_view_search_filter(qapp):
    game_room = GameRoomView()
    game_room.show()
    now = [{"id": 1, "title": "Super Mario Odyssey", "status": "Jogando"}]
    next_g = [{"id": 2, "title": "Metroid Prime", "status": "Próximo"}]
    queue = [{"id": 3, "title": "The Legend of Zelda", "status": "Fila"}]
    finished = [{"id": 4, "title": "Super Mario World", "status": "Zerado"}]
    plat = [{"id": 5, "title": "Hollow Knight", "status": "Platinado"}]

    game_room.set_games(now, next_g, queue, finished, plat)
    assert game_room.sec_now.isHidden() is False
    assert game_room.sec_next.isHidden() is False
    assert game_room.sec_queue.isHidden() is False
    assert game_room.sec_finished.isHidden() is False
    assert game_room.sec_platinum.isHidden() is False

    # Filtrar por "Mario" (deve manter Now e Finished visíveis, e ocultar Next, Queue, Plat)
    game_room.search_input.setText("mario")
    assert game_room.sec_now.isHidden() is False
    assert game_room.sec_finished.isHidden() is False
    assert game_room.sec_next.isHidden() is True
    assert game_room.sec_queue.isHidden() is True
    assert game_room.sec_platinum.isHidden() is True

    # Limpar pesquisa restaura todas as seções com itens
    game_room.clear_search()
    assert game_room.sec_now.isHidden() is False
    assert game_room.sec_next.isHidden() is False
    assert game_room.sec_queue.isHidden() is False
    assert game_room.sec_finished.isHidden() is False
    assert game_room.sec_platinum.isHidden() is False


def test_filter_panel_logic(qapp):
    panel = FilterPanel()
    panel.set_options(
        genres=[{"id": 1, "name": "RPG"}, {"id": 2, "name": "Ação"}],
        developers=[{"id": 1, "name": "FromSoftware"}, {"id": 2, "name": "Nintendo"}],
        platforms=[{"id": 1, "name": "PC"}, {"id": 2, "name": "Switch"}],
        franchises=[{"id": 1, "name": "Souls"}, {"id": 2, "name": "Zelda"}]
    )

    game = {
        "id": 10,
        "title": "Dark Souls",
        "developer": "FromSoftware",
        "platform": {"id": 1, "name": "PC"},
        "franchise": {"id": 1, "name": "Souls"},
        "genres": [{"id": 1, "name": "RPG"}],
        "hltb_hours": 45.0
    }

    # Inicialmente passa em tudo
    assert panel.matches(game) is True
    assert panel.count_active_filters() == 0

    # 1. Filtro de Desenvolvedora
    panel.combo_dev.setCurrentText("FromSoftware")
    assert panel.matches(game) is True
    panel.combo_dev.setCurrentText("Nintendo")
    assert panel.matches(game) is False
    panel.combo_dev.setCurrentIndex(0)

    # 2. Filtro de Gênero
    panel.combo_genre.setCurrentText("RPG")
    assert panel.matches(game) is True
    panel.combo_genre.setCurrentText("Ação")
    assert panel.matches(game) is False
    panel.combo_genre.setCurrentIndex(0)

    # 3. Filtro de Plataforma
    panel.combo_plat.setCurrentText("PC")
    assert panel.matches(game) is True
    panel.combo_plat.setCurrentText("Switch")
    assert panel.matches(game) is False
    panel.combo_plat.setCurrentIndex(0)

    # 4. Filtro de Franquia
    panel.combo_fran.setCurrentText("Souls")
    assert panel.matches(game) is True
    panel.combo_fran.setCurrentText("Zelda")
    assert panel.matches(game) is False
    panel.combo_fran.setCurrentIndex(0)

    # 5. Filtro de HLTB (>= 40h e <= 40h)
    panel.combo_hltb_op.setCurrentText("≥ Maior ou igual a")
    panel.spin_hltb.setValue(40)
    assert panel.matches(game) is True
    panel.spin_hltb.setValue(50)
    assert panel.matches(game) is False

    panel.combo_hltb_op.setCurrentText("≤ Menor ou igual a")
    panel.spin_hltb.setValue(50)
    assert panel.matches(game) is True
    panel.spin_hltb.setValue(30)
    assert panel.matches(game) is False

    # 6. Limpar Filtros
    panel.clear_filters()
    assert panel.count_active_filters() == 0
    assert panel.matches(game) is True

def test_scrollable_game_grid_combined_search_and_filter(qapp):
    scroll_grid = ScrollableGameGrid()
    scroll_grid.set_filter_options(
        genres=[{"id": 1, "name": "RPG"}, {"id": 2, "name": "Plataforma"}],
        developers=[{"id": 1, "name": "Nintendo"}, {"id": 2, "name": "Square Enix"}],
        platforms=[{"id": 1, "name": "Switch"}, {"id": 2, "name": "PC"}],
        franchises=[{"id": 1, "name": "Mario"}, {"id": 2, "name": "Final Fantasy"}]
    )

    games = [
        {"id": 1, "title": "Super Mario Odyssey", "developer": "Nintendo", "genres": [{"name": "Plataforma"}], "hltb_hours": 15.0},
        {"id": 2, "title": "Super Mario RPG", "developer": "Nintendo", "genres": [{"name": "RPG"}], "hltb_hours": 12.0},
        {"id": 3, "title": "Final Fantasy VII", "developer": "Square Enix", "genres": [{"name": "RPG"}], "hltb_hours": 40.0},
    ]
    scroll_grid.set_games(games)
    assert len(scroll_grid.grid.games) == 3

    # Busca por "Super" + Filtro de Gênero "RPG"
    scroll_grid.search_input.setText("Super")
    scroll_grid.filter_panel.combo_genre.setCurrentText("RPG")
    assert len(scroll_grid.grid.games) == 1
    assert scroll_grid.grid.games[0]["title"] == "Super Mario RPG"

    # Limpar tudo
    scroll_grid.clear_filters()
    assert len(scroll_grid.grid.games) == 3

def test_game_dialog_editable_combos(qapp, monkeypatch):
    from frontend_desktop.views.dialogs import game_dialog as gd
    monkeypatch.setattr(gd.GameDialog, "fetch_options", staticmethod(lambda: {"developers": [], "platforms": [], "franchises": [], "genres": []}))
    dialog = GameDialog()
    _wait_dialog(dialog, qapp)
    assert dialog.combo_developer.isEditable() is True
    assert dialog.combo_franchise.isEditable() is True
    assert dialog.combo_genre.isEditable() is True

def _wait_dialog(dialog, qapp):
    for _ in range(100):
        if not any(w.isRunning() for w in dialog.__dict__.get("_workers", ())):
            break
        dialog._wait_workers()
    qapp.processEvents()


def test_game_dialog_loads_options_in_background(qapp, monkeypatch):
    from frontend_desktop.views.dialogs import game_dialog as gd
    monkeypatch.setattr(gd.GameDialog, "fetch_options", staticmethod(lambda: {
        "developers": [{"name": "Studio A"}],
        "platforms": [{"id": 1, "name": "PC"}],
        "franchises": [{"id": 2, "name": "Saga"}],
        "genres": [{"id": 3, "name": "RPG"}],
    }))
    dialog = gd.GameDialog(game_data={"id": 9, "title": "Teste", "status": "Fila", "platform_id": 1})
    _wait_dialog(dialog, qapp)
    assert dialog.combo_platform.findText("PC") >= 0
    assert dialog.combo_developer.findText("Studio A") >= 0
    assert dialog.btn_save.isEnabled() is True
    assert dialog.input_title.text() == "Teste"


def test_game_dialog_survives_offline_api(qapp, monkeypatch):
    from frontend_desktop.views.dialogs import game_dialog as gd
    def boom():
        raise ConnectionError("offline")
    monkeypatch.setattr(gd.GameDialog, "fetch_options", staticmethod(boom))
    dialog = gd.GameDialog(game_data={"id": 9, "title": "Teste", "status": "Fila"})
    _wait_dialog(dialog, qapp)
    assert dialog.btn_save.isEnabled() is True
    assert dialog.input_title.text() == "Teste"


def test_game_dialog_auto_cover_runs_async(qapp, monkeypatch):
    from frontend_desktop.views.dialogs import game_dialog as gd
    monkeypatch.setattr(gd.GameDialog, "fetch_options", staticmethod(lambda: {"developers": [], "platforms": [], "franchises": [], "genres": []}))
    monkeypatch.setattr(gd.api_client, "auto_search_cover", lambda title, api_key=None: "cover123.jpg")
    monkeypatch.setattr(gd.GameDialog, "update_cover_preview", lambda self: None)
    dialog = gd.GameDialog()
    _wait_dialog(dialog, qapp)
    dialog.input_title.setText("Zelda")
    dialog.auto_search_cover()
    _wait_dialog(dialog, qapp)
    assert dialog.cover_filename == "cover123.jpg"
    assert dialog.btn_auto_cover.isEnabled() is True


# --- save_game / delete_game assíncronos ---
@pytest.fixture
def save_dialog(qapp, monkeypatch):
    from frontend_desktop.views.dialogs import game_dialog as gd
    monkeypatch.setattr(gd.GameDialog, "fetch_options", staticmethod(lambda: {
        "developers": [], "platforms": [{"id": 1, "name": "PC"}],
        "franchises": [{"id": 2, "name": "Saga"}], "genres": [{"id": 3, "name": "RPG"}]}))
    calls = {"created": [], "sent": None}
    monkeypatch.setattr(gd.api_client, "create_franchise", lambda name: calls["created"].append(("franchise", name)) or {"id": 20})
    monkeypatch.setattr(gd.api_client, "create_genre", lambda name: calls["created"].append(("genre", name)) or {"id": 30})
    monkeypatch.setattr(gd.api_client, "create_game", lambda payload: calls.__setitem__("sent", ("create", payload)) or {**payload, "id": 99})
    monkeypatch.setattr(gd.api_client, "update_game", lambda gid, payload: calls.__setitem__("sent", ("update", gid, payload)) or {**payload, "id": gid})
    return gd, calls


def _fill(dialog, qapp, **kw):
    _wait_dialog(dialog, qapp)
    dialog.input_title.setText(kw.get("title", "Novo Jogo"))
    dialog.combo_franchise.setCurrentText(kw.get("franchise", ""))
    dialog.combo_genre.setCurrentText(kw.get("genre", ""))


def test_save_new_game_creates_missing_franchise_and_genre(qapp, save_dialog):
    gd, calls = save_dialog
    dialog = gd.GameDialog()
    _fill(dialog, qapp, franchise="Nova Saga", genre="Roguelike")
    dialog.save_game()
    assert dialog.btn_save.isEnabled() is False and dialog.btn_save.text() == "Salvando..."
    assert dialog.btn_cancel.isEnabled() is False
    _wait_dialog(dialog, qapp)
    assert calls["created"] == [("franchise", "Nova Saga"), ("genre", "Roguelike")]
    kind, payload = calls["sent"]
    assert kind == "create" and payload["franchise_id"] == 20 and payload["genre_ids"] == [30]
    assert dialog.saved_game["id"] == 99 and dialog.result() == gd.QDialog.Accepted


def test_save_reuses_existing_categories_without_creating(qapp, save_dialog):
    gd, calls = save_dialog
    dialog = gd.GameDialog()
    _fill(dialog, qapp, franchise="saga", genre="rpg")
    dialog.save_game()
    _wait_dialog(dialog, qapp)
    assert calls["created"] == []
    assert calls["sent"][1]["franchise_id"] == 2 and calls["sent"][1]["genre_ids"] == [3]


def test_edit_game_uses_update(qapp, save_dialog):
    gd, calls = save_dialog
    dialog = gd.GameDialog(game_data={"id": 7, "title": "Antigo", "status": "Fila"})
    _fill(dialog, qapp, title="Editado")
    dialog.save_game()
    _wait_dialog(dialog, qapp)
    assert calls["sent"][0] == "update" and calls["sent"][1] == 7
    assert dialog.saved_game["title"] == "Editado"


def test_save_failure_keeps_dialog_open_and_reenables_buttons(qapp, save_dialog, monkeypatch):
    gd, calls = save_dialog
    shown = []
    monkeypatch.setattr(gd.QMessageBox, "critical", lambda *a, **k: shown.append(a[2]))
    def boom(payload):
        raise ConnectionError("API caiu")
    monkeypatch.setattr(gd.api_client, "create_game", boom)
    dialog = gd.GameDialog()
    _fill(dialog, qapp)
    dialog.save_game()
    _wait_dialog(dialog, qapp)
    assert dialog.saved_game is None
    assert dialog.btn_save.isEnabled() and dialog.btn_cancel.isEnabled()
    assert dialog.btn_save.text() == "Salvar Jogo"
    assert shown and "API caiu" in shown[0]


def test_save_requires_title(qapp, save_dialog, monkeypatch):
    gd, calls = save_dialog
    warned = []
    monkeypatch.setattr(gd.QMessageBox, "warning", lambda *a, **k: warned.append(1))
    dialog = gd.GameDialog()
    _fill(dialog, qapp, title="   ")
    dialog.save_game()
    assert warned and calls["sent"] is None


def test_delete_game_success_and_failure(qapp, save_dialog, monkeypatch):
    gd, calls = save_dialog
    monkeypatch.setattr(gd.QMessageBox, "question", lambda *a, **k: gd.QMessageBox.Yes)
    shown = []
    monkeypatch.setattr(gd.QMessageBox, "critical", lambda *a, **k: shown.append(a[2]))

    monkeypatch.setattr(gd.api_client, "delete_game", lambda gid: False)
    d1 = gd.GameDialog(game_data={"id": 5, "title": "X", "status": "Fila"})
    _wait_dialog(d1, qapp)
    d1.delete_game()
    _wait_dialog(d1, qapp)
    assert not d1.is_deleted and shown and d1.btn_delete.isEnabled()

    monkeypatch.setattr(gd.api_client, "delete_game", lambda gid: True)
    d2 = gd.GameDialog(game_data={"id": 5, "title": "X", "status": "Fila"})
    _wait_dialog(d2, qapp)
    d2.delete_game()
    _wait_dialog(d2, qapp)
    assert d2.is_deleted and d2.saved_game["id"] == 5


def test_filter_panel_reuses_completers_when_options_change(qapp):
    panel = FilterPanel()
    panel.set_options([{"name": "RPG"}], [{"name": "Nintendo"}], [{"name": "PC"}], [{"name": "Mario"}])
    completer = panel.combo_genre.completer()
    panel.set_options([{"name": "RPG"}, {"name": "Ação"}], [], [], [])
    assert panel.combo_genre.completer() is completer
    assert completer.model().stringList() == ["RPG", "Ação"]
    assert panel.combo_genre.findText("Ação") >= 0
