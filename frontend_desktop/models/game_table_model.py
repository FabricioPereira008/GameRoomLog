"""Model da tabela da biblioteca (dados em memória; ordenação e filtro via proxy)."""
from typing import Callable, List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor

from frontend_desktop.models.game_list_model import GameRole
from frontend_desktop.styles.tokens import COLORS

SortRole = Qt.UserRole + 2

COLUMNS = [
    "Jogo", "Status", "Gênero", "Plataforma", "Desenvolvedora",
    "Ano", "Nota", "Dific.", "HLTB", "Jogadas", "Tipo",
]
COLUMN_TOOLTIPS = {7: "Dificuldade", 8: "Duração estimada (HowLongToBeat)", 9: "Horas jogadas", 10: "Tipo de jogada"}
NUMERIC_COLUMNS = {5, 6, 7, 8, 9}

STATUS_COLORS = {
    "Jogando": COLORS["accent_text"], "Zerado": COLORS["success"], "Platinado": COLORS["warning"],
    "Desisti": COLORS["danger"],
}


def _hours(value) -> str:
    return f"{int(value)}h" if value else ""


def cell_text(game: dict, column: int) -> str:
    if column == 0:
        return game.get("title", "")
    if column == 1:
        return game.get("status", "")
    if column == 2:
        return ", ".join(g.get("name", "") for g in game.get("genres") or [])
    if column == 3:
        return (game.get("platform") or {}).get("name", "")
    if column == 4:
        return game.get("developer") or ""
    if column == 5:
        return str(game.get("completion_year") or "")
    if column == 6:
        return str(game.get("score") or "")
    if column == 7:
        return str(game.get("difficulty") or "")
    if column == 8:
        return _hours(game.get("hltb_hours"))
    if column == 9:
        return _hours(game.get("played_hours"))
    return game.get("play_type", "")


def sort_key(game: dict, column: int):
    if column == 5:
        return game.get("completion_year") or 0
    if column == 6:
        return game.get("score") or 0
    if column == 7:
        return game.get("difficulty") or 0
    if column == 8:
        return game.get("hltb_hours") or 0
    if column == 9:
        return game.get("played_hours") or 0
    return cell_text(game, column).lower()


class GameTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._games: List[dict] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._games)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return COLUMNS[section]
        if orientation == Qt.Horizontal and role == Qt.ToolTipRole:
            return COLUMN_TOOLTIPS.get(section, COLUMNS[section])
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        game = self._games[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            return cell_text(game, col)
        if role == GameRole:
            return game
        if role == SortRole:
            return sort_key(game, col)
        if role == Qt.TextAlignmentRole and col in NUMERIC_COLUMNS:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role == Qt.ForegroundRole and col == 1:
            color = STATUS_COLORS.get(game.get("status"))
            return QColor(color) if color else None
        return None

    @property
    def games(self) -> List[dict]:
        return list(self._games)

    def row_for_id(self, game_id) -> int:
        return next((r for r, g in enumerate(self._games) if g.get("id") == game_id), -1)

    def set_games(self, games: List[dict]) -> None:
        self.beginResetModel()
        self._games = list(games)
        self.endResetModel()

    def insert_game(self, game: dict, index: int = 0) -> None:
        self.beginInsertRows(QModelIndex(), index, index)
        self._games.insert(index, game)
        self.endInsertRows()

    def update_game(self, game: dict) -> bool:
        row = self.row_for_id(game.get("id"))
        if row < 0:
            return False
        self._games[row] = game
        self.dataChanged.emit(self.index(row, 0), self.index(row, len(COLUMNS) - 1))
        return True

    def remove_game(self, game_id) -> bool:
        row = self.row_for_id(game_id)
        if row < 0:
            return False
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._games[row]
        self.endRemoveRows()
        return True


class GameTableProxy(QSortFilterProxyModel):
    """Filtro (predicado) + ordenação numérica/textual pelas SortRole."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortRole(SortRole)
        self._predicate: Optional[Callable[[dict], bool]] = None

    def set_predicate(self, predicate: Optional[Callable[[dict], bool]]) -> None:
        if hasattr(self, "beginFilterChange"):
            self.beginFilterChange()
            self._predicate = predicate
            self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        else:
            self._predicate = predicate
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent) -> bool:
        if self._predicate is None:
            return True
        game = self.sourceModel().index(source_row, 0, source_parent).data(GameRole)
        return bool(game) and self._predicate(game)

    @property
    def games(self) -> List[dict]:
        return [self.index(r, 0).data(GameRole) for r in range(self.rowCount())]
