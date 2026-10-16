from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QTableView, QVBoxLayout, QWidget
)

from frontend_desktop.models.game_list_model import GameRole
from frontend_desktop.models.game_table_model import GameTableModel, GameTableProxy
from frontend_desktop.ui_helpers import add_search_icon
from frontend_desktop.views import game_status as gs

COLUMN_WIDTHS = {0: 300, 1: 100, 2: 130, 3: 110, 4: 150, 5: 60, 6: 65, 7: 90, 8: 95, 9: 105, 10: 120}


class GameTable(QWidget):
    """Biblioteca em tabela virtualizada (QTableView), ordenável por coluna."""
    game_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = GameTableModel(self)
        self.proxy = GameTableProxy(self)
        self.proxy.setSourceModel(self.model)
        self.init_ui()
        self.proxy.rowsInserted.connect(self.update_count_label)
        self.proxy.rowsRemoved.connect(self.update_count_label)
        self.proxy.modelReset.connect(self.update_count_label)
        self.proxy.layoutChanged.connect(self.update_count_label)

    # compat com a API anterior
    @property
    def games(self) -> list:
        return self.model.games

    @property
    def filtered_games(self) -> list:
        return self.proxy.games

    @property
    def rendered_count(self) -> int:
        return self.proxy.rowCount()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filtrar por nome ou desenvolvedora...")
        add_search_icon(self.search_input)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setProperty("class", "search-input")
        self.search_input.textChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.search_input)

        self.status_filter = QComboBox()
        self.status_filter.addItem("Todos os status", None)
        for status in gs.ALL_STATUSES:
            self.status_filter.addItem(status, status)
        self.status_filter.currentIndexChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.status_filter)

        self.count_label = QLabel("0 jogos")
        self.count_label.setProperty("class", "card-meta")
        filter_layout.addWidget(self.count_label)
        layout.addLayout(filter_layout)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setCursor(Qt.PointingHandCursor)

        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setStretchLastSection(False)
        for col in range(self.model.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
            self.table.setColumnWidth(col, COLUMN_WIDTHS.get(col, 100))
        header.setSortIndicatorShown(True)

        self.table.doubleClicked.connect(self.on_row_activated)
        self.table.activated.connect(self.on_row_activated)
        layout.addWidget(self.table)

    # --- dados ---
    def set_games(self, games: list):
        self.model.set_games(games)
        self.apply_filter()

    def insert_game(self, game_data: dict):
        self.model.insert_game(game_data, 0)

    def update_game(self, game_data: dict) -> bool:
        return self.model.update_game(game_data)

    def remove_game(self, game_id: int) -> bool:
        return self.model.remove_game(game_id)

    # --- filtro ---
    def apply_filter(self, *_):
        text = self.search_input.text().lower().strip()
        status = self.status_filter.currentData()

        def predicate(game: dict) -> bool:
            if status and game.get("status") != status:
                return False
            if text:
                return text in (game.get("title") or "").lower() or text in (game.get("developer") or "").lower()
            return True

        self.proxy.set_predicate(predicate)
        self.update_count_label()

    def update_count_label(self, *_):
        total = self.proxy.rowCount()
        self.count_label.setText(f"{total} {'jogo' if total == 1 else 'jogos'}")

    def on_row_activated(self, index: QModelIndex):
        game = index.sibling(index.row(), 0).data(GameRole)
        if game:
            self.game_selected.emit(game)
