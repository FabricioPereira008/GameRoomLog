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
    monkeypatch.setattr(mv.api_client, "get_platforms", lambda: [{"id": 1, "name": "PC", "games_count": 2}, {"id": 2, "name": "Switch", "games_count": 0}])
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
    monkeypatch.setattr(cv.api_client, "get_genre_details", lambda gid: {"id": gid, "name": "RPG", "color": "#fff", "total_games": 2, "total_hours_played": 10, "games": []})
    view = CategoryDetailView()
    view.load_category("genre", 1)
    wait(view, qapp)
    assert view.title_label.text() == "RPG"
    assert view.category_data["total_games"] == 2
    view.category_id = 99
    view._on_category_loaded("genre", 1, {"name": "Velho"})
    assert view.title_label.text() == "RPG"
