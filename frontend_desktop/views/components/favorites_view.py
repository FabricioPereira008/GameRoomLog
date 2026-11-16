"""Página Favoritos: rankings pessoais ordenados (Top 10 de todos os tempos, Top Soulslike...) e todos os favoritos."""
import logging
from typing import Callable, Dict, List, Optional

import requests
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QScrollArea, QToolButton, QVBoxLayout, QWidget,
)

from frontend_desktop import icons
from frontend_desktop.api_client.client import api_client
from frontend_desktop.cover_loader import cover_loader
from frontend_desktop.rankings import entry_ids, filter_text
from frontend_desktop.styles.tokens import COLORS
from frontend_desktop.ui_helpers import set_button_icon
from frontend_desktop.views.components.game_card_delegate import placeholder_pixmap
from frontend_desktop.views.components.game_grid import MODE_FULL, GameGrid
from frontend_desktop.views.components.yearbook_view import RANK_COLORS, hours_text
from frontend_desktop.views.dialogs.ranking_dialog import RankingDialog
from frontend_desktop.views.dialogs.ranking_picker_dialog import RankingPickerDialog
from frontend_desktop.workers import run_async

logger = logging.getLogger(__name__)

ROW_HEIGHT = 78
COVER_W, COVER_H = 44, 66


def with_detail(func: Callable) -> Callable:
    """Erro HTTP da API vira uma mensagem legível (o `detail` do backend, ex.: nome já usado)."""
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.HTTPError as exc:
            try:
                detail = exc.response.json().get("detail")
            except Exception:
                detail = None
            if isinstance(detail, str):
                raise RuntimeError(detail) from exc
            raise
    return wrapped


def sort_favorites(games: List[dict]) -> List[dict]:
    """Favoritos (sem rejogadas, para cada jogo aparecer uma vez) por nota e título."""
    favs = [g for g in games if g.get("is_favorite") and not g.get("replay_of_id")]
    return sorted(favs, key=lambda g: (g.get("score") is None, -(g.get("score") or 0), (g.get("title") or "").casefold()))


class RankingEntryRow(QFrame):
    """Uma posição do ranking: número, capa, título, nota/horas e ações (subir, descer, remover)."""
    open_requested = Signal(dict)
    move_requested = Signal(int, int)   # game_id, -1 sobe / +1 desce
    remove_requested = Signal(int)

    def __init__(self, position: int, game: dict, total: int, out_of_filter: bool = False, parent=None):
        super().__init__(parent)
        self.game = game
        self.position = position
        self.setProperty("class", "ranking-row")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(ROW_HEIGHT - 6)
        self.setCursor(Qt.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(12)

        self.rank = QLabel(f"{position}º")
        self.rank.setAlignment(Qt.AlignCenter)
        self.rank.setFixedSize(40, 40)
        if position <= len(RANK_COLORS):
            self.rank.setStyleSheet(f"color: #0b0c10; background-color: {RANK_COLORS[position - 1]};"
                                    " border-radius: 20px; font-weight: 800; font-size: 15px;")
        else:
            self.rank.setStyleSheet(f"color: {COLORS['text']}; background-color: {COLORS['surface_3']};"
                                    " border-radius: 20px; font-weight: 700; font-size: 14px;")
        layout.addWidget(self.rank)

        self.cover = QLabel()
        self.cover.setFixedSize(COVER_W, COVER_H)
        layout.addWidget(self.cover)

        text = QVBoxLayout()
        text.setSpacing(2)
        self.title = QLabel(game.get("title") or "Sem título")
        self.title.setProperty("class", "podium-title")
        text.addWidget(self.title)
        score = game.get("score")
        meta = ([f"Nota {score:g}"] if score is not None else []) + \
            [hours_text(game.get("played_hours") or game.get("hltb_hours"))]
        if game.get("platform"):
            meta.append(game["platform"].get("name", ""))
        self.meta = QLabel(" · ".join(m for m in meta if m))
        self.meta.setProperty("class", "status-muted")
        text.addWidget(self.meta)
        self.warning = QLabel("Não casa mais com o filtro do ranking")
        self.warning.setStyleSheet(f"color: {COLORS['warning']};")
        self.warning.setVisible(out_of_filter)
        text.addWidget(self.warning)
        layout.addLayout(text, 1)

        self.btn_up = self._tool("chevron-up", "Subir uma posição", lambda: self.move_requested.emit(game["id"], -1))
        self.btn_up.setEnabled(position > 1)
        self.btn_down = self._tool("chevron-down", "Descer uma posição", lambda: self.move_requested.emit(game["id"], 1))
        self.btn_down.setEnabled(position < total)
        self.btn_remove = self._tool("x", "Tirar do ranking", lambda: self.remove_requested.emit(game["id"]))
        for button in (self.btn_up, self.btn_down, self.btn_remove):
            layout.addWidget(button)

        self._update_cover()
        cover_loader.loaded.connect(self._on_cover_loaded)

    def _tool(self, icon: str, tip: str, slot) -> QToolButton:
        button = QToolButton()
        button.setIcon(icons.icon(icon, COLORS["text_muted"], 16))
        button.setToolTip(tip)
        button.setCursor(Qt.PointingHandCursor)
        button.setAutoRaise(True)
        button.clicked.connect(slot)
        return button

    def _update_cover(self):
        filename = self.game.get("cover_image")
        pixmap = cover_loader.request(filename, COVER_W, COVER_H) if filename else None
        self.cover.setPixmap(pixmap or placeholder_pixmap(COVER_W, COVER_H))

    def _on_cover_loaded(self, filename: str):
        if filename == self.game.get("cover_image"):
            self._update_cover()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.open_requested.emit(self.game)
        super().mouseDoubleClickEvent(event)


class FavoritesView(QWidget):
    game_selected = Signal(dict)
    rankings_changed = Signal()

    def __init__(self, games_provider: Callable[[], List[dict]] = lambda: [], parent=None):
        super().__init__(parent)
        self.games_provider = games_provider
        self.rankings: List[dict] = []
        self.current_id: Optional[int] = None
        self.options: Dict[str, List[dict]] = {"genre": [], "franchise": [], "platform": []}
        self._load_seq = 0
        self.init_ui()

    # --- montagem ---
    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName("favoritesScrollContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 10, 12, 16)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignTop)

        # 1. Rankings
        section = self._section("Meus rankings")
        body = QHBoxLayout()
        body.setSpacing(16)

        side = QVBoxLayout()
        side.setSpacing(8)
        self.ranking_list = QListWidget()
        self.ranking_list.setProperty("class", "ranking-nav")
        self.ranking_list.setFixedWidth(240)
        self.ranking_list.setMinimumHeight(260)
        self.ranking_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.ranking_list.setToolTip("Arraste para reordenar os rankings")
        self.ranking_list.currentItemChanged.connect(self._on_ranking_clicked)
        self.ranking_list.model().rowsMoved.connect(lambda *_: QTimer.singleShot(0, self._save_ranking_order))
        side.addWidget(self.ranking_list, 1)
        self.btn_new = QPushButton("Novo ranking")
        self.btn_new.setProperty("class", "action-btn")
        self.btn_new.setCursor(Qt.PointingHandCursor)
        set_button_icon(self.btn_new, "plus", COLORS["text"])
        self.btn_new.clicked.connect(self.create_ranking)
        side.addWidget(self.btn_new)
        body.addLayout(side)

        detail = QVBoxLayout()
        detail.setSpacing(10)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.ranking_title = QLabel("")
        self.ranking_title.setProperty("class", "section-header")
        titles.addWidget(self.ranking_title)
        self.ranking_meta = QLabel("")
        self.ranking_meta.setProperty("class", "status-muted")
        titles.addWidget(self.ranking_meta)
        head.addLayout(titles)
        head.addStretch()
        self.btn_add = self._small_button("Adicionar jogos", "plus", self.add_games)
        self.btn_edit = self._small_button("Editar", "pencil", self.edit_ranking)
        self.btn_delete = self._small_button("Excluir", "trash-2", self.delete_ranking)
        for button in (self.btn_add, self.btn_edit, self.btn_delete):
            head.addWidget(button)
        detail.addLayout(head)

        self.entry_list = QListWidget()
        self.entry_list.setProperty("class", "ranking-list")
        self.entry_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.entry_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.entry_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.entry_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.entry_list.setToolTip("Arraste para mudar a posição; duplo clique abre o jogo")
        self.entry_list.model().rowsMoved.connect(lambda *_: QTimer.singleShot(0, self._save_dragged_order))
        detail.addWidget(self.entry_list)

        self.entries_empty = QLabel("")
        self.entries_empty.setProperty("class", "empty-state-text")
        self.entries_empty.setAlignment(Qt.AlignCenter)
        self.entries_empty.setWordWrap(True)
        detail.addWidget(self.entries_empty)
        detail.addStretch()
        body.addLayout(detail, 1)
        section.body.addLayout(body)
        layout.addWidget(section)

        # 2. Todos os favoritos
        favs = self._section("Todos os favoritos")
        self.favorites_count = QLabel("")
        self.favorites_count.setProperty("class", "section-count")
        favs.header.addWidget(self.favorites_count)
        favs.header.addStretch()
        self.favorites_grid = GameGrid(mode=MODE_FULL)
        self.favorites_grid.empty_label.setText("Nenhum favorito ainda. Marque com o coração no jogo, "
                                                "no clique direito de uma capa ou com Ctrl+D.")
        self.favorites_grid.game_selected.connect(self.game_selected.emit)
        favs.body.addWidget(self.favorites_grid)
        layout.addWidget(favs)

        scroll.setWidget(container)
        outer.addWidget(scroll)
        self._show_current()

    @staticmethod
    def _section(title: str) -> QFrame:
        frame = QFrame()
        frame.setProperty("class", "game-section-card")
        frame.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)
        frame.header = QHBoxLayout()
        frame.title = QLabel(title)
        frame.title.setProperty("class", "section-header")
        frame.header.addWidget(frame.title)
        layout.addLayout(frame.header)
        frame.body = QVBoxLayout()
        frame.body.setSpacing(10)
        layout.addLayout(frame.body)
        return frame

    @staticmethod
    def _small_button(text: str, icon: str, slot) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("class", "small-btn")
        button.setCursor(Qt.PointingHandCursor)
        set_button_icon(button, icon)
        button.clicked.connect(slot)
        return button

    # --- dados ---
    def set_filter_options(self, genres: list, developers: list, platforms: list, franchises: list) -> None:
        self.options = {"genre": list(genres or []), "franchise": list(franchises or []),
                        "platform": list(platforms or [])}

    @property
    def current(self) -> Optional[dict]:
        return next((r for r in self.rankings if r["id"] == self.current_id), None)

    def load_data(self):
        self.refresh_favorites()
        self._load_seq += 1
        seq = self._load_seq
        run_async(self, api_client.get_rankings, lambda data: self._on_rankings_loaded(seq, data),
                  lambda msg: logger.warning("Falha ao carregar rankings: %s", msg))

    def _on_rankings_loaded(self, seq: int, rankings: list) -> None:
        if seq != self._load_seq:
            return  # resposta antiga
        self.set_rankings(rankings)

    def set_rankings(self, rankings: list, select_id: Optional[int] = None) -> None:
        self.rankings = list(rankings)
        ids = [r["id"] for r in self.rankings]
        if select_id is not None:
            self.current_id = select_id
        if self.current_id not in ids:
            self.current_id = ids[0] if ids else None
        # só o widget é silenciado (currentItemChanged); o model precisa avisar a view das linhas novas
        self.ranking_list.blockSignals(True)
        self.ranking_list.clear()
        for ranking in self.rankings:
            filled = len(ranking.get("entries") or [])
            item = QListWidgetItem(f"{ranking['name']}  ({filled}/{ranking['max_size']})")
            item.setData(Qt.UserRole, ranking["id"])
            item.setToolTip(filter_text(ranking) or "Sem filtro")
            self.ranking_list.addItem(item)
            if ranking["id"] == self.current_id:
                self.ranking_list.setCurrentItem(item)
        self.ranking_list.blockSignals(False)
        self._show_current()

    def _replace_ranking(self, ranking: dict) -> None:
        """Atualiza um ranking vindo da API (resposta de salvar) sem recarregar todos."""
        rankings = [ranking if r["id"] == ranking["id"] else r for r in self.rankings]
        if all(r["id"] != ranking["id"] for r in rankings):
            rankings.append(ranking)
        self.set_rankings(rankings, select_id=ranking["id"])
        self.rankings_changed.emit()

    def _on_ranking_clicked(self, item: Optional[QListWidgetItem], _previous=None) -> None:
        if item is not None:
            self.current_id = item.data(Qt.UserRole)
            self._show_current()

    def _show_current(self) -> None:
        ranking = self.current
        has = ranking is not None
        for button in (self.btn_add, self.btn_edit, self.btn_delete):
            button.setVisible(has)
        self.entry_list.clear()
        if not has:
            self.ranking_title.setText("Nenhum ranking ainda")
            self.ranking_meta.setText("")
            self.entries_empty.setText("Crie um ranking como \"Top 10 de todos os tempos\" ou \"Top Soulslike\" "
                                       "e escolha os jogos na ordem que você quiser.")
            self.entries_empty.setVisible(True)
            self.entry_list.setVisible(False)
            return
        entries = ranking.get("entries") or []
        self.ranking_title.setText(ranking["name"])
        self.ranking_meta.setText(" · ".join(filter(None, [
            filter_text(ranking) or "Sem filtro", f"{len(entries)}/{ranking['max_size']} posições"])))
        self.btn_add.setEnabled(len(entries) < ranking["max_size"])
        self.btn_add.setToolTip("" if self.btn_add.isEnabled() else "O ranking está completo")
        out = set(ranking.get("out_of_filter_ids") or [])
        for position, game in enumerate(entries, 1):
            row = RankingEntryRow(position, game, len(entries), game["id"] in out)
            row.open_requested.connect(self.game_selected.emit)
            row.move_requested.connect(self.move_entry)
            row.remove_requested.connect(self.remove_entry)
            item = QListWidgetItem()
            item.setData(Qt.UserRole, game["id"])
            item.setSizeHint(QSize(0, ROW_HEIGHT))
            self.entry_list.addItem(item)
            self.entry_list.setItemWidget(item, row)
        self.entry_list.setFixedHeight(len(entries) * ROW_HEIGHT + 6)
        self.entry_list.setVisible(bool(entries))
        self.entries_empty.setText("Nenhum jogo neste ranking. Use \"Adicionar jogos\".")
        self.entries_empty.setVisible(not entries)

    def refresh_favorites(self) -> None:
        favorites = sort_favorites(self.games_provider())
        self.favorites_grid.set_games(favorites)
        self.favorites_count.setText(str(len(favorites)))

    # --- mutações vindas de fora (edição/exclusão de jogo) ---
    def apply_game(self, game: dict) -> None:
        """Jogo salvo em outro lugar: atualiza a grade de favoritos e as linhas dos rankings in-place."""
        favorite = bool(game.get("is_favorite")) and not game.get("replay_of_id")
        if favorite:
            if not self.favorites_grid.update_game(game):
                self.favorites_grid.insert_game(0, game)
        else:
            self.favorites_grid.remove_game(game.get("id"))
        self.favorites_count.setText(str(len(self.favorites_grid.games)))
        touched = False
        for ranking in self.rankings:
            entries = ranking.get("entries") or []
            for i, entry in enumerate(entries):
                if entry.get("id") == game.get("id"):
                    entries[i] = game
                    touched = True
        if touched:
            self._show_current()

    def remove_game(self, game_id: int) -> None:
        self.favorites_grid.remove_game(game_id)
        self.favorites_count.setText(str(len(self.favorites_grid.games)))
        if any(game_id in entry_ids(r) for r in self.rankings):
            self.load_data()  # o servidor renumerou as posições

    # --- ações ---
    def _error(self, msg: str) -> None:
        QMessageBox.critical(self, "Rankings", f"Não foi possível salvar: {msg}")
        self.load_data()

    def create_ranking(self) -> None:
        dialog = RankingDialog(self.options, parent=self)
        if dialog.exec() and dialog.payload:
            run_async(self, with_detail(api_client.create_ranking), self._replace_ranking, self._error,
                      dialog.payload)

    def edit_ranking(self) -> None:
        ranking = self.current
        if ranking is None:
            return
        dialog = RankingDialog(self.options, ranking, parent=self)
        if dialog.exec() and dialog.payload:
            run_async(self, with_detail(api_client.update_ranking), self._replace_ranking, self._error,
                      ranking["id"], dialog.payload)

    def delete_ranking(self) -> None:
        ranking = self.current
        if ranking is None:
            return
        answer = QMessageBox.question(self, "Excluir ranking",
                                      f"Excluir o ranking \"{ranking['name']}\"? Os jogos continuam na biblioteca.",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        rid = ranking["id"]

        def done(_ok):
            self.set_rankings([r for r in self.rankings if r["id"] != rid])
            self.rankings_changed.emit()
        run_async(self, with_detail(api_client.delete_ranking), done, self._error, rid)

    def add_games(self) -> None:
        ranking = self.current
        if ranking is None:
            return
        dialog = RankingPickerDialog(ranking, self.games_provider(), parent=self)
        if dialog.exec() and dialog.selected_ids:
            self.save_entries(entry_ids(ranking) + dialog.selected_ids)

    def save_entries(self, game_ids: List[int], ranking_id: Optional[int] = None) -> None:
        rid = ranking_id if ranking_id is not None else self.current_id
        if rid is None:
            return
        run_async(self, with_detail(api_client.set_ranking_entries), self._replace_ranking, self._error, rid, game_ids)

    def move_entry(self, game_id: int, delta: int) -> None:
        ids = entry_ids(self.current or {})
        if game_id not in ids:
            return
        i = ids.index(game_id)
        j = i + delta
        if not 0 <= j < len(ids):
            return
        ids[i], ids[j] = ids[j], ids[i]
        self._apply_local_order(ids)
        self.save_entries(ids)

    def remove_entry(self, game_id: int) -> None:
        ids = [gid for gid in entry_ids(self.current or {}) if gid != game_id]
        self._apply_local_order(ids)
        self.save_entries(ids)

    def _apply_local_order(self, ids: List[int]) -> None:
        """Mostra a nova ordem na hora; a resposta da API confirma (ou o erro recarrega)."""
        ranking = self.current
        by_id = {g["id"]: g for g in ranking.get("entries") or []}
        ranking["entries"] = [by_id[gid] for gid in ids if gid in by_id]
        self._show_current()

    def _save_dragged_order(self) -> None:
        ids = [self.entry_list.item(i).data(Qt.UserRole) for i in range(self.entry_list.count())]
        if ids != entry_ids(self.current or {}):
            self._apply_local_order(ids)
            self.save_entries(ids)

    def _save_ranking_order(self) -> None:
        ids = [self.ranking_list.item(i).data(Qt.UserRole) for i in range(self.ranking_list.count())]
        if ids == [r["id"] for r in self.rankings]:
            return
        by_id = {r["id"]: r for r in self.rankings}
        self.rankings = [by_id[i] for i in ids]
        run_async(self, with_detail(api_client.reorder_rankings), lambda data: self.set_rankings(data),
                  self._error, ids)
