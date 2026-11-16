"""Filtro "Só jogos favoritos" e atualização in-place da página de categoria."""
import json

import pytest

from frontend_desktop import page_settings, preferences
from frontend_desktop.page_settings import page_config, set_page_config
from frontend_desktop.views.components.filter_panel import FilterPanel
from frontend_desktop.views.components.game_grid import ScrollableGameGrid

GAMES = [
    {"id": 1, "title": "Elden Ring", "status": "Zerado", "is_favorite": True, "genres": [{"id": 7, "name": "Soulslike"}],
     "played_hours": 100},
    {"id": 2, "title": "Dark Souls", "status": "Zerado", "is_favorite": False, "genres": [{"id": 7, "name": "Soulslike"}],
     "played_hours": 50},
]


def _ids(grid):
    return [g["id"] for g in grid.grid.games]


# --- filtro ---
def test_favorites_checkbox_filters_counts_and_clears(qapp):
    panel = FilterPanel()
    panel.set_visible_fields(page_settings.PAGES["finished"].filters)
    assert panel.is_field_visible("favorites")
    assert panel.matches(GAMES[1])
    panel.chk_favorites.setChecked(True)
    assert panel.matches(GAMES[0]) and not panel.matches(GAMES[1])
    assert panel.count_active_filters() == 1 and panel.btn_toggle.text() == "Filtros (1)"
    panel.clear_filters()
    assert not panel.chk_favorites.isChecked() and panel.matches(GAMES[1])


def test_hidden_favorites_field_is_reset(qapp):
    panel = FilterPanel()
    panel.set_visible_fields(page_settings.PAGES["finished"].filters)
    panel.chk_favorites.setChecked(True)
    panel.set_visible_fields(("genre",))
    assert not panel.chk_favorites.isChecked() and not panel.chk_favorites.isVisibleTo(panel)


def test_unfavoriting_hides_card_while_filter_is_on(qapp):
    grid = ScrollableGameGrid()
    grid.configure_page("finished")
    grid.set_games([dict(g) for g in GAMES])
    grid.filter_panel.chk_favorites.setChecked(True)
    assert _ids(grid) == [1]
    grid.update_game(dict(GAMES[1], is_favorite=True))
    assert sorted(_ids(grid)) == [1, 2]
    grid.update_game(dict(GAMES[0], is_favorite=False))
    assert _ids(grid) == [2]


# --- configuração das páginas ---
def test_favorites_field_is_on_every_page():
    for page, spec in page_settings.PAGES.items():
        assert "favorites" in spec.filters, page
        assert "favorites" in page_config(page).filters


def test_config_saved_before_the_field_existed_shows_it():
    # como as versões anteriores gravavam: sem "known_filters" e, claro, sem "favorites"
    preferences.settings().setValue("pages/finished", json.dumps({
        "sorts": ["finish_date", "name"], "default_sort": "name", "default_descending": False,
        "filters": ["genre", "plays"]}))
    config = page_config("finished")
    assert config.filters == ("genre", "favorites", "plays")
    assert config.default_sort == "name"


def test_user_can_hide_the_new_field():
    config = page_config("finished")
    set_page_config("finished", page_settings.PageConfig(config.sorts, config.default_sort,
                                                         config.default_descending,
                                                         tuple(f for f in config.filters if f != "favorites")))
    assert "favorites" not in page_config("finished").filters  # escolha gravada com known_filters
    raw = json.loads(preferences.settings().value("pages/finished"))
    assert "favorites" in raw["known_filters"]


# --- página de categoria ---
@pytest.fixture
def window(qapp, monkeypatch):
    from frontend_desktop.views import main_window as mw
    monkeypatch.setattr(mw.api_client, "get_games", lambda **kw: [dict(g) for g in GAMES])
    for name in ("get_genres", "get_developers", "get_platforms", "get_franchises"):
        monkeypatch.setattr(mw.api_client, name, lambda: [])
    w = mw.MainWindow(auto_load=False)
    w.refresh_all_data_sync()
    yield w
    w.close()
    for owner in [w, *w._views.values()]:
        for worker in list(owner.__dict__.get("_workers", ())):
            worker.wait(5000)
    import shiboken6
    shiboken6.delete(w)


@pytest.fixture
def category(window, monkeypatch):
    """Página do gênero Soulslike aberta, com carregamento síncrono e contagem de recargas."""
    from frontend_desktop.views.components import category_detail_view as cdv
    loads = []
    served = [dict(g) for g in GAMES]  # o que o servidor devolve (o teste pode tirar jogos)

    def details(category_id, scope=None):
        loads.append(category_id)
        return {"name": "Soulslike", "color": "#16a34a", "total_games": len(served), "total_hours_played": 150,
                "games": [dict(g) for g in served]}
    monkeypatch.setattr(cdv.api_client, "get_genre_details", details)
    monkeypatch.setattr(cdv, "run_async", lambda owner, fn, ok, err=None, *a: ok(fn(*a)))
    window.open_category_detail("genre", 7)
    assert loads == [7]
    view = window.view_category_detail
    view.served = served
    return view, loads


def _card(view, gid):
    return next(g for g in view.game_grid.all_games_source if g["id"] == gid)


def test_favorite_toggle_updates_category_page_in_place(window, category, monkeypatch):
    view, loads = category
    from frontend_desktop.views import main_window as mw
    monkeypatch.setattr(mw, "run_async", lambda owner, fn, ok, err=None, *a: ok(fn(*a)))
    monkeypatch.setattr(mw.api_client, "update_game", lambda gid, data: dict(GAMES[1], **data))
    window.toggle_favorite(dict(GAMES[1]))
    assert _card(view, 2)["is_favorite"] is True
    assert loads == [7]  # só o card mudou: sem recarregar a página


def test_category_reloads_when_membership_or_stats_change(window, category):
    view, loads = category
    window.apply_game_mutation(dict(GAMES[0], played_hours=120), old_status="Zerado")
    assert loads == [7, 7]
    window.apply_game_mutation(dict(GAMES[0], played_hours=120, genres=[]), old_status="Zerado")
    assert loads == [7, 7, 7]


def test_category_not_current_only_updates_in_place(window, category):
    view, loads = category
    window.switch_view(0)
    window.apply_game_mutation(dict(GAMES[0], played_hours=1, is_favorite=False), old_status="Zerado")
    assert loads == [7] and _card(view, 1)["is_favorite"] is False


def test_deleting_game_removes_it_from_category(window, category):
    view, loads = category
    view.served.pop()  # o servidor já excluiu o jogo 2
    window.apply_game_deletion(2)
    assert [g["id"] for g in view.game_grid.all_games_source] == [1]
    assert loads == [7, 7]  # números da categoria mudaram
    window.apply_game_deletion(99)  # não estava na página
    assert loads == [7, 7]


def test_without_category_page_nothing_breaks(window):
    window.apply_game_mutation(dict(GAMES[0], is_favorite=False), old_status="Zerado")
    window.apply_game_deletion(1)
