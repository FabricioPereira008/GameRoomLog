from PySide6.QtWidgets import (
    QWidget, QScrollArea, QGridLayout, QVBoxLayout, QLabel, QSizePolicy
)
from PySide6.QtCore import Signal, Qt
from frontend_desktop.views.components.game_card import GameCard

class GameGrid(QWidget):
    """Grid plana que se expande verticalmente conforme o conteúdo (sem scroll interno)."""
    game_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gameGridContainer")
        self.setProperty("class", "game-grid-container")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.grid_layout = QGridLayout(self)
        self.grid_layout.setContentsMargins(6, 6, 6, 6)
        self.grid_layout.setSpacing(14)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.games = []

    def set_games(self, games: list):
        self.games = games
        self.render()

    def render(self):
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

        # Renderiza em grid de 5 colunas para o novo formato vertical
        cols = 5
        for idx, game in enumerate(self.games):
            row = idx // cols
            col = idx % cols
            card = GameCard(game)
            card.clicked.connect(self.on_card_clicked)
            self.grid_layout.addWidget(card, row, col)

    def on_card_clicked(self, game_data: dict):
        self.game_selected.emit(game_data)


class ScrollableGameGrid(QScrollArea):
    """Container com barra de rolagem unificada para abas independentes (ex: Zerados, Fila, etc)."""
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

    def set_games(self, games: list):
        self.grid.set_games(games)
