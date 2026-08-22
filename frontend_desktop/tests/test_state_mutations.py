import pytest
from PySide6.QtCore import Qt
from frontend_desktop.views.components.game_card import GameCard, LoadMoreCard, _COVER_PIXMAP_CACHE
from frontend_desktop.views.components.game_grid import GameGrid, ScrollableGameGrid
from frontend_desktop.views.components.game_room_view import GameRoomView
from frontend_desktop.views.components.filter_panel import FilterPanel
from frontend_desktop.views.dialogs.game_dialog import GameDialog

def test_game_card_creation_and_update(qapp):
    game_data = {
        "id": 1,
        "title": "Celeste",
        "score": 9.5,
        "status": "Zerado",
        "developer": "Maddy Makes Games",
        "hltb_hours": 8.0,
        "played_hours": 12.0
    }
    card = GameCard(game_data)
    assert card.game_data["id"] == 1
    assert card.game_data["title"] == "Celeste"
    assert card.title_label.text() == "Celeste"

    # Update data
    updated_data = dict(game_data)
    updated_data["title"] = "Celeste (Updated)"
    updated_data["score"] = 10.0
    card.update_data(updated_data)

    assert card.game_data["title"] == "Celeste (Updated)"
    assert card.title_label.text() == "Celeste (Updated)"

def test_load_more_card_creation(qapp):
    load_card = LoadMoreCard(size_mode="medium")
    assert load_card.size_mode == "medium"
    assert load_card.card_width == 170

def test_game_grid_batch_population_and_mutations(qapp):
    grid = GameGrid()
    sample_games = [
        {"id": i, "title": f"Game {i}", "status": "Zerado", "score": 8.0}
        for i in range(1, 40)
    ]

    # 1. Set games
    grid.set_games(sample_games)
    assert len(grid.games) == 39
    # Initial batch size is capped (at least 24 or cols*4)
    assert len(grid.cards) >= 24
    assert grid.rendered_count == len(grid.cards)

    # 2. Insert new game at index 0
    new_game = {"id": 999, "title": "Game 999", "status": "Zerado"}
    grid.insert_game(0, new_game)
    assert any(g["id"] == 999 for g in grid.games)
    assert any(c.game_data.get("id") == 999 for c in grid.cards)

    # 3. Update existing game
    updated_game = {"id": 999, "title": "Game 999 (Edited)", "status": "Zerado"}
    grid.update_game(updated_game)
    card_999 = next(c for c in grid.cards if c.game_data.get("id") == 999)
    assert card_999.game_data["title"] == "Game 999 (Edited)"

    # 4. Remove game
    grid.remove_game(999)
    assert not any(g["id"] == 999 for g in grid.games)
    assert not any(c.game_data.get("id") == 999 for c in grid.cards)

def test_scrollable_game_grid_pagination(qapp):
    scroll_grid = ScrollableGameGrid()
    sample_games = [
        {"id": i, "title": f"RPG {i}", "status": "Fila"}
        for i in range(1, 60)
    ]
    scroll_grid.set_games(sample_games)
    initial_loaded = scroll_grid.grid.rendered_count
    assert initial_loaded < 60

    # Trigger load more
    scroll_grid.grid.load_more_cards()
    assert scroll_grid.grid.rendered_count > initial_loaded

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

def test_game_dialog_editable_combos(qapp):
    dialog = GameDialog()
    assert dialog.combo_developer.isEditable() is True
    assert dialog.combo_franchise.isEditable() is True
    assert dialog.combo_genre.isEditable() is True
