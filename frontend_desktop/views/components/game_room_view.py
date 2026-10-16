from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame, QLineEdit
)
from PySide6.QtCore import Signal, Qt, QTimer
from frontend_desktop.views.components.game_grid import GameGrid, MODE_BUTTON, FILTER_DEBOUNCE_MS, make_predicate
from frontend_desktop.views.components.filter_panel import FilterPanel
from frontend_desktop.ui_helpers import add_search_icon

class GameRoomView(QWidget):
    game_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gameRoomView")
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(FILTER_DEBOUNCE_MS)
        self._debounce.timeout.connect(self.apply_filter)

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        # Barra Superior: Pesquisa por Título + Botão de Filtro
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar jogos por título no Game Room...")
        add_search_icon(self.search_input)
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
        container_layout.setSpacing(12)

        # --- FUNÇÃO HELPER PARA CRIAR SEÇÕES ---
        def create_section(title, object_name):
            section = QFrame()
            section.setObjectName(object_name)
            section.setProperty("class", "game-section-card")
            section.setAttribute(Qt.WA_StyledBackground, True)
            layout = QVBoxLayout(section)
            layout.setContentsMargins(16, 14, 16, 16)
            layout.setSpacing(12)
            
            header = QLabel(title)
            header.setProperty("class", "section-header")
            layout.addWidget(header)
            
            # Altura limitada a algumas linhas, com botão "Mostrar mais"
            grid = GameGrid(mode=MODE_BUTTON)
            layout.addWidget(grid)
            
            container_layout.addWidget(section)
            
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setProperty("class", "divider-line")
            container_layout.addWidget(line)
            
            return grid, section, line

        # Criar as 5 seções
        self.grid_now, self.sec_now, self.line_now = create_section("Agora (em andamento)", "nowPlayingSection")
        self.grid_next, self.sec_next, self.line_next = create_section("Próximos", "nextSection")
        self.grid_queue, self.sec_queue, self.line_queue = create_section("Fila de espera", "queueSection")
        self.grid_finished, self.sec_finished, self.line_finished = create_section("Zerados", "finishedSection")
        self.grid_platinum, self.sec_platinum, self.line_platinum = create_section("Platinados", "platinumSection")

        # Conectar eventos
        self.grid_now.game_selected.connect(self.game_selected.emit)
        self.grid_next.game_selected.connect(self.game_selected.emit)
        self.grid_queue.game_selected.connect(self.game_selected.emit)
        self.grid_finished.game_selected.connect(self.game_selected.emit)
        self.grid_platinum.game_selected.connect(self.game_selected.emit)

        self.scroll.setWidget(container)
        main_layout.addWidget(self.scroll)

    def _sections(self):
        return [
            (self.grid_now, self.sec_now, self.line_now),
            (self.grid_next, self.sec_next, self.line_next),
            (self.grid_queue, self.sec_queue, self.line_queue),
            (self.grid_finished, self.sec_finished, self.line_finished),
            (self.grid_platinum, self.sec_platinum, self.line_platinum),
        ]

    def _sync_visibility(self):
        """Mostra apenas as seções que têm jogos após a busca/filtros."""
        for grid, sec, line in self._sections():
            has_games = grid.proxy.rowCount() > 0
            sec.setVisible(has_games)
            line.setVisible(has_games)

    def set_games(self, now_games: list, next_games: list, queue_games: list, finished_games: list, platinum_games: list):
        for (grid, _, _), games in zip(
            self._sections(), (now_games, next_games, queue_games, finished_games, platinum_games)
        ):
            grid.set_games(games)
        self.apply_filter()

    def set_filter_options(self, genres: list, developers: list, platforms: list, franchises: list):
        self.filter_panel.set_options(genres, developers, platforms, franchises)

    def on_search_changed(self, text: str):
        if self.search_input.hasFocus():
            self._debounce.start()
        else:
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
        self.apply_filter()

    def apply_filter(self):
        self._debounce.stop()
        predicate = make_predicate(self.search_input.text(), self.filter_panel.build_matcher())
        for grid, _, _ in self._sections():
            grid.set_predicate(predicate)
        self._sync_visibility()

    def update_game(self, game_data: dict) -> bool:
        """Atualiza o jogo in-place em qualquer seção em que ele esteja."""
        updated = False
        for grid, _, _ in self._sections():
            updated = grid.update_game(game_data) or updated
        return updated

    def remove_game(self, game_id: int) -> bool:
        """Remove o jogo in-place de todas as seções."""
        removed = False
        for grid, _, _ in self._sections():
            removed = grid.remove_game(game_id) or removed
        self._sync_visibility()
        return removed

    def insert_game_by_status(self, game_data: dict):
        """Insere o jogo no topo das seções correspondentes ao status (Platinado entra em duas)."""
        status = game_data.get("status")
        targets = []
        if status == "Jogando":
            targets.append(self.grid_now)
        elif status == "Próximo":
            targets.append(self.grid_next)
        elif status in ["Fila", "Pausado"]:
            targets.append(self.grid_queue)
        elif status in ["Zerado", "Platinado"]:
            targets.append(self.grid_finished)
            if status == "Platinado":
                targets.append(self.grid_platinum)
        for grid in targets:
            grid.insert_game(0, game_data)
        self._sync_visibility()
