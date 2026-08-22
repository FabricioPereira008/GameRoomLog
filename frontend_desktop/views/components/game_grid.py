from PySide6.QtWidgets import (
    QWidget, QScrollArea, QGridLayout, QVBoxLayout, QLabel, QSizePolicy
)
from PySide6.QtCore import Signal, Qt, QSettings
from frontend_desktop.views.components.game_card import GameCard, LoadMoreCard

class GameGrid(QWidget):
    """Grid adaptativa e de alta performance com colunas dinâmicas e carregamento sob demanda."""
    game_selected = Signal(dict)

    def __init__(self, mode: str = "infinite", initial_batch: int = 35, parent=None):
        super().__init__(parent)
        self.mode = mode  # "infinite" ou "button"
        self.initial_batch = initial_batch if mode == "infinite" else 14
        self.batch_size = 35 if mode == "infinite" else 14
        
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
        self.load_more_btn = None
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
        self.games = list(games)
        self.rendered_count = 0
        self.cards = []
        self.load_more_btn = None
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
        if self.rendered_count >= total and not self.load_more_btn:
            return

        cols = self.current_cols
        
        # Remove o botão "Carregar Mais" temporariamente se ele já existir no layout
        if self.load_more_btn is not None:
            self.grid_layout.removeWidget(self.load_more_btn)
            self.load_more_btn.deleteLater()
            self.load_more_btn = None

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

        # Se for modo "button" e ainda houver itens restantes, adiciona o botão '+' no final
        if self.mode == "button" and self.rendered_count < total:
            self.load_more_btn = LoadMoreCard()
            self.load_more_btn.clicked.connect(self.load_more_cards)
            btn_idx = self.rendered_count
            row = btn_idx // cols
            col = btn_idx % cols
            self.grid_layout.addWidget(self.load_more_btn, row, col)

        self.setUpdatesEnabled(True)

    def relayout_cards(self):
        """Re-posiciona os cards existentes e botão de carregar mais quando a largura da tela muda."""
        if not self.cards and not self.load_more_btn:
            return

        new_cols = self.calculate_cols()
        if new_cols == self.current_cols:
            return

        self.current_cols = new_cols
        self.setUpdatesEnabled(False)

        # Remove todos da grid sem deletar os widgets
        while self.grid_layout.count():
            self.grid_layout.takeAt(0)

        # Reinsere os cards de jogos nas novas posições (row, col)
        for idx, card in enumerate(self.cards):
            row = idx // self.current_cols
            col = idx % self.current_cols
            self.grid_layout.addWidget(card, row, col)

        # Reinsere o botão de carregar mais se existir
        if self.load_more_btn is not None:
            btn_idx = len(self.cards)
            row = btn_idx // self.current_cols
            col = btn_idx % self.current_cols
            self.grid_layout.addWidget(self.load_more_btn, row, col)

        self.setUpdatesEnabled(True)

    def update_game(self, game_data: dict) -> bool:
        """Atualiza um jogo in-place sem recarregar todo o grid."""
        game_id = game_data.get("id")
        updated = False
        for idx, g in enumerate(self.games):
            if g.get("id") == game_id:
                self.games[idx] = game_data
                updated = True
                break

        for card in self.cards:
            if card.game_data.get("id") == game_id:
                card.update_data(game_data)
                return True
        return updated

    def remove_game(self, game_id: int) -> bool:
        """Remove um jogo in-place do grid."""
        removed = False
        self.games = [g for g in self.games if g.get("id") != game_id]

        target_card = None
        for card in self.cards:
            if card.game_data.get("id") == game_id:
                target_card = card
                break

        if target_card:
            self.cards.remove(target_card)
            self.grid_layout.removeWidget(target_card)
            target_card.deleteLater()
            self.rendered_count = len(self.cards)
            
            # Reorganiza o grid
            self.current_cols = self.calculate_cols()
            self.relayout_cards()
            removed = True

        return removed

    def insert_game(self, index: int, game_data: dict):
        """Insere um novo jogo in-place no grid."""
        self.games.insert(index, game_data)
        
        card = GameCard(game_data)
        card.clicked.connect(self.on_card_clicked)
        self.cards.insert(index, card)
        self.rendered_count = len(self.cards)

        self.current_cols = self.calculate_cols()
        
        # Limpa e repõe
        while self.grid_layout.count():
            self.grid_layout.takeAt(0)

        for idx, c in enumerate(self.cards):
            row = idx // self.current_cols
            col = idx % self.current_cols
            self.grid_layout.addWidget(c, row, col)

        if self.load_more_btn is not None:
            btn_idx = len(self.cards)
            row = btn_idx // self.current_cols
            col = btn_idx % self.current_cols
            self.grid_layout.addWidget(self.load_more_btn, row, col)

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

        self.grid = GameGrid(mode="infinite")
        self.grid.game_selected.connect(self.game_selected.emit)
        self.setWidget(self.grid)

        self.verticalScrollBar().valueChanged.connect(self.on_scroll)

    def set_games(self, games: list):
        self.grid.set_games(games)

    def update_game(self, game_data: dict):
        return self.grid.update_game(game_data)

    def remove_game(self, game_id: int):
        return self.grid.remove_game(game_id)

    def insert_game(self, index: int, game_data: dict):
        self.grid.insert_game(index, game_data)

    def on_scroll(self, value: int):
        scroll_bar = self.verticalScrollBar()
        # Carregamento antecipado (quando atingir 75% ou faltar 350px para o final)
        if value >= scroll_bar.maximum() * 0.75 or value >= scroll_bar.maximum() - 350:
            self.grid.load_more_cards()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.grid.relayout_cards()
