"""Revisão dos eventos recebidos do app do portátil: vincular/criar o jogo, conferir o diff e aplicar."""
import logging
from typing import List, Optional

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QRadioButton, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from frontend_desktop.api_client.client import api_client
from frontend_desktop.ui_helpers import set_status
from frontend_desktop.views.dialogs.game_dialog import GameDialog
from frontend_desktop.workers import run_async

logger = logging.getLogger(__name__)

EVENT_LABELS = {"playing": "Jogando", "finished": "Zerado", "platinum": "Platinado"}
MATCH_MARKS = {"exact": "✓", "confirm": "?", "none": "+"}
FIELD_LABELS = {
    "status": "Status",
    "play_type": "Tipo de jogada",
    "play_count": "Nº de jogadas",
    "finish_date": "Zerado em",
    "platinum_date": "Platinado em",
    "played_hours": "Horas jogadas",
    "score": "Nota",
    "difficulty": "Dificuldade",
    "notes": "Observações",
}
NEW_GAME = 0  # id do botão "Criar novo jogo" (ids de jogos começam em 1; -1 = nada marcado)


def format_value(field: str, value) -> str:
    if value is None or value == "":
        return "—"
    if field.endswith("_date") and isinstance(value, str) and len(value) == 10:
        y, m, d = value.split("-")
        return f"{d}/{m}/{y}"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def describe_event(event: dict) -> str:
    parts = [format_value("x_date", event["event_date"]), EVENT_LABELS.get(event["event_type"], event["event_type"])]
    if event.get("played_hours") is not None:
        parts.append(f"{event['played_hours']:g}h")
    if event.get("score") is not None:
        parts.append(f"nota {event['score']:g}")
    if event.get("difficulty") is not None:
        parts.append(f"dificuldade {event['difficulty']:g}")
    line = " · ".join(parts)
    if event.get("notes"):
        line += f" — “{event['notes']}”"
    return line


def candidate_label(cand: dict) -> str:
    platform = f" ({cand['platform']})" if cand.get("platform") else ""
    label = f"{cand['title']}{platform} — {cand['status']} · {cand['similarity']}%"
    if not cand.get("platform_matches"):
        label += "  ⚠ plataforma diferente"
    return label


def apply_to_existing(game_id: int, changes: dict, event_ids: List[int]) -> dict:
    """Grava as mudanças propostas e marca os eventos como aplicados (fora da thread da UI)."""
    old = api_client.get_game(game_id)
    game = api_client.update_game(game_id, changes) if changes else old
    api_client.inbox_resolve(event_ids, "applied", game_id)
    return {"game": game, "old_status": old.get("status")}


def resolve_saved(game: dict, event_ids: List[int], is_new: bool, cover_key: str = "") -> dict:
    """Marca os eventos de um jogo salvo pelo GameDialog; jogos novos ganham capa automática."""
    api_client.inbox_resolve(event_ids, "applied", game["id"])
    if is_new and not game.get("cover_image"):
        try:
            if api_client.auto_cover_game(game["id"], cover_key or None).get("success"):
                game = api_client.get_game(game["id"])
        except Exception as exc:
            logger.warning("Falha ao buscar capa de %s: %s", game.get("title"), exc)
    return game


class GamePickerDialog(QDialog):
    """Lista filtrável dos jogos do GameRoom para vincular um evento manualmente."""

    def __init__(self, games: List[dict], initial_filter: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vincular a um jogo do GameRoom")
        self.resize(520, 520)
        self.selected_id: Optional[int] = None
        self._games = sorted(games, key=lambda g: (g.get("title") or "").lower())

        layout = QVBoxLayout(self)
        self.input_filter = QLineEdit(initial_filter)
        self.input_filter.setPlaceholderText("Filtrar por título...")
        self.input_filter.textChanged.connect(self._refill)
        layout.addWidget(self.input_filter)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda *_: self._accept())
        layout.addWidget(self.list, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.setProperty("class", "cancel-btn")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Vincular")
        ok.setProperty("class", "action-btn")
        ok.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        layout.addLayout(buttons)
        self._refill(initial_filter)

    def _refill(self, text: str):
        needle = text.strip().lower()
        self.list.clear()
        for g in self._games:
            if needle and needle not in (g.get("title") or "").lower():
                continue
            plat = (g.get("platform") or {}).get("name")
            item = QListWidgetItem(f"{g['title']}{f' ({plat})' if plat else ''}")
            item.setData(Qt.UserRole, g["id"])
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _accept(self):
        item = self.list.currentItem()
        if item is not None:
            self.selected_id = item.data(Qt.UserRole)
            self.accept()


class InboxReviewDialog(QDialog):
    game_saved = Signal(dict, bool, object)  # jogo, é novo, status anterior

    def __init__(self, threshold: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.threshold = threshold
        self.groups: List[dict] = []
        self.applied_count = 0
        self._busy = False
        self.setWindowTitle("Caixa de entrada do portátil")
        self.setMinimumSize(900, 560)
        self.resize(1040, 640)
        self._init_ui()
        self.load()

    # --- construção ---
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)

        self.lbl_summary = QLabel("Carregando eventos pendentes...")
        self.lbl_summary.setProperty("class", "settings-desc")
        layout.addWidget(self.lbl_summary)

        splitter = QSplitter(Qt.Horizontal)
        self.group_list = QListWidget()
        self.group_list.setMinimumWidth(260)
        self.group_list.currentRowChanged.connect(self._show_group)
        splitter.addWidget(self.group_list)
        splitter.addWidget(self._build_detail())
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        bottom = QHBoxLayout()
        self.lbl_status = QLabel("")
        bottom.addWidget(self.lbl_status, 1)
        btn_close = QPushButton("Fechar")
        btn_close.setProperty("class", "cancel-btn")
        btn_close.clicked.connect(self.accept)
        bottom.addWidget(btn_close)
        layout.addLayout(bottom)

    def _build_detail(self) -> QWidget:
        self.detail = QWidget()
        box = QVBoxLayout(self.detail)
        box.setContentsMargins(12, 0, 0, 0)
        box.setSpacing(10)

        self.lbl_title = QLabel("")
        self.lbl_title.setProperty("class", "section-header")
        box.addWidget(self.lbl_title)
        self.lbl_events = QLabel("")
        self.lbl_events.setWordWrap(True)
        self.lbl_events.setTextFormat(Qt.PlainText)
        box.addWidget(self.lbl_events)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        box.addWidget(sep)

        self.lbl_match = QLabel("")
        self.lbl_match.setWordWrap(True)
        box.addWidget(self.lbl_match)
        self.candidates_box = QVBoxLayout()
        box.addLayout(self.candidates_box)
        self.candidate_group = QButtonGroup(self)
        self.candidate_group.idClicked.connect(self._on_candidate_chosen)

        self.btn_pick = QPushButton("Vincular a outro jogo...")
        self.btn_pick.setProperty("class", "cancel-btn")
        self.btn_pick.clicked.connect(self.pick_other_game)
        pick_row = QHBoxLayout()
        pick_row.addWidget(self.btn_pick)
        pick_row.addStretch()
        box.addLayout(pick_row)

        self.lbl_platform = QLabel("")
        self.lbl_platform.setWordWrap(True)
        box.addWidget(self.lbl_platform)

        self.diff_table = QTableWidget(0, 3)
        self.diff_table.setHorizontalHeaderLabels(["Campo", "Atual", "Proposto"])
        self.diff_table.verticalHeader().setVisible(False)
        self.diff_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.diff_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.diff_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        box.addWidget(self.diff_table, 1)

        actions = QHBoxLayout()
        self.btn_discard = QPushButton("Descartar eventos")
        self.btn_discard.setProperty("class", "delete-btn")
        self.btn_discard.clicked.connect(self.discard_current)
        actions.addWidget(self.btn_discard)
        actions.addStretch()
        self.btn_edit = QPushButton("Editar e aplicar...")
        self.btn_edit.setProperty("class", "cancel-btn")
        self.btn_edit.clicked.connect(self.edit_and_apply)
        actions.addWidget(self.btn_edit)
        self.btn_apply = QPushButton("Aplicar")
        self.btn_apply.setProperty("class", "action-btn")
        self.btn_apply.clicked.connect(self.apply_current)
        actions.addWidget(self.btn_apply)
        box.addLayout(actions)

        self.detail.setVisible(False)
        return self.detail

    # --- carga ---
    def load(self):
        run_async(self, api_client.inbox_pending, self._on_loaded, self._on_failed, self.threshold)

    def _on_loaded(self, data: dict):
        self.groups = list(data.get("groups", []))
        self.group_list.clear()
        for group in self.groups:
            self.group_list.addItem(self._group_item(group))
        self._update_summary()
        if self.groups:
            self.group_list.setCurrentRow(0)

    def _on_failed(self, message: str):
        self._set_busy(False)
        set_status(self.lbl_status, "error", f"Erro: {message}")

    @staticmethod
    def _group_item(group: dict) -> QListWidgetItem:
        platform = f" · {group['platform']}" if group.get("platform") else ""
        n = len(group["events"])
        item = QListWidgetItem(f"{MATCH_MARKS[group['match']]}  {group['title']}{platform}  ({n} evento{'s' if n > 1 else ''})")
        item.setToolTip({"exact": "Jogo encontrado", "confirm": "Confirme qual é o jogo",
                         "none": "Nenhum jogo parecido: criar ou vincular"}[group["match"]])
        return item

    def _update_summary(self):
        if not self.groups:
            self.lbl_summary.setText("Nenhum evento pendente do portátil.")
            self.detail.setVisible(False)
            return
        total = sum(len(g["events"]) for g in self.groups)
        self.lbl_summary.setText(
            f"{total} evento(s) em {len(self.groups)} jogo(s). ✓ encontrado · ? confirmar · + sem correspondência"
        )

    # --- detalhe ---
    @property
    def current_group(self) -> Optional[dict]:
        row = self.group_list.currentRow()
        return self.groups[row] if 0 <= row < len(self.groups) else None

    def _show_group(self, row: int):
        group = self.current_group
        self.detail.setVisible(group is not None)
        if group is None:
            return
        platform = f" — {group['platform']}" if group.get("platform") else ""
        self.lbl_title.setText(f"{group['title']}{platform}")
        self.lbl_events.setText("\n".join(describe_event(e) for e in group["events"]))
        self.lbl_match.setText({
            "exact": "Jogo encontrado no GameRoom:",
            "confirm": "Encontramos jogos parecidos. Estes são o mesmo jogo?",
            "none": "Nenhum jogo parecido no GameRoom.",
        }[group["match"]])
        self._fill_candidates(group)
        self._show_platform(group)

    def _fill_candidates(self, group: dict, select_id: Optional[int] = None):
        for button in self.candidate_group.buttons():
            self.candidate_group.removeButton(button)
            button.deleteLater()
        for cand in group["candidates"]:
            radio = QRadioButton(candidate_label(cand))
            self.candidate_group.addButton(radio, cand["game_id"])
            self.candidates_box.addWidget(radio)
        radio_new = QRadioButton("Criar novo jogo com estes dados")
        self.candidate_group.addButton(radio_new, NEW_GAME)
        self.candidates_box.addWidget(radio_new)

        if select_id is None:
            # "confirm" não escolhe sozinho: o usuário confirma qual é o jogo
            select_id = group["candidates"][0]["game_id"] if group["match"] == "exact" else (
                NEW_GAME if group["match"] == "none" else None)
        button = self.candidate_group.button(select_id) if select_id is not None else None
        if button is not None:
            button.setChecked(True)
        self._on_candidate_chosen(select_id if button is not None else None)

    def _show_platform(self, group: dict):
        pm = group.get("platform_match")
        if not pm:
            self.lbl_platform.setText("Plataforma: não informada pelo app.")
        elif pm["is_new"]:
            self.lbl_platform.setText(f"Plataforma: “{pm['name']}” não existe no GameRoom e será criada ao criar o jogo.")
        elif pm["similarity"] < 100:
            self.lbl_platform.setText(f"Plataforma: “{group['platform']}” → {pm['name']} ({pm['similarity']}%).")
        else:
            self.lbl_platform.setText(f"Plataforma: {pm['name']}.")

    def selected_candidate(self) -> Optional[dict]:
        group = self.current_group
        chosen = self.candidate_group.checkedId()
        if group is None or chosen in (-1, NEW_GAME):
            return None
        return next((c for c in group["candidates"] if c["game_id"] == chosen), None)

    def _on_candidate_chosen(self, button_id):
        group = self.current_group
        is_new = button_id == NEW_GAME
        cand = None if is_new or group is None else next(
            (c for c in group["candidates"] if c["game_id"] == button_id), None)
        self.diff_table.setRowCount(0)
        if is_new and group is not None:
            rows = [(f, None, group["new_game"].get(f)) for f in FIELD_LABELS if group["new_game"].get(f) is not None]
        elif cand is not None:
            rows = [(f, cand["current"].get(f), cand["changes"][f]) for f in FIELD_LABELS if f in cand["changes"]]
        else:
            rows = []
        for field, old, new in rows:
            r = self.diff_table.rowCount()
            self.diff_table.insertRow(r)
            self.diff_table.setItem(r, 0, QTableWidgetItem(FIELD_LABELS[field]))
            self.diff_table.setItem(r, 1, QTableWidgetItem(format_value(field, old)))
            self.diff_table.setItem(r, 2, QTableWidgetItem(format_value(field, new)))
        self.diff_table.resizeRowsToContents()

        self.btn_apply.setText("Criar jogo..." if is_new else "Aplicar")
        self.btn_apply.setEnabled(not self._busy and (is_new or cand is not None))
        self.btn_edit.setVisible(not is_new)
        self.btn_edit.setEnabled(not self._busy and cand is not None)
        if cand is not None and not cand["changes"]:
            set_status(self.lbl_status, "ok", "Nada muda neste jogo; aplicar só marca os eventos como revisados.")
        else:
            self.lbl_status.setText("")

    def _set_busy(self, busy: bool):
        self._busy = busy
        for b in (self.btn_apply, self.btn_edit, self.btn_discard, self.btn_pick):
            b.setEnabled(not busy)
        if not busy:
            self._on_candidate_chosen(self.candidate_group.checkedId())

    def _event_ids(self, group: dict) -> List[int]:
        return [e["id"] for e in group["events"]]

    def _remove_current(self, message: str):
        row = self.group_list.currentRow()
        self.groups.pop(row)
        self.group_list.takeItem(row)
        self._update_summary()
        set_status(self.lbl_status, "ok", message)

    # --- vincular manualmente ---
    def pick_other_game(self):
        group = self.current_group
        if group is None:
            return
        self._set_busy(True)
        run_async(self, api_client.get_games, lambda games: self._open_picker(group, games), self._on_failed)

    def _open_picker(self, group: dict, games: list):
        self._set_busy(False)
        picker = GamePickerDialog(games, group["title"], self)
        if picker.exec() != QDialog.Accepted or picker.selected_id is None:
            return
        self._set_busy(True)
        run_async(self, api_client.inbox_proposal, lambda cand: self._on_manual_candidate(group, cand),
                  self._on_failed, self._event_ids(group), picker.selected_id, self.threshold)

    def _on_manual_candidate(self, group: dict, cand: dict):
        group["candidates"] = [cand] + [c for c in group["candidates"] if c["game_id"] != cand["game_id"]]
        if self.current_group is group:
            self._fill_candidates(group, cand["game_id"])
        self._set_busy(False)

    # --- ações ---
    def apply_current(self):
        group = self.current_group
        if group is None:
            return
        if self.candidate_group.checkedId() == NEW_GAME:
            self.create_game(group)
            return
        cand = self.selected_candidate()
        if cand is None:
            return
        self._set_busy(True)
        run_async(self, apply_to_existing, lambda res: self._on_applied(group, res), self._on_failed,
                  cand["game_id"], cand["changes"], self._event_ids(group))

    def _on_applied(self, group: dict, result: dict):
        self.applied_count += 1
        self.game_saved.emit(result["game"], False, result["old_status"])
        if self.current_group is group:
            self._remove_current(f"“{result['game']['title']}” atualizado.")
        self._set_busy(False)

    def edit_and_apply(self):
        group, cand = self.current_group, self.selected_candidate()
        if group is None or cand is None:
            return
        self._set_busy(True)
        run_async(self, api_client.get_game, lambda game: self._open_edit_dialog(group, cand, game),
                  self._on_failed, cand["game_id"])

    def _open_edit_dialog(self, group: dict, cand: dict, game: dict):
        self._set_busy(False)
        dialog = GameDialog({**game, **cand["changes"]}, self)
        if dialog.exec() != QDialog.Accepted or not dialog.saved_game or dialog.is_deleted:
            return
        self._finish_with_dialog(group, dialog.saved_game, is_new=False, old_status=game.get("status"))

    def create_game(self, group: dict):
        pm = group.get("platform_match")
        if pm and pm["is_new"]:
            self._set_busy(True)
            run_async(self, api_client.create_platform, lambda plat: self._open_create_dialog(group, plat["id"]),
                      self._on_failed, pm["name"])
        else:
            self._open_create_dialog(group, group["new_game"].get("platform_id"))

    def _open_create_dialog(self, group: dict, platform_id: Optional[int]):
        self._set_busy(False)
        pm = group.get("platform_match")
        if pm and pm["is_new"] and platform_id:
            # criada agora: os próximos grupos com a mesma plataforma não a criam de novo
            for g in self.groups:
                other = g.get("platform_match")
                if other and other["is_new"] and other["name"].lower() == pm["name"].lower():
                    g["platform_match"] = {**other, "platform_id": platform_id, "is_new": False, "similarity": 100}
                    g["new_game"]["platform_id"] = platform_id
        data = {k: v for k, v in group["new_game"].items() if k != "platform_id"}
        if platform_id:
            data["platform"] = {"id": platform_id}
        dialog = GameDialog(data, self)
        if dialog.exec() != QDialog.Accepted or not dialog.saved_game:
            return
        self._finish_with_dialog(group, dialog.saved_game, is_new=True, old_status=None)

    def _finish_with_dialog(self, group: dict, game: dict, is_new: bool, old_status):
        self._set_busy(True)
        cover_key = QSettings("GameRoom", "GameRoomLog").value("steamgriddb_key", "") if is_new else ""
        run_async(self, resolve_saved, lambda saved: self._on_dialog_resolved(group, saved, is_new, old_status),
                  self._on_failed, game, self._event_ids(group), is_new, cover_key)

    def _on_dialog_resolved(self, group: dict, game: dict, is_new: bool, old_status):
        self.applied_count += 1
        self.game_saved.emit(game, is_new, old_status)
        if self.current_group is group:
            self._remove_current(f"“{game['title']}” {'criado' if is_new else 'atualizado'}.")
        self._set_busy(False)

    def discard_current(self):
        group = self.current_group
        if group is None:
            return
        confirm = QMessageBox.question(
            self, "Descartar eventos",
            f"Descartar os {len(group['events'])} evento(s) de “{group['title']}”? Eles não voltarão em reimportações.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self._set_busy(True)
        run_async(self, api_client.inbox_resolve, lambda _: self._on_discarded(group), self._on_failed,
                  self._event_ids(group), "discarded")

    def _on_discarded(self, group: dict):
        if self.current_group is group:
            self._remove_current(f"Eventos de “{group['title']}” descartados.")
        self._set_busy(False)
