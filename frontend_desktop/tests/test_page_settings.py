"""Personalização das páginas (ordenação e filtros), aba Páginas, aba Atalhos e abertura do app."""
import pytest
from PySide6.QtWidgets import QMessageBox

from frontend_desktop import page_settings, preferences
from frontend_desktop.page_settings import PAGES, PageConfig, default_config, page_config, set_page_config
from frontend_desktop.views.components.filter_panel import FilterPanel
from frontend_desktop.views.components.game_grid import ScrollableGameGrid
from frontend_desktop.views.components.settings_tabs import PagesSettingsTab, ShortcutsTab

GAMES = [
    {"id": 1, "title": "Bravo", "status": "Zerado", "finish_date": "2024-05-01", "score": 8, "played_hours": 20,
     "difficulty": 6, "created_at": "2024-01-01T00:00:00"},
    {"id": 2, "title": "Alfa", "status": "Zerado", "finish_date": "2025-02-01", "score": None, "played_hours": 0,
     "difficulty": None, "created_at": "2025-01-01T00:00:00"},
    {"id": 3, "title": "Charlie", "status": "Zerado", "finish_date": None, "score": 9, "played_hours": 50,
     "difficulty": 3, "created_at": "2023-01-01T00:00:00"},
]


def _grid(page="finished"):
    grid = ScrollableGameGrid()
    grid.set_games([dict(g) for g in GAMES])
    grid.configure_page(page)
    return grid


def _ids(grid):
    return [g["id"] for g in grid.grid.games]


# --- regras da configuração ---

def test_defaults_per_page():
    assert page_config("finished") == PageConfig(
        ("finish_date", "score", "played_hours", "difficulty", "name"), "finish_date", True,
        PAGES["finished"].filters)
    assert page_config("wishlist").sorts == ("name", "created") and page_config("wishlist").default_descending is False
    assert page_config("game_room").sorts == () and page_config("game_room").default_sort is None
    assert "status" in page_config("category").filters and "status" not in page_config("queue").filters


def test_normalize_keeps_at_least_one_sort_and_valid_default():
    saved = set_page_config("finished", PageConfig((), "score", True, ("genre", "inventado")))
    assert saved.sorts == ("finish_date",) and saved.default_sort == "finish_date" and saved.default_descending
    assert saved.filters == ("genre",)
    saved = set_page_config("finished", PageConfig(("score", "name"), "finish_date", False, ()))
    assert saved.default_sort == "score" and saved.default_descending  # direção inicial do novo padrão
    assert page_config("finished") == saved
    saved = set_page_config("finished", PageConfig(("score", "name"), "name", True, ()))
    assert saved.default_sort == "name" and saved.default_descending  # padrão válido mantém a direção escolhida


def test_corrupted_settings_fall_back_to_default():
    preferences.settings().setValue("pages/queue", "{quebrado")
    assert page_config("queue") == default_config("queue")


def test_reset_all():
    set_page_config("queue", PageConfig(("hltb",), "hltb", True, ()))
    page_settings.reset_all()
    assert page_config("queue") == default_config("queue")


# --- ordenação nas páginas ---

def test_finished_page_sorts_by_date_with_missing_values_last(qapp):
    grid = _grid()
    assert grid.sort_combo.currentData() == "finish_date" and grid.sort_dir_btn.text() == "Recentes primeiro"
    assert _ids(grid) == [2, 1, 3]
    grid.sort_dir_btn.setChecked(False)
    assert _ids(grid) == [1, 2, 3] and grid.sort_dir_btn.text() == "Antigos primeiro"  # sem data segue no fim
    grid.sort_combo.setCurrentIndex(grid.sort_combo.findData("played_hours"))
    assert _ids(grid) == [3, 1, 2]                                   # 0 h conta como sem valor
    grid.sort_dir_btn.setChecked(False)
    assert _ids(grid) == [1, 3, 2] and grid.sort_dir_btn.text() == "Menor→Maior"
    grid.sort_combo.setCurrentIndex(grid.sort_combo.findData("difficulty"))
    assert _ids(grid) == [1, 3, 2]


def test_ties_are_broken_by_name(qapp):
    grid = ScrollableGameGrid()
    grid.set_games([{"id": 1, "title": "Zeta", "score": 8}, {"id": 2, "title": "Alfa", "score": 8}])
    grid.configure_page("category")
    grid.sort_combo.setCurrentIndex(grid.sort_combo.findData("score"))
    assert _ids(grid) == [2, 1]


def test_settings_change_applies_now_and_keeps_session_choice(qapp):
    grid = _grid()
    set_page_config("finished", PageConfig(("finish_date", "score"), "score", True, ()))
    assert grid.sort_combo.count() == 2 and grid.sort_combo.currentData() == "score"  # nada escolhido: segue o padrão
    grid.sort_combo.setCurrentIndex(grid.sort_combo.findData("finish_date"))  # escolha na página (sessão)
    set_page_config("finished", PageConfig(("finish_date", "score", "name"), "score", True, ()))
    assert grid.sort_combo.currentData() == "finish_date"           # a escolha da sessão continua
    set_page_config("finished", PageConfig(("score", "name"), "name", False, ()))
    assert grid.sort_combo.currentData() == "name"                   # critério escolhido sumiu: volta ao padrão
    assert not grid.filter_panel.btn_toggle.isVisibleTo(grid)        # sem campos de filtro: some o botão


def test_single_criterion_shows_only_the_direction(qapp):
    set_page_config("wishlist", PageConfig(("created",), "created", True, ("genre",)))
    grid = _grid("wishlist")
    assert not grid.sort_combo.isVisibleTo(grid) and grid.sort_dir_btn.isVisibleTo(grid)
    assert grid.sort_dir_btn.text() == "Recentes primeiro"


def test_new_window_starts_with_the_default_sort(qapp):
    first = _grid()
    first.sort_combo.setCurrentIndex(first.sort_combo.findData("score"))
    assert _grid().sort_combo.currentData() == "finish_date"         # escolha não é salva entre aberturas


# --- filtros visíveis ---

def test_hidden_filter_fields_are_cleared_and_ignored(qapp):
    panel = FilterPanel()
    panel.set_options(genres=[{"id": 1, "name": "RPG"}], developers=[], platforms=[], franchises=[])
    game = {"id": 1, "title": "X", "genres": [{"id": 2, "name": "Ação"}], "play_type": "Primeira Jogada",
            "hltb_hours": 5}
    panel.combo_genre.setText("RPG")
    panel.spin_hltb.setValue(50)
    panel.chk_incomplete.setChecked(True)
    assert not panel.matches(game)
    changed = []
    panel.filters_changed.connect(lambda: changed.append(1))
    panel.set_visible_fields({"developer"})
    assert changed and panel.matches(game) and panel.count_active_filters() == 0
    assert panel.combo_genre.isHidden() and panel.spin_hltb.isHidden() and panel.chk_incomplete.isHidden()
    assert not panel.combo_dev.isHidden() and not panel.btn_toggle.isHidden()
    panel.btn_toggle.setChecked(True)
    panel.set_visible_fields(set())
    assert panel.btn_toggle.isHidden() and not panel.btn_toggle.isChecked() and panel.panel_frame.isHidden()


def test_status_needs_page_and_scope(qapp):
    panel = FilterPanel()
    assert not panel.is_field_visible("status")                       # escondido até o modo "todos"
    panel.set_status_filter_visible(True)
    assert panel.is_field_visible("status") and not panel.combo_status.isHidden()
    panel.set_visible_fields({"genre"})
    assert not panel.is_field_visible("status") and panel.combo_status.isHidden()


def test_locked_category_field_is_not_cleared(qapp):
    panel = FilterPanel()
    panel.set_locked_filters({"genre": "RPG"})
    panel.set_visible_fields({"developer"})
    assert panel.combo_genre.text() == "RPG"


def test_game_room_filters_follow_settings(qapp):
    from frontend_desktop.views.components.game_room_view import GameRoomView
    view = GameRoomView()
    view.filter_panel.bind_page("game_room")
    set_page_config("game_room", PageConfig((), None, False, ("platform",)))
    assert view.filter_panel.is_field_visible("platform") and not view.filter_panel.is_field_visible("genre")


# --- aba Páginas ---

@pytest.fixture
def tab(qapp):
    return PagesSettingsTab()


def test_pages_tab_lists_pages_and_shows_page_options(tab):
    assert [tab.combo_page.itemText(i) for i in range(tab.combo_page.count())] == [s.title for s in PAGES.values()]
    assert tab.current_page == "game_room" and tab.sort_group.isHidden()  # Game Room: só filtros
    tab.combo_page.setCurrentIndex(tab.combo_page.findData("finished"))
    assert not tab.sort_group.isHidden() and list(tab.sort_checks) == list(PAGES["finished"].sorts)
    assert tab.combo_default.currentData() == "finish_date" and tab.combo_direction.currentText() == "Recentes primeiro"
    assert "status" not in tab.filter_checks
    tab.combo_page.setCurrentIndex(tab.combo_page.findData("category"))
    assert "Todos os jogos" in tab.filter_checks["status"].text()


def test_pages_tab_saves_each_change(tab):
    tab.combo_page.setCurrentIndex(tab.combo_page.findData("finished"))
    tab.sort_checks["difficulty"].setChecked(False)
    assert "difficulty" not in page_config("finished").sorts
    tab.combo_default.setCurrentIndex(tab.combo_default.findData("name"))
    assert page_config("finished").default_sort == "name" and tab.combo_direction.currentText() == "A→Z"
    tab.combo_direction.setCurrentIndex(1)
    assert page_config("finished").default_descending is True
    tab.sort_checks["name"].setChecked(False)                         # padrão desmarcado: vai para o 1º marcado
    assert page_config("finished").default_sort == "finish_date" and tab.combo_default.currentData() == "finish_date"
    tab.filter_checks["genre"].setChecked(False)
    assert "genre" not in page_config("finished").filters


def test_last_sort_cannot_be_unchecked(tab):
    tab.combo_page.setCurrentIndex(tab.combo_page.findData("wishlist"))
    tab.sort_checks["created"].setChecked(False)
    assert not tab.sort_checks["name"].isEnabled() and "Pelo menos" in tab.sort_checks["name"].toolTip()
    tab.sort_checks["created"].setChecked(True)
    assert tab.sort_checks["name"].isEnabled()


def test_restore_pages_asks_first(tab, monkeypatch):
    set_page_config("queue", PageConfig(("hltb",), "hltb", True, ()))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    tab.restore_defaults()
    assert page_config("queue").sorts == ("hltb",)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    tab.combo_page.setCurrentIndex(tab.combo_page.findData("queue"))
    tab.restore_defaults()
    assert page_config("queue") == default_config("queue") and tab.sort_checks["created"].isChecked()


# --- aba Atalhos e Aparência ---

def test_shortcuts_tab_lists_the_registry(qapp):
    from frontend_desktop.shortcuts import GROUPS, SHORTCUTS
    tab = ShortcutsTab()
    assert [k.text() for k in tab.key_labels] == [s.keys for g in GROUPS for s in SHORTCUTS if s.group == g]
    assert "F5" not in [s.keys for s in SHORTCUTS]


def test_restore_appearance(qapp, monkeypatch):
    from frontend_desktop.views.components.settings_view import SettingsView
    view = SettingsView()
    emitted = []
    view.settings_changed.connect(lambda: emitted.append(1))
    preferences.set_card_size("large")
    preferences.set_category_scope(preferences.SCOPE_ALL)
    view.restore_appearance()
    assert preferences.card_size() == "medium" and preferences.category_scope() == preferences.SCOPE_COMPLETED
    assert view.scope_buttons[preferences.SCOPE_COMPLETED].isChecked() and emitted == [1]
    view.restore_appearance()
    assert emitted == [1]                                              # nada mudou: não recarrega


# --- abertura do app ---

def test_main_window_opens_maximized_and_f5_only_in_dev(qapp, monkeypatch):
    import sys
    from frontend_desktop import main_app
    from frontend_desktop.views import main_window as mw
    monkeypatch.setattr(mw.MainWindow, "refresh_all_data", lambda self: None)
    preferences.settings().setValue("last_view", 3)
    dev = main_app.create_main_window(qapp)
    assert not preferences.settings().contains("last_view")
    assert any(s.key().toString() == "F5" for s in dev.findChildren(main_app.QShortcut))
    shown = []
    monkeypatch.setattr(dev, "showMaximized", lambda: shown.append(1))
    main_app.show_main_window(dev)
    assert shown == [1]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    packaged = main_app.create_main_window(qapp)
    assert not any(s.key().toString() == "F5" for s in packaged.findChildren(main_app.QShortcut))
    for window in (dev, packaged):
        window.close()
