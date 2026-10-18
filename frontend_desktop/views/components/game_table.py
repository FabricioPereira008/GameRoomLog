from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QTableView, QVBoxLayout, QWidget
)

from frontend_desktop import preferences
from frontend_desktop.models.game_list_model import GameRole
from frontend_desktop.models.game_table_model import COLUMN_TOOLTIPS, COLUMNS, GameTableModel, GameTableProxy
from frontend_desktop.ui_helpers import add_search_icon
from frontend_desktop.views import game_status as gs

# A coluna 0 (título) ocupa o espaço que sobrar; as demais têm largura inicial ajustável
COLUMN_WIDTHS = {1: 92, 2: 180, 3: 92, 4: 150, 5: 60, 6: 52, 7: 60, 8: 62, 9: 72, 10: 120}
HIDDEN_COLUMNS_KEY = "table_hidden_columns"
DEFAULT_HIDDEN_COLUMNS = {10}  # "Tipo"


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
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setMinimumSectionSize(44)
        header.setSortIndicatorShown(True)
        # Clique direito no cabeçalho: mostrar/esconder colunas (lembrado entre sessões)
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self.show_columns_menu)
        for col in self.hidden_columns():
            self.table.setColumnHidden(col, True)

        self.table.doubleClicked.connect(self.on_row_activated)
        self.table.activated.connect(self.on_row_activated)
        layout.addWidget(self.table)

    # --- colunas ---
    @staticmethod
    def hidden_columns() -> set:
        raw = preferences.settings().value(HIDDEN_COLUMNS_KEY, None)
        if raw is None:
            return set(DEFAULT_HIDDEN_COLUMNS)
        if isinstance(raw, str):
            raw = [raw] if raw else []
        return {int(c) for c in raw if str(c).isdigit() and 0 < int(c) < len(COLUMNS)}

    def set_column_visible(self, column: int, visible: bool) -> None:
        if column == 0:
            return  # o título sempre aparece
        self.table.setColumnHidden(column, not visible)
        hidden = sorted(c for c in range(1, len(COLUMNS)) if self.table.isColumnHidden(c))
        preferences.settings().setValue(HIDDEN_COLUMNS_KEY, [str(c) for c in hidden] or "")

    def build_columns_menu(self) -> QMenu:
        menu = QMenu(self)
        for col, name in enumerate(COLUMNS):
            if col == 0:
                continue
            action = menu.addAction(COLUMN_TOOLTIPS.get(col, name))
            action.setCheckable(True)
            action.setChecked(not self.table.isColumnHidden(col))
            action.toggled.connect(lambda checked, c=col: self.set_column_visible(c, checked))
        return menu

    def show_columns_menu(self, pos) -> None:
        self.build_columns_menu().exec(self.table.horizontalHeader().mapToGlobal(pos))

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
