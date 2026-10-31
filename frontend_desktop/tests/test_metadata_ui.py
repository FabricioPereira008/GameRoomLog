"""Busca de dados do jogo na GUI: cliente da API, prévia com checkboxes e aplicação no GameDialog."""
import pytest
import responses
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog, QMessageBox

from frontend_desktop.api_client.client import ApiClient
from frontend_desktop.views.dialogs import game_dialog as gd
from frontend_desktop.views.dialogs import game_dialog_metadata as gdm
from frontend_desktop.views.dialogs.metadata_preview_dialog import (
    MetadataPreviewDialog, candidate_label, format_value, proposal_values,
)

BASE = "http://test-server:8000/api/v1"
OPTIONS = {
    "developers": [{"name": "Team Cherry"}], "franchises": [], "genres": [{"name": "Metroidvania"}],
    "platforms": [{"id": 1, "name": "PC"}, {"id": 2, "name": "Switch"}],
}
SEARCH = {"candidates": [
    {"source": "igdb", "source_id": "1", "name": "Hollow Knight", "year": 2017, "platforms": ["PC", "Switch"]},
    {"source": "igdb", "source_id": "2", "name": "Hollow Knight: Silksong", "year": None, "platforms": []},
], "warning": None}
PROPOSAL = {
    "source": "igdb", "name": "Hollow Knight", "year": 2017, "developer": "Team Cherry",
    "franchise": "Hollow Knight", "genres": ["Metroidvania", "Plataforma"], "platforms": ["PC", "Switch"],
    "hltb_hours": 26.98, "hltb_source": "HowLongToBeat",
}


def _wait(dialog, qapp):
    for _ in range(100):
        workers = dialog.__dict__.get("_workers", ())
        if not any(w.isRunning() for w in workers):
            break
        for w in list(workers):
            w.wait(5000)
    qapp.processEvents()


def _preview(qapp, current=None, search=None, details=None):
    calls = []

    def fake_search(title, igdb):
        calls.append(("search", title, igdb))
        if isinstance(search, Exception):
            raise search
        return search or SEARCH

    def fake_details(source, source_id, title, igdb):
        calls.append(("details", source_id, title))
        if isinstance(details, Exception):
            raise details
        return details or PROPOSAL

    dialog = MetadataPreviewDialog("Hollow Knight", current or {}, {"igdb_client_id": "c"},
                                   search=fake_search, details=fake_details)
    _wait(dialog, qapp)
    _wait(dialog, qapp)
    return dialog, calls


def test_helpers():
    assert candidate_label(SEARCH["candidates"][0]) == "Hollow Knight   —   2017 · PC, Switch"
    assert candidate_label(SEARCH["candidates"][1]) == "Hollow Knight: Silksong"
    assert format_value("hltb_hours", 26.98) == "27 h"
    assert format_value("developer", None) == "—"
    values = proposal_values({"genres": ["RPG"], "platforms": []})
    assert values["genre"] == "RPG" and values["genre2"] is None and values["platform"] == []


def test_preview_checks_only_empty_fields(qapp):
    current = {"developer": "", "franchise": "Outra", "genre": "metroidvania", "hltb_hours": 0, "platform": ""}
    dialog, calls = _preview(qapp, current)
    assert dialog.list_candidates.count() == 2 and dialog.list_candidates.currentRow() == 0
    assert calls[1] == ("details", "1", "Hollow Knight")
    rows = dialog._rows
    assert rows["developer"][0].isChecked()
    assert rows["franchise"][0].isEnabled() and not rows["franchise"][0].isChecked()  # sobrescreveria
    assert not rows["genre"][0].isEnabled()  # igual ao atual
    assert rows["genre2"][0].isChecked() and rows["hltb_hours"][0].isChecked()
    assert rows["platform"][1].count() == 2 and rows["platform"][1].isEnabled()
    assert dialog.btn_apply.isEnabled()
    assert "HowLongToBeat" in dialog.lbl_status.text()

    rows["franchise"][0].setChecked(True)
    rows["genre2"][0].setChecked(False)
    rows["platform"][1].setCurrentIndex(1)
    dialog.apply()
    assert dialog.result() == QDialog.Accepted
    assert dialog.chosen == {"developer": "Team Cherry", "franchise": "Hollow Knight",
                             "platform": "Switch", "hltb_hours": 26.98}


def test_preview_switching_candidate_reloads_details(qapp):
    dialog, calls = _preview(qapp)
    dialog.list_candidates.setCurrentRow(1)
    _wait(dialog, qapp)
    assert calls[-1] == ("details", "2", "Hollow Knight: Silksong")
    dialog._on_details(0, {"developer": "Antiga"})  # resposta atrasada de outro candidato: ignorada
    assert dialog._values["developer"] == "Team Cherry"


def test_preview_errors_and_warning(qapp):
    dialog, _ = _preview(qapp, search=RuntimeError("Nenhum jogo encontrado para 'X'."))
    assert "Nenhum jogo" in dialog.lbl_status.text() and not dialog.btn_apply.isEnabled()

    dialog, _ = _preview(qapp, search={**SEARCH, "warning": "Credenciais recusadas. Resultados da Steam."},
                         details=RuntimeError("A fonte de dados não respondeu."))
    assert "não respondeu" in dialog.lbl_status.text() and not dialog.btn_apply.isEnabled()

    dialog, _ = _preview(qapp, details={"source": "steam", "name": "X", "genres": [], "platforms": []})
    assert "duração: não encontrada" in dialog.lbl_status.text()
    assert not any(check.isEnabled() for check, _ in dialog._rows.values())
    dialog.load_details(5)  # linha inexistente não faz nada


def test_closing_hands_running_workers_to_parent(qapp):
    from PySide6.QtWidgets import QWidget
    parent = QWidget()
    dialog = MetadataPreviewDialog("X", {}, None, parent=parent,
                                   search=lambda *_: SEARCH, details=lambda *_: PROPOSAL)
    dialog.reject()
    assert not dialog.__dict__.get("_workers") or all(w.parent() is parent for w in dialog._workers)
    _wait(parent, qapp)


# --- GameDialog ---

@pytest.fixture
def game_dialog(qapp, monkeypatch):
    monkeypatch.setattr(gd.GameDialog, "fetch_options", staticmethod(lambda: OPTIONS))
    dialog = gd.GameDialog()
    _wait(dialog, qapp)
    return dialog


def test_apply_metadata_fills_form(game_dialog):
    game_dialog.apply_metadata({"developer": "Team Cherry", "franchise": "Hollow Knight", "genre": "Metroidvania",
                                "genre2": "Plataforma", "platform": "switch", "hltb_hours": 26.98})
    values = game_dialog.current_metadata_values()
    assert values == {"developer": "Team Cherry", "franchise": "Hollow Knight", "genre": "Metroidvania",
                      "genre2": "Plataforma", "platform": "Switch", "hltb_hours": 27}
    game_dialog.apply_metadata({"platform": "PS5"})  # plataforma não cadastrada: mantém a atual
    assert game_dialog.combo_platform.currentText() == "Switch"


def test_fetch_game_data_requires_title(game_dialog, monkeypatch):
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warned.append(a[2]))
    game_dialog.fetch_game_data()
    assert warned and "título" in warned[0]


def test_fetch_game_data_opens_preview_and_applies(game_dialog, monkeypatch):
    opened = {}

    class FakePreview:
        def __init__(self, title, current, igdb, parent=None):
            opened.update(title=title, current=current, igdb=igdb)
            self.chosen = {"developer": "Team Cherry"}

        def exec(self):
            return QDialog.Accepted

    monkeypatch.setattr(gdm, "MetadataPreviewDialog", FakePreview)
    game_dialog.input_title.setText("  Hollow Knight ")
    game_dialog.fetch_game_data()
    assert opened["title"] == "Hollow Knight" and opened["current"]["developer"] == ""
    assert game_dialog.combo_developer.currentText() == "Team Cherry"


def test_igdb_credentials_from_settings():
    settings = QSettings("GameRoom", "GameRoomLog")
    settings.setValue("igdb_client_id", "cid")
    settings.setValue("igdb_client_secret", "")
    assert gdm.igdb_credentials() == {}
    settings.setValue("igdb_client_secret", " sec ")
    assert gdm.igdb_credentials() == {"igdb_client_id": "cid", "igdb_client_secret": "sec"}
    settings.remove("igdb_client_id")
    settings.remove("igdb_client_secret")


def test_settings_saves_igdb_credentials(qapp, monkeypatch):
    from frontend_desktop.views.components.settings_view import SettingsView
    monkeypatch.setattr(QMessageBox, "information", lambda *a: None)
    view = SettingsView()
    view.input_igdb_id.setText(" cid ")
    view.input_igdb_secret.setText("sec")
    view.save_igdb_credentials()
    assert gdm.igdb_credentials() == {"igdb_client_id": "cid", "igdb_client_secret": "sec"}
    QSettings("GameRoom", "GameRoomLog").remove("igdb_client_id")
    QSettings("GameRoom", "GameRoomLog").remove("igdb_client_secret")


# --- ApiClient ---

@responses.activate
def test_api_client_metadata():
    client = ApiClient(base_url=BASE)
    responses.add(responses.POST, f"{BASE}/metadata/search", json=SEARCH)
    responses.add(responses.POST, f"{BASE}/metadata/details", json=PROPOSAL)
    assert client.search_game_metadata("Hollow Knight", {"igdb_client_id": "c"}) == SEARCH
    assert b'"igdb_client_id": "c"' in responses.calls[0].request.body
    assert client.get_game_metadata("igdb", "1", "Hollow Knight")["developer"] == "Team Cherry"


@responses.activate
def test_api_client_metadata_errors():
    client = ApiClient(base_url=BASE)
    responses.add(responses.POST, f"{BASE}/metadata/search", json={"detail": "Nenhum jogo encontrado."}, status=404)
    with pytest.raises(RuntimeError, match="Nenhum jogo"):
        client.search_game_metadata("Nada")
    responses.add(responses.POST, f"{BASE}/metadata/details", body="erro", status=500)
    with pytest.raises(RuntimeError, match="500"):
        client.get_game_metadata("steam", "1", "X")
