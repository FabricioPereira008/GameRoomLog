import json

import pytest
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from frontend_desktop.views.components import settings_view as sv
from frontend_desktop.views.dialogs import inbox_review_dialog as ird
from frontend_desktop.views.dialogs.inbox_review_dialog import (
    NEW_GAME, InboxReviewDialog, GamePickerDialog, describe_event, format_value,
)


def sync_run_async(owner, func, on_success, on_error=None, *args, **kwargs):
    try:
        result = func(*args, **kwargs)
    except Exception as exc:
        if on_error:
            on_error(str(exc))
        return None
    on_success(result)


@pytest.fixture(autouse=True)
def sync_workers(monkeypatch):
    monkeypatch.setattr(ird, "run_async", sync_run_async)
    monkeypatch.setattr(sv, "run_async", sync_run_async)


def event(eid, type_="finished", day="2026-10-12", **kw):
    return {"id": eid, "uuid": f"u{eid}", "event_type": type_, "title": "Hollow Knight", "platform": "Switch",
            "game_id": None, "event_date": day, "played_hours": None, "score": None, "difficulty": None,
            "notes": None, **kw}


def candidate(gid, title="Hollow Knight", similarity=100, platform_matches=True, changes=None):
    return {"game_id": gid, "title": title, "platform": "Nintendo Switch", "status": "Fila", "cover_image": None,
            "similarity": similarity, "platform_matches": platform_matches,
            "current": {"status": "Fila"}, "changes": changes if changes is not None else {"status": "Zerado"}}


def group(match="exact", candidates=None, events=None, platform_match=None, title="Hollow Knight"):
    return {
        "key": f"t:{title}", "title": title, "platform": "Switch",
        "events": events or [event(1, played_hours=38)],
        "match": match,
        "candidates": candidates if candidates is not None else ([candidate(7)] if match != "none" else []),
        "platform_match": platform_match or {"platform_id": 3, "name": "Nintendo Switch", "similarity": 100, "is_new": False},
        "new_game": {"title": title, "status": "Zerado", "finish_date": "2026-10-12", "play_count": 1, "platform_id": 3},
    }


@pytest.fixture
def api(monkeypatch):
    calls = {"resolve": [], "update": [], "platform": []}
    state = {"pending": {"total_events": 0, "groups": []}}
    monkeypatch.setattr(ird.api_client, "inbox_pending", lambda threshold=None: state["pending"])
    monkeypatch.setattr(ird.api_client, "inbox_resolve",
                        lambda ids, action, game_id=None: calls["resolve"].append((ids, action, game_id)) or {"resolved": len(ids)})
    monkeypatch.setattr(ird.api_client, "get_game", lambda gid: {"id": gid, "title": "Hollow Knight", "status": "Fila"})
    monkeypatch.setattr(ird.api_client, "update_game",
                        lambda gid, data: calls["update"].append((gid, data)) or {"id": gid, "title": "Hollow Knight", **data})
    monkeypatch.setattr(ird.api_client, "create_platform",
                        lambda name: calls["platform"].append(name) or {"id": 99, "name": name})
    monkeypatch.setattr(ird.api_client, "auto_cover_game", lambda gid, key=None: {"success": False})
    return calls, state


class FakeGameDialog:
    """Substitui o GameDialog: registra os dados recebidos e 'salva' sem abrir janela."""
    opened = []
    accept = True

    def __init__(self, data, parent=None):
        FakeGameDialog.opened.append(data)
        self.saved_game = {"id": data.get("id", 50), "title": data.get("title"), "status": data.get("status")}
        self.is_deleted = False

    def exec(self):
        return QDialog.Accepted if FakeGameDialog.accept else QDialog.Rejected


@pytest.fixture
def fake_dialog(monkeypatch):
    FakeGameDialog.opened = []
    FakeGameDialog.accept = True
    monkeypatch.setattr(ird, "GameDialog", FakeGameDialog)
    return FakeGameDialog


def make_dialog(state, *groups):
    state["pending"] = {"total_events": sum(len(g["events"]) for g in groups), "groups": list(groups)}
    return InboxReviewDialog(85)


# --- formatação ---

def test_format_helpers():
    assert format_value("finish_date", "2026-10-12") == "12/10/2026"
    assert format_value("played_hours", 38.0) == "38"
    assert format_value("score", None) == "—"
    text = describe_event(event(1, played_hours=38, score=9.5, notes="Final verdadeiro"))
    assert text == "12/10/2026 · Zerado · 38h · nota 9.5 — “Final verdadeiro”"


# --- lista e seleção ---

def test_empty_inbox(qapp, api):
    dialog = make_dialog(api[1])
    assert "Nenhum evento pendente" in dialog.lbl_summary.text()
    assert not dialog.detail.isVisibleTo(dialog)


def test_exact_match_preselects_candidate_and_shows_diff(qapp, api):
    dialog = make_dialog(api[1], group("exact"))
    assert dialog.group_list.count() == 1 and dialog.group_list.item(0).text().startswith("✓")
    assert dialog.candidate_group.checkedId() == 7
    assert dialog.diff_table.rowCount() == 1
    assert [dialog.diff_table.item(0, c).text() for c in range(3)] == ["Status", "Fila", "Zerado"]
    assert dialog.btn_apply.isEnabled() and dialog.btn_apply.text() == "Aplicar"


def test_confirm_match_requires_choice(qapp, api):
    g = group("confirm", candidates=[candidate(7, similarity=92), candidate(8, "Hollow Knight: Silksong", 88, False)])
    dialog = make_dialog(api[1], g)
    assert dialog.candidate_group.checkedId() == -1
    assert not dialog.btn_apply.isEnabled()
    assert "plataforma diferente" in dialog.candidate_group.button(8).text()
    dialog.candidate_group.button(8).click()
    assert dialog.btn_apply.isEnabled()


def test_no_match_defaults_to_new_game(qapp, api):
    dialog = make_dialog(api[1], group("none"))
    assert dialog.candidate_group.checkedId() == NEW_GAME
    assert dialog.btn_apply.text() == "Criar jogo..."
    assert dialog.btn_edit.isHidden()
    fields = [dialog.diff_table.item(r, 0).text() for r in range(dialog.diff_table.rowCount())]
    assert "Status" in fields and "Zerado em" in fields


# --- ações ---

def test_apply_updates_game_resolves_events_and_emits(qapp, api):
    calls, state = api
    dialog = make_dialog(state, group("exact"), group("none", title="Dead Cells", events=[event(2)]))
    emitted = []
    dialog.game_saved.connect(lambda game, is_new, old: emitted.append((game["id"], is_new, old)))
    dialog.apply_current()
    assert calls["update"] == [(7, {"status": "Zerado"})]
    assert calls["resolve"] == [([1], "applied", 7)]
    assert emitted == [(7, False, "Fila")]
    assert dialog.group_list.count() == 1 and dialog.current_group["title"] == "Dead Cells"
    assert dialog.applied_count == 1


def test_apply_without_changes_only_resolves(qapp, api):
    calls, state = api
    dialog = make_dialog(state, group("exact", candidates=[candidate(7, changes={})]))
    assert "Nada muda" in dialog.lbl_status.text()
    dialog.apply_current()
    assert calls["update"] == [] and calls["resolve"] == [([1], "applied", 7)]


def test_edit_and_apply_opens_dialog_with_proposal(qapp, api, fake_dialog):
    calls, state = api
    dialog = make_dialog(state, group("exact"))
    dialog.edit_and_apply()
    assert fake_dialog.opened[0]["id"] == 7 and fake_dialog.opened[0]["status"] == "Zerado"
    assert calls["resolve"] == [([1], "applied", 7)]
    assert dialog.group_list.count() == 0


def test_cancelled_edit_keeps_events_pending(qapp, api, fake_dialog):
    calls, state = api
    fake_dialog.accept = False
    dialog = make_dialog(state, group("exact"))
    dialog.edit_and_apply()
    assert calls["resolve"] == [] and dialog.group_list.count() == 1


def test_create_game_with_new_platform(qapp, api, fake_dialog):
    calls, state = api
    new_plat = {"platform_id": None, "name": "Android", "similarity": 0, "is_new": True}
    g1 = group("none", platform_match=dict(new_plat))
    g1["new_game"].pop("platform_id")
    g2 = group("none", title="Dead Cells", events=[event(2)], platform_match=dict(new_plat))
    g2["new_game"].pop("platform_id")
    dialog = make_dialog(state, g1, g2)
    emitted = []
    dialog.game_saved.connect(lambda game, is_new, old: emitted.append((game["id"], is_new)))
    dialog.apply_current()
    assert calls["platform"] == ["Android"]
    assert fake_dialog.opened[0]["platform"] == {"id": 99} and "platform_id" not in fake_dialog.opened[0]
    assert calls["resolve"] == [([1], "applied", 50)]
    assert emitted == [(50, True)]
    # a plataforma criada é reaproveitada pelo grupo seguinte
    assert dialog.current_group["platform_match"]["is_new"] is False
    dialog.apply_current()
    assert calls["platform"] == ["Android"]
    assert fake_dialog.opened[1]["platform"] == {"id": 99}


def test_discard_after_confirmation(qapp, api, monkeypatch):
    calls, state = api
    dialog = make_dialog(state, group("exact"))
    monkeypatch.setattr(ird.QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    dialog.discard_current()
    assert calls["resolve"] == []
    monkeypatch.setattr(ird.QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    dialog.discard_current()
    assert calls["resolve"] == [([1], "discarded", None)]
    assert "Nenhum evento pendente" in dialog.lbl_summary.text()


def test_manual_link_uses_server_proposal(qapp, api, monkeypatch):
    calls, state = api
    monkeypatch.setattr(ird.api_client, "get_games", lambda: [{"id": 30, "title": "HK", "platform": None}])
    monkeypatch.setattr(ird.api_client, "inbox_proposal",
                        lambda ids, gid, threshold=None: candidate(gid, "HK", 40, changes={"status": "Zerado"}))

    class Picker:
        def __init__(self, games, initial, parent=None):
            self.selected_id = games[0]["id"]

        def exec(self):
            return QDialog.Accepted

    monkeypatch.setattr(ird, "GamePickerDialog", Picker)
    dialog = make_dialog(state, group("none"))
    dialog.pick_other_game()
    assert dialog.candidate_group.checkedId() == 30
    assert dialog.btn_apply.text() == "Aplicar" and dialog.btn_apply.isEnabled()
    dialog.apply_current()
    assert calls["resolve"] == [([1], "applied", 30)]


def test_api_error_is_shown(qapp, api, monkeypatch):
    calls, state = api
    dialog = make_dialog(state, group("exact"))

    def boom(*_a, **_k):
        raise RuntimeError("offline")
    monkeypatch.setattr(ird.api_client, "update_game", boom)
    dialog.apply_current()
    assert "offline" in dialog.lbl_status.text()
    assert dialog.group_list.count() == 1 and dialog.btn_apply.isEnabled()


def test_game_picker_filters(qapp):
    games = [{"id": 1, "title": "Celeste", "platform": {"name": "PC"}}, {"id": 2, "title": "Hades", "platform": None}]
    picker = GamePickerDialog(games, "cel")
    assert picker.list.count() == 1 and picker.list.item(0).text() == "Celeste (PC)"
    picker.input_filter.setText("")
    assert picker.list.count() == 2
    picker.list.setCurrentRow(1)
    picker._accept()
    assert picker.selected_id == 2


# --- Configurações → App do Portátil ---

@pytest.fixture
def settings_view(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(sv.api_client, "inbox_pending", lambda threshold=None: {"total_events": 2, "groups": []})
    view = sv.SettingsView()
    view.settings.setValue("inbox_threshold", 85)
    return view


def test_settings_shows_pending_count(settings_view):
    settings_view.refresh_inbox_count()
    assert settings_view.btn_inbox_review.text() == "Revisar pendentes (2)"
    assert settings_view.btn_inbox_review.isEnabled()


def test_settings_import_file_opens_review(settings_view, monkeypatch, tmp_path):
    path = tmp_path / "eventos.json"
    path.write_text(json.dumps({"format": "gameroom-inbox", "version": 1, "events": []}), encoding="utf-8")
    monkeypatch.setattr(sv.QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), ""))
    sent, opened = [], []
    monkeypatch.setattr(sv.api_client, "inbox_import",
                        lambda pkg: sent.append(pkg) or {"received": 3, "imported": 2, "duplicates": 1, "rejected": []})
    monkeypatch.setattr(settings_view, "open_inbox_review", lambda: opened.append(True))
    settings_view.on_inbox_import()
    assert sent[0]["format"] == "gameroom-inbox"
    assert "2 evento(s) novo(s), 1 já recebido(s) antes" in settings_view.lbl_inbox_status.text()
    assert opened == [True]


def test_settings_import_rejects_foreign_file(settings_view, monkeypatch, tmp_path):
    path = tmp_path / "outro.json"
    path.write_text(json.dumps({"format": "gameroom-catalog"}), encoding="utf-8")
    monkeypatch.setattr(sv.QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), ""))
    errors = []
    monkeypatch.setattr(sv.QMessageBox, "critical", lambda *a, **k: errors.append(a[2]))
    monkeypatch.setattr(sv.api_client, "inbox_import", lambda pkg: pytest.fail("não deveria importar"))
    settings_view.on_inbox_import()
    assert "não foi exportado pelo app" in errors[0]


def test_settings_import_reports_rejected_and_server_error(settings_view, monkeypatch, tmp_path):
    path = tmp_path / "eventos.json"
    path.write_text(json.dumps({"format": "gameroom-inbox", "version": 1, "events": []}), encoding="utf-8")
    monkeypatch.setattr(sv.QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), ""))
    warnings, errors = [], []
    monkeypatch.setattr(sv.QMessageBox, "warning", lambda *a, **k: warnings.append(a[2]))
    monkeypatch.setattr(sv.QMessageBox, "critical", lambda *a, **k: errors.append(a[2]))
    monkeypatch.setattr(sv.api_client, "inbox_import",
                        lambda pkg: {"received": 1, "imported": 0, "duplicates": 0, "rejected": ["Evento 1: campo 'score' inválido"]})
    settings_view.on_inbox_import()
    assert "score" in warnings[0]

    def boom(_pkg):
        raise RuntimeError("422 versão")
    monkeypatch.setattr(sv.api_client, "inbox_import", boom)
    settings_view.on_inbox_import()
    assert "422 versão" in errors[0] and settings_view.btn_inbox_import.isEnabled()


def test_settings_export_catalog(settings_view, monkeypatch, tmp_path):
    target = tmp_path / "catalogo.json"
    monkeypatch.setattr(sv.QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    monkeypatch.setattr(sv.api_client, "inbox_catalog",
                        lambda: {"format": "gameroom-catalog", "version": 1, "games": [{"id": 1, "title": "Ação"}], "platforms": []})
    settings_view.on_export_catalog()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["games"][0]["title"] == "Ação"
    assert "1 jogos" in settings_view.lbl_inbox_status.text()


def test_settings_review_forwards_saved_games(settings_view, monkeypatch):
    from PySide6.QtCore import QObject, Signal

    class FakeReview(QObject):
        game_saved = Signal(dict, bool, object)

        def __init__(self, threshold, parent=None):
            super().__init__()
            self.applied_count = 1

        def exec(self):
            self.game_saved.emit({"id": 1, "title": "X"}, True, None)

    received = []
    settings_view.game_saved.connect(lambda g, is_new, old: received.append((g["id"], is_new)))
    monkeypatch.setattr(sv, "InboxReviewDialog", FakeReview)
    settings_view.open_inbox_review()
    assert received == [(1, True)]
    assert "1 jogo(s) atualizado(s)" in settings_view.lbl_inbox_status.text()
