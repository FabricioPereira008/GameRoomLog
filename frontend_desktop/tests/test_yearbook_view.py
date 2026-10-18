from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QMessageBox

from frontend_desktop.views.components import yearbook_view as yv
from frontend_desktop.views.components.charts import BarRow, HorizontalBarChart, MonthlyBarChart, _bar_path
from frontend_desktop.views.dialogs.top3_dialog import Top3Dialog, game_option_text

GAMES = [
    {"id": 1, "title": "Hades", "score": 9.0},
    {"id": 2, "title": "Celeste", "score": 9.5},
    {"id": 3, "title": "Sem Nota", "score": None},
]


def wait(widget, qapp):
    for w in list(widget.__dict__.get("_workers", ())):
        w.wait(5000)
    qapp.processEvents()


def test_bar_path_rounds_only_the_tip():
    from PySide6.QtCore import QRectF
    vertical = _bar_path(QRectF(0, 0, 10, 50), vertical=True).boundingRect()
    horizontal = _bar_path(QRectF(0, 0, 50, 10), vertical=False).boundingRect()
    assert (vertical.width(), vertical.height()) == (10, 50)
    assert (horizontal.width(), horizontal.height()) == (50, 10)


def test_monthly_chart_pads_data_paints_and_hits(qapp):
    chart = MonthlyBarChart()
    chart.set_data([1, 0, 3], 2025)
    assert len(chart.values) == 12 and chart.values[2] == 3
    chart.resize(600, 200)
    chart.grab()  # executa o paintEvent
    assert len(chart._hits) == 12
    index = chart.index_at(QPointF(chart._hits[2][0].center()))
    assert index == 2
    assert chart.tooltip_for(2) == "mar/2025: 3 jogos zerados"
    assert chart.tooltip_for(0) == "jan/2025: 1 jogo zerado"
    assert chart.index_at(QPointF(-5, -5)) is None
    chart.set_data([], None)
    chart.grab()  # estado vazio
    assert chart.tooltip_for(0) == "jan: 0 jogos zerados"


def test_hover_dims_other_bars(qapp):
    chart = MonthlyBarChart()
    assert chart._bar_color(0).alpha() == 255
    chart.hover_index = 1
    assert chart._bar_color(0).alpha() == 150
    assert chart._bar_color(1).alpha() == 255


def test_horizontal_chart_rows_height_and_tooltips(qapp):
    chart = HorizontalBarChart(value_format=lambda v: f"{v:g}h", max_rows=2)
    chart.resize(400, 100)
    chart.grab()  # estado vazio
    chart.set_rows([BarRow("RPG", 30, dot_color="#ff0000"), BarRow("Ação", 0), BarRow("Cortado", 5)])
    assert [r.label for r in chart.rows] == ["RPG", "Ação"]
    assert chart.height() == 2 * chart.ROW_H + 8
    chart.grab()
    assert len(chart._hits) == 2
    assert chart.tooltip_for(1) == "Ação: 0h"
    chart.set_rows([BarRow("RPG", 30, tooltip="RPG: 2 jogos")])
    assert chart.tooltip_for(0) == "RPG: 2 jogos"


def test_top3_dialog_orders_by_score_and_preselects(qapp):
    dialog = Top3Dialog(2025, GAMES, [1], None)
    combo = dialog.combos[0]
    assert [combo.itemData(i) for i in range(combo.count())] == [None, 2, 1, 3]
    assert combo.currentData() == 1
    assert dialog.combos[1].currentData() is None
    assert game_option_text(GAMES[0]) == "Hades   (nota 9)"
    assert game_option_text({"title": None, "score": None}) == "Sem título"


def test_top3_dialog_save_rejects_duplicates(qapp, monkeypatch):
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a))
    dialog = Top3Dialog(2025, GAMES, [2, 2], None)
    dialog.save()
    assert warned and dialog.selected_ids is None
    dialog.combos[1].setCurrentIndex(dialog.combos[1].findData(1))
    dialog.save()
    assert dialog.selected_ids == [2, 1]


def test_top3_dialog_suggestion_returns_empty_list(qapp):
    dialog = Top3Dialog(2025, GAMES, [], None)
    dialog.use_suggestion()
    assert dialog.selected_ids == []


def _summary(**extra):
    base = {
        "total_games_finished": 2, "total_platinums": 1, "total_hours_played": 50, "average_score": 9.2,
        "previous_year_finished": 1, "games": GAMES[:2], "top3": [GAMES[1], GAMES[0]], "top3_custom": False,
        "monthly_finished": [0, 1, 1] + [0] * 9,
        "genres": [{"name": "Roguelike", "count": 1, "hours": 20, "color": "#123456"}],
        "platforms": [{"name": "PC", "count": 2, "hours": 50}],
        "developers": [{"name": "Supergiant", "count": 1}], "franchises": [],
        "longest_game": {"title": "Hades", "played_hours": 30}, "best_game": GAMES[1],
        "hardest_game": {"title": "Celeste", "difficulty": 9}, "average_hours": 25, "average_difficulty": 7,
        "replays": 1,
    }
    base.update(extra)
    return base


def test_yearbook_shows_podium_charts_and_highlights(qapp):
    view = yv.YearbookView()
    view._year_seq = 1
    view._on_year_loaded(1, 2025, _summary())
    assert view.podium_cards[1].game["id"] == 2
    assert view.podium_cards[3].isHidden()
    assert view.podium_hint.text().startswith("Sugestão")
    assert view.btn_top3.isEnabled()
    assert view.card_finished.findChildren(type(view.podium_hint))  # título com comparação
    assert view.monthly_chart.values[1] == 1
    assert view.genre_chart.rows[0].dot_color == "#123456"
    assert view.platform_chart.rows[0].value == 50
    assert view.compare_text(2, 1, 2025) == "Jogos Zerados · +1 vs 2024"
    assert view.compare_text(1, 1, 2025) == "Jogos Zerados · igual a 2024"
    assert view.compare_text(1, None, 2025) == "Jogos Zerados"

    view._on_year_loaded(1, 2025, _summary(top3_custom=True))
    assert view.podium_hint.text() == "Escolhido por você"
    view._on_year_loaded(1, 2025, _summary(games=[], top3=[], developers=[], average_hours=None,
                                           average_difficulty=None, replays=0, longest_game=None,
                                           best_game=None, hardest_game=None))
    assert not view.btn_top3.isEnabled()
    assert view.podium_empty.isVisibleTo(view)
    assert view.podium_hint.text() == ""


def test_choose_top3_saves_and_reloads(qapp, monkeypatch):
    saved = []
    monkeypatch.setattr(yv.api_client, "set_yearbook_top3",
                        lambda year, ids: saved.append((year, ids)) or _summary(top3=[GAMES[0]], top3_custom=True))

    class FakeDialog:
        def __init__(self, year, games, current, parent):
            assert current == [2, 1]  # pódio escolhido antes vem pré-selecionado
            self.selected_ids = [1]

        def exec(self):
            return True

    monkeypatch.setattr(yv, "Top3Dialog", FakeDialog)
    view = yv.YearbookView()
    view._year_seq = 1
    view._on_year_loaded(1, 2025, _summary(top3_custom=True))
    view.choose_top3()
    wait(view, qapp)
    assert saved == [(2025, [1])]
    assert view.podium_cards[1].game["id"] == 1
    assert view.podium_cards[2].isHidden()


def test_choose_top3_without_games_does_nothing(qapp, monkeypatch):
    monkeypatch.setattr(yv, "Top3Dialog", lambda *a: (_ for _ in ()).throw(AssertionError("não deve abrir")))
    view = yv.YearbookView()
    view.choose_top3()


def test_save_top3_error_is_reported(qapp, monkeypatch):
    errors = []
    monkeypatch.setattr(yv.api_client, "set_yearbook_top3", lambda year, ids: (_ for _ in ()).throw(RuntimeError("422")))
    monkeypatch.setattr(yv.QMessageBox, "critical", lambda *a: errors.append(a[2]))
    view = yv.YearbookView()
    view.current_year = 2025
    view._save_top3([1, 1])
    wait(view, qapp)
    assert errors and "422" in errors[0]


def test_podium_card_click_emits_game(qapp):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    view = yv.YearbookView()
    view._year_seq = 1
    view._on_year_loaded(1, 2025, _summary())
    got = []
    card = view.podium_cards[1]
    card.clicked.connect(got.append)
    QTest.mouseClick(card, Qt.LeftButton, pos=QPoint(5, 5))
    assert got and got[0]["id"] == 2
