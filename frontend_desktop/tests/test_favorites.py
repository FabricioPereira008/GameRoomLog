"""Favoritos e rankings na GUI: regras, ApiClient, diálogos, tela, menu de contexto e selo nas capas."""
import json

import pytest
import requests
import responses
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QContextMenuEvent, QImage, QPainter
from PySide6.QtWidgets import QMessageBox, QStyleOptionViewItem

from frontend_desktop import rankings as rk
from frontend_desktop.api_client.client import ApiClient
from frontend_desktop.models.game_table_model import FAVORITE_COLUMN, cell_text, sort_key
from frontend_desktop.views.components import favorites_view as fv
from frontend_desktop.views.dialogs import ranking_dialog as rd
from frontend_desktop.views.dialogs.game_dialog import rankings_text
from frontend_desktop.views.dialogs.ranking_picker_dialog import RankingPickerDialog, candidates

SOUL = {"id": 7, "name": "Soulslike"}
ELDEN = {"id": 1, "title": "Elden Ring", "status": "Zerado", "score": 10, "is_favorite": True,
         "genres": [{"id": 3, "name": "RPG"}, SOUL], "platform": {"id": 2, "name": "PC"}, "platform_id": 2}
DS = {"id": 2, "title": "Dark Souls", "status": "Zerado", "score": 9, "genres": [SOUL], "franchise_id": 5}
MARIO = {"id": 3, "title": "Mario", "status": "Fila", "score": None, "genres": [], "is_favorite": True}
DS_REPLAY = {"id": 4, "title": "Dark Souls", "status": "Zerado", "genres": [SOUL], "replay_of_id": 2,
             "is_favorite": True}
GAMES = [ELDEN, DS, MARIO, DS_REPLAY]


def ranking(rid=10, name="Top", max_size=10, entries=(), **extra):
    return {"id": rid, "name": name, "max_size": max_size, "position": 0, "entries": list(entries),
            "genre_id": None, "franchise_id": None, "platform_id": None, "filter_type": None,
            "filter_label": None, "out_of_filter_ids": [], **extra}


SOULS = ranking(11, "Top Soulslike", 3, genre_id=7, filter_type="genre", filter_label="Soulslike")


@pytest.fixture
def sync(monkeypatch):
    """run_async síncrono na tela de Favoritos e na janela principal."""
    from frontend_desktop.views import main_window as mw

    def run(owner, fn, ok, err=None, *args):
        try:
            result = fn(*args)
        except Exception as exc:
            if err:
                err(str(exc))
            return
        ok(result)
    monkeypatch.setattr(fv, "run_async", run)
    monkeypatch.setattr(mw, "run_async", run)


# --- regras ---
def test_game_matches_each_filter():
    assert rk.game_matches(ranking(), MARIO)
    assert rk.game_matches(SOULS, ELDEN)  # gênero secundário também vale
    assert not rk.game_matches(SOULS, MARIO)
    assert rk.game_matches(ranking(franchise_id=5), DS)
    assert rk.game_matches(ranking(franchise_id=5), {"franchise": {"id": 5}})
    assert not rk.game_matches(ranking(franchise_id=5), ELDEN)
    assert rk.game_matches(ranking(platform_id=2), ELDEN)
    assert not rk.game_matches(ranking(platform_id=2), DS)


def test_add_block_reason_and_filter_text():
    full = ranking(max_size=1, entries=[MARIO])
    assert rk.add_block_reason(full, MARIO) == "já está no ranking"
    assert rk.add_block_reason(full, ELDEN) == "ranking completo"
    assert rk.add_block_reason(SOULS, MARIO) == "fora do filtro"
    assert rk.add_block_reason(SOULS, DS) is None
    assert rk.filter_text(SOULS) == "Gênero: Soulslike"
    assert rk.filter_text(ranking()) is None


# --- ApiClient ---
@responses.activate
def test_api_client_ranking_calls():
    client = ApiClient(base_url="http://t:8000/api/v1")
    base = "http://t:8000/api/v1/rankings"
    responses.add(responses.GET, f"{base}/", json=[ranking()])
    responses.add(responses.POST, f"{base}/", json=ranking(), status=201)
    responses.add(responses.GET, f"{base}/10", json=ranking())
    responses.add(responses.PUT, f"{base}/10", json=ranking(name="Novo"))
    responses.add(responses.DELETE, f"{base}/10", status=204)
    responses.add(responses.PUT, f"{base}/10/entries", json=ranking(entries=[ELDEN]))
    responses.add(responses.PUT, f"{base}/order", json=[])
    responses.add(responses.GET, f"{base}/by-game/1", json=[{"ranking_id": 10, "name": "Top", "position": 1}])
    assert client.get_rankings()[0]["id"] == 10
    assert client.create_ranking({"name": "Top"})["name"] == "Top"
    assert client.get_ranking(10)["id"] == 10
    assert client.update_ranking(10, {"name": "Novo"})["name"] == "Novo"
    assert client.delete_ranking(10) is True
    assert client.set_ranking_entries(10, [1])["entries"][0]["id"] == 1
    assert json.loads(responses.calls[5].request.body) == {"game_ids": [1]}
    assert client.reorder_rankings([10]) == []
    assert json.loads(responses.calls[6].request.body) == {"ranking_ids": [10]}
    assert client.get_game_rankings(1)[0]["position"] == 1


def test_with_detail_exposes_api_message():
    response = requests.Response()
    response.status_code = 409
    response._content = b'{"detail": "Ja existe"}'

    def boom():
        raise requests.HTTPError(response=response)
    with pytest.raises(RuntimeError, match="Ja existe"):
        fv.with_detail(boom)()
    response._content = b"nada"
    with pytest.raises(requests.HTTPError):
        fv.with_detail(boom)()


# --- diálogos ---
OPTIONS = {"genre": [SOUL, {"id": 3, "name": "RPG"}], "franchise": [{"id": 5, "name": "Souls"}], "platform": []}


def test_ranking_dialog_new_builds_payload(qapp):
    dialog = rd.RankingDialog(OPTIONS)
    assert not dialog.combo_filter_item.isVisibleTo(dialog)
    dialog.input_name.setText("  Top Soulslike ")
    dialog.spin_size.setValue(5)
    dialog.combo_filter_type.setCurrentIndex(dialog.combo_filter_type.findData("genre"))
    assert [dialog.combo_filter_item.itemText(i) for i in range(dialog.combo_filter_item.count())] == ["RPG", "Soulslike"]
    dialog.combo_filter_item.setCurrentIndex(dialog.combo_filter_item.findData(7))
    dialog.save()
    assert dialog.payload == {"name": "Top Soulslike", "max_size": 5, "genre_id": 7, "franchise_id": None,
                              "platform_id": None}


def test_ranking_dialog_validation(qapp, monkeypatch):
    warned = []
    monkeypatch.setattr(rd.QMessageBox, "warning", lambda *a: warned.append(a[2]))
    dialog = rd.RankingDialog(OPTIONS)
    dialog.save()
    dialog.input_name.setText("Plataforma")
    dialog.combo_filter_type.setCurrentIndex(dialog.combo_filter_type.findData("platform"))  # sem plataformas
    dialog.save()
    assert len(warned) == 2 and dialog.payload is None


def test_ranking_dialog_edit_prefills_and_confirms_shrink(qapp, monkeypatch):
    current = dict(SOULS, entries=[ELDEN, DS])
    dialog = rd.RankingDialog(OPTIONS, current)
    assert dialog.input_name.text() == "Top Soulslike" and dialog.spin_size.value() == 3
    assert dialog.combo_filter_item.currentData() == 7
    dialog.spin_size.setValue(1)
    monkeypatch.setattr(rd.QMessageBox, "question", lambda *a: QMessageBox.No)
    dialog.save()
    assert dialog.payload is None
    monkeypatch.setattr(rd.QMessageBox, "question", lambda *a: QMessageBox.Yes)
    dialog.save()
    assert dialog.payload["max_size"] == 1


def test_picker_candidates_respect_filter_entries_and_replays():
    assert [g["id"] for g in candidates(ranking(), GAMES)] == [1, 3, 2]  # favoritos primeiro; sem a rejogada
    assert [g["id"] for g in candidates(dict(SOULS, entries=[ELDEN]), GAMES)] == [2]


def test_picker_limits_slots_keeps_check_order_and_searches(qapp):
    dialog = RankingPickerDialog(ranking(max_size=2), GAMES)
    assert dialog.list.count() == 3 and not dialog.btn_add.isEnabled()
    assert dialog.list.item(0).text().startswith("♥")
    dialog.list.item(2).setCheckState(Qt.Checked)  # Dark Souls
    dialog.list.item(0).setCheckState(Qt.Checked)  # Elden Ring
    assert dialog.selected_ids == [2, 1]
    assert not (dialog.list.item(1).flags() & Qt.ItemIsEnabled)  # vagas esgotadas
    dialog.list.item(2).setCheckState(Qt.Unchecked)
    assert dialog.selected_ids == [1] and dialog.list.item(1).flags() & Qt.ItemIsEnabled
    dialog.search.setText("mario")
    assert dialog.list.item(0).isHidden() and not dialog.list.item(1).isHidden()
    assert not dialog.empty.isVisibleTo(dialog)
    empty = RankingPickerDialog(dict(SOULS, entries=[ELDEN, DS]), GAMES)
    assert empty.empty.isVisibleTo(empty)


# --- tela de Favoritos ---
@pytest.fixture
def view(qapp):
    v = fv.FavoritesView(games_provider=lambda: list(GAMES))
    yield v
    import shiboken6
    shiboken6.delete(v)


def test_view_empty_state(view):
    view.set_rankings([])
    assert view.ranking_title.text() == "Nenhum ranking ainda"
    assert view.entries_empty.isVisibleTo(view) and not view.btn_add.isVisibleTo(view)


def test_view_shows_rankings_entries_and_favorites(view, sync, monkeypatch):
    data = [ranking(entries=[MARIO, ELDEN], out_of_filter_ids=[1]), SOULS]
    monkeypatch.setattr(fv.api_client, "get_rankings", lambda: data)
    view.load_data()
    assert view.ranking_list.count() == 2 and view.ranking_list.item(0).text() == "Top  (2/10)"
    # a view só desenha as linhas se o model avisar (bug: sinais do model bloqueados = lista vazia na tela)
    inserted = []
    view.ranking_list.model().rowsInserted.connect(lambda *a: inserted.append(a))
    view.set_rankings(data)
    assert len(inserted) == 2
    assert view.ranking_title.text() == "Top" and "2/10 posições" in view.ranking_meta.text()
    rows = [view.entry_list.itemWidget(view.entry_list.item(i)) for i in range(view.entry_list.count())]
    assert [r.rank.text() for r in rows] == ["1º", "2º"]
    assert not rows[0].btn_up.isEnabled() and not rows[1].btn_down.isEnabled()
    assert rows[1].warning.isVisibleTo(rows[1]) and not rows[0].warning.isVisibleTo(rows[0])
    # favoritos: sem a rejogada, por nota
    assert [g["id"] for g in view.favorites_grid.games] == [1, 3]
    assert view.favorites_count.text() == "2"
    view.ranking_list.setCurrentRow(1)
    assert view.current_id == 11 and view.ranking_meta.text().startswith("Gênero: Soulslike")
    assert view.entries_empty.isVisibleTo(view)


def test_view_ignores_stale_response(view):
    view._load_seq = 2
    view._on_rankings_loaded(1, [ranking()])
    assert view.rankings == []


def test_move_and_remove_entries_save_order(view, sync, monkeypatch):
    saved = []
    monkeypatch.setattr(fv.api_client, "set_ranking_entries",
                        lambda rid, ids: saved.append(ids) or ranking(entries=[g for i in ids for g in GAMES if g["id"] == i]))
    view.set_rankings([ranking(entries=[MARIO, ELDEN, DS])])
    view.move_entry(2, -1)
    assert saved[-1] == [3, 2, 1]
    view.move_entry(3, -1)  # já é o primeiro
    view.move_entry(99, 1)
    view.remove_entry(3)
    assert saved == [[3, 2, 1], [2, 1]]
    assert [view.entry_list.itemWidget(view.entry_list.item(i)).game["id"] for i in range(2)] == [2, 1]
    # arrastar: a ordem da lista vira a nova ordem
    first = view.entry_list.takeItem(0)
    view.entry_list.addItem(first)
    view._save_dragged_order()
    assert saved[-1] == [1, 2]


def test_row_buttons_and_double_click(view, qapp):
    opened, moved, removed = [], [], []
    row = fv.RankingEntryRow(2, ELDEN, 3)
    row.open_requested.connect(opened.append)
    row.move_requested.connect(lambda gid, d: moved.append((gid, d)))
    row.remove_requested.connect(removed.append)
    row.btn_up.click()
    row.btn_down.click()
    row.btn_remove.click()
    from PySide6.QtTest import QTest
    QTest.mouseDClick(row, Qt.LeftButton)
    assert moved == [(1, -1), (1, 1)] and removed == [1] and opened == [ELDEN]
    assert "Nota 10" in row.meta.text() and "PC" in row.meta.text()
    row._on_cover_loaded("outra.jpg")


def test_add_games_appends_selection(view, sync, monkeypatch):
    saved = []
    monkeypatch.setattr(fv.api_client, "set_ranking_entries", lambda rid, ids: saved.append((rid, ids)) or ranking())

    class Picker:
        def __init__(self, r, games, parent=None):
            self.selected_ids = [1, 2]

        def exec(self):
            return True
    monkeypatch.setattr(fv, "RankingPickerDialog", Picker)
    view.set_rankings([ranking(entries=[MARIO])])
    view.add_games()
    assert saved == [(10, [3, 1, 2])]


def test_create_edit_delete_ranking(view, sync, monkeypatch):
    class Dialog:
        def __init__(self, options, current=None, parent=None):
            self.payload = {"name": "Editado" if current else "Novo"}

        def exec(self):
            return True
    monkeypatch.setattr(fv, "RankingDialog", Dialog)
    monkeypatch.setattr(fv.api_client, "create_ranking", lambda p: ranking(20, p["name"]))
    monkeypatch.setattr(fv.api_client, "update_ranking", lambda rid, p: ranking(rid, p["name"]))
    monkeypatch.setattr(fv.api_client, "delete_ranking", lambda rid: True)
    changed = []
    view.rankings_changed.connect(lambda: changed.append(1))
    view.set_rankings([ranking()])
    view.create_ranking()
    assert view.current_id == 20 and view.ranking_list.count() == 2
    view.edit_ranking()
    assert view.ranking_title.text() == "Editado"
    monkeypatch.setattr(fv.QMessageBox, "question", lambda *a: QMessageBox.No)
    view.delete_ranking()
    assert view.ranking_list.count() == 2
    monkeypatch.setattr(fv.QMessageBox, "question", lambda *a: QMessageBox.Yes)
    view.delete_ranking()
    assert [r["id"] for r in view.rankings] == [10] and len(changed) == 3


def test_actions_without_ranking_do_nothing(view):
    view.set_rankings([])
    view.edit_ranking()
    view.delete_ranking()
    view.add_games()
    view.save_entries([1])


def test_save_error_is_reported_and_reloads(view, sync, monkeypatch):
    errors, reloads = [], []
    monkeypatch.setattr(fv.QMessageBox, "critical", lambda *a: errors.append(a[2]))
    monkeypatch.setattr(fv.api_client, "set_ranking_entries",
                        lambda rid, ids: (_ for _ in ()).throw(RuntimeError("fora do filtro")))
    monkeypatch.setattr(view, "load_data", lambda: reloads.append(1))
    view.set_rankings([ranking(entries=[MARIO])])
    view.remove_entry(3)
    assert errors and "fora do filtro" in errors[0] and reloads == [1]


def test_reorder_rankings_by_drag(view, sync, monkeypatch):
    sent = []
    monkeypatch.setattr(fv.api_client, "reorder_rankings",
                        lambda ids: sent.append(ids) or [ranking(11, "B"), ranking(10, "A")])
    view.set_rankings([ranking(10, "A"), ranking(11, "B")])
    view._save_ranking_order()  # nada mudou
    item = view.ranking_list.takeItem(0)
    view.ranking_list.addItem(item)
    view._save_ranking_order()
    assert sent == [[11, 10]] and view.ranking_list.item(0).text().startswith("B")


def test_apply_and_remove_game_in_place(view, monkeypatch):
    view.set_rankings([ranking(entries=[DS])])
    view.refresh_favorites()
    view.apply_game(dict(DS, is_favorite=True, title="Dark Souls Remastered"))
    assert 2 in [g["id"] for g in view.favorites_grid.games]
    assert view.entry_list.itemWidget(view.entry_list.item(0)).title.text() == "Dark Souls Remastered"
    view.apply_game(dict(ELDEN, score=8))  # já favorito: atualiza
    view.apply_game(dict(MARIO, is_favorite=False))
    assert 3 not in [g["id"] for g in view.favorites_grid.games]
    reloads = []
    monkeypatch.setattr(view, "load_data", lambda: reloads.append(1))
    view.remove_game(1)  # não está em ranking
    assert reloads == [] and 1 not in [g["id"] for g in view.favorites_grid.games]
    view.remove_game(2)
    assert reloads == [1]


# --- janela principal ---
@pytest.fixture
def window(qapp, monkeypatch):
    from frontend_desktop.views import main_window as mw
    monkeypatch.setattr(mw.api_client, "get_games", lambda **kw: [dict(g) for g in GAMES])
    for name in ("get_genres", "get_developers", "get_platforms", "get_franchises"):
        monkeypatch.setattr(mw.api_client, name, lambda: [])
    monkeypatch.setattr(mw.api_client, "get_rankings", lambda: [ranking(entries=[MARIO]), SOULS])
    w = mw.MainWindow(auto_load=False)
    w.refresh_all_data_sync()
    yield w
    w.close()
    for owner in [w, *w._views.values()]:
        for worker in list(owner.__dict__.get("_workers", ())):
            worker.wait(5000)
    import shiboken6
    shiboken6.delete(w)


def test_favorites_page_in_sidebar_and_loads(window, sync):
    from frontend_desktop.views.view_ids import NAV_SECTIONS, ViewId
    assert ViewId.FAVORITES in NAV_SECTIONS[0][1]
    assert ViewId.FAVORITES not in window._views
    window.switch_view(int(ViewId.FAVORITES))
    assert window.view_title_label.text() == "Favoritos e rankings"
    assert window.view_favorites.ranking_list.count() == 2
    assert [g["id"] for g in window.view_favorites.favorites_grid.games] == [1, 3]
    window.refresh_all_data_sync()  # opções de filtro chegam à tela já criada
    assert window.view_favorites.options["genre"] == []


def test_toggle_favorite_updates_views_in_place(window, sync, monkeypatch):
    from frontend_desktop.views.view_ids import ViewId
    window.switch_view(int(ViewId.FAVORITES))
    sent = []
    monkeypatch.setattr(window.__class__, "selected_game_in", staticmethod(lambda w: dict(DS)))
    monkeypatch.setattr("frontend_desktop.views.main_window.api_client.update_game",
                        lambda gid, data: sent.append((gid, data)) or dict(DS, **data))
    window.toggle_favorite_selected()
    assert sent == [(2, {"is_favorite": True})]
    assert next(g for g in window.all_games if g["id"] == 2)["is_favorite"] is True
    assert 2 in [g["id"] for g in window.view_favorites.favorites_grid.games]
    assert "marcado como favorito" in window.statusBar().currentMessage()
    window.apply_game_deletion(3)
    assert 3 not in [g["id"] for g in window.view_favorites.favorites_grid.games]


def test_toggle_without_selection_does_nothing(window, monkeypatch):
    monkeypatch.setattr(window.__class__, "selected_game_in", staticmethod(lambda w: None))
    window.toggle_favorite_selected()


def test_game_menu_lists_actions_and_rankings(window):
    menu = window.build_game_menu(ELDEN)
    labels = [a.text() for a in menu.actions()]
    assert labels[:2] == ["Abrir", "Remover dos favoritos"]
    sub = menu.actions()[2].menu()
    items = {a.text(): a.isEnabled() for a in sub.actions() if a.text()}
    assert items == {"Top": True, "Top Soulslike": True, "Ver rankings...": True}
    blocked = window.build_game_menu(MARIO).actions()[2].menu()
    states = {a.text(): a.isEnabled() for a in blocked.actions() if a.text()}
    assert states["Top  (já está no ranking)"] is False
    assert states["Top Soulslike  (fora do filtro)"] is False
    assert window.build_game_menu(DS).actions()[1].text() == "Favoritar"


def test_game_menu_without_rankings(window, monkeypatch):
    from frontend_desktop.views import main_window as mw
    monkeypatch.setattr(mw.api_client, "get_rankings", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    sub = window.build_game_menu(ELDEN).actions()[2].menu()
    assert sub.actions()[0].text() == "Nenhum ranking criado" and not sub.actions()[0].isEnabled()


def test_add_to_ranking_appends_and_reloads(window, sync, monkeypatch):
    from frontend_desktop.views import main_window as mw
    from frontend_desktop.views.view_ids import ViewId
    window.switch_view(int(ViewId.FAVORITES))
    sent = []
    monkeypatch.setattr(mw.api_client, "set_ranking_entries",
                        lambda rid, ids: sent.append((rid, ids)) or ranking(entries=[MARIO, ELDEN]))
    window.add_to_ranking(ranking(entries=[MARIO]), ELDEN)
    assert sent == [(10, [3, 1])]
    assert "posição 2" in window.statusBar().currentMessage()
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a: errors.append(a[2]))
    monkeypatch.setattr(mw.api_client, "set_ranking_entries",
                        lambda rid, ids: (_ for _ in ()).throw(RuntimeError("completo")))
    window.add_to_ranking(ranking(), ELDEN)
    assert errors and "completo" in errors[0]


def test_right_click_on_card_and_table_opens_menu(window, monkeypatch):
    shown = []
    monkeypatch.setattr(window, "show_game_menu", lambda game, pos: shown.append(game["id"]))
    grid = window.view_zerados_grid.grid
    grid.resize(800, 600)
    grid.view.resize(800, 600)
    grid._apply_grid_size()
    index = grid.view.model().index(0, 0)
    rect = grid.view.visualRect(index)
    event = QContextMenuEvent(QContextMenuEvent.Mouse, rect.center(), grid.view.mapToGlobal(rect.center()))
    grid.view.contextMenuEvent(event)
    empty = QContextMenuEvent(QContextMenuEvent.Mouse, QPoint(-50, -50), QPoint(0, 0))
    grid.view.contextMenuEvent(empty)
    table = window.view_table
    table.resize(800, 400)
    table.show_game_menu(table.table.visualRect(table.proxy.index(0, 0)).center())
    table.show_game_menu(QPoint(-10, -10))
    assert len(shown) == 2


def test_show_game_menu_executes(window, monkeypatch):
    executed = []

    class FakeMenu:
        def exec(self, pos):
            executed.append(pos)
    monkeypatch.setattr(window, "build_game_menu", lambda game: FakeMenu())
    window.show_game_menu(ELDEN, QPoint(1, 1))
    assert executed == [QPoint(1, 1)]


# --- selo e diálogo do jogo ---
def test_table_favorite_column():
    assert cell_text(ELDEN, FAVORITE_COLUMN) == "♥" and cell_text(DS, FAVORITE_COLUMN) == ""
    assert sort_key(ELDEN, FAVORITE_COLUMN) == 1 and sort_key(DS, FAVORITE_COLUMN) == 0


def test_table_model_favorite_roles(qapp):
    from frontend_desktop.models.game_table_model import GameTableModel
    model = GameTableModel()
    model.set_games([ELDEN])
    index = model.index(0, FAVORITE_COLUMN)
    assert model.data(index, Qt.TextAlignmentRole) == int(Qt.AlignCenter)
    assert model.data(index, Qt.ForegroundRole) is not None


def test_card_paints_favorite_mark(qapp, monkeypatch):
    from frontend_desktop.models.game_list_model import GameListModel
    from frontend_desktop.views.components.game_card_delegate import GameCardDelegate
    marks = []
    monkeypatch.setattr(GameCardDelegate, "_favorite_mark", staticmethod(lambda p, r: marks.append(r)))
    model = GameListModel()
    model.set_games([ELDEN, DS])
    delegate = GameCardDelegate("medium")
    image = QImage(400, 400, QImage.Format_ARGB32)
    painter = QPainter(image)
    for row in range(2):
        option = QStyleOptionViewItem()
        option.rect = image.rect()
        delegate.paint(painter, option, model.index(row, 0))
    painter.end()
    assert len(marks) == 1


def test_favorite_mark_draws(qapp):
    from PySide6.QtCore import QRect
    from frontend_desktop.views.components.game_card_delegate import GameCardDelegate
    image = QImage(100, 100, QImage.Format_ARGB32)
    painter = QPainter(image)
    GameCardDelegate._favorite_mark(painter, QRect(0, 0, 80, 100))
    painter.end()


def test_rankings_text_and_game_dialog_label(qapp, sync, monkeypatch):
    assert rankings_text([]) == ""
    text = rankings_text([{"ranking_id": 1, "name": "Top", "position": 2},
                          {"ranking_id": 2, "name": "Souls", "position": 1}])
    assert text == "Nos rankings: #2 em Top · #1 em Souls"
    from frontend_desktop.views.dialogs import game_dialog as gd
    monkeypatch.setattr(gd, "run_async", lambda owner, fn, ok, err=None, *a: ok(fn(*a)))
    monkeypatch.setattr(gd.api_client, "get_game_rankings", lambda gid: [{"ranking_id": 1, "name": "Top", "position": 3}])
    monkeypatch.setattr(gd.GameDialog, "fetch_options",
                        staticmethod(lambda: {"developers": [], "platforms": [], "franchises": [], "genres": []}))
    dialog = gd.GameDialog(game_data=dict(ELDEN))
    assert dialog.lbl_rankings.text() == "Nos rankings: #3 em Top"
    assert dialog.lbl_rankings.isVisibleTo(dialog)
    dialog._on_rankings_loaded([])
    assert not dialog.lbl_rankings.isVisibleTo(dialog)
