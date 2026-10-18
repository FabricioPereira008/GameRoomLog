"""Testes das melhorias de interface: categorias em dois modos, horas por status, incompletos, Game Room em
faixas, seletor de tamanho, tabela, Configurações em abas, busca rápida e atalhos."""
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QLabel

from frontend_desktop import preferences
from frontend_desktop.data_quality import is_incomplete, missing_fields
from frontend_desktop.views import game_status as gs

COMPLETE = {"id": 1, "title": "Hades", "status": "Fila", "developer": "Supergiant", "genres": [{"name": "Roguelike"}],
            "platform": {"name": "PC"}, "cover_image": "h.jpg", "hltb_hours": 22}


@pytest.fixture(autouse=True)
def reset_prefs():
    preferences.settings().clear()
    yield
    preferences.settings().clear()


def _games(n, status="Fila", **extra):
    return [{"id": i, "title": f"Jogo {i}", "status": status, "genres": [], **extra} for i in range(1, n + 1)]


# --- regras de dados ---
def test_display_hours_follows_status():
    assert gs.display_hours({"status": "Zerado", "played_hours": 30, "hltb_hours": 20}) == 30
    assert gs.display_hours({"status": "Platinado", "played_hours": None, "hltb_hours": 20}) == 0
    assert gs.display_hours({"status": "Jogando", "played_hours": 5, "hltb_hours": 80}) == 80
    assert gs.display_hours({"status": "Fila"}) == 0
    assert gs.is_completed("Platinado") and not gs.is_completed("Jogando")


def test_missing_fields_basic_and_completed_requirements():
    assert missing_fields(COMPLETE) == [] and not is_incomplete(COMPLETE)
    assert missing_fields({"status": "Fila", "developer": "  "}) == [
        "desenvolvedora", "gênero", "plataforma", "capa", "duração (HLTB)"]
    done = {**COMPLETE, "status": "Zerado"}
    assert missing_fields(done) == ["horas jogadas", "nota", "data de zeramento"]
    plat = {**COMPLETE, "status": "Platinado", "played_hours": 30, "score": 0, "finish_date": "2026-01-01"}
    assert missing_fields(plat) == ["data da platina"]  # nota 0 conta como preenchida
    assert is_incomplete(plat)


# --- preferências ---
def test_preferences_defaults_validation_and_notifier():
    assert preferences.category_scope() == "completed" and preferences.card_size() == "medium"
    preferences.set_category_scope("all")
    assert preferences.category_scope() == "all"
    preferences.set_category_scope("tudo")
    assert preferences.category_scope() == "completed"
    preferences.settings().setValue("category_scope", "lixo")
    assert preferences.category_scope() == "completed"

    seen = []
    preferences.notifier.card_size_changed.connect(seen.append)
    try:
        preferences.set_card_size("large")
        preferences.set_card_size("large")  # sem mudança: não avisa de novo
        preferences.set_card_size("gigante")  # inválido vira médio
    finally:
        preferences.notifier.card_size_changed.disconnect(seen.append)
    assert seen == ["large", "medium"] and preferences.card_size() == "medium"
    preferences.settings().setValue("card_size", "xx")
    assert preferences.card_size() == "medium"


# --- filtro: status e incompletos ---
def test_filter_panel_status_and_incomplete(qapp):
    from frontend_desktop.views.components.filter_panel import STATUS_COMPLETED, FilterPanel
    panel = FilterPanel()
    assert panel.combo_status.isHidden() and panel.status_label.isHidden()
    panel.set_status_filter_visible(True)
    assert not panel.combo_status.isHidden()

    zerado = {**COMPLETE, "status": "Zerado", "played_hours": 1, "score": 8, "finish_date": "2026-01-01"}
    fila = dict(COMPLETE)
    panel.combo_status.setCurrentIndex(panel.combo_status.findData("Fila"))
    match = panel.build_matcher()
    assert match(fila) and not match(zerado)
    panel.combo_status.setCurrentIndex(panel.combo_status.findData(STATUS_COMPLETED))
    match = panel.build_matcher()
    assert match(zerado) and match({**zerado, "status": "Platinado", "platinum_date": "2026-02-01"}) and not match(fila)
    assert panel.count_active_filters() == 1

    panel.chk_incomplete.setChecked(True)
    match = panel.build_matcher()
    assert not match(zerado) and match({**zerado, "cover_image": None})
    assert panel.count_active_filters() == 2 and panel.btn_toggle.text() == "Filtros (2)"

    panel.clear_filters()
    assert panel.combo_status.currentIndex() == 0 and not panel.chk_incomplete.isChecked()
    panel.combo_status.setCurrentIndex(2)
    panel.set_status_filter_visible(False)  # esconder zera o filtro
    assert panel.combo_status.currentIndex() == 0 and panel.count_active_filters() == 0


# --- páginas de categoria ---
def test_card_count_text_by_scope():
    from frontend_desktop.views.components.management_view import card_count_text
    item = {"games_count": 30, "completed_count": 1, "total_hours": 12.5}
    assert card_count_text(item, "completed") == "30 jogos · 12.5h"
    assert card_count_text(item, "all") == "30 jogos · 1 zerado · 12.5h"
    assert card_count_text({"games_count": 1, "completed_count": 0}, "all") == "1 jogo · 0 zerados"


def _wait(owner, qapp):
    for w in list(owner.__dict__.get("_workers", ())):
        w.wait(3000)
    qapp.processEvents()


def test_management_view_requests_current_scope(qapp, monkeypatch):
    from frontend_desktop.views.components import management_view as mv
    calls = []
    monkeypatch.setattr(mv.api_client, "get_genres",
                        lambda scope=None: calls.append(scope) or [{"id": 1, "name": "FPS", "games_count": 30, "completed_count": 2}])
    view = mv.ManagementView("genre", "Gênero")
    view.load_data()
    _wait(view, qapp)
    preferences.set_category_scope("all")
    view.load_data()
    _wait(view, qapp)
    assert calls == ["completed", "all"]
    texts = [l.text() for l in view.container.findChildren(QLabel)]
    assert "30 jogos · 2 zerados" in texts


def test_category_detail_all_scope_shows_totals_and_status_filter(qapp, monkeypatch):
    from frontend_desktop.views.components import category_detail_view as cv
    calls = []
    data = {"id": 1, "name": "FPS", "color": "#fff", "total_games": 36, "completed_games": 4,
            "total_hours_played": 50, "games": _games(3)}
    monkeypatch.setattr(cv.api_client, "get_genre_details", lambda gid, scope=None: calls.append(scope) or data)
    view = cv.CategoryDetailView()
    view.load_category("genre", 1)
    _wait(view, qapp)
    assert view.card_all_games.isHidden() and view.game_grid.filter_panel.combo_status.isHidden()
    assert view.section_label.text() == "Jogos Zerados / Platinados"
    preferences.set_category_scope("all")
    view.load_category("genre", 1)
    _wait(view, qapp)
    assert calls == ["completed", "all"]
    assert not view.card_all_games.isHidden() and not view.game_grid.filter_panel.combo_status.isHidden()
    assert view.section_label.text() == "Todos os jogos"
    assert len(view.game_grid.all_games_source) == 3


# --- grades ---
def test_grid_distributes_width_and_fixed_size_ignores_preference(qapp):
    from frontend_desktop.views.components.game_grid import GRID_SPACING, MODE_FULL, GameGrid
    grid = GameGrid(mode=MODE_FULL)
    grid.resize(900, 600)
    grid.set_games(_games(8))
    grid.show()
    qapp.processEvents()
    grid._apply_grid_size()
    cols = grid._columns()
    cell = grid.view.gridSize().width()
    assert cell >= grid.delegate.metrics.card_width + GRID_SPACING
    assert cols * cell <= grid.view.viewport().width()

    featured = GameGrid(mode=MODE_FULL, size_mode="large")
    featured.set_games(_games(2))
    before = featured.delegate.metrics
    preferences.set_card_size("small")
    assert featured.delegate.metrics == before  # destaque não muda
    assert grid.delegate.metrics.card_width < before.card_width  # a grade comum segue a preferência
    grid.close()


def test_strip_mode_single_row_and_horizontal_scroll(qapp):
    from frontend_desktop.views.components.game_grid import GRID_SPACING, MODE_STRIP, GameGrid
    grid = GameGrid(mode=MODE_STRIP)
    grid.resize(500, 400)
    grid.set_games(_games(20))
    grid.show()
    qapp.processEvents()
    grid._update_height()
    assert grid.view.height() == grid.delegate.metrics.card_height + 2 * GRID_SPACING
    assert grid.strip_overflows()
    bar = grid.view.horizontalScrollBar()
    grid.scroll_strip(1)
    assert bar.value() > 0
    grid.scroll_strip(-1)
    assert bar.value() == 0

    def wheel(dx, dy, mods=Qt.NoModifier):
        ev = QWheelEvent(QPointF(10, 10), QPointF(10, 10), QPoint(), QPoint(dx, dy), Qt.NoButton, mods, Qt.NoScrollPhase, False)
        grid.view.wheelEvent(ev)
        return ev
    assert not wheel(0, -120).isAccepted() and bar.value() == 0  # roda comum: rola a página
    wheel(0, -120, Qt.ShiftModifier)
    assert bar.value() == 120
    wheel(60, 0)
    assert bar.value() == 60
    grid.set_games([])
    grid._update_height()
    assert grid.view.height() == 0
    grid.close()


def test_card_size_selector_sets_and_follows_preference(qapp):
    from frontend_desktop.views.components.game_grid import CardSizeSelector
    a, b = CardSizeSelector(), CardSizeSelector()
    assert a.buttons["medium"].isChecked()
    a.buttons["large"].click()
    assert preferences.card_size() == "large" and b.buttons["large"].isChecked()


# --- Game Room ---
def test_game_room_featured_strips_counts_and_view_all(qapp):
    from frontend_desktop.views.components.game_grid import MODE_FULL, MODE_STRIP
    from frontend_desktop.views.components.game_room_view import GameRoomView
    room = GameRoomView()
    room.resize(1000, 800)
    asked = []
    room.view_all_requested.connect(asked.append)
    room.set_games(_games(2, "Jogando"), [], _games(15), _games(1, "Zerado"), [])
    room.show()
    qapp.processEvents()
    assert room.grid_now.mode == MODE_FULL and room.grid_now.delegate.metrics.card_width == 230
    assert room.grid_queue.mode == MODE_STRIP
    assert room._counts[room.grid_queue].text() == "15" and room.sec_next.isHidden()
    arrows = room._arrows[room.grid_queue]
    room._update_arrows(room.grid_queue, arrows)
    assert not arrows[0].isHidden() and not arrows[0].isEnabled() and arrows[1].isEnabled()
    arrows[1].click()
    assert room.grid_queue.view.horizontalScrollBar().value() > 0
    from PySide6.QtWidgets import QPushButton
    view_all = [b for b in room.sec_queue.findChildren(QPushButton) if b.text() == "Ver todos"]
    view_all[0].click()
    assert asked == ["queue"]
    assert not [b for b in room.sec_next.findChildren(QPushButton) if b.text() == "Ver todos"]  # Próximos não tem página
    room.close()


# --- tabela ---
def test_table_columns_menu_hides_and_remembers(qapp):
    from frontend_desktop.views.components.game_table import GameTable
    table = GameTable()
    assert table.table.isColumnHidden(10) and not table.table.isColumnHidden(2)  # "Tipo" começa escondida
    menu = table.build_columns_menu()
    actions = {a.text(): a for a in menu.actions()}
    assert "Jogo" not in actions and actions["Tipo de jogada"].isChecked() is False
    actions["Plataforma"].setChecked(False)
    actions["Tipo de jogada"].setChecked(True)
    assert table.table.isColumnHidden(3) and not table.table.isColumnHidden(10)
    again = GameTable()
    assert again.hidden_columns() == {3} and again.table.isColumnHidden(3)
    table.set_column_visible(0, False)  # título nunca some
    assert not table.table.isColumnHidden(0)
    table.set_column_visible(3, True)
    assert GameTable.hidden_columns() == set()


def test_table_header_tooltips():
    from frontend_desktop.models.game_table_model import GameTableModel
    model = GameTableModel()
    assert model.headerData(8, Qt.Horizontal, Qt.ToolTipRole) == "Duração estimada (HowLongToBeat)"
    assert model.headerData(0, Qt.Horizontal, Qt.ToolTipRole) == "Jogo"
    assert model.headerData(0, Qt.Vertical, Qt.ToolTipRole) is None


# --- tela de edição: aviso da capa ---
def test_dialog_cover_status_only_when_missing(qapp, monkeypatch):
    from frontend_desktop.views.dialogs import game_dialog as gd
    monkeypatch.setattr(gd.GameDialog, "fetch_options", staticmethod(
        lambda: {"developers": [], "platforms": [], "franchises": [], "genres": []}))
    monkeypatch.setattr(gd.GameDialog, "load_options", lambda self: None)
    with_cover = gd.GameDialog(game_data={"id": 1, "title": "X", "status": "Fila", "cover_image": "x.jpg"})
    assert with_cover.lbl_cover_status.text() == ""
    without = gd.GameDialog()
    assert without.lbl_cover_status.text() == gd.NO_COVER_TEXT
    without.cover_filename = "nova.jpg"
    without.update_cover_preview()
    assert without.lbl_cover_status.text() == ""


# --- Configurações ---
def test_settings_tabs_scope_and_card_size(qapp):
    from frontend_desktop.views.components.settings_view import SettingsView
    view = SettingsView()
    assert [view.tabs.tabText(i) for i in range(view.tabs.count())] == ["Aparência", "Capas", "Sobre"]
    assert not hasattr(view, "chk_auto_covers")  # importação do Notion removida
    changed = []
    view.settings_changed.connect(lambda: changed.append(True))
    assert view.scope_buttons["completed"].isChecked()
    view.scope_buttons["all"].click()
    assert preferences.category_scope() == "all" and changed == [True]
    view.on_scope_changed("all")  # sem mudança: não recarrega de novo
    assert changed == [True]
    view.rb_small.click()
    assert preferences.card_size() == "small"
    preferences.set_card_size("large")
    assert view.rb_large.isChecked()


# --- busca rápida ---
def test_search_games_folds_accents_and_ranks_prefix_first():
    from frontend_desktop.views.dialogs.quick_search_dialog import describe, search_games
    games = [{"id": 1, "title": "The Legend of Zelda"}, {"id": 2, "title": "Zelda: Wind Waker"},
             {"id": 3, "title": "Pokémon Pokopia"}, {"id": 4, "title": None}]
    assert [g["id"] for g in search_games(games, "zelda")] == [2, 1]
    assert [g["id"] for g in search_games(games, "POKEMON")] == [3]
    assert [g["id"] for g in search_games(games, "wind zel")] == [2]  # todas as palavras, em qualquer ordem
    assert search_games(games, "   ") == []
    assert len(search_games([{"title": f"Jogo {i}"} for i in range(80)], "jogo")) == 50
    assert describe({"title": "Celeste", "status": "Zerado", "platform": {"name": "PC"}}) == "Celeste   —   Zerado · PC"
    assert describe({"title": "Celeste"}) == "Celeste"


def test_quick_search_dialog_keyboard_and_accept(qapp):
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent
    from frontend_desktop.views.dialogs.quick_search_dialog import QuickSearchDialog
    dialog = QuickSearchDialog([{"id": 1, "title": "Zelda A"}, {"id": 2, "title": "Zelda B"}])
    assert dialog.results.count() == 0
    dialog.input.setText("zelda")
    assert dialog.results.count() == 2 and dialog.results.currentRow() == 0
    dialog.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Down, Qt.NoModifier))
    assert dialog.results.currentRow() == 1
    dialog.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Down, Qt.NoModifier))
    assert dialog.results.currentRow() == 1  # não passa do fim
    dialog.accept_current()
    from PySide6.QtWidgets import QDialog
    assert dialog.selected_game["id"] == 2 and dialog.result() == QDialog.Accepted
    empty = QuickSearchDialog([])
    empty.input.setText("nada")
    assert empty.hint.text() == "Nenhum jogo encontrado."
    empty.accept_current()
    assert empty.selected_game is None
