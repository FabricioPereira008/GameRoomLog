import logging
from typing import Optional
from app_version import __version__
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QPushButton, QLabel, QStatusBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from frontend_desktop.views.components.sidebar import Sidebar
from frontend_desktop.views.components.game_room_view import GameRoomView
from frontend_desktop.views.components.game_grid import GameGrid, ScrollableGameGrid
from frontend_desktop.views.components.game_table import GameTable
from frontend_desktop.views.components.yearbook_view import YearbookView
from frontend_desktop.views.components.management_view import ManagementView
from frontend_desktop.views.components.category_detail_view import CategoryDetailView
from frontend_desktop.views.components.settings_view import SettingsView
from frontend_desktop.views.components.library_sync_view import LibrarySyncView
from frontend_desktop.views.components.portable_app_view import PortableAppView
from frontend_desktop.views.components.game_grid import GameListView
from frontend_desktop.models.game_list_model import GameRole
from frontend_desktop.views.dialogs.game_dialog import GameDialog
from frontend_desktop.views.dialogs.quick_search_dialog import QuickSearchDialog
from frontend_desktop.workers import run_async
from frontend_desktop.api_client.client import api_client
from frontend_desktop.views import game_status as gs
from frontend_desktop.views.view_ids import NAV_SECTIONS, ViewId, VIEW_META
from frontend_desktop import preferences
from frontend_desktop.styles.tokens import COLORS
from frontend_desktop.ui_helpers import set_button_icon

logger = logging.getLogger(__name__)

class DataLoaderThread(QThread):
    """Busca jogos e opções de filtro fora da thread da UI."""
    loaded = Signal(list, object)  # games, options (tupla ou None)
    failed = Signal(str)

    def run(self):
        try:
            self.loaded.emit(*fetch_all_data())
        except Exception as e:
            self.failed.emit(str(e))


def fetch_all_data():
    """Retorna (games, options); options = (genres, devs, platforms, franchises) ou None se falhar."""
    games = api_client.get_games()
    try:
        options = (
            api_client.get_genres(), api_client.get_developers(),
            api_client.get_platforms(), api_client.get_franchises(),
        )
    except Exception:
        logger.warning("Erro ao carregar opções de filtros", exc_info=True)
        options = None
    return games, options


class MainWindow(QMainWindow):
    def __init__(self, auto_load: bool = True, restore_state: Optional[bool] = None):
        super().__init__()
        self.setWindowTitle("GameRoomLog — Backlog & Anuário Gamer")
        self.resize(1260, 790)
        self.setMinimumSize(980, 640)
        self.previous_nav_index = 0
        self.all_games = []
        self._filter_options = None
        self._loader = None
        self._loading = False
        self._refresh_pending = False
        self.init_ui()
        if auto_load if restore_state is None else restore_state:
            self.restore_window_state()
        if auto_load:
            self.refresh_all_data()

    def init_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        central_widget.setAttribute(Qt.WA_StyledBackground, True)
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sidebar à esquerda
        self.sidebar = Sidebar()
        self.sidebar.navigation_changed.connect(self.switch_view)
        self.sidebar.add_game_requested.connect(self.open_add_game_dialog)
        main_layout.addWidget(self.sidebar)

        # 2. Área de Conteúdo à direita
        content_widget = QWidget()
        content_widget.setObjectName("contentArea")
        content_widget.setAttribute(Qt.WA_StyledBackground, True)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 16, 20, 16)
        content_layout.setSpacing(12)

        # Cabeçalho Superior
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        self.view_title_label = QLabel(VIEW_META[ViewId.GAME_ROOM].title)
        self.view_title_label.setObjectName("viewTitle")
        header_layout.addWidget(self.view_title_label)

        header_layout.addStretch()

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setProperty("class", "small-btn")
        set_button_icon(self.btn_refresh, "refresh-cw", COLORS["text_muted"])
        self.btn_refresh.clicked.connect(self.refresh_all_data)
        header_layout.addWidget(self.btn_refresh)

        content_layout.addLayout(header_layout)

        # QStackedWidget: telas de jogos são criadas já (recebem dados); as demais sob demanda
        self.stack = QStackedWidget()
        self._views = {}

        self.view_game_room = self._register(ViewId.GAME_ROOM, GameRoomView())
        self.view_game_room.game_selected.connect(self.open_edit_game_dialog)
        self.view_game_room.view_all_requested.connect(self.open_list_view)

        self.view_queue_grid = self._new_game_grid(ViewId.QUEUE)
        self.view_disponiveis_grid = self._new_game_grid(ViewId.AVAILABLE)
        self.view_zerados_grid = self._new_game_grid(ViewId.FINISHED)  # Zerados + Platinados
        self.view_platinados_grid = self._new_game_grid(ViewId.PLATINUM)
        self.view_wishlist_grid = self._new_game_grid(ViewId.WISHLIST)

        self.view_table = self._register(ViewId.LIBRARY, GameTable())
        self.view_table.game_selected.connect(self.open_edit_game_dialog)

        # Telas pesadas/analíticas: criadas na primeira visita
        self._lazy_factories = {
            ViewId.YEARBOOK: self._create_yearbook,
            ViewId.GENRES: lambda: self._create_management("genre", "Gênero"),
            ViewId.PLATFORMS: lambda: self._create_management("platform", "Plataforma"),
            ViewId.FRANCHISES: lambda: self._create_management("franchise", "Série / Franquia"),
            ViewId.SETTINGS: self._create_settings,
            ViewId.SYNC: self._create_sync,
            ViewId.PORTABLE: self._create_portable,
            ViewId.CATEGORY_DETAIL: self._create_category_detail,
        }

        content_layout.addWidget(self.stack)
        main_layout.addWidget(content_widget)

        # Barra de status
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"Pronto • GameRoomLog v{__version__} Online")
        self._setup_shortcuts()

    # --- atalhos de teclado ---
    def _setup_shortcuts(self):
        """Ctrl+N novo jogo · Ctrl+F busca rápida · Del exclui o jogo selecionado (Enter abre, nativo das listas)."""
        self._shortcuts = []
        for keys, handler in ((QKeySequence.New, self.open_add_game_dialog),
                              ("Ctrl+F", self.open_quick_search),
                              (QKeySequence.Delete, self.delete_selected_game)):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)

    def open_quick_search(self):
        dialog = QuickSearchDialog(self.all_games, self)
        if dialog.exec() and dialog.selected_game:
            self.open_edit_game_dialog(dialog.selected_game)

    @staticmethod
    def selected_game_in(widget):
        """Jogo selecionado na lista/tabela que tem o foco (ou None)."""
        while widget is not None and not isinstance(widget, (GameListView, GameTable)):
            widget = widget.parentWidget()
        if isinstance(widget, GameListView):
            index = widget.currentIndex()
            return index.data(GameRole) if index.isValid() and widget.selectionModel().isSelected(index) else None
        if isinstance(widget, GameTable):
            index = widget.table.currentIndex()
            return index.sibling(index.row(), 0).data(GameRole) if index.isValid() else None
        return None

    def delete_selected_game(self):
        game = self.selected_game_in(QApplication.focusWidget())
        if not game:
            return
        confirm = QMessageBox.question(self, "Confirmar exclusão", f"Tem certeza que deseja excluir '{game.get('title')}'?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        run_async(self, api_client.delete_game,
                  lambda ok, gid=game["id"]: self.apply_game_deletion(gid) if ok else None,
                  lambda msg: QMessageBox.critical(self, "Erro", f"Erro ao excluir jogo: {msg}"),
                  game["id"])

    LIST_VIEWS = {"queue": ViewId.QUEUE, "zerados": ViewId.FINISHED, "platinados": ViewId.PLATINUM}

    def open_list_view(self, list_key: str):
        """"Ver todos" das faixas do Game Room: abre a página completa da lista."""
        if list_key in self.LIST_VIEWS:
            self.switch_view(int(self.LIST_VIEWS[list_key]))

    # --- registro de views ---
    def _register(self, view_id: ViewId, widget: QWidget) -> QWidget:
        self._views[view_id] = widget
        self.stack.addWidget(widget)
        return widget

    def _new_game_grid(self, view_id: ViewId) -> ScrollableGameGrid:
        grid = self._register(view_id, ScrollableGameGrid())
        grid.game_selected.connect(self.open_edit_game_dialog)
        return grid

    def _ensure_view(self, view_id: ViewId) -> QWidget:
        if view_id not in self._views:
            self._register(view_id, self._lazy_factories[view_id]())
        return self._views[view_id]

    def _create_yearbook(self):
        view = YearbookView()
        view.game_selected.connect(self.open_edit_game_dialog)
        return view

    def _create_management(self, category_type: str, title: str):
        view = ManagementView(category_type, title)
        view.category_selected.connect(self.open_category_detail)
        view.data_changed.connect(self.refresh_all_data)
        return view

    def _create_settings(self):
        view = SettingsView()
        view.settings_changed.connect(self.refresh_all_data)
        view.data_imported.connect(self.refresh_all_data)
        return view

    def _create_portable(self):
        view = PortableAppView()
        view.game_saved.connect(self.apply_game_mutation)
        return view

    def _create_sync(self):
        view = LibrarySyncView()
        view.games_imported.connect(self._on_games_imported)
        view.games_updated.connect(self._on_games_updated)
        return view

    def _on_games_imported(self, games: list):
        """Insere os jogos importados in-place (sem recarregar as telas)."""
        for game in reversed(games):
            self.apply_game_mutation(game, is_new=True)
        self.statusBar().showMessage(f"{len(games)} jogo(s) importado(s). Total: {len(self.all_games)}")

    def _on_games_updated(self, games: list):
        for game in games:
            self.apply_game_mutation(game, is_new=False, old_status=game.get("status"))

    def _create_category_detail(self):
        view = CategoryDetailView()
        view.back_requested.connect(self.return_from_category_detail)
        view.game_selected.connect(self.open_edit_game_dialog)
        if self._filter_options:
            view.set_filter_options(*self._filter_options)
        return view

    view_yearbook = property(lambda self: self._ensure_view(ViewId.YEARBOOK))
    view_genres = property(lambda self: self._ensure_view(ViewId.GENRES))
    view_platforms = property(lambda self: self._ensure_view(ViewId.PLATFORMS))
    view_franchises = property(lambda self: self._ensure_view(ViewId.FRANCHISES))
    view_settings = property(lambda self: self._ensure_view(ViewId.SETTINGS))
    view_category_detail = property(lambda self: self._ensure_view(ViewId.CATEGORY_DETAIL))

    @property
    def current_view_id(self) -> ViewId:
        widget = self.stack.currentWidget()
        for view_id, view in self._views.items():
            if view is widget:
                return view_id
        return ViewId.GAME_ROOM

    # --- navegação ---
    DYNAMIC_VIEWS = (ViewId.YEARBOOK, ViewId.GENRES, ViewId.PLATFORMS, ViewId.FRANCHISES)

    def switch_view(self, index: int):
        view_id = ViewId(index)
        self.previous_nav_index = int(view_id)
        self.stack.setCurrentWidget(self._ensure_view(view_id) if view_id in self._lazy_factories else self._views[view_id])
        self.view_title_label.setText(VIEW_META[view_id].title)
        self.sidebar.set_current_index(int(view_id))

        # Limpa filtros de busca e categorias ao navegar entre as páginas
        self.view_game_room.clear_filters()
        for _, grid in self._list_grids():
            grid.clear_filters()

        # Só telas analíticas/dinâmicas recarregam; as demais usam o cache existente
        if view_id in self.DYNAMIC_VIEWS:
            self._views[view_id].load_data()

    def open_category_detail(self, category_type: str, item_id: int):
        self.view_category_detail.load_category(category_type, item_id)
        self.stack.setCurrentWidget(self.view_category_detail)
        self.view_title_label.setText(VIEW_META[ViewId.CATEGORY_DETAIL].title)

    def return_from_category_detail(self):
        self.switch_view(self.previous_nav_index)

    def refresh_all_data(self):
        """Recarrega jogos e opções em background; a UI continua responsiva."""
        if self._loading:
            self._refresh_pending = True
            return
        self._loading = True
        self.statusBar().showMessage("Carregando jogos...")
        self._loader = DataLoaderThread(self)
        self._loader.loaded.connect(self._apply_loaded_data)
        self._loader.failed.connect(self._on_load_failed)
        self._loader.finished.connect(self._on_loader_finished)
        self._loader.start()

    def refresh_all_data_sync(self):
        """Versão bloqueante (testes e usos pontuais)."""
        try:
            self._apply_loaded_data(*fetch_all_data())
        except Exception as e:
            self._on_load_failed(str(e))

    def _on_loader_finished(self):
        self._loading = False
        if self._refresh_pending:
            self._refresh_pending = False
            self.refresh_all_data()

    def _on_load_failed(self, message: str):
        self.statusBar().showMessage(f"Erro de conexão com a API: {message}")

    # --- estado da janela (tamanho/posição e última tela) ---
    RESTORABLE_VIEWS = {int(v) for _section, ids in NAV_SECTIONS for v in ids} | {int(ViewId.SETTINGS)}

    def restore_window_state(self):
        geometry = preferences.window_geometry()
        if geometry is not None:
            self.restoreGeometry(geometry)
        view = preferences.last_view(int(ViewId.GAME_ROOM))
        if view in self.RESTORABLE_VIEWS and view != int(ViewId.GAME_ROOM):
            self.switch_view(view)

    def save_window_state(self):
        view = int(self.current_view_id)
        if view not in self.RESTORABLE_VIEWS:  # ex.: detalhe de categoria volta para a lista de origem
            view = self.previous_nav_index if self.previous_nav_index in self.RESTORABLE_VIEWS else int(ViewId.GAME_ROOM)
        preferences.save_window_state(self.saveGeometry(), view)

    def closeEvent(self, event):
        self.save_window_state()
        if self._loader is not None and self._loader.isRunning():
            self._loader.wait(5000)
        super().closeEvent(event)

    def _apply_loaded_data(self, games: list, options):
        """Distribui os dados carregados pelas views (sempre na thread da UI)."""
        try:
            self.all_games = games

            if options:
                self._filter_options = options
                if ViewId.CATEGORY_DETAIL in self._views:
                    self.view_category_detail.set_filter_options(*options)
                for view in [
                    self.view_game_room, self.view_queue_grid, self.view_disponiveis_grid,
                    self.view_zerados_grid, self.view_platinados_grid, self.view_wishlist_grid
                ]:
                    if hasattr(view, "set_filter_options"):
                        view.set_filter_options(*options)

            now_games = [g for g in games if g.get("status") == gs.JOGANDO]
            next_games = [g for g in games if g.get("status") == gs.PROXIMO]
            queue_games = gs.filter_games("queue", games)
            disponiveis_games = gs.filter_games("disponiveis", games)

            # Zerados (Zerados + Platinados) ordenados por data de finalização (mais recente -> mais antigo)
            zerados_games = gs.filter_games("zerados", games)
            zerados_games.sort(key=lambda g: g.get("finish_date") or "", reverse=True)

            # Platinados ordenados por data de platina (mais recente -> mais antigo)
            platinados_games = gs.filter_games("platinados", games)
            platinados_games.sort(key=lambda g: g.get("platinum_date") or g.get("finish_date") or "", reverse=True)

            wishlist_games = gs.filter_games("wishlist", games)

            # Atualizar todas as views
            self.view_game_room.set_games(now_games, next_games, queue_games, zerados_games, platinados_games)
            self.view_queue_grid.set_games(queue_games)
            self.view_disponiveis_grid.set_games(disponiveis_games)
            self.view_zerados_grid.set_games(zerados_games)
            self.view_platinados_grid.set_games(platinados_games)
            self.view_wishlist_grid.set_games(wishlist_games)
            self.view_table.set_games(games)


            current = self.current_view_id
            if current in self.DYNAMIC_VIEWS:
                self._views[current].load_data()
            elif current == ViewId.CATEGORY_DETAIL and self.view_category_detail.category_id:
                self.view_category_detail.load_category(
                    self.view_category_detail.category_type,
                    self.view_category_detail.category_id
                )

            self.statusBar().showMessage(f"Total de jogos carregados: {len(games)}")
        except Exception as e:
            self.statusBar().showMessage(f"Erro de conexão com a API: {e}")

    def open_add_game_dialog(self):
        dialog = GameDialog(parent=self)
        if dialog.exec() and dialog.saved_game:
            self.apply_game_mutation(dialog.saved_game, is_new=True)

    def open_edit_game_dialog(self, game_data: dict):
        dialog = GameDialog(game_data=game_data, parent=self)
        if dialog.exec():
            if dialog.is_deleted:
                self.apply_game_deletion(game_data.get("id"))
            elif dialog.saved_game:
                self.apply_game_mutation(dialog.saved_game, is_new=False, old_status=game_data.get("status"))

    def apply_game_deletion(self, game_id: int):
        """Remove o jogo in-place de todas as views sem recarregar telas."""
        deleted = next((g for g in self.all_games if g.get("id") == game_id), {})
        if deleted.get("replays_count"):
            # Era o original de rejogadas: o servidor promoveu outra jogada e religou as demais
            self.refresh_all_data()
            return
        self.all_games = [g for g in self.all_games if g.get("id") != game_id]
        self._refresh_replay_originals({deleted.get("replay_of_id")})
        self.view_game_room.remove_game(game_id)
        for _, grid in self._list_grids():
            grid.remove_game(game_id)
        self.view_table.remove_game(game_id)
        self.statusBar().showMessage(f"Jogo removido com sucesso. Total: {len(self.all_games)}")

    def _refresh_replay_originals(self, game_ids) -> None:
        """Rejogada ligada/desligada/excluída: atualiza o contador de rejogadas dos registros originais."""
        for original_id in {i for i in game_ids if i}:
            original = next((g for g in self.all_games if g.get("id") == original_id), None)
            if original is None:
                continue
            run_async(self, api_client.get_game,
                      lambda game, status=original.get("status"): self.apply_game_mutation(game, old_status=status),
                      lambda msg: logger.warning("Falha ao atualizar o original da rejogada: %s", msg),
                      original_id)

    def _list_grids(self):
        """Pares (chave da lista, grid) alimentados por status; ver game_status.LIST_STATUSES."""
        return [
            ("queue", self.view_queue_grid),
            ("disponiveis", self.view_disponiveis_grid),
            ("zerados", self.view_zerados_grid),
            ("platinados", self.view_platinados_grid),
            ("wishlist", self.view_wishlist_grid),
        ]

    def apply_game_mutation(self, saved_game: dict, is_new: bool = False, old_status: str = None):
        """Aplica inserções e edições in-place sem resetar a posição de rolagem."""
        game_id = saved_game.get("id")
        new_status = saved_game.get("status")
        title = saved_game.get("title")
        previous = {} if is_new else next((g for g in self.all_games if g.get("id") == game_id), {})
        if previous.get("replay_of_id") != saved_game.get("replay_of_id"):
            self._refresh_replay_originals({previous.get("replay_of_id"), saved_game.get("replay_of_id")})

        if is_new:
            self.all_games.insert(0, saved_game)
            self.view_table.insert_game(saved_game)
            self.view_game_room.insert_game_by_status(saved_game)
            for key, grid in self._list_grids():
                if gs.in_list(key, new_status):
                    grid.insert_game(0, saved_game)
            self.statusBar().showMessage(f"Jogo '{title}' adicionado com sucesso. Total: {len(self.all_games)}")
            return

        # Edição existente
        for i, g in enumerate(self.all_games):
            if g.get("id") == game_id:
                self.all_games[i] = saved_game
                break

        # Cada lista: entra, sai ou apenas atualiza o card conforme a mudança de status
        for key, grid in self._list_grids():
            was_in, is_in = gs.in_list(key, old_status), gs.in_list(key, new_status)
            if was_in and is_in:
                grid.update_game(saved_game)
            elif was_in:
                grid.remove_game(game_id)
            elif is_in:
                grid.insert_game(0, saved_game)

        if old_status == new_status:
            self.view_game_room.update_game(saved_game)
            self.view_table.update_game(saved_game)
            self.statusBar().showMessage(f"Jogo '{title}' atualizado com sucesso.")
            return

        self.view_game_room.remove_game(game_id)
        self.view_game_room.insert_game_by_status(saved_game)
        self.view_table.update_game(saved_game)
        self.statusBar().showMessage(f"Jogo '{title}' movido para '{new_status}'.")
