"""Rejogadas na GUI: vínculo no GameDialog, filtro, contador do original e revisão da caixa de entrada."""
import pytest
from PySide6.QtWidgets import QDialog

from frontend_desktop.views.components.filter_panel import PLAYS_REPLAYED, PLAYS_REPLAYS, FilterPanel
from frontend_desktop.views.dialogs import game_dialog as gd
from frontend_desktop.views.dialogs.game_dialog import brief_label, describe_plays, replay_group

BRIEFS = [
    {"id": 1, "title": "Hades", "platform": "PC", "status": "Zerado", "play_type": "Primeira Jogada",
     "play_count": 1, "replay_of_id": None, "completion_year": 2020, "score": 9},
    {"id": 2, "title": "Hades", "platform": "Switch", "status": "Zerado", "play_type": "Rejogada",
     "play_count": 2, "replay_of_id": 1, "completion_year": 2024, "score": 10},
    {"id": 3, "title": "Celeste", "platform": None, "status": "Fila", "play_type": "Primeira Jogada",
     "play_count": 1, "replay_of_id": None, "completion_year": None, "score": None},
]
OPTIONS = {"developers": [], "platforms": [], "franchises": [], "genres": []}


def _wait(dialog, qapp):
    for _ in range(100):
        if not any(w.isRunning() for w in dialog.__dict__.get("_workers", ())):
            break
        dialog._wait_workers()
    qapp.processEvents()


@pytest.fixture
def dialog_factory(qapp, monkeypatch):
    monkeypatch.setattr(gd.GameDialog, "fetch_options", staticmethod(lambda: OPTIONS))
    calls = []
    monkeypatch.setattr(gd.api_client, "get_game_briefs", lambda: calls.append("briefs") or list(BRIEFS))

    def make(data=None):
        dialog = gd.GameDialog(game_data=data)
        _wait(dialog, qapp)
        return dialog
    return make, calls


def test_helpers():
    assert brief_label(BRIEFS[0]) == "Hades (PC, 2020)" and brief_label(BRIEFS[2]) == "Celeste"
    group = replay_group(BRIEFS, 2, 1)
    assert [b["id"] for b in group] == [1, 2] and replay_group(BRIEFS, None, None) == []
    assert describe_plays(group, 2) == "1ª: 2020 · Zerado · nota 9  |  2ª (esta): 2024 · Zerado · nota 10"


def test_briefs_load_only_when_needed(dialog_factory, qapp):
    make, calls = dialog_factory
    dialog = make()
    assert calls == [] and dialog.field_replay_of.isHidden()
    dialog.chk_replay.setChecked(True)
    _wait(dialog, qapp)
    assert calls == ["briefs"] and not dialog.field_replay_of.isHidden()
    # só originais (registros que não são rejogadas) podem ser escolhidos
    assert [dialog.combo_replay_of.itemText(i) for i in range(dialog.combo_replay_of.count())] == \
        ["Hades (PC, 2020)", "Celeste"]


def test_new_replay_suggests_original_by_title_and_next_play_number(dialog_factory, qapp):
    make, _ = dialog_factory
    dialog = make()
    dialog.input_title.setText("hades")
    dialog.combo_status.setCurrentText("Jogando")
    dialog.chk_replay.setChecked(True)
    _wait(dialog, qapp)
    assert dialog.combo_replay_of.currentData() == 1
    assert dialog.spin_play_count.value() == 3                       # já houve 2 jogadas
    assert "1ª: 2020" in dialog.lbl_plays.text() and not dialog.lbl_plays.isHidden()
    payload = dialog._build_payload("Hades")
    assert payload["replay_of_id"] == 1 and payload["play_type"] == "Rejogada"


def test_edit_replay_shows_its_group_and_keeps_link(dialog_factory, qapp):
    make, calls = dialog_factory
    dialog = make({"id": 2, "title": "Hades", "status": "Zerado", "play_type": "Rejogada", "play_count": 2,
                   "replay_of_id": 1})
    _wait(dialog, qapp)
    assert calls == ["briefs"] and dialog.combo_replay_of.currentData() == 1
    assert "2ª (esta)" in dialog.lbl_plays.text()
    assert dialog.spin_play_count.value() == 2                       # editar não renumera
    assert dialog._build_payload("Hades")["replay_of_id"] == 1


def test_original_with_replays_shows_history(dialog_factory, qapp):
    make, calls = dialog_factory
    dialog = make({"id": 1, "title": "Hades", "status": "Zerado", "play_type": "Primeira Jogada", "replays_count": 1})
    _wait(dialog, qapp)
    assert calls == ["briefs"] and "1ª (esta)" in dialog.lbl_plays.text()
    assert dialog._build_payload("Hades")["replay_of_id"] is None


def test_unchecking_replay_unlinks_and_unknown_text_clears(dialog_factory, qapp):
    make, _ = dialog_factory
    dialog = make({"id": 2, "title": "Hades", "status": "Zerado", "play_type": "Rejogada", "play_count": 2,
                   "replay_of_id": 1})
    _wait(dialog, qapp)
    dialog.combo_replay_of.setEditText("algo que não existe")
    assert dialog.selected_replay_of() is None
    dialog.chk_replay.setChecked(False)
    assert dialog._build_payload("Hades")["replay_of_id"] is None


def test_link_kept_when_briefs_fail(qapp, monkeypatch):
    monkeypatch.setattr(gd.GameDialog, "fetch_options", staticmethod(lambda: OPTIONS))
    monkeypatch.setattr(gd.api_client, "get_game_briefs", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    dialog = gd.GameDialog(game_data={"id": 2, "title": "Hades", "status": "Fila", "play_type": "Rejogada",
                                      "play_count": 2, "replay_of_id": 1})
    _wait(dialog, qapp)
    assert dialog._build_payload("Hades")["replay_of_id"] == 1
    dialog.load_briefs()                                             # tenta de novo
    _wait(dialog, qapp)


# --- filtro ---

def test_filter_by_plays(qapp):
    panel = FilterPanel()
    original = {"id": 1, "title": "Hades", "replays_count": 1, "play_type": "Primeira Jogada"}
    replay = {"id": 2, "title": "Hades", "replay_of_id": 1, "play_type": "Rejogada"}
    unlinked = {"id": 3, "title": "Doom", "play_type": "Rejogada"}
    single = {"id": 4, "title": "Celeste", "play_type": "Primeira Jogada"}
    games = [original, replay, unlinked, single]
    shown = lambda: [g["id"] for g in games if panel.matches(g)]
    assert shown() == [1, 2, 3, 4]
    panel.combo_plays.setCurrentIndex(panel.combo_plays.findData(PLAYS_REPLAYED))
    assert shown() == [1, 2, 3] and panel.count_active_filters() == 1
    panel.combo_plays.setCurrentIndex(panel.combo_plays.findData(PLAYS_REPLAYS))
    assert shown() == [2, 3]
    panel.clear_filters()
    assert shown() == [1, 2, 3, 4] and panel.count_active_filters() == 0
