import io
import time

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from PySide6.QtGui import QImage

from frontend_desktop import cover_loader as cl
from frontend_desktop.models.game_list_model import GameFilterProxy, GameListModel, GameRole
from frontend_desktop.views.components.game_card_delegate import (
    CARD_WIDTHS, CardMetrics, genre_badge_limits, GameCardDelegate, text_color_for
)
from frontend_desktop.views.components.game_grid import (
    MODE_BUTTON, MODE_FULL, GameGrid, ScrollableGameGrid, make_predicate
)
from frontend_desktop.views.components.game_room_view import GameRoomView


def games(n, status="Fila", start=1):
    return [{"id": i, "title": f"Jogo {i}", "status": status} for i in range(start, start + n)]


# ---------- model / proxy ----------
def test_model_set_insert_update_remove(qapp):
    model = GameListModel()
    model.set_games(games(3))
    assert model.rowCount() == 3 and model.index(1).data(GameRole)["title"] == "Jogo 2"

    model.insert_game(0, {"id": 99, "title": "Novo"})
    assert model.index(0).data(GameRole)["id"] == 99 and model.rowCount() == 4

    assert model.update_game({"id": 2, "title": "Editado"}) is True
    assert model.index(model.row_for_id(2)).data() == "Editado"
    assert model.update_game({"id": 1234, "title": "x"}) is False

    assert model.remove_game(99) is True and model.remove_game(99) is False
    assert [g["id"] for g in model.games] == [1, 2, 3]


def test_model_tooltip_lists_genres(qapp):
    from PySide6.QtCore import Qt
    model = GameListModel()
    model.set_games([{"id": 1, "title": "Dead Cells", "genres": [{"name": "Roguelike"}, {"name": "Metroidvania"}]},
                     {"id": 2, "title": "Sem gênero"}])
    assert model.index(0, 0).data(Qt.ToolTipRole) == "Dead Cells\nRoguelike · Metroidvania"
    assert model.index(1, 0).data(Qt.ToolTipRole) == "Sem gênero"
    assert model.index(0, 0).data(Qt.DisplayRole) == "Dead Cells"


def test_model_notifies_in_place_changes(qapp):
    model = GameListModel()
    model.set_games(games(2))
    events = []
    model.rowsInserted.connect(lambda *a: events.append("insert"))
    model.rowsRemoved.connect(lambda *a: events.append("remove"))
    model.dataChanged.connect(lambda *a: events.append("changed"))
    model.insert_game(1, {"id": 7, "title": "A"})
    model.update_game({"id": 7, "title": "B"})
    model.remove_game(7)
    assert events == ["insert", "changed", "remove"]  # nenhum reset completo


def test_proxy_filters_by_predicate_and_follows_edits(qapp):
    model = GameListModel()
    model.set_games([{"id": 1, "title": "Zelda"}, {"id": 2, "title": "Mario"}])
    proxy = GameFilterProxy()
    proxy.setSourceModel(model)
    proxy.set_predicate(lambda g: "zel" in g["title"].lower())
    assert [g["id"] for g in proxy.games] == [1]
    model.update_game({"id": 2, "title": "Zelda 2"})
    assert [g["id"] for g in proxy.games] == [1, 2]
    proxy.set_predicate(None)
    assert len(proxy.games) == 2


def test_make_predicate_combines_query_and_matcher():
    pred = make_predicate("  MAR ", lambda g: g.get("developer") == "Nintendo")
    assert pred({"title": "Super Mario", "developer": "Nintendo"}) is True
    assert pred({"title": "Super Mario", "developer": "Outra"}) is False
    assert pred({"title": "Zelda", "developer": "Nintendo"}) is False


# ---------- grid ----------
def test_grid_exposes_all_games_and_mutates_in_place(qapp):
    grid = GameGrid(mode=MODE_FULL)
    grid.resize(900, 600)
    grid.set_games(games(39))
    assert len(grid.games) == 39 and grid.rendered_count == 39

    grid.insert_game(0, {"id": 999, "title": "Novo", "status": "Fila"})
    assert grid.games[0]["id"] == 999
    assert grid.update_game({"id": 999, "title": "Editado", "status": "Fila"})
    assert grid.games[0]["title"] == "Editado"
    assert grid.remove_game(999) is True and all(g["id"] != 999 for g in grid.games)


def test_button_mode_limits_rows_and_shows_more(qapp):
    grid = GameGrid(mode=MODE_BUTTON)
    grid.resize(900, 400)
    grid.show()
    grid.set_games(games(60))
    qapp.processEvents()
    first = grid.rendered_count
    assert 0 < first < 60 and not grid.more_button.isHidden()
    grid.load_more_cards()
    assert grid.rendered_count > first
    for _ in range(10):
        grid.load_more_cards()
    assert grid.rendered_count == 60 and grid.more_button.isHidden()
    grid.close()


def test_button_mode_height_follows_content(qapp):
    grid = GameGrid(mode=MODE_BUTTON)
    grid.resize(900, 400)
    grid.show()
    grid.set_games([])
    assert grid.view.height() == 0 or grid.view.maximumHeight() == 0
    grid.set_games(games(3))
    qapp.processEvents()
    assert grid.view.maximumHeight() >= grid.delegate.metrics.card_height
    grid.close()


def test_grid_click_emits_game(qapp):
    grid = GameGrid(mode=MODE_FULL)
    grid.resize(900, 600)
    grid.set_games(games(3))
    got = []
    grid.game_selected.connect(got.append)
    grid.view.game_clicked.emit({"id": 2})
    assert got == [{"id": 2}]
    grid.view._emit_game(grid.proxy.index(1, 0))
    assert got[-1]["id"] == 2


def test_scrollable_grid_filters_and_keeps_full_source(qapp):
    sg = ScrollableGameGrid()
    sg.set_games(games(59))
    assert len(sg.all_games_source) == 59 and len(sg.grid.games) == 59
    sg.search_input.setText("Jogo 5")
    assert {g["id"] for g in sg.grid.games} == {5, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59}
    assert len(sg.all_games_source) == 59  # fonte intacta
    sg.clear_filters()
    assert len(sg.grid.games) == 59


def test_scrollable_grid_in_place_mutations_respect_filter(qapp):
    sg = ScrollableGameGrid()
    sg.set_games([{"id": 1, "title": "Zelda"}, {"id": 2, "title": "Mario"}])
    sg.search_input.setText("zel")
    sg.insert_game(0, {"id": 3, "title": "Outro"})       # não casa com a busca
    sg.insert_game(0, {"id": 4, "title": "Zelda II"})    # casa
    assert {g["id"] for g in sg.grid.games} == {1, 4}
    assert len(sg.all_games_source) == 4
    sg.remove_game(1)
    assert {g["id"] for g in sg.grid.games} == {4}


def test_search_typing_is_debounced_but_programmatic_is_immediate(qapp):
    sg = ScrollableGameGrid()
    sg.set_games(games(10))
    sg.show()
    sg.search_input.setFocus()
    qapp.processEvents()
    if sg.search_input.hasFocus():
        sg.search_input.setText("Jogo 1")
        assert sg._debounce.isActive()           # digitação: espera o timer
        assert len(sg.grid.games) == 10
        sg._debounce.timeout.emit()              # equivale a esperar 150 ms
        assert len(sg.grid.games) == 2           # Jogo 1 e Jogo 10
    sg.close()


def test_changing_card_size_updates_delegate(qapp):
    from PySide6.QtCore import QSettings
    settings = QSettings("GameRoom", "GameRoomLog")
    old = settings.value("card_size", "medium")
    try:
        grid = GameGrid(mode=MODE_FULL)
        settings.setValue("card_size", "large")
        grid.set_games(games(2))
        assert grid.delegate.metrics.card_width == CARD_WIDTHS["large"]
        settings.setValue("card_size", "small")
        grid.set_games(games(2))
        assert grid.delegate.metrics.card_width == CARD_WIDTHS["small"]
    finally:
        settings.setValue("card_size", old)


# ---------- game room ----------
def test_game_room_sections_follow_data_and_mutations(qapp):
    room = GameRoomView()
    room.show()
    room.set_games(games(1, "Jogando"), [], games(2, "Fila", 10), games(3, "Zerado", 20), [])
    assert not room.sec_now.isHidden() and room.sec_next.isHidden() and room.sec_platinum.isHidden()

    room.insert_game_by_status({"id": 50, "title": "Platina", "status": "Platinado"})
    assert not room.sec_platinum.isHidden() and not room.sec_finished.isHidden()
    assert room.grid_finished.games[0]["id"] == 50 and room.grid_platinum.games[0]["id"] == 50

    assert room.update_game({"id": 50, "title": "Platina 2", "status": "Platinado"})
    assert room.grid_platinum.games[0]["title"] == "Platina 2"

    assert room.remove_game(50) is True
    assert room.sec_platinum.isHidden() and all(g["id"] != 50 for g in room.grid_finished.games)
    room.close()


# ---------- delegate ----------
def test_card_metrics_scale_with_size_mode():
    small, medium, large = (CardMetrics.for_mode(m) for m in ("small", "medium", "large"))
    assert small.card_width < medium.card_width < large.card_width
    assert small.card_height < medium.card_height < large.card_height
    assert CardMetrics.for_mode("desconhecido") == medium


class _FakeFM:
    """Métrica de fonte previsível: 6px por caractere."""
    def horizontalAdvance(self, text):
        return 6 * len(text)


def test_genre_badge_limits_share_space():
    fm = _FakeFM()
    g = lambda n: {"name": n}
    assert genre_badge_limits([], fm, 150) == []
    assert genre_badge_limits([g("RPG")], fm, 150) == [150]
    # cabem inteiros: o secundário usa o que sobra depois do principal
    assert genre_badge_limits([g("RPG"), g("Terror")], fm, 150) == [150, 150 - (18 + 12 + 4)]
    # não cabem: secundário curto cede espaço ao principal
    limits = genre_badge_limits([g("A" * 20), g("Terror")], fm, 110)
    assert limits == [110 - 4 - 48, 48]
    # dois longos: metade para cada
    assert genre_badge_limits([g("A" * 20), g("B" * 20)], fm, 110) == [53, 53]


def test_card_paints_both_genres_and_platform(qapp, monkeypatch):
    from frontend_desktop.views.components import game_card_delegate as gcd
    drawn = []
    original = gcd.GameCardDelegate._badge

    def spy(painter, font, fm, x, y, text, bg, fg, right_limit, border=None):
        drawn.append((text, border is not None))
        return original(painter, font, fm, x, y, text, bg, fg, right_limit, border)
    monkeypatch.setattr(gcd.GameCardDelegate, "_badge", staticmethod(spy))
    grid = GameGrid(mode=MODE_FULL)
    grid.resize(700, 500)
    grid.set_games([{"id": 1, "title": "Dead Cells", "platform": {"name": "PC"}, "score": 9.0, "played_hours": 30,
                     "genres": [{"name": "Roguelike", "color": "#ff0000"}, {"name": "Metroidvania", "color": "bad"}]}])
    grid.show()
    qapp.processEvents()
    grid.grab()
    texts = [t for t, _ in drawn]
    assert "Roguelike" in texts and "PC" in texts and "9.0" in texts
    secondary = [t for t, outlined in drawn if outlined]
    assert secondary and secondary[0].startswith("Metro")  # secundário com contorno (pode ser elidido)
    grid.close()


def test_text_color_contrast_for_genre_badges():
    assert text_color_for("#ffffff").name() == "#000000"
    assert text_color_for("#111111").name() == "#ffffff"
    assert text_color_for("não-é-cor").name() == "#ffffff"


def test_delegate_paints_full_and_minimal_games(qapp):
    grid = GameGrid(mode=MODE_FULL)
    grid.resize(700, 500)
    grid.set_games([
        {"id": 1, "title": "Completo com um título realmente muito longo para elidir", "status": "Zerado",
         "platform": {"name": "PlayStation 5"}, "genres": [{"name": "Action RPG", "color": "#7c3aed"}],
         "score": 9.5, "played_hours": 42, "cover_image": None},
        {"id": 2, "title": "Mínimo"},
    ])
    grid.show()
    qapp.processEvents()
    image = grid.grab().toImage()
    non_bg = sum(1 for x in range(0, image.width(), 7) for y in range(0, image.height(), 7)
                 if image.pixelColor(x, y).alpha() > 0 and image.pixelColor(x, y).lightness() > 25)
    assert non_bg > 50  # algo foi pintado (cards, texto, badges)
    grid.close()


# ---------- cover loader ----------
def _png(path, size=(60, 90)):
    img = QImage(size[0], size[1], QImage.Format_RGB32)
    img.fill(0xFF3366CC)
    assert img.save(str(path), "PNG")
    return str(path)


def _wait(loader, cond, timeout_ms=3000):
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(10)
    deadline = time.monotonic() + timeout_ms / 1000

    def check():
        QCoreApplication.processEvents()
        if cond() or time.monotonic() > deadline:
            loop.quit()
    timer.timeout.connect(check)
    timer.start()
    loop.exec()
    timer.stop()


def test_cover_loader_loads_in_background_and_caches(qapp, tmp_path, monkeypatch):
    path = _png(tmp_path / "a.png")
    calls = []
    monkeypatch.setattr(cl.api_client, "get_cover_path", lambda name: calls.append(name) or path)
    loader = cl.CoverLoader(max_items=10, threads=2)
    ready = []
    loader.loaded.connect(ready.append)

    assert loader.request("a.png", 100, 150) is None          # nunca bloqueia
    _wait(loader, lambda: ready)
    pm = loader.request("a.png", 100, 150)
    assert pm is not None and (pm.width(), pm.height()) == (100, 150)
    assert loader.request("a.png", 100, 150) is pm            # cache hit
    assert calls == ["a.png"]
    loader.wait_for_done()


def test_cover_loader_failure_is_not_retried_until_invalidated(qapp, monkeypatch):
    calls = []
    monkeypatch.setattr(cl.api_client, "get_cover_path", lambda name: calls.append(name) or None)
    loader = cl.CoverLoader(max_items=10, threads=1)
    loader.request("x.png", 50, 75)
    _wait(loader, lambda: not loader._pending)
    loader.request("x.png", 50, 75)
    loader.wait_for_done()
    QCoreApplication.processEvents()
    assert calls == ["x.png"]
    loader.invalidate("x.png")
    loader.request("x.png", 50, 75)
    _wait(loader, lambda: not loader._pending)
    assert calls == ["x.png", "x.png"]


def test_cover_loader_lru_evicts_oldest(qapp, tmp_path, monkeypatch):
    path = _png(tmp_path / "b.png")
    monkeypatch.setattr(cl.api_client, "get_cover_path", lambda name: path)
    loader = cl.CoverLoader(max_items=3, threads=2)
    for i in range(5):
        loader.request(f"c{i}.png", 40, 60)
    _wait(loader, lambda: len(loader._pending) == 0 and len(loader) >= 3)
    loader.wait_for_done()
    QCoreApplication.processEvents()
    assert len(loader) <= 3


def test_render_cover_image_crops_and_rounds(qapp, tmp_path):
    path = _png(tmp_path / "wide.png", size=(300, 100))
    out = cl.render_cover_image(path, 80, 120)
    assert (out.width(), out.height()) == (80, 120)
    assert out.pixelColor(0, 0).alpha() == 0          # canto arredondado transparente
    assert out.pixelColor(40, 60).alpha() == 255
    assert cl.render_cover_image(str(tmp_path / "nao-existe.png"), 10, 10) is None


def test_empty_state_message_follows_results(qapp):
    from frontend_desktop.views.components.game_grid import MODE_INFINITE
    grid = GameGrid(mode=MODE_INFINITE)
    grid.resize(800, 500)
    grid.set_games([])
    assert not grid.empty_label.isHidden()
    grid.set_games(games(3))
    assert grid.empty_label.isHidden()
    grid.set_predicate(lambda g: False)
    assert not grid.empty_label.isHidden()
    section = GameGrid(mode=MODE_BUTTON)
    section.set_games([])
    assert section.empty_label.isHidden()  # seções do Game Room simplesmente somem
