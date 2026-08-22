from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QPushButton, QLabel, QStatusBar
)
from PySide6.QtCore import Qt
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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GameRoomLog — Backlog & Anuário Gamer")
        self.resize(1260, 790)
        self.setMinimumSize(980, 640)
        self.previous_nav_index = 0
        self.all_games = []
        self.init_ui()
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
        self.statusBar().showMessage("Pronto • GameRoomLog v0.2.1 Online")

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
        """Carregamento completo dos jogos a partir do backend."""
        try:
            games = api_client.get_games()
            self.all_games = games

            # Separar por categorias com fidelidade aos status
            now_games = [g for g in games if g.get("status") == "Jogando"]
            next_games = [g for g in games if g.get("status") == "Próximo"]
            queue_games = [g for g in games if g.get("status") in ["Fila", "Pausado"]]
            disponiveis_games = [g for g in games if g.get("status") == "Disponível"]
            
            # Zerados (Zerados + Platinados) ordenados por data de finalização (mais recente -> mais antigo)
            zerados_games = [g for g in games if g.get("status") in ["Zerado", "Platinado"]]
            zerados_games.sort(key=lambda g: g.get("finish_date") or "", reverse=True)
            
            # Platinados ordenados por data de platina (mais recente -> mais antigo)
            platinados_games = [g for g in games if g.get("status") == "Platinado"]
            platinados_games.sort(key=lambda g: g.get("platinum_date") or g.get("finish_date") or "", reverse=True)
            
            wishlist_games = [g for g in games if g.get("status") == "Lista de Desejos"]

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
        self.view_queue_grid.remove_game(game_id)
        self.view_disponiveis_grid.remove_game(game_id)
        self.view_zerados_grid.remove_game(game_id)
        self.view_platinados_grid.remove_game(game_id)
        self.view_wishlist_grid.remove_game(game_id)
        self.view_table.remove_game(game_id)
        self.statusBar().showMessage(f"Jogo removido com sucesso. Total: {len(self.all_games)}")

    def apply_game_mutation(self, saved_game: dict, is_new: bool = False, old_status: str = None):
        """Aplica inserções e edições in-place sem resetar a posição de rolagem."""
        game_id = saved_game.get("id")
        new_status = saved_game.get("status")

        if is_new:
            self.all_games.insert(0, saved_game)
            self.view_table.insert_game(saved_game)
            self.view_game_room.insert_game_by_status(saved_game)

            if new_status in ["Fila", "Pausado"]:
                self.view_queue_grid.insert_game(0, saved_game)
            elif new_status == "Disponível":
                self.view_disponiveis_grid.insert_game(0, saved_game)
            elif new_status in ["Zerado", "Platinado"]:
                self.view_zerados_grid.insert_game(0, saved_game)
                if new_status == "Platinado":
                    self.view_platinados_grid.insert_game(0, saved_game)
            elif new_status == "Lista de Desejos":
                self.view_wishlist_grid.insert_game(0, saved_game)

            self.statusBar().showMessage(f"Jogo '{saved_game.get('title')}' adicionado com sucesso. Total: {len(self.all_games)}")
            return

        # Edição existente
        for i, g in enumerate(self.all_games):
            if g.get("id") == game_id:
                self.all_games[i] = saved_game
                break

        # Se o status não foi alterado, apenas atualiza visualmente os cards existentes
        if old_status == new_status:
            self.view_game_room.update_game(saved_game)
            self.view_queue_grid.update_game(saved_game)
            self.view_disponiveis_grid.update_game(saved_game)
            self.view_zerados_grid.update_game(saved_game)
            self.view_platinados_grid.update_game(saved_game)
            self.view_wishlist_grid.update_game(saved_game)
            self.view_table.update_game(saved_game)
            self.statusBar().showMessage(f"Jogo '{saved_game.get('title')}' atualizado com sucesso.")
            return

        # Se o status mudou:
        # 1. Remove dos grids antigos
        if old_status in ["Fila", "Pausado"]:
            self.view_queue_grid.remove_game(game_id)
        elif old_status == "Disponível":
            self.view_disponiveis_grid.remove_game(game_id)
        elif old_status in ["Zerado", "Platinado"]:
            if new_status not in ["Zerado", "Platinado"]:
                self.view_zerados_grid.remove_game(game_id)
            if old_status == "Platinado" and new_status != "Platinado":
                self.view_platinados_grid.remove_game(game_id)
        elif old_status == "Lista de Desejos":
            self.view_wishlist_grid.remove_game(game_id)

        # 2. Insere ou atualiza nos novos grids
        if new_status in ["Fila", "Pausado"]:
            self.view_queue_grid.insert_game(0, saved_game)
        elif new_status == "Disponível":
            self.view_disponiveis_grid.insert_game(0, saved_game)
        elif new_status in ["Zerado", "Platinado"]:
            if old_status not in ["Zerado", "Platinado"]:
                self.view_zerados_grid.insert_game(0, saved_game)
            else:
                self.view_zerados_grid.update_game(saved_game)
            if new_status == "Platinado" and old_status != "Platinado":
                self.view_platinados_grid.insert_game(0, saved_game)
        elif new_status == "Lista de Desejos":
            self.view_wishlist_grid.insert_game(0, saved_game)

        # 3. Atualiza Game Room e Tabela
        self.view_game_room.remove_game(game_id)
        self.view_game_room.insert_game_by_status(saved_game)
        self.view_table.update_game(saved_game)

        self.statusBar().showMessage(f"Jogo '{saved_game.get('title')}' movido para '{new_status}'.")
