from PySide6.QtCore import Qt

from frontend_desktop.models.game_list_model import GameRole
from frontend_desktop.models.game_table_model import COLUMNS, GameTableModel, SortRole, cell_text
from frontend_desktop.views.components.game_table import GameTable

GAMES = [
    {"id": 1, "title": "Zelda", "status": "Zerado", "developer": "Nintendo", "score": 9.5, "played_hours": 100,
     "completion_year": 2023, "genres": [{"name": "Aventura"}, {"name": "RPG"}], "platform": {"name": "Switch"}},
    {"id": 2, "title": "Hades", "status": "Platinado", "developer": "Supergiant", "score": 10, "played_hours": 9,
     "completion_year": 2021, "hltb_hours": 22},
    {"id": 3, "title": "Celeste", "status": "Fila", "developer": "Maddy"},
]


def test_cell_text_formats_every_column():
    g = GAMES[0]
    assert [cell_text(g, c) for c in range(len(COLUMNS))][:6] == ["Zelda", "Zerado", "Aventura, RPG", "Switch", "Nintendo", "2023"]
    assert cell_text(GAMES[1], 8) == "22h" and cell_text(GAMES[2], 9) == ""


def test_model_crud_in_place(qapp):
    m = GameTableModel()
    m.set_games(GAMES)
    events = []
    m.rowsInserted.connect(lambda *a: events.append("i"))
    m.dataChanged.connect(lambda *a: events.append("c"))
    m.rowsRemoved.connect(lambda *a: events.append("r"))
    m.insert_game({"id": 9, "title": "Novo"})
    assert m.update_game({"id": 9, "title": "Novo 2"}) and not m.update_game({"id": 77})
    assert m.remove_game(9) and not m.remove_game(9)
    assert events == ["i", "c", "r"] and m.rowCount() == 3


def test_status_is_colored_and_numbers_right_aligned(qapp):
    m = GameTableModel()
    m.set_games(GAMES)
    assert m.index(0, 1).data(Qt.ForegroundRole) is not None       # Zerado
    assert m.index(2, 1).data(Qt.ForegroundRole) is None            # Fila: cor padrão
    assert m.index(0, 6).data(Qt.TextAlignmentRole) & Qt.AlignRight


def test_table_sorts_numerically_not_alphabetically(qapp):
    t = GameTable()
    t.set_games([{"id": i, "title": f"J{i}", "played_hours": h} for i, h in enumerate([9, 100, 20], start=1)])
    t.table.sortByColumn(9, Qt.AscendingOrder)
    assert [g["played_hours"] for g in t.filtered_games] == [9, 20, 100]   # "100" < "20" em texto
    t.table.sortByColumn(9, Qt.DescendingOrder)
    assert [g["played_hours"] for g in t.filtered_games] == [100, 20, 9]


def test_table_filters_by_text_and_status(qapp):
    t = GameTable()
    t.set_games(GAMES)
    assert t.rendered_count == 3 and t.count_label.text() == "3 jogos"
    t.search_input.setText("nintendo")                     # busca também na desenvolvedora
    assert [g["id"] for g in t.filtered_games] == [1] and t.count_label.text() == "1 jogo"
    t.search_input.setText("")
    t.status_filter.setCurrentIndex(t.status_filter.findData("Fila"))
    assert [g["id"] for g in t.filtered_games] == [3]


def test_table_in_place_mutations_and_selection_signal(qapp):
    t = GameTable()
    t.set_games(GAMES)
    t.insert_game({"id": 4, "title": "Inserido", "status": "Fila"})
    assert len(t.games) == 4 and t.rendered_count == 4
    assert t.update_game({"id": 4, "title": "Editado", "status": "Fila"})
    assert t.remove_game(4) and not t.remove_game(4)
    got = []
    t.game_selected.connect(got.append)
    t.on_row_activated(t.proxy.index(0, 3))                # qualquer coluna da linha emite o jogo inteiro
    assert got and got[0]["id"] == t.proxy.index(0, 0).data(GameRole)["id"]


def test_sort_role_for_text_is_case_insensitive(qapp):
    m = GameTableModel()
    m.set_games([{"id": 1, "title": "bravo"}, {"id": 2, "title": "Alpha"}])
    assert m.index(1, 0).data(SortRole) < m.index(0, 0).data(SortRole)
