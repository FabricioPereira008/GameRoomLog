"""Escolher jogos para entrar num ranking (respeita o filtro e as vagas restantes)."""
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
)

from frontend_desktop.rankings import entry_ids, filter_text, game_matches
from frontend_desktop.text_search import fold, fold_query
from frontend_desktop.ui_helpers import add_search_icon
from frontend_desktop.views.dialogs.top3_dialog import game_option_text


def candidates(ranking: dict, games: List[dict]) -> List[dict]:
    """Jogos que podem entrar: casam com o filtro, ainda não estão no ranking e não são rejogadas
    (a rejogada é outro registro do mesmo jogo). Favoritos primeiro, depois por nota e título."""
    taken = set(entry_ids(ranking))
    pool = [g for g in games if g.get("id") not in taken and not g.get("replay_of_id") and game_matches(ranking, g)]
    return sorted(pool, key=lambda g: (not g.get("is_favorite"), g.get("score") is None, -(g.get("score") or 0),
                                       (g.get("title") or "").casefold()))


class RankingPickerDialog(QDialog):
    def __init__(self, ranking: dict, games: List[dict], parent=None):
        super().__init__(parent)
        self.ranking = ranking
        self.slots = max(0, ranking.get("max_size", 0) - len(ranking.get("entries") or []))
        self.selected_ids: List[int] = []  # na ordem em que foram marcados (vão para as próximas posições)
        self.setWindowTitle(f"Adicionar a {ranking.get('name', 'ranking')}")
        self.setMinimumSize(520, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        title = QLabel(f"Adicionar jogos a \"{ranking.get('name', '')}\"")
        title.setProperty("class", "section-header")
        layout.addWidget(title)
        parts = [filter_text(ranking) or "Sem filtro", f"{self.slots} vaga(s)", "♥ = favorito"]
        hint = QLabel(" · ".join(parts) + ". Os marcados entram nas próximas posições, na ordem em que você marcar.")
        hint.setWordWrap(True)
        hint.setProperty("class", "settings-desc")
        layout.addWidget(hint)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar pelo título...")
        self.search.setClearButtonEnabled(True)
        self.search.setProperty("class", "search-input")
        add_search_icon(self.search)
        self.search.textChanged.connect(self.apply_search)
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.games = candidates(ranking, games)
        for game in self.games:
            prefix = "♥  " if game.get("is_favorite") else ""
            item = QListWidgetItem(prefix + game_option_text(game))
            item.setData(Qt.UserRole, game["id"])
            item.setData(Qt.UserRole + 1, fold(game.get("title") or ""))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.list.addItem(item)
        self.list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.list, 1)

        self.empty = QLabel("Nenhum jogo disponível para este ranking." if not self.games else "")
        self.empty.setProperty("class", "empty-state-text")
        self.empty.setVisible(not self.games)
        layout.addWidget(self.empty)

        buttons = QHBoxLayout()
        self.counter = QLabel("")
        self.counter.setProperty("class", "status-muted")
        buttons.addWidget(self.counter)
        buttons.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.setProperty("class", "cancel-btn")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.btn_add = QPushButton("Adicionar")
        self.btn_add.setProperty("class", "action-btn")
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.clicked.connect(self.accept)
        buttons.addWidget(self.btn_add)
        layout.addLayout(buttons)
        self._sync()

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        gid = item.data(Qt.UserRole)
        if item.checkState() == Qt.Checked and gid not in self.selected_ids:
            self.selected_ids.append(gid)
        elif item.checkState() != Qt.Checked and gid in self.selected_ids:
            self.selected_ids.remove(gid)
        self._sync()

    def _sync(self) -> None:
        """Esgotadas as vagas, os demais jogos ficam desabilitados."""
        full = len(self.selected_ids) >= self.slots
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            item = self.list.item(i)
            checked = item.checkState() == Qt.Checked
            flags = item.flags() | Qt.ItemIsEnabled
            if full and not checked:
                flags &= ~Qt.ItemIsEnabled
            item.setFlags(flags)
        self.list.blockSignals(False)
        self.counter.setText(f"{len(self.selected_ids)} de {self.slots} vaga(s)")
        self.btn_add.setEnabled(bool(self.selected_ids))

    def apply_search(self, text: str) -> None:
        query = fold_query(text)
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(bool(query) and query not in item.data(Qt.UserRole + 1))
