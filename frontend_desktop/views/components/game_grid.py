"""Grades de jogos baseadas em model/view: cards pintados por delegate, filtro sem recriar widgets."""
import math

import shiboken6
from typing import Callable, List, Optional

from PySide6.QtCore import QModelIndex, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QComboBox, QHBoxLayout, QLabel, QLineEdit, QListView, QPushButton, QSizePolicy,
    QToolButton, QVBoxLayout, QWidget
)

from frontend_desktop import page_settings, preferences
from frontend_desktop.cover_loader import cover_loader
from frontend_desktop.text_search import fold, fold_query
from frontend_desktop.models.game_list_model import GameFilterProxy, GameListModel, GameRole
from frontend_desktop.ui_helpers import add_search_icon
from frontend_desktop.views.components.filter_panel import FilterPanel
from frontend_desktop.views.components.game_card_delegate import GameCardDelegate, current_size_mode

GRID_SPACING = 12
FILTER_DEBOUNCE_MS = 150
MODE_INFINITE = "infinite"  # preenche a área e rola sozinho (listas de status)
MODE_BUTTON = "button"      # altura limitada em linhas + botão "Mostrar mais" (seções do Game Room)
MODE_FULL = "full"          # mostra todas as linhas, sem rolagem própria (ex.: Anuário)
MODE_STRIP = "strip"        # uma linha só, rolando na horizontal (faixas do Game Room)


class GameListView(QListView):
    """QListView em modo ícones, com tamanhos uniformes e hover; pode ceder a rolagem ao pai."""
    game_clicked = Signal(dict)

    def __init__(self, scrolls: bool = True, strip: bool = False, parent=None):
        super().__init__(parent)
        self._scrolls = scrolls
        self._strip = strip
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setWrapping(not strip)
        self.setFlow(QListView.LeftToRight)
        self.setUniformItemSizes(True)
        self.setSpacing(GRID_SPACING)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setFrameShape(QListView.NoFrame)
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(28)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        if not scrolls:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.viewport().setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self._emit_game)
        self.activated.connect(self._emit_game)

    def _emit_game(self, index: QModelIndex):
        game = index.data(GameRole)
        if game:
            self.game_clicked.emit(game)

    def wheelEvent(self, event):
        if self._strip:
            # Faixa: rolagem horizontal (trackpad ou Shift+roda); a roda comum continua rolando a página
            delta = event.angleDelta()
            step = delta.x() or (delta.y() if event.modifiers() & Qt.ShiftModifier else 0)
            if step:
                bar = self.horizontalScrollBar()
                bar.setValue(bar.value() - step)
                event.accept()
                return
            event.ignore()
        elif self._scrolls:
            super().wheelEvent(event)
        else:
            event.ignore()  # o QScrollArea pai rola


class GameGrid(QWidget):
    """Lista de cards. A fonte de dados completa fica em `model`; `proxy` aplica o filtro."""
    game_selected = Signal(dict)

    def __init__(self, mode: str = MODE_INFINITE, initial_rows: int = 2, parent=None, size_mode: Optional[str] = None):
        super().__init__(parent)
        self.mode = mode
        self._fixed_size = size_mode  # ex.: "large" nos destaques; None segue a preferência do usuário
        self._rows_step = max(1, initial_rows)
        self._visible_rows = self._rows_step

        self.model = GameListModel(self)
        self.proxy = GameFilterProxy(self)
        self.proxy.setSourceModel(self.model)

        self.delegate = GameCardDelegate(size_mode, parent=self)
        self.view = GameListView(scrolls=(mode == MODE_INFINITE), strip=(mode == MODE_STRIP), parent=self)
        self.view.setModel(self.proxy)
        self.view.setItemDelegate(self.delegate)
        self.view.game_clicked.connect(self.game_selected.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.view)

        self.empty_label = QLabel("Nenhum jogo encontrado.")
        self.empty_label.setProperty("class", "empty-state-text")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        self.more_button = QPushButton("Mostrar mais")
        self.more_button.setProperty("class", "small-btn")
        self.more_button.setCursor(Qt.PointingHandCursor)
        self.more_button.clicked.connect(self.load_more_cards)
        self.more_button.setVisible(False)
        layout.addWidget(self.more_button, alignment=Qt.AlignLeft)

        if mode != MODE_INFINITE:
            self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.proxy.rowsInserted.connect(self._schedule_height_update)
            self.proxy.rowsRemoved.connect(self._schedule_height_update)
            self.proxy.modelReset.connect(self._schedule_height_update)
            self.proxy.layoutChanged.connect(self._schedule_height_update)

        for signal in (self.proxy.rowsInserted, self.proxy.rowsRemoved, self.proxy.modelReset, self.proxy.layoutChanged):
            signal.connect(self._update_empty_state)
        cover_loader.loaded.connect(self._on_cover_loaded)
        preferences.subscribe_card_size(self._on_card_size_changed)

    def _on_card_size_changed(self, size: str) -> None:
        if self._fixed_size is None and self.delegate.set_size_mode(size):
            self._apply_grid_size()
            self.view.scheduleDelayedItemsLayout()
            self._update_height()

    def _apply_grid_size(self) -> None:
        """Distribui a sobra de largura entre as colunas (sem faixa vazia à direita)."""
        if self.mode == MODE_STRIP:
            return
        m = self.delegate.metrics
        width = self.view.viewport().width() or self.width()
        cols = self._columns()
        cell_w = max(m.card_width + GRID_SPACING, (width - GRID_SPACING) // cols)
        size = QSize(cell_w, m.card_height + GRID_SPACING)
        if self.view.gridSize() != size:
            self.view.setGridSize(size)

    def _update_empty_state(self, *args) -> None:
        """Mensagem amigável quando a lista (ou o resultado da busca) está vazia; seções do Game Room somem sozinhas."""
        self.empty_label.setVisible(self.mode != MODE_BUTTON and self.proxy.rowCount() == 0)

    # --- dados ---
    @property
    def games(self) -> List[dict]:
        """Jogos que passam no filtro atual (ordem exibida)."""
        return self.proxy.games

    @property
    def rendered_count(self) -> int:
        """Quantos cards estão visíveis (em MODE_BUTTON, limitado pelas linhas abertas)."""
        total = self.proxy.rowCount()
        if self.mode == MODE_BUTTON:
            return min(total, self._columns() * self._visible_rows)
        return total

    def set_predicate(self, predicate: Optional[Callable[[dict], bool]]) -> None:
        self.proxy.set_predicate(predicate)
        self._update_height()

    def set_games(self, games: list) -> None:
        if self.delegate.set_size_mode(self._fixed_size or current_size_mode()):
            self._apply_grid_size()
            self.view.scheduleDelayedItemsLayout()
        self._visible_rows = self._rows_step
        self.model.set_games(games)
        self._update_height()

    def insert_game(self, index: int, game_data: dict) -> None:
        self.model.insert_game(index, game_data)

    def update_game(self, game_data: dict) -> bool:
        return self.model.update_game(game_data)

    def remove_game(self, game_id: int) -> bool:
        return self.model.remove_game(game_id)

    # --- layout ---
    def _columns(self) -> int:
        cell = self.delegate.metrics.card_width + GRID_SPACING
        width = self.view.viewport().width() or self.width()
        return max(1, (width - GRID_SPACING) // cell)

    def _total_rows(self) -> int:
        return math.ceil(self.proxy.rowCount() / self._columns()) if self.proxy.rowCount() else 0

    def _schedule_height_update(self, *args) -> None:
        QTimer.singleShot(0, self, self._update_height)  # com contexto: cancelado se a grade for destruída

    def _update_height(self) -> None:
        """Em modos sem rolagem própria, ajusta a altura da lista ao número de linhas exibidas."""
        if self.mode == MODE_INFINITE or not shiboken6.isValid(self.proxy):
            return
        if self.mode == MODE_STRIP:
            has = self.proxy.rowCount() > 0
            self.view.setFixedHeight(self.delegate.metrics.card_height + 2 * GRID_SPACING if has else 0)
            return
        total_rows = self._total_rows()
        rows = min(total_rows, self._visible_rows) if self.mode == MODE_BUTTON else total_rows
        height = rows * (self.delegate.metrics.card_height + GRID_SPACING) + GRID_SPACING if rows else 0
        self.view.setFixedHeight(height)
        hidden = self.proxy.rowCount() - self.rendered_count
        self.more_button.setVisible(self.mode == MODE_BUTTON and hidden > 0)
        if hidden > 0:
            self.more_button.setText(f"Mostrar mais ({hidden})")

    def relayout_cards(self, force: bool = False) -> None:  # compat: antigo relayout manual
        self._update_height()

    def load_more_cards(self) -> None:
        """Abre mais linhas (MODE_BUTTON). Nos demais modos a lista já mostra tudo."""
        if self.mode == MODE_BUTTON:
            self._visible_rows += self._rows_step
            self._update_height()

    def _on_cover_loaded(self, filename: str) -> None:
        self.view.viewport().update()

    def scroll_strip(self, direction: int) -> None:
        """Faixa: avança/volta quase uma tela de cards."""
        bar = self.view.horizontalScrollBar()
        bar.setValue(bar.value() + direction * int(self.view.viewport().width() * 0.8))

    def strip_overflows(self) -> bool:
        return self.mode == MODE_STRIP and self.view.horizontalScrollBar().maximum() > 0

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_grid_size()
        self._update_height()

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_grid_size()
        self._update_height()


class CardSizeSelector(QWidget):
    """Seletor rápido P/M/G do tamanho dos cards; fica em sincronia com as demais telas."""
    LABELS = (("small", "P", "Cards pequenos"), ("medium", "M", "Cards médios"), ("large", "G", "Cards grandes"))

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        for i, (size, text, tip) in enumerate(self.LABELS):
            btn = QToolButton()
            btn.setText(text)
            btn.setToolTip(tip)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("class", "segmented-btn segmented-" + ("first" if i == 0 else "last" if i == 2 else "mid"))
            self.group.addButton(btn)
            self.buttons[size] = btn
            layout.addWidget(btn)
            btn.clicked.connect(lambda _checked=False, s=size: preferences.set_card_size(s))
        self._sync(preferences.card_size())
        preferences.subscribe_card_size(self._sync)

    def _sync(self, size: str) -> None:
        btn = self.buttons.get(size)
        if btn and not btn.isChecked():
            btn.setChecked(True)


class ScrollableGameGrid(QWidget):
    """Grade com busca, painel de filtros e rolagem nativa. A busca digitada usa debounce."""
    game_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("scrollableGameGridWrapper")
        self.setAttribute(Qt.WA_StyledBackground, True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar jogos por título...")
        add_search_icon(self.search_input)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setProperty("class", "search-input")
        self.search_input.textChanged.connect(self.on_search_changed)
        top_bar_layout.addWidget(self.search_input)

        self.filter_panel = FilterPanel()
        self.filter_panel.filters_changed.connect(self.apply_filter)
        top_bar_layout.addWidget(self.filter_panel.btn_toggle)

        # Ordenação (opcional): critério + direção; só aparece após configure_page()
        self.sort_combo = QComboBox()
        self.sort_combo.setProperty("class", "filter-combo")
        self.sort_combo.currentIndexChanged.connect(self._on_sort_key_changed)
        self.sort_combo.setVisible(False)
        self._sorting = False
        self._sort_touched = False  # o usuário mexeu na ordenação nesta sessão
        top_bar_layout.addWidget(self.sort_combo)

        self.sort_dir_btn = QPushButton("A→Z")
        self.sort_dir_btn.setProperty("class", "small-btn")
        self.sort_dir_btn.setCheckable(True)
        self.sort_dir_btn.setCursor(Qt.PointingHandCursor)
        self.sort_dir_btn.setToolTip("Alternar direção da ordenação")
        self.sort_dir_btn.toggled.connect(self._on_direction_toggled)
        self.sort_dir_btn.setVisible(False)
        top_bar_layout.addWidget(self.sort_dir_btn)

        self.size_selector = CardSizeSelector()
        top_bar_layout.addWidget(self.size_selector)

        main_layout.addLayout(top_bar_layout)
        main_layout.addWidget(self.filter_panel)

        self.grid = GameGrid(mode=MODE_INFINITE)
        self.grid.game_selected.connect(self.game_selected.emit)
        main_layout.addWidget(self.grid)

        # Debounce: só para digitação do usuário (campo com foco); setText programático aplica na hora
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(FILTER_DEBOUNCE_MS)
        self._debounce.timeout.connect(self.apply_filter)

    # --- dados ---
    @property
    def all_games_source(self) -> List[dict]:
        """Lista completa (sem filtro)."""
        return self.grid.model.games

    def set_games(self, games: list) -> None:
        self.grid.set_games(games)
        self.apply_filter()

    def set_filter_options(self, genres: list, developers: list, platforms: list, franchises: list) -> None:
        self.filter_panel.set_options(genres, developers, platforms, franchises)

    def set_locked_filters(self, locked) -> None:
        self.filter_panel.set_locked_filters(locked)

    def update_game(self, game_data: dict) -> bool:
        return self.grid.update_game(game_data)

    def remove_game(self, game_id: int) -> bool:
        return self.grid.remove_game(game_id)

    def insert_game(self, index: int, game_data: dict) -> None:
        self.grid.insert_game(index, game_data)

    # --- ordenação e filtros da página (Configurações → Páginas) ---
    def configure_page(self, page: str) -> None:
        """Usa os critérios de ordenação e os campos do Filtro escolhidos para `page`."""
        self.filter_panel.bind_page(page)
        self.apply_page_config(page_settings.page_config(page))
        page_settings.subscribe(page, self.apply_page_config)

    def apply_page_config(self, config) -> None:
        """Monta o seletor com os critérios visíveis. A escolha feita na página nesta sessão é mantida
        enquanto o critério continuar disponível; senão (ou se nada foi escolhido) vale o padrão."""
        current = self.sort_combo.currentData()
        keep = self._sort_touched and current in config.sorts
        self.sort_combo.blockSignals(True)
        self.sort_combo.clear()
        for key in config.sorts:
            self.sort_combo.addItem(f"Ordenar: {page_settings.SORT_CRITERIA[key].label}", key)
        self.sort_combo.setCurrentIndex(self.sort_combo.findData(current if keep else config.default_sort))
        self.sort_combo.blockSignals(False)
        if not keep:
            self._sort_touched = False
            self._set_direction(config.default_descending)
        self._sorting = bool(config.sorts)
        self.sort_combo.setVisible(len(config.sorts) > 1)  # um critério só: fica só a direção
        self.sort_dir_btn.setVisible(self._sorting)
        self._apply_sort()

    def _set_direction(self, descending: bool) -> None:
        self.sort_dir_btn.blockSignals(True)
        self.sort_dir_btn.setChecked(descending)
        self.sort_dir_btn.blockSignals(False)

    def _on_sort_key_changed(self, *args) -> None:
        key = self.sort_combo.currentData()
        if key is None:
            return
        self._sort_touched = True
        self._set_direction(page_settings.SORT_CRITERIA[key].descending)  # cada critério tem sua direção inicial
        self._apply_sort()

    def _on_direction_toggled(self, *args) -> None:
        self._sort_touched = True
        self._apply_sort()

    def _apply_sort(self, *args) -> None:
        key = self.sort_combo.currentData()
        if not self._sorting or key is None:
            self.grid.proxy.set_sort(None)
            return
        criterion = page_settings.SORT_CRITERIA[key]
        descending = self.sort_dir_btn.isChecked()
        self.sort_dir_btn.setText(criterion.direction_label(descending))
        self.grid.proxy.set_sort(criterion.key, descending)

    # --- busca e filtros ---
    def on_search_changed(self, text: str) -> None:
        if self.search_input.hasFocus():
            self._debounce.start()
        else:
            self.apply_filter()

    def clear_search(self) -> None:
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self.apply_filter()

    def clear_filters(self) -> None:
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self.filter_panel.clear_filters()
        self.apply_filter()

    def apply_filter(self) -> None:
        self._debounce.stop()
        self.grid.set_predicate(make_predicate(self.search_input.text(), self.filter_panel.build_matcher()))


def make_predicate(query: str, panel_matcher: Callable[[dict], bool]) -> Callable[[dict], bool]:
    """Predicado de busca por título + filtros do painel (estado lido uma única vez)."""
    needle = fold_query(query)

    def predicate(game: dict) -> bool:
        if needle and needle not in fold(game.get("title")):
            return False
        return panel_matcher(game)

    return predicate
