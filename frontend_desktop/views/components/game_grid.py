from PySide6.QtWidgets import (
    QWidget, QScrollArea, QGridLayout, QVBoxLayout, QLabel, QSizePolicy
)
from PySide6.QtCore import Signal, Qt, QSettings
from frontend_desktop.views.components.game_card import GameCard

class GameGrid(QWidget):
    """Grid adaptativa e de alta performance com colunas dinâmicas e carregamento sob demanda."""
    game_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gameGridContainer")
        self.setProperty("class", "game-grid-container")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.grid_layout = QGridLayout(self)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setSpacing(14)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.games = []
        self.cards = []
        self.batch_size = 35
        self.rendered_count = 0
        self.current_cols = 5

    def get_card_width(self) -> int:
        size_mode = QSettings("GameRoom", "GameRoomLog").value("card_size", "medium")
        if size_mode == "small":
            return 130
        elif size_mode == "large":
            return 230
        return 170

    def calculate_cols(self) -> int:
        available_width = self.width()
        if available_width <= 200 and self.parentWidget():
            available_width = self.parentWidget().width()
        if available_width <= 200:
            available_width = 1200  # Fallback razoável para renderização inicial

        card_width = self.get_card_width()
        spacing = 14
        cols = max(2, (available_width - 16) // (card_width + spacing))
        return cols

    def set_games(self, games: list):
        self.games = games
        self.rendered_count = 0
        self.cards = []
        self.current_cols = self.calculate_cols()

        # Limpa widgets anteriores
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self.games:
            empty_label = QLabel("Nenhum jogo encontrado nesta categoria.")
            empty_label.setProperty("class", "empty-state-text")
            empty_label.setAlignment(Qt.AlignCenter)
            self.grid_layout.addWidget(empty_label, 0, 0)
            return

        self.load_more_cards()

    def load_more_cards(self):
        total = len(self.games)
        if self.rendered_count >= total:
            return

        cols = self.current_cols
        next_count = min(self.rendered_count + self.batch_size, total)
        batch = self.games[self.rendered_count:next_count]

        self.setUpdatesEnabled(False)
        for idx, game in enumerate(batch):
            global_idx = self.rendered_count + idx
            row = global_idx // cols
            col = global_idx % cols
            card = GameCard(game)
            card.clicked.connect(self.on_card_clicked)
            self.cards.append(card)
            self.grid_layout.addWidget(card, row, col)

        self.rendered_count = next_count
        self.setUpdatesEnabled(True)

    def relayout_cards(self):
        """Re-posiciona os cards existentes quando a largura da tela muda."""
        if not self.cards:
            return

        new_cols = self.calculate_cols()
        if new_cols == self.current_cols:
            return

        self.current_cols = new_cols
        self.setUpdatesEnabled(False)

        # Remove todos da grid sem deletar
        while self.grid_layout.count():
            self.grid_layout.takeAt(0)

        # Reinsere nas novas posições (row, col)
        for idx, card in enumerate(self.cards):
            row = idx // self.current_cols
            col = idx % self.current_cols
            self.grid_layout.addWidget(card, row, col)

        self.setUpdatesEnabled(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.relayout_cards()

    def on_card_clicked(self, game_data: dict):
        self.game_selected.emit(game_data)


class ScrollableGameGrid(QScrollArea):
    """Container com barra de rolagem e carregamento infinito sob demanda."""
    game_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gameGridScrollArea")
        self.setProperty("class", "game-grid")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.grid = GameGrid()
        self.grid.game_selected.connect(self.game_selected.emit)
        self.setWidget(self.grid)

        self.verticalScrollBar().valueChanged.connect(self.on_scroll)

    def set_games(self, games: list):
        self.grid.set_games(games)

    def on_scroll(self, value: int):
        scroll_bar = self.verticalScrollBar()
        if value >= scroll_bar.maximum() - 60:
            self.grid.load_more_cards()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.grid.relayout_cards()
