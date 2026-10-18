"""Busca rápida (Ctrl+F): encontra qualquer jogo da biblioteca pelo título e abre a edição."""
import unicodedata
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from frontend_desktop.ui_helpers import add_search_icon

MAX_RESULTS = 50


def fold(text: str) -> str:
    """Minúsculas e sem acentos ("Pokémon" encontra "pokemon")."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


def search_games(games: List[dict], query: str, limit: int = MAX_RESULTS) -> List[dict]:
    """Títulos que contêm todas as palavras da busca; os que começam com ela vêm primeiro."""
    words = fold(query).split()
    if not words:
        return []
    needle = " ".join(words)
    hits = [g for g in games if all(w in fold(g.get("title")) for w in words)]
    hits.sort(key=lambda g: (not fold(g.get("title")).startswith(needle), fold(g.get("title"))))
    return hits[:limit]


def describe(game: dict) -> str:
    platform = (game.get("platform") or {}).get("name")
    extra = " · ".join(p for p in (game.get("status"), platform) if p)
    return f"{game.get('title') or 'Sem título'}" + (f"   —   {extra}" if extra else "")


class QuickSearchDialog(QDialog):
    def __init__(self, games: List[dict], parent=None):
        super().__init__(parent)
        self.games = games
        self.selected_game: Optional[dict] = None
        self.setWindowTitle("Buscar jogo")
        self.setMinimumSize(560, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Digite o título do jogo...")
        self.input.setProperty("class", "search-input")
        self.input.setClearButtonEnabled(True)
        add_search_icon(self.input)
        self.input.textChanged.connect(self.update_results)
        self.input.returnPressed.connect(self.accept_current)
        layout.addWidget(self.input)

        self.results = QListWidget()
        self.results.setObjectName("quickSearchResults")
        self.results.itemActivated.connect(lambda _item: self.accept_current())
        layout.addWidget(self.results, 1)

        self.hint = QLabel("↑ ↓ para escolher · Enter para abrir · Esc para fechar")
        self.hint.setProperty("class", "status-muted")
        layout.addWidget(self.hint)
        self.update_results("")

    def update_results(self, text: str) -> None:
        self.results.clear()
        for game in search_games(self.games, text):
            item = QListWidgetItem(describe(game))
            item.setData(Qt.UserRole, game)
            self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(0)
        if text.strip() and not self.results.count():
            self.hint.setText("Nenhum jogo encontrado.")
        else:
            self.hint.setText("↑ ↓ para escolher · Enter para abrir · Esc para fechar")

    def keyPressEvent(self, event):
        # Setas no campo de busca movem a seleção da lista
        if event.key() in (Qt.Key_Down, Qt.Key_Up) and self.results.count():
            step = 1 if event.key() == Qt.Key_Down else -1
            row = max(0, min(self.results.count() - 1, self.results.currentRow() + step))
            self.results.setCurrentRow(row)
            return
        super().keyPressEvent(event)

    def accept_current(self) -> None:
        item = self.results.currentItem()
        if item is None:
            return
        self.selected_game = item.data(Qt.UserRole)
        self.accept()
