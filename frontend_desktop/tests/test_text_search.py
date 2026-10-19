"""Buscas e filtros da GUI ignoram maiúsculas e acentos."""
from frontend_desktop.text_search import fold, fold_query
from frontend_desktop.views.components.filter_panel import FilterPanel
from frontend_desktop.views.components.game_grid import make_predicate
from frontend_desktop.views.components.game_table import GameTable
from frontend_desktop.views.components.management_view import ManagementView

POKEMON = {"id": 1, "title": "Pokémon Legends: Arceus", "developer": "Game Freak", "status": "Fila"}
OKAMI = {"id": 2, "title": "Ōkami HD", "developer": "Clover Studio", "status": "Fila"}
SOULS = {"id": 3, "title": "Dark Souls", "developer": "FromSoftware", "status": "Zerado"}


def test_fold_removes_accents_and_case():
    assert fold("Pokémon") == "pokemon"
    assert fold("ÉRICA São Paulo") == "erica sao paulo"
    assert fold("Ōkami") == "okami"
    assert fold(None) == "" and fold("") == ""


def test_fold_query_strips_whitespace():
    assert fold_query("  Pokémon  ") == "pokemon"
    assert fold_query(None) == ""


def test_grid_predicate_matches_without_accents():
    always = lambda g: True
    assert make_predicate("pokemon", always)(POKEMON)
    assert make_predicate("POKÉMON legends", always)(POKEMON)
    assert make_predicate("okami", always)(OKAMI)
    assert not make_predicate("okami", always)(SOULS)
    assert make_predicate("", always)(SOULS)


def test_table_search_matches_without_accents(qapp):
    t = GameTable()
    t.set_games([POKEMON, OKAMI, SOULS])
    t.search_input.setText("pokemon")
    assert [g["id"] for g in t.filtered_games] == [1]
    t.search_input.setText("clover")                       # desenvolvedora também
    assert [g["id"] for g in t.filtered_games] == [2]


def test_filter_panel_text_filters_ignore_accents(qapp):
    panel = FilterPanel()
    panel.set_options(genres=[{"id": 1, "name": "Ação"}], developers=[], platforms=[], franchises=[])
    game = {**POKEMON, "genres": [{"id": 1, "name": "Ação"}], "platform": None, "franchise": None}
    panel.combo_genre.setText("acao")
    assert panel.matches(game)
    panel.combo_genre.clear()
    panel.combo_dev.setText("GAME FREAK")
    assert panel.matches(game)
    panel.combo_dev.setText("nintendo")
    assert not panel.matches(game)


def test_management_view_search_ignores_accents(qapp):
    view = ManagementView("genre", "Gênero")
    view.items = [{"id": 1, "name": "Ação", "games_count": 1}, {"id": 2, "name": "Puzzle", "games_count": 1}]
    view.search_input.setText("acao")
    view.render_items()
    assert view.grid_layout.count() == 1
