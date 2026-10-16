import logging
from app_version import __version__
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QPushButton, QLabel, QStatusBar
)
from PySide6.QtCore import Qt, QThread, Signal
from frontend_desktop.views.components.sidebar import Sidebar
from frontend_desktop.views.components.game_room_view import GameRoomView
from frontend_desktop.views.components.game_grid import GameGrid, ScrollableGameGrid
from frontend_desktop.views.components.game_table import GameTable
from frontend_desktop.views.components.yearbook_view import YearbookView
from frontend_desktop.views.components.management_view import ManagementView
from frontend_desktop.views.components.category_detail_view import CategoryDetailView
from frontend_desktop.views.components.settings_view import SettingsView
from frontend_desktop.views.dialogs.game_dialog import GameDialog
from frontend_desktop.api_client.client import api_client
from frontend_desktop.views import game_status as gs

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
    def __init__(self, auto_load: bool = True):
        super().__init__()
        self.setWindowTitle("GameRoomLog — Backlog & Anuário Gamer")
        self.resize(1260, 790)
        self.setMinimumSize(980, 640)
        self.previous_nav_index = 0
        self.all_games = []
        self._loader = None
        self._loading = False
        self._refresh_pending = False
        self.init_ui()
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

        self.view_title_label = QLabel("🕹️ Game Room")
        self.view_title_label.setObjectName("viewTitle")
        header_layout.addWidget(self.view_title_label)

        header_layout.addStretch()

        self.btn_refresh = QPushButton("🔄 Atualizar")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setProperty("class", "small-btn")
        self.btn_refresh.clicked.connect(self.refresh_all_data)
        header_layout.addWidget(self.btn_refresh)

        content_layout.addLayout(header_layout)

        # QStackedWidget com as Telas em Cache
        self.stack = QStackedWidget()

        # View 0: Game Room (Agora + Próximos + Fila + Zerados + Platinados)
        self.view_game_room = GameRoomView()
        self.view_game_room.game_selected.connect(self.open_edit_game_dialog)
        self.stack.addWidget(self.view_game_room)

        # View 1: Fila de Espera
        self.view_queue_grid = ScrollableGameGrid()
        self.view_queue_grid.game_selected.connect(self.open_edit_game_dialog)
        self.stack.addWidget(self.view_queue_grid)

        # View 2: Disponíveis
        self.view_disponiveis_grid = ScrollableGameGrid()
        self.view_disponiveis_grid.game_selected.connect(self.open_edit_game_dialog)
        self.stack.addWidget(self.view_disponiveis_grid)

        # View 3: Zerados (Inclui Zerados e Platinados)
        self.view_zerados_grid = ScrollableGameGrid()
        self.view_zerados_grid.game_selected.connect(self.open_edit_game_dialog)
        self.stack.addWidget(self.view_zerados_grid)

        # View 4: Platinados (Apenas Platinados)
        self.view_platinados_grid = ScrollableGameGrid()
        self.view_platinados_grid.game_selected.connect(self.open_edit_game_dialog)
        self.stack.addWidget(self.view_platinados_grid)

        # View 5: Anuário
        self.view_yearbook = YearbookView()
        self.view_yearbook.game_selected.connect(self.open_edit_game_dialog)
        self.stack.addWidget(self.view_yearbook)

        # View 6: Gêneros (Gerenciamento)
        self.view_genres = ManagementView("genre", "Gênero")
        self.view_genres.category_selected.connect(self.open_category_detail)
        self.view_genres.data_changed.connect(self.refresh_all_data)
        self.stack.addWidget(self.view_genres)

        # View 7: Plataformas (Gerenciamento)
        self.view_platforms = ManagementView("platform", "Plataforma")
        self.view_platforms.category_selected.connect(self.open_category_detail)
        self.view_platforms.data_changed.connect(self.refresh_all_data)
        self.stack.addWidget(self.view_platforms)

        # View 8: Séries / Franquias (Gerenciamento)
        self.view_franchises = ManagementView("franchise", "Série / Franquia")
        self.view_franchises.category_selected.connect(self.open_category_detail)
        self.view_franchises.data_changed.connect(self.refresh_all_data)
        self.stack.addWidget(self.view_franchises)

        # View 9: Biblioteca (Tabela Completa)
        self.view_table = GameTable()
        self.view_table.game_selected.connect(self.open_edit_game_dialog)
        self.stack.addWidget(self.view_table)

        # View 10: Lista de Desejos
        self.view_wishlist_grid = ScrollableGameGrid()
        self.view_wishlist_grid.game_selected.connect(self.open_edit_game_dialog)
        self.stack.addWidget(self.view_wishlist_grid)

        # View 11: Configurações
        self.view_settings = SettingsView()
        self.view_settings.settings_changed.connect(self.refresh_all_data)
        self.view_settings.data_imported.connect(self.refresh_all_data)
        self.stack.addWidget(self.view_settings)

        # View 12: Detalhes de Categoria (Subpágina)
        self.view_category_detail = CategoryDetailView()
        self.view_category_detail.back_requested.connect(self.return_from_category_detail)
        self.view_category_detail.game_selected.connect(self.open_edit_game_dialog)
        self.stack.addWidget(self.view_category_detail)

        content_layout.addWidget(self.stack)
        main_layout.addWidget(content_widget)

        # Barra de status
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"Pronto • GameRoomLog v{__version__} Online")

    def switch_view(self, index: int):
        self.previous_nav_index = index
        self.stack.setCurrentIndex(index)
        titles = [
            "🕹️ Game Room",
            "📋 Fila de Espera",
            "🟢 Jogos Disponíveis",
            "🏆 Jogos Zerados",
            "👑 Jogos Platinados",
            "📊 Anuário Gamer",
            "🎨 Gerenciar Gêneros",
            "🎮 Gerenciar Plataformas",
            "👾 Gerenciar Séries / Franquias",
            "📑 Biblioteca de Jogos (Tabela)",
            "⭐ Lista de Desejos",
            "⚙️ Configurações"
        ]
        if 0 <= index < len(titles):
            self.view_title_label.setText(titles[index])

        # Limpa filtros de busca e categorias ao navegar entre as páginas
        self.view_game_room.clear_filters()
        self.view_queue_grid.clear_filters()
        self.view_disponiveis_grid.clear_filters()
        self.view_zerados_grid.clear_filters()
        self.view_platinados_grid.clear_filters()
        self.view_wishlist_grid.clear_filters()

        # Apenas recarrega dados para páginas analíticas ou dinâmicas que dependem de agregação
        if index == 5:
            self.view_yearbook.load_data()
        elif index == 6:
            self.view_genres.load_data()
        elif index == 7:
            self.view_platforms.load_data()
        elif index == 8:
            self.view_franchises.load_data()
        # Todas as outras páginas (Game Room, Fila, Zerados, etc.) utilizam o cache existente instantaneamente!


    def open_category_detail(self, category_type: str, item_id: int):
        self.view_category_detail.load_category(category_type, item_id)
        self.stack.setCurrentIndex(12)
        self.view_title_label.setText("📋 Detalhes da Categoria")

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

    def closeEvent(self, event):
        if self._loader is not None and self._loader.isRunning():
            self._loader.wait(5000)
        super().closeEvent(event)

    def _apply_loaded_data(self, games: list, options):
        """Distribui os dados carregados pelas views (sempre na thread da UI)."""
        try:
            self.all_games = games

            if options:
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


            cur_idx = self.stack.currentIndex()
            if cur_idx == 5:
                self.view_yearbook.load_data()
            elif cur_idx == 6:
                self.view_genres.load_data()
            elif cur_idx == 7:
                self.view_platforms.load_data()
            elif cur_idx == 8:
                self.view_franchises.load_data()
            elif cur_idx == 12 and self.view_category_detail.category_id:
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
        self.all_games = [g for g in self.all_games if g.get("id") != game_id]
        self.view_game_room.remove_game(game_id)
        for _, grid in self._list_grids():
            grid.remove_game(game_id)
        self.view_table.remove_game(game_id)
        self.statusBar().showMessage(f"Jogo removido com sucesso. Total: {len(self.all_games)}")

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
