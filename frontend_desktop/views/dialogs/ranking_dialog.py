"""Criar/editar um ranking de favoritos: nome, tamanho e filtro opcional (gênero, franquia ou plataforma)."""
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QVBoxLayout,
)

from frontend_desktop.rankings import FILTER_FIELD, FILTER_TYPES

MAX_SIZE = 50
DEFAULT_SIZE = 10


class RankingDialog(QDialog):
    def __init__(self, options: Dict[str, List[dict]], ranking: Optional[dict] = None, parent=None):
        """`options`: {"genre": [...], "franchise": [...], "platform": [...]} (itens com id e name)."""
        super().__init__(parent)
        self.ranking = ranking or {}
        self.options = options
        self.payload: Optional[dict] = None
        self.setWindowTitle("Editar ranking" if ranking else "Novo ranking")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        title = QLabel("Editar ranking" if ranking else "Novo ranking")
        title.setProperty("class", "section-header")
        layout.addWidget(title)
        hint = QLabel("Ex.: \"Top 10 de todos os tempos\" sem filtro, ou \"Top Soulslike\" filtrado pelo gênero. "
                      "Com filtro, só entram jogos daquele gênero, franquia ou plataforma.")
        hint.setWordWrap(True)
        hint.setProperty("class", "settings-desc")
        layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(10)
        self.input_name = QLineEdit(self.ranking.get("name", ""))
        self.input_name.setPlaceholderText("Nome do ranking")
        self.input_name.setMaxLength(100)
        form.addRow("Nome", self.input_name)

        self.spin_size = QSpinBox()
        self.spin_size.setRange(1, MAX_SIZE)
        self.spin_size.setValue(int(self.ranking.get("max_size") or DEFAULT_SIZE))
        self.spin_size.setPrefix("Top ")
        form.addRow("Posições", self.spin_size)

        self.combo_filter_type = QComboBox()
        self.combo_filter_type.addItem("Sem filtro (qualquer jogo)", None)
        for kind, label in FILTER_TYPES:
            self.combo_filter_type.addItem(label, kind)
        form.addRow("Filtro", self.combo_filter_type)

        self.combo_filter_item = QComboBox()
        self.combo_filter_item.setEditable(True)
        self.combo_filter_item.setInsertPolicy(QComboBox.NoInsert)
        form.addRow("", self.combo_filter_item)
        layout.addLayout(form)

        self.combo_filter_type.currentIndexChanged.connect(self._fill_filter_items)
        current_kind = self.ranking.get("filter_type")
        self.combo_filter_type.setCurrentIndex(max(0, self.combo_filter_type.findData(current_kind)))
        self._fill_filter_items()
        if current_kind:
            idx = self.combo_filter_item.findData(self.ranking.get(FILTER_FIELD[current_kind]))
            self.combo_filter_item.setCurrentIndex(max(0, idx))

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.setProperty("class", "cancel-btn")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.btn_save = QPushButton("Salvar")
        self.btn_save.setProperty("class", "action-btn")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self.save)
        buttons.addWidget(self.btn_save)
        layout.addLayout(buttons)

    def _fill_filter_items(self, *_):
        kind = self.combo_filter_type.currentData()
        self.combo_filter_item.clear()
        self.combo_filter_item.setVisible(kind is not None)
        for item in sorted(self.options.get(kind, []) if kind else [], key=lambda i: (i.get("name") or "").casefold()):
            self.combo_filter_item.addItem(item.get("name") or "", item.get("id"))

    def build_payload(self) -> dict:
        kind = self.combo_filter_type.currentData()
        payload = {"name": self.input_name.text().strip(), "max_size": self.spin_size.value()}
        for k, field in FILTER_FIELD.items():
            payload[field] = self.combo_filter_item.currentData() if k == kind else None
        return payload

    def save(self) -> None:
        payload = self.build_payload()
        if not payload["name"]:
            QMessageBox.warning(self, "Ranking", "Dê um nome ao ranking.")
            return
        if self.combo_filter_type.currentData() and payload[FILTER_FIELD[self.combo_filter_type.currentData()]] is None:
            QMessageBox.warning(self, "Ranking", "Escolha o item do filtro (ou deixe sem filtro).")
            return
        filled = len(self.ranking.get("entries") or [])
        if filled > payload["max_size"]:
            answer = QMessageBox.question(
                self, "Reduzir ranking",
                f"O ranking tem {filled} jogos. As posições depois do {payload['max_size']}º serão removidas. Continuar?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
        self.payload = payload
        self.accept()
