import pytest
from PySide6.QtCore import Qt
from frontend_desktop.views.components.game_grid import ScrollableGameGrid
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
    panel.combo_dev.setText("FromSoftware")
    assert panel.matches(game) is True
    panel.combo_dev.setText("Nintendo")
    assert panel.matches(game) is False
    panel.combo_dev.clear()

    # 2. Filtro de Gênero
    panel.combo_genre.setText("RPG")
    assert panel.matches(game) is True
    panel.combo_genre.setText("Ação")
    assert panel.matches(game) is False
    panel.combo_genre.clear()

    # 3. Filtro de Plataforma
    panel.combo_plat.setText("PC")
    assert panel.matches(game) is True
    panel.combo_plat.setText("Switch")
    assert panel.matches(game) is False
    panel.combo_plat.clear()

    # 4. Filtro de Franquia
    panel.combo_fran.setText("Souls")
    assert panel.matches(game) is True
    panel.combo_fran.setText("Zelda")
    assert panel.matches(game) is False
    panel.combo_fran.clear()

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
    scroll_grid.filter_panel.combo_genre.setText("RPG")
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


def test_game_dialog_prefills_new_game_without_id(qapp, monkeypatch):
    """Jogo novo vindo da caixa de entrada do portátil: abre como 'Novo Jogo', já preenchido."""
    from frontend_desktop.views.dialogs import game_dialog as gd
    monkeypatch.setattr(gd.GameDialog, "fetch_options", staticmethod(lambda: {
        "developers": [], "platforms": [{"id": 4, "name": "Android"}], "franchises": [], "genres": []}))
    dialog = gd.GameDialog(game_data={"title": "Dead Cells", "status": "Zerado", "finish_date": "2026-10-12",
                                      "played_hours": 20.0, "platform": {"id": 4}})
    _wait_dialog(dialog, qapp)
    assert dialog.is_edit is False and dialog.windowTitle() == "Novo Jogo"
    assert dialog.input_title.text() == "Dead Cells"
    assert dialog.combo_status.currentText() == "Zerado"
    assert dialog.combo_platform.currentData() == 4
    assert dialog.spin_played.value() == 20
    payload = dialog._build_payload("Dead Cells")
    assert payload["finish_date"] == "2026-10-12"


def test_game_dialog_prefills_platform_by_name(qapp, monkeypatch):
    """Importação das lojas manda a plataforma só pelo nome ("PC"), sem id."""
    from frontend_desktop.views.dialogs import game_dialog as gd
    monkeypatch.setattr(gd.GameDialog, "fetch_options", staticmethod(lambda: {
        "developers": [], "platforms": [{"id": 2, "name": "3DS"}, {"id": 1, "name": "pc"}], "franchises": [], "genres": []}))
    dialog = gd.GameDialog(game_data={"title": "Hades", "status": "Disponível", "format": "Digital",
                                      "played_hours": 12, "platform": {"name": "PC"}})
    _wait_dialog(dialog, qapp)
    assert dialog.is_edit is False
    assert dialog.combo_platform.currentData() == 1
    assert dialog.combo_status.currentText() == "Disponível"
    assert dialog.spin_played.value() == 12


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
    if dialog.combo_status.currentIndex() < 0:
        dialog.combo_status.setCurrentText(kw.get("status", "Fila"))
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


# --- diálogo de jogo: campos em branco, tipos de campo e payload ---
OPTIONS = {
    "developers": [{"name": "Capcom"}], "platforms": [{"id": 1, "name": "PC"}],
    "franchises": [{"id": 2, "name": "Saga"}], "genres": [{"id": 3, "name": "RPG"}],
}


def _dialog(qapp, monkeypatch, game_data=None):
    from frontend_desktop.views.dialogs import game_dialog as gd
    monkeypatch.setattr(gd.GameDialog, "fetch_options", staticmethod(lambda: OPTIONS))
    dialog = gd.GameDialog(game_data=game_data)
    _wait_dialog(dialog, qapp)
    return gd, dialog


def test_new_game_dialog_starts_completely_blank(qapp, monkeypatch):
    _, d = _dialog(qapp, monkeypatch)
    assert d.input_title.text() == ""
    # combos editáveis não podem vir com o 1º item das listas
    assert d.combo_developer.currentText() == "" and d.combo_franchise.currentText() == ""
    assert d.combo_genre.currentText() == ""
    assert d.combo_status.currentIndex() == -1 and d.combo_status.placeholderText()
    assert d.combo_platform.currentIndex() == -1 and d.combo_platform.currentData() is None
    assert d.combo_format.currentIndex() == -1
    assert d.spin_hltb.value() == 0 and d.spin_hltb.text() == "—"
    assert d.spin_score.text() == "Sem nota" and d.spin_diff.text() == "Sem nota"
    assert d.date_finish.is_blank() and d.date_plat.is_blank()
    assert d.date_finish.text() == "Selecione a data"
    assert not d.chk_replay.isChecked() and not d.chk_favorite.isChecked()
    assert d.input_notes.toPlainText() == "" and d.cover_filename is None


def test_save_requires_status(qapp, monkeypatch):
    gd, d = _dialog(qapp, monkeypatch)
    warned = []
    monkeypatch.setattr(gd.QMessageBox, "warning", lambda *a, **k: warned.append(a[2]))
    sent = []
    monkeypatch.setattr(gd.api_client, "create_game", lambda p: sent.append(p) or {**p, "id": 1})
    d.input_title.setText("Zelda")
    d.save_game()
    assert warned == ["Selecione o status do jogo."] and not sent


def test_conditional_fields_follow_status(qapp, monkeypatch):
    _, d = _dialog(qapp, monkeypatch)
    d.show()
    d.combo_status.setCurrentText("Fila")
    assert not any(f.isVisible() for f in (d.field_played, d.field_score, d.field_diff, d.field_finish, d.field_plat))
    d.combo_status.setCurrentText("Zerado")
    assert all(f.isVisible() for f in (d.field_played, d.field_score, d.field_diff, d.field_finish))
    assert not d.field_plat.isVisible()
    d.combo_status.setCurrentText("Platinado")
    assert d.field_plat.isVisible()
    assert not d.field_play_count.isVisible()
    d.chk_replay.setChecked(True)
    assert d.field_play_count.isVisible()
    d.close()


def test_payload_for_blank_new_game_omits_format_and_dates(qapp, monkeypatch):
    _, d = _dialog(qapp, monkeypatch)
    d.combo_status.setCurrentText("Zerado")
    p = d._build_payload("Zelda")
    assert "format" not in p and p["platform_id"] is None
    assert p["finish_date"] is None and p["completion_year"] is None and p["platinum_date"] is None
    assert p["score"] is None and p["play_type"] == "Primeira Jogada" and p["play_count"] == 1
    d.combo_format.setCurrentText("Físico")
    d.date_finish.setDate(d.date_finish.date().fromString("2024-05-20", "yyyy-MM-dd"))
    p = d._build_payload("Zelda")
    assert p["format"] == "Físico" and p["finish_date"] == "2024-05-20" and p["completion_year"] == 2024


def test_payload_platinum_year_prefers_platinum_date(qapp, monkeypatch):
    from PySide6.QtCore import QDate
    _, d = _dialog(qapp, monkeypatch)
    d.combo_status.setCurrentText("Platinado")
    d.date_finish.setDate(QDate(2023, 12, 30))
    assert d._build_payload("X")["completion_year"] == 2023
    d.date_plat.setDate(QDate(2024, 1, 5))
    p = d._build_payload("X")
    assert p["completion_year"] == 2024 and p["platinum_date"] == "2024-01-05"


def test_payload_replay(qapp, monkeypatch):
    _, d = _dialog(qapp, monkeypatch)
    d.combo_status.setCurrentText("Fila")
    d.chk_replay.setChecked(True)
    d.spin_play_count.setValue(3)
    p = d._build_payload("X")
    assert p["play_type"] == "Rejogada" and p["play_count"] == 3


def test_edit_dialog_populates_all_fields(qapp, monkeypatch):
    data = {
        "id": 4, "title": "Elden Ring", "developer": "Capcom", "status": "Platinado",
        "platform": {"id": 1, "name": "PC"}, "franchise": {"id": 2, "name": "Saga"},
        "genres": [{"id": 3, "name": "RPG"}], "hltb_hours": 60, "played_hours": 120,
        "score": 9.5, "difficulty": 7, "finish_date": "2024-03-01", "platinum_date": "2024-04-02",
        "play_type": "Rejogada", "play_count": 3, "format": "Físico", "is_favorite": True, "notes": "ótimo",
    }
    _, d = _dialog(qapp, monkeypatch, data)
    assert d.input_title.text() == "Elden Ring" and d.combo_developer.currentText() == "Capcom"
    assert d.combo_status.currentText() == "Platinado" and d.combo_platform.currentText() == "PC"
    assert d.combo_franchise.currentText() == "Saga" and d.combo_genre.currentText() == "RPG"
    assert (d.spin_hltb.value(), d.spin_played.value()) == (60, 120)
    assert d.spin_score.value() == 9.5 and d.spin_diff.value() == 7
    assert d.date_finish.date().toString("yyyy-MM-dd") == "2024-03-01"
    assert d.date_plat.date().toString("yyyy-MM-dd") == "2024-04-02"
    assert d.chk_replay.isChecked() and d.spin_play_count.value() == 3
    assert d.combo_format.currentText() == "Físico" and d.chk_favorite.isChecked()
    assert d.input_notes.toPlainText() == "ótimo"


def test_optional_date_edit_behaviour(qapp):
    from PySide6.QtCore import QDate, QEvent, QPoint, QPointF
    from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
    from frontend_desktop.views.dialogs.game_dialog import OptionalDateEdit
    w = OptionalDateEdit()
    assert w.is_blank() and w.date_or_none() is None
    # rodar a roda do mouse não preenche
    w.wheelEvent(QWheelEvent(QPointF(1, 1), QPointF(1, 1), QPoint(0, 0), QPoint(0, 120), Qt.NoButton,
                             Qt.NoModifier, Qt.NoScrollPhase, False))
    assert w.is_blank()
    # setas / clique partem de hoje
    w.stepBy(1)
    assert w.date() == QDate.currentDate()
    w.stepBy(1)
    assert w.date() == QDate.currentDate().addDays(1)
    # Delete limpa
    w.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))
    assert w.is_blank()
    w.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, QPointF(2, 2), QPointF(2, 2), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    assert w.date() == QDate.currentDate()
    w.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier))
    w.set_optional_date(QDate(2020, 1, 2))
    assert w.date_or_none() == QDate(2020, 1, 2)
    w.set_optional_date(None)
    assert w.is_blank()
    w.set_optional_date(QDate())  # inválida
    assert w.is_blank()
    w.setDate(QDate(2021, 6, 1))
    w.wheelEvent(QWheelEvent(QPointF(1, 1), QPointF(1, 1), QPoint(0, 0), QPoint(0, 120), Qt.NoButton,
                             Qt.NoModifier, Qt.NoScrollPhase, False))
    w.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Up, Qt.NoModifier))


def test_filter_field_matches_partial_while_typing_and_exact_when_picked(qapp):
    panel = FilterPanel()
    zelda = {"id": 1, "franchise": {"name": "Zelda"}, "genres": []}
    zelda2 = {"id": 2, "franchise": {"name": "Zelda II"}, "genres": []}
    other = {"id": 3, "franchise": {"name": "Mario"}, "genres": []}
    panel.combo_fran.setText("zel")  # digitação parcial: já filtra, sem o nome inteiro
    assert [panel.matches(g) for g in (zelda, zelda2, other)] == [True, True, False]
    panel.combo_fran._on_picked("Zelda")  # escolhido na lista: exato
    panel.combo_fran.setText("Zelda")
    assert [panel.matches(g) for g in (zelda, zelda2, other)] == [True, False, False]
    panel.combo_fran.textEdited.emit("Zelda")  # voltou a digitar: contém de novo
    assert panel.matches(zelda2) is True
    assert panel.count_active_filters() == 1


def test_filter_field_debounces_typing_and_emits_for_programmatic_text(qapp, monkeypatch):
    panel = FilterPanel()
    fired = []
    panel.filters_changed.connect(lambda: fired.append(1))
    panel.combo_genre.setText("RPG")  # sem foco = alteração programática: imediato
    assert fired == [1]
    monkeypatch.setattr(panel.combo_genre, "hasFocus", lambda: True)
    panel.combo_genre.setText("RPGs")
    assert fired == [1] and panel.combo_genre._debounce.isActive()
    panel.combo_genre._debounce.timeout.emit()
    assert fired == [1, 1]


def test_filter_locked_dimension_is_visible_disabled_and_ignored(qapp):
    panel = FilterPanel()
    panel.combo_genre.setText("RPG")
    panel.set_locked_filters({"genre": "Aventura"})
    assert not panel.combo_genre.isHidden() and not panel.combo_genre.isEnabled()
    assert panel.combo_genre.text() == "Aventura"  # visível, mas não filtra
    assert panel.combo_dev.isEnabled() and panel.count_active_filters() == 0
    assert panel.matches({"id": 1, "genres": [{"name": "Ação"}]}) is True
    panel.set_locked_filters({})
    assert panel.combo_genre.isEnabled() and panel.combo_genre.text() == ""


def test_filter_clear_resets_all_fields(qapp):
    panel = FilterPanel()
    panel.combo_plat.setText("PC")
    panel.spin_hltb.setValue(10)
    panel.clear_filters()
    assert panel.combo_plat.text() == "" and panel.count_active_filters() == 0


def test_scrollable_grid_sorting_by_name_score_and_hours(qapp):
    grid = ScrollableGameGrid()
    grid.set_games([
        {"id": 1, "title": "banana", "score": 5, "played_hours": 30, "status": "Zerado"},
        {"id": 2, "title": "Abacaxi", "score": None, "played_hours": 10, "status": "Zerado"},
        {"id": 3, "title": "Cereja", "score": 9, "hltb_hours": 50},
    ])
    ids = lambda: [g["id"] for g in grid.grid.games]  # noqa: E731
    grid.configure_page("category")
    assert ids() == [2, 1, 3]  # nome A–Z (sem diferenciar maiúsculas)
    grid.sort_dir_btn.setChecked(True)
    assert ids() == [3, 1, 2]
    grid.sort_combo.setCurrentIndex(grid.sort_combo.findData("score"))  # nota: maior primeiro
    assert ids() == [3, 1, 2] and grid.sort_dir_btn.isChecked()
    grid.sort_dir_btn.setChecked(False)
    assert ids() == [1, 3, 2]  # sem nota fica no fim também em ordem crescente
    grid.sort_combo.setCurrentIndex(grid.sort_combo.findData("hours"))
    assert ids() == [3, 1, 2]
    grid.sort_combo.setCurrentIndex(grid.sort_combo.findData("name"))
    assert not grid.sort_dir_btn.isChecked() and ids() == [2, 1, 3]


def test_category_detail_locks_own_dimension_and_enables_sorting(qapp):
    from frontend_desktop.views.components.category_detail_view import CategoryDetailView
    view = CategoryDetailView()
    assert not view.game_grid.sort_combo.isHidden()
    view.game_grid.filter_panel.combo_genre.setText("RPG")
    view.load_category("country", 1)  # tipo desconhecido não quebra
    view.load_category("genre", 1)
    panel = view.game_grid.filter_panel
    assert not panel.combo_genre.isEnabled() and panel.combo_plat.isEnabled()
    view._on_category_loaded("genre", 1, {"name": "Aventura"})
    assert panel.combo_genre.text() == "Aventura"
    view.set_filter_options([{"name": "RPG"}], [], [{"name": "PC"}], [])
    assert panel.combo_plat.completer().model().stringList() == ["PC"]
    view.load_category("platform", 2)
    assert panel.combo_genre.isEnabled() and not panel.combo_plat.isEnabled()
    view._on_category_loaded("platform", 2, {"name": "Switch"})
    assert panel.combo_plat.text() == "Switch" and panel.combo_genre.text() == ""


def test_save_primary_and_secondary_genres_in_order(qapp, save_dialog):
    gd, calls = save_dialog
    dialog = gd.GameDialog()
    _fill(dialog, qapp, genre="Roguelike")
    dialog.combo_genre2.setCurrentText("rpg")
    dialog.save_game()
    _wait_dialog(dialog, qapp)
    assert calls["created"] == [("genre", "Roguelike")]
    assert calls["sent"][1]["genre_ids"] == [30, 3]  # principal (criado) e secundário (existente)


def test_secondary_genre_alone_or_repeated(qapp, save_dialog):
    gd, calls = save_dialog
    dialog = gd.GameDialog()
    _fill(dialog, qapp)
    dialog.combo_genre2.setCurrentText("RPG")  # só o secundário: vira o único gênero
    dialog.save_game()
    _wait_dialog(dialog, qapp)
    assert calls["sent"][1]["genre_ids"] == [3]

    dialog = gd.GameDialog()
    _fill(dialog, qapp, genre="RPG")
    dialog.combo_genre2.setCurrentText("rpg")  # repetido: ignorado
    dialog.save_game()
    _wait_dialog(dialog, qapp)
    assert calls["sent"][1]["genre_ids"] == [3]


def test_dialog_loads_both_genres(qapp, monkeypatch):
    from frontend_desktop.views.dialogs import game_dialog as gd
    monkeypatch.setattr(gd.GameDialog, "fetch_options", staticmethod(lambda: {
        "developers": [], "platforms": [], "franchises": [],
        "genres": [{"id": 1, "name": "Roguelike"}, {"id": 2, "name": "Metroidvania"}]}))
    dialog = gd.GameDialog(game_data={"id": 5, "title": "Dead Cells", "status": "Fila",
                                      "genres": [{"name": "Roguelike"}, {"name": "Metroidvania"}]})
    _wait_dialog(dialog, qapp)
    assert dialog.combo_genre.currentText() == "Roguelike"
    assert dialog.combo_genre2.currentText() == "Metroidvania"
    assert dialog.combo_genre2.findText("Metroidvania") >= 0

    one = gd.GameDialog(game_data={"id": 6, "title": "X", "status": "Fila", "genres": [{"name": "Roguelike"}]})
    _wait_dialog(one, qapp)
    assert one.combo_genre.currentText() == "Roguelike" and one.combo_genre2.currentText() == ""


def test_genre_names_dedup_and_limit():
    from frontend_desktop.views.dialogs.game_dialog import GameDialog
    assert GameDialog.genre_names(["  RPG ", "rpg"]) == ["RPG"]
    assert GameDialog.genre_names(["", "Terror"]) == ["Terror"]
    assert GameDialog.genre_names(["A", "B", "C"]) == ["A", "B"]
    assert GameDialog.genre_names([None, ""]) == []


def test_suggest_developer_only_fills_empty_field(qapp, monkeypatch):
    from frontend_desktop.views.dialogs import game_dialog as gd
    monkeypatch.setattr(gd.GameDialog, "load_options", lambda self: None)
    empty = gd.GameDialog(game_data={"title": "Half-Life 2"})
    empty.suggest_developer("Valve")
    assert empty.combo_developer.currentText() == "Valve" and empty.game_data["developer"] == "Valve"
    empty.suggest_developer(None)
    assert empty.combo_developer.currentText() == "Valve"
    filled = gd.GameDialog(game_data={"title": "Prey", "developer": "Arkane Austin"})
    filled.suggest_developer("Arkane Studios")
    assert filled.game_data["developer"] == "Arkane Austin"
