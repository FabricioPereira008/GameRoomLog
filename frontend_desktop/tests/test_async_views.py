import pytest
from frontend_desktop.views.components.management_view import ManagementView
from frontend_desktop.views.components.yearbook_view import YearbookView
from frontend_desktop.views.components.category_detail_view import CategoryDetailView
from frontend_desktop.workers import ApiWorker, run_async


def wait(widget, qapp):
    for w in list(widget.__dict__.get("_workers", ())):
        w.wait(5000)
    qapp.processEvents()


def test_api_worker_success_and_failure(qapp):
    results, errors = [], []
    ok = ApiWorker(lambda x: x * 2, 21)
    ok.succeeded.connect(results.append)
    ok.run()
    assert results == [42]

    def boom():
        raise RuntimeError("falhou")
    bad = ApiWorker(boom)
    bad.failed.connect(errors.append)
    bad.run()
    assert errors == ["falhou"]


def test_run_async_keeps_reference_until_finished(qapp):
    from PySide6.QtWidgets import QWidget
    owner = QWidget()
    got = []
    run_async(owner, lambda: "ok", got.append)
    wait(owner, qapp)
    assert got == ["ok"]
    assert not owner._workers


def test_management_view_loads_and_filters(qapp, monkeypatch):
    from frontend_desktop.views.components import management_view as mv
    monkeypatch.setattr(mv.api_client, "get_platforms", lambda scope=None: [{"id": 1, "name": "PC", "games_count": 2}, {"id": 2, "name": "Switch", "games_count": 0}])
    view = ManagementView("platform", "Plataforma")
    view.load_data()
    wait(view, qapp)
    assert [i["name"] for i in view.items] == ["PC", "Switch"]
    view.search_input.setText("swi")
    view.render_items()
    assert view.grid_layout.count() == 1


def test_management_view_ignores_stale_response(qapp):
    view = ManagementView("genre", "Gênero")
    view._load_seq = 5
    view.items = [{"id": 1, "name": "atual"}]
    view._on_items_loaded(4, [{"id": 2, "name": "velho"}])
    assert view.items[0]["name"] == "atual"


def test_yearbook_loads_overall_then_year(qapp, monkeypatch):
    from frontend_desktop.views.components import yearbook_view as yv
    monkeypatch.setattr(yv.api_client, "get_overall_stats", lambda: {"available_years": [2025, 2024]})
    monkeypatch.setattr(yv.api_client, "get_yearbook", lambda year: {
        "total_games_finished": 3, "total_platinums": 1, "total_hours_played": 40, "average_score": 8.5, "games": []})
    view = YearbookView()
    view.load_data()
    wait(view, qapp)
    wait(view, qapp)
    assert view.year_combo.count() == 2


def test_yearbook_stale_year_is_ignored(qapp):
    view = YearbookView()
    view._year_seq = 3
    view._on_year_loaded(2, 2020, {"games": [{"id": 1}]})  # resposta antiga: não deve tocar a UI
    assert view.game_grid.games == []


def test_category_detail_loads_and_ignores_navigation_race(qapp, monkeypatch):
    from frontend_desktop.views.components import category_detail_view as cv
    monkeypatch.setattr(cv.api_client, "get_genre_details", lambda gid, scope=None: {"id": gid, "name": "RPG", "color": "#fff", "total_games": 2, "total_hours_played": 10, "games": []})
    view = CategoryDetailView()
    view.load_category("genre", 1)
    wait(view, qapp)
    assert view.title_label.text() == "RPG"
    assert view.category_data["total_games"] == 2
    view.category_id = 99
    view._on_category_loaded("genre", 1, {"name": "Velho"})
    assert view.title_label.text() == "RPG"


def test_shutdown_workers_waits_for_running_threads(qapp):
    import time
    from PySide6.QtWidgets import QWidget
    from frontend_desktop.workers import shutdown_workers
    owner = QWidget()
    done = []
    run_async(owner, lambda: (time.sleep(0.15), "ok")[1], done.append)
    shutdown_workers(qapp)
    qapp.processEvents()
    assert done == ["ok"] and not any(w.isRunning() for w in owner._workers)


def test_management_card_shows_cover_mosaic_hours_and_menu(qapp):
    from frontend_desktop.views.components.management_view import ManageItemCard
    card = ManageItemCard("genre", {"id": 1, "name": "RPG", "color": "#ff0000", "games_count": 3,
                                    "total_hours": 42.5, "cover_samples": ["a.jpg", "b.jpg"]})
    assert card.mosaic.covers == ["a.jpg", "b.jpg"] and card.mosaic.accent_color == "#ff0000"
    from PySide6.QtWidgets import QLabel
    texts = [l.text() for l in card.findChildren(QLabel)]
    assert "3 jogos · 42.5h" in texts
    assert [a.text() for a in card.menu.actions()] == ["Editar", "Excluir"]
    assert card.menu_btn.isHidden()
    card.enterEvent(None)
    assert not card.menu_btn.isHidden()
    card.leaveEvent(None)
    assert card.menu_btn.isHidden()


def test_management_card_platform_badge_and_empty_cover(qapp):
    from frontend_desktop.views.components.management_view import ManageItemCard
    card = ManageItemCard("platform", {"id": 2, "name": "PC", "icon_name": "pc", "games_count": 1})
    assert card.mosaic.badge_icon == "monitor" and card.mosaic.covers == []
    card.mosaic.resize(230, 150)
    card.mosaic.grab()  # pinta o placeholder com a inicial sem falhar


def test_tile_rects_are_side_by_side_slots_inside_the_area():
    from frontend_desktop.views.components.cover_mosaic import tile_rects
    for count in (1, 2, 3, 4):
        rects = tile_rects(count, 240, 160)
        assert len(rects) == count
        assert all(r.left() >= 0 and r.right() < 240 and r.top() >= 0 and r.bottom() < 160 for r in rects)
        assert all(a.right() < b.left() for a, b in zip(rects, rects[1:]))  # sem sobreposição


def test_render_cover_image_contain_keeps_whole_cover(qapp, tmp_path):
    from PySide6.QtGui import QImage, QColor
    from frontend_desktop import cover_loader as cl
    src = QImage(200, 300, QImage.Format_RGB32)
    src.fill(QColor("red"))
    path = str(tmp_path / "c.png")
    src.save(path)
    out = cl.render_cover_image(path, 100, 100, contain=True)
    assert (out.width(), out.height()) in ((66, 100), (67, 100))  # 2:3 inteira, sem recorte
    cropped = cl.render_cover_image(path, 100, 100)
    assert (cropped.width(), cropped.height()) == (100, 100)
