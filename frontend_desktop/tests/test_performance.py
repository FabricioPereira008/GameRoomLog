import os
import time

from frontend_desktop.models.game_list_model import GameFilterProxy, GameListModel
from frontend_desktop.views.components.game_grid import MODE_BUTTON, MODE_FULL, GameGrid, ScrollableGameGrid, make_predicate

# Orçamentos de tempo escalam em CI/máquinas lentas: PERF_FACTOR=3 pytest
PERF_FACTOR = float(os.environ.get("PERF_FACTOR", "1"))


def sample(n):
    return [
        {"id": i, "title": f"Performance Test Game {i}", "status": "Zerado", "score": 8.5,
         "developer": "Studio Test", "hltb_hours": 20.0, "played_hours": 22.0,
         "platform": {"name": "PC"}, "genres": [{"name": "RPG", "color": "#7c3aed"}]}
        for i in range(n)
    ]


def timed(fn):
    start = time.perf_counter()
    fn()
    return (time.perf_counter() - start) * 1000


def test_loading_600_games_into_grid_is_fast(qapp):
    """Biblioteca real (~600 jogos): carregar não cria widgets por card."""
    grid = ScrollableGameGrid()
    grid.resize(1000, 700)
    grid.show()
    ms = timed(lambda: grid.set_games(sample(600)))
    qapp.processEvents()
    print(f"\n[PERFORMANCE] 600 jogos carregados em {ms:.2f} ms")
    assert len(grid.grid.games) == 600
    assert ms < 80 * PERF_FACTOR, f"Carga de 600 jogos levou {ms:.2f}ms"
    grid.close()


def test_filtering_600_games_is_fast(qapp):
    grid = ScrollableGameGrid()
    grid.resize(1000, 700)
    grid.set_games(sample(600))
    ms = timed(lambda: grid.search_input.setText("Game 55"))
    print(f"\n[PERFORMANCE] Filtro sobre 600 jogos em {ms:.2f} ms")
    assert 0 < len(grid.grid.games) < 600
    assert ms < 50 * PERF_FACTOR, f"Filtro levou {ms:.2f}ms"


def test_proxy_refilter_speed(qapp):
    model = GameListModel()
    model.set_games(sample(2000))
    proxy = GameFilterProxy()
    proxy.setSourceModel(model)
    pred = make_predicate("game 1", lambda g: True)
    ms = timed(lambda: proxy.set_predicate(pred))
    print(f"\n[PERFORMANCE] Proxy refiltrou 2000 jogos em {ms:.2f} ms")
    assert ms < 80 * PERF_FACTOR


def test_in_place_insert_remove_do_not_rebuild(qapp):
    grid = GameGrid(mode=MODE_FULL)
    grid.resize(1000, 700)
    grid.set_games(sample(600))

    def mutate():
        for i in range(100):
            grid.insert_game(0, {"id": 10_000 + i, "title": f"Novo {i}"})
        for i in range(100):
            grid.remove_game(10_000 + i)

    ms = timed(mutate)
    print(f"\n[PERFORMANCE] 100 inserts + 100 removes em {ms:.2f} ms")
    assert len(grid.games) == 600
    assert ms < 100 * PERF_FACTOR


def test_game_room_section_render_is_bounded(qapp):
    grid = GameGrid(mode=MODE_BUTTON)
    grid.resize(1000, 300)
    grid.show()
    ms = timed(lambda: grid.set_games(sample(300)))
    qapp.processEvents()
    print(f"\n[PERFORMANCE] Seção com 300 jogos em {ms:.2f} ms")
    assert grid.rendered_count < 300  # só as linhas abertas
    assert ms < 40 * PERF_FACTOR
    grid.close()
