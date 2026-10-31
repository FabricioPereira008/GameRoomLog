"""Busca de dados do jogo (IGDB / Steam / HowLongToBeat): escolhe o jogo certo e marca o que aplicar."""
from typing import Any, Callable, Dict, Optional

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from frontend_desktop.api_client.client import api_client
from frontend_desktop.ui_helpers import set_status
from frontend_desktop.workers import run_async

SOURCE_NAMES = {"igdb": "IGDB", "steam": "Steam"}

# (campo, rótulo) na ordem do formulário
FIELDS = (
    ("developer", "Desenvolvedora"),
    ("franchise", "Franquia / Série"),
    ("genre", "Gênero principal"),
    ("genre2", "Gênero secundário"),
    ("platform", "Plataforma"),
    ("hltb_hours", "Duração (HowLongToBeat)"),
)


def candidate_label(c: dict) -> str:
    extra = " · ".join(p for p in (str(c["year"]) if c.get("year") else "", ", ".join(c.get("platforms") or [])) if p)
    return f"{c.get('name')}" + (f"   —   {extra}" if extra else "")


def format_value(field: str, value: Any) -> str:
    if value in (None, "", 0):
        return "—"
    if field == "hltb_hours":
        return f"{round(float(value))} h"
    return str(value)


def proposal_values(proposal: dict) -> Dict[str, Any]:
    """Proposta da API -> valores por campo do formulário (plataforma: lista de opções)."""
    genres = list(proposal.get("genres") or []) + [None, None]
    return {
        "developer": proposal.get("developer"),
        "franchise": proposal.get("franchise"),
        "genre": genres[0],
        "genre2": genres[1],
        "platform": list(proposal.get("platforms") or []),
        "hltb_hours": proposal.get("hltb_hours"),
    }


def _same(field: str, current: Any, suggested: Any) -> bool:
    if field == "hltb_hours":
        return bool(current) and round(float(current)) == round(float(suggested))
    return str(current or "").strip().casefold() == str(suggested or "").strip().casefold()


class MetadataPreviewDialog(QDialog):
    """`current`: valores atuais do formulário por campo (ver FIELDS). Ao aceitar, `chosen` traz o que aplicar."""

    def __init__(self, title: str, current: Dict[str, Any], igdb: Optional[Dict[str, str]] = None,
                 parent=None, search: Optional[Callable] = None, details: Optional[Callable] = None):
        super().__init__(parent)
        self.title = title
        self.current = current
        self.igdb = igdb
        self._search = search or api_client.search_game_metadata
        self._details = details or api_client.get_game_metadata
        self.candidates: list = []
        self.chosen: Dict[str, Any] = {}
        self._rows: Dict[str, tuple] = {}  # campo -> (checkbox, widget do valor sugerido)
        self._values: Dict[str, Any] = {}
        self._request = 0  # descarta respostas de um candidato que já não está selecionado

        self.setWindowTitle("Buscar dados do jogo")
        self.setMinimumSize(640, 560)
        self._build_ui()
        self.start_search()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        heading = QLabel(f"Resultados para “{self.title}”")
        heading.setProperty("class", "card-title")
        layout.addWidget(heading)
        hint = QLabel("Escolha o jogo certo; depois marque os dados que devem ir para o cadastro.")
        hint.setProperty("class", "settings-desc")
        layout.addWidget(hint)

        self.list_candidates = QListWidget()
        self.list_candidates.setObjectName("metadataCandidates")
        self.list_candidates.setMaximumHeight(170)
        self.list_candidates.currentRowChanged.connect(self.load_details)
        layout.addWidget(self.list_candidates)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        self.fields_box = QWidget()
        grid = QGridLayout(self.fields_box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        for col, text in enumerate(("Campo", "Atual", "Sugerido")):
            lbl = QLabel(text)
            lbl.setProperty("class", "form-label")
            grid.addWidget(lbl, 0, col)
        for row, (field, label) in enumerate(FIELDS, start=1):
            check = QCheckBox(label)
            current = QLabel(format_value(field, self.current.get(field)))
            current.setProperty("class", "status-muted")
            value = QComboBox() if field == "platform" else QLabel("—")
            grid.addWidget(check, row, 0)
            grid.addWidget(current, row, 1)
            grid.addWidget(value, row, 2)
            self._rows[field] = (check, value)
        grid.setColumnStretch(2, 1)
        self.fields_box.setEnabled(False)
        layout.addWidget(self.fields_box)
        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("class", "cancel-btn")
        btn_cancel.clicked.connect(self.reject)
        self.btn_apply = QPushButton("Aplicar marcados")
        self.btn_apply.setProperty("class", "action-btn")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self.apply)
        buttons.addWidget(btn_cancel)
        buttons.addWidget(self.btn_apply)
        layout.addLayout(buttons)

    # --- busca ---
    def start_search(self):
        set_status(self.lbl_status, "muted", "Pesquisando...")
        run_async(self, self._search, self._on_search_done, self._on_error, self.title, self.igdb)

    def _on_search_done(self, result: dict):
        self.candidates = result.get("candidates") or []
        for c in self.candidates:
            item = QListWidgetItem(candidate_label(c))
            item.setToolTip(f"Fonte: {SOURCE_NAMES.get(c.get('source'), c.get('source'))}")
            self.list_candidates.addItem(item)
        if result.get("warning"):
            set_status(self.lbl_status, "error", result["warning"])
        if self.candidates:
            self.list_candidates.setCurrentRow(0)

    def _on_error(self, message: str):
        set_status(self.lbl_status, "error", message or "Não foi possível buscar os dados.")

    def load_details(self, row: int):
        if not 0 <= row < len(self.candidates):
            return
        self._request += 1
        request = self._request
        c = self.candidates[row]
        self.fields_box.setEnabled(False)
        self.btn_apply.setEnabled(False)
        set_status(self.lbl_status, "muted", "Carregando dados (o HowLongToBeat pode demorar alguns segundos)...")
        run_async(
            self, self._details,
            lambda proposal: self._on_details(request, proposal),
            lambda msg: request == self._request and self._on_error(msg),
            c["source"], c["source_id"], c.get("name") or self.title, self.igdb,
        )

    def _on_details(self, request: int, proposal: dict):
        if request != self._request:
            return
        self.show_proposal(proposal)
        source = SOURCE_NAMES.get(proposal.get("source"), proposal.get("source"))
        hours_from = proposal.get("hltb_source")
        text = f"Fonte: {source} · duração: {hours_from or 'não encontrada'}."
        set_status(self.lbl_status, "ok", text)

    def show_proposal(self, proposal: dict):
        """Preenche a coluna "Sugerido"; vem marcado só o que preenche um campo vazio."""
        self._values = proposal_values(proposal)
        for field, suggested in self._values.items():
            check, widget = self._rows[field]
            current = self.current.get(field)
            if field == "platform":
                widget.clear()
                widget.addItems(suggested)
                widget.setEnabled(len(suggested) > 1)
                first = suggested[0] if suggested else None
                has_value = bool(first)
                differs = has_value and not any(_same(field, current, s) for s in suggested)
            else:
                widget.setText(format_value(field, suggested))
                has_value = suggested not in (None, "", 0)
                differs = has_value and not _same(field, current, suggested)
            check.setEnabled(bool(differs))
            check.setChecked(bool(differs) and not current)
        self.fields_box.setEnabled(True)
        self.btn_apply.setEnabled(True)

    def apply(self):
        chosen = {}
        for field, (check, widget) in self._rows.items():
            if not (check.isEnabled() and check.isChecked()):
                continue
            chosen[field] = widget.currentText() if field == "platform" else self._values.get(field)
        self.chosen = {k: v for k, v in chosen.items() if v not in (None, "")}
        self.accept()

    def done(self, result):
        """Buscas ainda em andamento passam para o diálogo pai (que as espera ao fechar) e são ignoradas."""
        self._request += 1
        owner = self.parent()
        for worker in list(self.__dict__.get("_workers", ())):
            for signal in (worker.succeeded, worker.failed):
                signal.disconnect()
            if owner is not None:
                worker.setParent(owner)
                owner.__dict__.setdefault("_workers", set()).add(worker)
                worker.finished.connect(lambda w=worker: owner.__dict__["_workers"].discard(w))
            else:
                worker.wait()
        super().done(result)
