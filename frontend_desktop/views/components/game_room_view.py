from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame
)
from PySide6.QtCore import Signal, Qt
from frontend_desktop.views.components.game_grid import GameGrid

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
            
            # Grid configurado no modo 'button' para ter lote inicial de 14 e botão '+' exclusivo
            grid = GameGrid(mode="button", initial_batch=14)
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

    def update_game(self, game_data: dict) -> bool:
        """Atualiza o jogo in-place em qualquer seção que ele estiver."""
        updated = False
        for grid in [self.grid_now, self.grid_next, self.grid_queue, self.grid_finished, self.grid_platinum]:
            if grid.update_game(game_data):
                updated = True
        return updated

    def remove_game(self, game_id: int) -> bool:
        """Remove o jogo in-place de todas as seções."""
        removed = False
        for grid, sec, line in [
            (self.grid_now, self.sec_now, self.line_now),
            (self.grid_next, self.sec_next, self.line_next),
            (self.grid_queue, self.sec_queue, self.line_queue),
            (self.grid_finished, self.sec_finished, self.line_finished),
            (self.grid_platinum, self.sec_platinum, self.line_platinum),
        ]:
            if grid.remove_game(game_id):
                removed = True
                sec.setVisible(bool(grid.games))
                line.setVisible(bool(grid.games))
        return removed

    def insert_game_by_status(self, game_data: dict):
        status = game_data.get("status")
        if status == "Jogando":
            self.grid_now.insert_game(0, game_data)
            self.sec_now.setVisible(True)
            self.line_now.setVisible(True)
        elif status == "Próximo":
            self.grid_next.insert_game(0, game_data)
            self.sec_next.setVisible(True)
            self.line_next.setVisible(True)
        elif status in ["Fila", "Pausado"]:
            self.grid_queue.insert_game(0, game_data)
            self.sec_queue.setVisible(True)
            self.line_queue.setVisible(True)
        elif status in ["Zerado", "Platinado"]:
            self.grid_finished.insert_game(0, game_data)
            self.sec_finished.setVisible(True)
            self.line_finished.setVisible(True)
            if status == "Platinado":
                self.grid_platinum.insert_game(0, game_data)
                self.sec_platinum.setVisible(True)
                self.line_platinum.setVisible(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.grid_now.relayout_cards()
        self.grid_next.relayout_cards()
        self.grid_queue.relayout_cards()
        self.grid_finished.relayout_cards()
        self.grid_platinum.relayout_cards()
