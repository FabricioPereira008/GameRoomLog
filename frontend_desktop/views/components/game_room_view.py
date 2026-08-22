from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame, QLineEdit
)
from PySide6.QtCore import Signal, Qt
from frontend_desktop.views.components.game_grid import GameGrid
from frontend_desktop.views.components.filter_panel import FilterPanel

class GameRoomView(QWidget):
    game_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gameRoomView")
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        self.all_now_games = []
        self.all_next_games = []
        self.all_queue_games = []
        self.all_finished_games = []
        self.all_platinum_games = []
        
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Barra Superior: Pesquisa por Título + Botão de Filtro
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Buscar jogos por título no Game Room...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setProperty("class", "search-input")
        self.search_input.textChanged.connect(self.on_search_changed)
        top_bar_layout.addWidget(self.search_input)

        self.filter_panel = FilterPanel()
        self.filter_panel.filters_changed.connect(self.apply_filter)
        top_bar_layout.addWidget(self.filter_panel.btn_toggle)

        main_layout.addLayout(top_bar_layout)
        main_layout.addWidget(self.filter_panel)

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
        self.all_now_games = list(now_games)
        self.all_next_games = list(next_games)
        self.all_queue_games = list(queue_games)
        self.all_finished_games = list(finished_games)
        self.all_platinum_games = list(platinum_games)
        self.apply_filter()

    def set_filter_options(self, genres: list, developers: list, platforms: list, franchises: list):
        self.filter_panel.set_options(genres, developers, platforms, franchises)

    def on_search_changed(self, text: str):
        self.apply_filter()

    def clear_search(self):
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self.apply_filter()

    def clear_filters(self):
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self.filter_panel.clear_filters()


    def apply_filter(self):
        query = self.search_input.text().strip().lower()

        def filter_list(lst):
            filtered = []
            for g in lst:
                if query and query not in (g.get("title") or "").lower():
                    continue
                if not self.filter_panel.matches(g):
                    continue
                filtered.append(g)
            return filtered

        now_f = filter_list(self.all_now_games)
        next_f = filter_list(self.all_next_games)
        queue_f = filter_list(self.all_queue_games)
        finished_f = filter_list(self.all_finished_games)
        platinum_f = filter_list(self.all_platinum_games)

        self.grid_now.set_games(now_f)
        self.sec_now.setVisible(bool(now_f))
        self.line_now.setVisible(bool(now_f))
        
        self.grid_next.set_games(next_f)
        self.sec_next.setVisible(bool(next_f))
        self.line_next.setVisible(bool(next_f))
        
        self.grid_queue.set_games(queue_f)
        self.sec_queue.setVisible(bool(queue_f))
        self.line_queue.setVisible(bool(queue_f))
        
        self.grid_finished.set_games(finished_f)
        self.sec_finished.setVisible(bool(finished_f))
        self.line_finished.setVisible(bool(finished_f))
        
        self.grid_platinum.set_games(platinum_f)
        self.sec_platinum.setVisible(bool(platinum_f))
        self.line_platinum.setVisible(bool(platinum_f))

    def update_game(self, game_data: dict) -> bool:
        """Atualiza o jogo in-place em qualquer seção que ele estiver."""
        game_id = game_data.get("id")
        for lst in [self.all_now_games, self.all_next_games, self.all_queue_games, self.all_finished_games, self.all_platinum_games]:
            for idx, g in enumerate(lst):
                if g.get("id") == game_id:
                    lst[idx] = game_data
                    break

        updated = False
        for grid in [self.grid_now, self.grid_next, self.grid_queue, self.grid_finished, self.grid_platinum]:
            if grid.update_game(game_data):
                updated = True
        return updated

    def remove_game(self, game_id: int) -> bool:
        """Remove o jogo in-place de todas as seções."""
        self.all_now_games = [g for g in self.all_now_games if g.get("id") != game_id]
        self.all_next_games = [g for g in self.all_next_games if g.get("id") != game_id]
        self.all_queue_games = [g for g in self.all_queue_games if g.get("id") != game_id]
        self.all_finished_games = [g for g in self.all_finished_games if g.get("id") != game_id]
        self.all_platinum_games = [g for g in self.all_platinum_games if g.get("id") != game_id]

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
        query = self.search_input.text().strip().lower()
        matches_query = (not query or query in (game_data.get("title") or "").lower()) and self.filter_panel.matches(game_data)

        if status == "Jogando":
            self.all_now_games.insert(0, game_data)
            if matches_query:
                self.grid_now.insert_game(0, game_data)
                self.sec_now.setVisible(True)
                self.line_now.setVisible(True)
        elif status == "Próximo":
            self.all_next_games.insert(0, game_data)
            if matches_query:
                self.grid_next.insert_game(0, game_data)
                self.sec_next.setVisible(True)
                self.line_next.setVisible(True)
        elif status in ["Fila", "Pausado"]:
            self.all_queue_games.insert(0, game_data)
            if matches_query:
                self.grid_queue.insert_game(0, game_data)
                self.sec_queue.setVisible(True)
                self.line_queue.setVisible(True)
        elif status in ["Zerado", "Platinado"]:
            self.all_finished_games.insert(0, game_data)
            if matches_query:
                self.grid_finished.insert_game(0, game_data)
                self.sec_finished.setVisible(True)
                self.line_finished.setVisible(True)
            if status == "Platinado":
                self.all_platinum_games.insert(0, game_data)
                if matches_query:
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
