"""Model/proxy de jogos: dados em memória, filtragem sem recriar widgets."""
from typing import Callable, List, Optional

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSortFilterProxyModel, Qt

from frontend_desktop.cover_loader import cover_loader
from frontend_desktop.data_quality import missing_fields
from frontend_desktop.text_search import fold
from frontend_desktop.views.game_status import display_hours, is_completed

GameRole = Qt.UserRole + 1


class GameListModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._games: List[dict] = []

    # --- leitura ---
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._games)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._games)):
            return None
        game = self._games[index.row()]
        if role == GameRole:
            return game
        if role == Qt.DisplayRole:
            return game.get("title") or ""
        if role == Qt.ToolTipRole:  # nome completo dos gêneros, que podem estar elididos no card
            genres = " · ".join(g["name"] for g in game.get("genres") or [] if g.get("name"))
            lines = [game.get("title") or ""] + ([genres] if genres else [])
            hours = display_hours(game)
            if hours:
                lines.append(f"{hours:g}h jogadas" if is_completed(game.get("status")) else f"{hours:g}h estimadas (HLTB)")
            missing = missing_fields(game)
            if missing:
                lines.append("Faltando: " + ", ".join(missing))
            return "\n".join(lines)
        return None

    @property
    def games(self) -> List[dict]:
        return list(self._games)

    def row_for_id(self, game_id) -> int:
        for row, game in enumerate(self._games):
            if game.get("id") == game_id:
                return row
        return -1

    # --- mutações in-place (respeitam a regra de não recarregar tudo) ---
    def set_games(self, games: List[dict]) -> None:
        self.beginResetModel()
        self._games = list(games)
        self.endResetModel()

    def insert_game(self, index: int, game: dict) -> None:
        index = max(0, min(index, len(self._games)))
        self.beginInsertRows(QModelIndex(), index, index)
        self._games.insert(index, game)
        self.endInsertRows()

    def update_game(self, game: dict) -> bool:
        row = self.row_for_id(game.get("id"))
        if row < 0:
            return False
        old_cover = self._games[row].get("cover_image")
        if old_cover != game.get("cover_image"):
            cover_loader.invalidate(old_cover)
            cover_loader.invalidate(game.get("cover_image"))
        self._games[row] = game
        idx = self.index(row)
        self.dataChanged.emit(idx, idx)
        return True

    def remove_game(self, game_id) -> bool:
        row = self.row_for_id(game_id)
        if row < 0:
            return False
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._games[row]
        self.endRemoveRows()
        return True


class GameFilterProxy(QSortFilterProxyModel):
    """Aplica um predicado (busca + painel de filtros) sobre o model."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._predicate: Optional[Callable[[dict], bool]] = None
        self._sort_key: Optional[Callable[[dict], object]] = None
        self._descending = False

    def set_sort(self, key: Optional[Callable[[dict], object]], descending: bool = False) -> None:
        """Ordena a exibição por `key(game)` (None volta à ordem original do model).

        Jogos em que `key` devolve None ficam sempre no fim, nas duas direções; empates saem por nome.
        A direção é aplicada aqui (o Qt ordena sempre "crescente") para não inverter esses dois casos.
        """
        self._sort_key = key
        self._descending = descending
        if key is None:
            self.sort(-1)
        else:
            self.invalidate()
            self.sort(0, Qt.AscendingOrder)

    def lessThan(self, left, right) -> bool:
        if self._sort_key is None:
            return left.row() < right.row()
        a, b = left.data(GameRole), right.data(GameRole)
        ka, kb = self._sort_key(a), self._sort_key(b)
        if (ka is None) != (kb is None):
            return kb is None  # quem tem valor vem antes
        if ka is not None and ka != kb:
            return ka > kb if self._descending else ka < kb
        ta, tb = fold(a.get("title")), fold(b.get("title"))
        if ta != tb:
            return ta < tb
        return left.row() < right.row()

    def set_predicate(self, predicate: Optional[Callable[[dict], bool]]) -> None:
        if hasattr(self, "beginFilterChange"):  # Qt >= 6.9 (invalidateFilter foi descontinuado)
            self.beginFilterChange()
            self._predicate = predicate
            self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        else:
            self._predicate = predicate
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        if self._predicate is None:
            return True
        game = self.sourceModel().index(source_row, 0, source_parent).data(GameRole)
        return bool(game) and self._predicate(game)

    @property
    def games(self) -> List[dict]:
        """Jogos que passam no filtro, na ordem exibida."""
        return [self.index(r, 0).data(GameRole) for r in range(self.rowCount())]
