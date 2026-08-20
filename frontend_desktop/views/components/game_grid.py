from PySide6.QtWidgets import (
    QWidget, QScrollArea, QGridLayout, QVBoxLayout, QLabel
)
from PySide6.QtCore import Signal, Qt
from frontend_desktop.views.components.game_card import GameCard

class GameGrid(QScrollArea):
    game_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        
        self.container = QWidget()
        
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.setWidget(self.container)
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
            empty_label.setStyleSheet("color: #72757e; font-size: 14px; padding: 40px;")
            empty_label.setAlignment(Qt.AlignCenter)
            self.grid_layout.addWidget(empty_label, 0, 0)
            return

        # Renderiza em grid de 4 colunas por padrão
        cols = 4
        for idx, game in enumerate(self.games):
            row = idx // cols
            col = idx % cols
            card = GameCard(game)
            card.clicked.connect(self.on_card_clicked)
            self.grid_layout.addWidget(card, row, col)

    def on_card_clicked(self, game_data: dict):
        self.game_selected.emit(game_data)
