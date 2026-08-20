from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame
)
from PySide6.QtCore import Signal, Qt
from frontend_desktop.views.components.game_grid import GameGrid
from frontend_desktop.views.components.game_card import GameCard

class GameRoomView(QWidget):
    game_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(20)

        # Scroll Area geral para a Game Room
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(24)

        # --- SEÇÃO: AGORA (Jogando & Próximos) ---
        now_header = QLabel("🕹️ Agora (Em Andamento)")
        now_header.setStyleSheet("font-size: 17px; font-weight: bold; color: #fffffe;")
        container_layout.addWidget(now_header)

        self.now_grid = GameGrid()
        self.now_grid.game_selected.connect(self.game_selected.emit)
        container_layout.addWidget(self.now_grid)

        # Divisor sutil
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #23232a; max-height: 1px;")
        container_layout.addWidget(line)

        # --- SEÇÃO: FILA DE ESPERA ---
        queue_header = QLabel("📋 Fila de Espera")
        queue_header.setStyleSheet("font-size: 17px; font-weight: bold; color: #fffffe;")
        container_layout.addWidget(queue_header)

        self.queue_grid = GameGrid()
        self.queue_grid.game_selected.connect(self.game_selected.emit)
        container_layout.addWidget(self.queue_grid)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def set_games(self, now_games: list, queue_games: list):
        self.now_grid.set_games(now_games)
        self.queue_grid.set_games(queue_games)
