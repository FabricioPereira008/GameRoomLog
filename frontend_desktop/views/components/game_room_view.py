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
        self.setObjectName("gameRoomView")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(20)

        # Scroll Area geral para a Game Room
        self.scroll = QScrollArea()
        self.scroll.setObjectName("gameRoomScrollArea")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.verticalScrollBar().valueChanged.connect(self.on_scroll)

        container = QWidget()
        container.setObjectName("gameRoomScrollContainer")
        container.setAttribute(Qt.WA_StyledBackground, True)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(24)

        # --- FUNÇÃO HELPER PARA CRIAR SEÇÕES ---
        def create_section(title, object_name):
            section = QFrame()
            section.setObjectName(object_name)
            section.setProperty("class", "game-section-card")
            section.setAttribute(Qt.WA_StyledBackground, True)
            layout = QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(12)
            
            header = QLabel(title)
            header.setProperty("class", "section-header")
            layout.addWidget(header)
            
            grid = GameGrid()
            layout.addWidget(grid)
            
            container_layout.addWidget(section)
            
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setProperty("class", "divider-line")
            container_layout.addWidget(line)
            
            return grid, section, line

        # Criar as 5 seções
        self.grid_now, self.sec_now, self.line_now = create_section("🕹️ Agora (Em Andamento)", "nowPlayingSection")
        self.grid_next, self.sec_next, self.line_next = create_section("⏭️ Próximos", "nextSection")
        self.grid_queue, self.sec_queue, self.line_queue = create_section("📋 Fila de Espera", "queueSection")
        self.grid_finished, self.sec_finished, self.line_finished = create_section("🏆 Zerados", "finishedSection")
        self.grid_platinum, self.sec_platinum, self.line_platinum = create_section("👑 Platinados", "platinumSection")

        # Conectar eventos
        self.grid_now.game_selected.connect(self.game_selected.emit)
        self.grid_next.game_selected.connect(self.game_selected.emit)
        self.grid_queue.game_selected.connect(self.game_selected.emit)
        self.grid_finished.game_selected.connect(self.game_selected.emit)
        self.grid_platinum.game_selected.connect(self.game_selected.emit)

        self.scroll.setWidget(container)
        main_layout.addWidget(self.scroll)

    def set_games(self, now_games: list, next_games: list, queue_games: list, finished_games: list, platinum_games: list):
        self.grid_now.set_games(now_games)
        self.sec_now.setVisible(bool(now_games))
        self.line_now.setVisible(bool(now_games))
        
        self.grid_next.set_games(next_games)
        self.sec_next.setVisible(bool(next_games))
        self.line_next.setVisible(bool(next_games))
        
        self.grid_queue.set_games(queue_games)
        self.sec_queue.setVisible(bool(queue_games))
        self.line_queue.setVisible(bool(queue_games))
        
        self.grid_finished.set_games(finished_games)
        self.sec_finished.setVisible(bool(finished_games))
        self.line_finished.setVisible(bool(finished_games))
        
        self.grid_platinum.set_games(platinum_games)
        self.sec_platinum.setVisible(bool(platinum_games))
        self.line_platinum.setVisible(bool(platinum_games))

    def on_scroll(self, value: int):
        scroll_bar = self.scroll.verticalScrollBar()
        if value >= scroll_bar.maximum() - 80:
            self.grid_queue.load_more_cards()
            self.grid_finished.load_more_cards()
            self.grid_platinum.load_more_cards()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.grid_now.relayout_cards()
        self.grid_next.relayout_cards()
        self.grid_queue.relayout_cards()
        self.grid_finished.relayout_cards()
        self.grid_platinum.relayout_cards()
