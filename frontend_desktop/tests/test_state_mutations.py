import pytest
from PySide6.QtCore import Qt
from frontend_desktop.views.components.game_card import GameCard, LoadMoreCard, _COVER_PIXMAP_CACHE
from frontend_desktop.views.components.game_grid import GameGrid, ScrollableGameGrid

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
