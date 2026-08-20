from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QPushButton, QLabel, QStatusBar
)
from PySide6.QtCore import Qt
from frontend_desktop.views.components.sidebar import Sidebar
from frontend_desktop.views.components.game_room_view import GameRoomView
from frontend_desktop.views.components.game_grid import GameGrid
from frontend_desktop.views.components.game_table import GameTable
from frontend_desktop.views.components.yearbook_view import YearbookView
from frontend_desktop.views.components.management_view import ManagementView
from frontend_desktop.views.dialogs.game_dialog import GameDialog
from frontend_desktop.api_client.client import api_client

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GameRoomLog — Backlog & Anuário Gamer")
        self.resize(1240, 780)
        self.setMinimumSize(980, 640)
        self.init_ui()
        self.refresh_all_data()

    def init_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
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
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 18, 20, 16)
        content_layout.setSpacing(14)

        # Cabeçalho Superior
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        self.view_title_label = QLabel("🕹️ Game Room")
        self.view_title_label.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff;")
        header_layout.addWidget(self.view_title_label)

        header_layout.addStretch()

        self.btn_refresh = QPushButton("🔄 Atualizar")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setProperty("class", "small-btn")
        self.btn_refresh.clicked.connect(self.refresh_all_data)
        header_layout.addWidget(self.btn_refresh)

        content_layout.addLayout(header_layout)

        # QStackedWidget com as 10 Telas
        self.stack = QStackedWidget()

        # View 0: Game Room (Agora + Fila)
        self.view_game_room = GameRoomView()
        self.view_game_room.game_selected.connect(self.open_edit_game_dialog)
        self.stack.addWidget(self.view_game_room)

        # View 1: Fila de Espera
        self.view_queue_grid = GameGrid()
        self.view_queue_grid.game_selected.connect(self.open_edit_game_dialog)
        self.stack.addWidget(self.view_queue_grid)

        # View 2: Zerados
        self.view_zerados_grid = GameGrid()
        self.view_zerados_grid.game_selected.connect(self.open_edit_game_dialog)
        self.stack.addWidget(self.view_zerados_grid)

        # View 3: Platinados
        self.view_platinados_grid = GameGrid()
        self.view_platinados_grid.game_selected.connect(self.open_edit_game_dialog)
        self.stack.addWidget(self.view_platinados_grid)

        # View 4: Anuário
        self.view_yearbook = YearbookView()
        self.view_yearbook.game_selected.connect(self.open_edit_game_dialog)
        self.stack.addWidget(self.view_yearbook)

        # View 5: Gêneros (Gerenciamento)
        self.view_genres = ManagementView("genre", "Gênero")
        self.view_genres.data_changed.connect(self.refresh_all_data)
        self.stack.addWidget(self.view_genres)

        # View 6: Plataformas (Gerenciamento)
        self.view_platforms = ManagementView("platform", "Plataforma")
        self.view_platforms.data_changed.connect(self.refresh_all_data)
        self.stack.addWidget(self.view_platforms)

        # View 7: Séries / Franquias (Gerenciamento)
        self.view_franchises = ManagementView("franchise", "Série / Franquia")
        self.view_franchises.data_changed.connect(self.refresh_all_data)
        self.stack.addWidget(self.view_franchises)

        # View 8: Biblioteca (Tabela Completa)
        self.view_table = GameTable()
        self.view_table.game_selected.connect(self.open_edit_game_dialog)
        self.stack.addWidget(self.view_table)

        # View 9: Lista de Desejos
        self.view_wishlist_grid = GameGrid()
        self.view_wishlist_grid.game_selected.connect(self.open_edit_game_dialog)
        self.stack.addWidget(self.view_wishlist_grid)

        content_layout.addWidget(self.stack)
        main_layout.addWidget(content_widget)

        # Barra de status no rodapé
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Pronto • Conectado à API local")

    def switch_view(self, index: int):
        self.stack.setCurrentIndex(index)
        titles = [
            "🕹️ Game Room",
            "📋 Fila de Espera",
            "🏆 Jogos Zerados",
            "👑 Jogos Platinados",
            "📊 Anuário Gamer",
            "🎨 Gerenciar Gêneros",
            "🎮 Gerenciar Plataformas",
            "👾 Gerenciar Séries / Franquias",
            "📑 Biblioteca de Jogos (Tabela)",
            "⭐ Lista de Desejos"
        ]
        if 0 <= index < len(titles):
            self.view_title_label.setText(titles[index])

        if index == 4:  # Anuário
            self.view_yearbook.load_data()
        elif index == 5:  # Gêneros
            self.view_genres.load_data()
        elif index == 6:  # Plataformas
            self.view_platforms.load_data()
        elif index == 7:  # Franquias
            self.view_franchises.load_data()
        else:
            self.refresh_all_data()

    def refresh_all_data(self):
        try:
            games = api_client.get_games()

            # Separar por categorias
            now_games = [g for g in games if g.get("status") in ["Jogando", "Próximo", "Pausado"]]
            queue_games = [g for g in games if g.get("status") in ["Fila", "Disponível"]]
            zerados_games = [g for g in games if g.get("status") == "Zerado"]
            platinados_games = [g for g in games if g.get("status") == "Platinado"]
            wishlist_games = [g for g in games if g.get("status") == "Lista de Desejos"]

            # Atualizar views
            self.view_game_room.set_games(now_games, queue_games)
            self.view_queue_grid.set_games(queue_games)
            self.view_zerados_grid.set_games(zerados_games)
            self.view_platinados_grid.set_games(platinados_games)
            self.view_wishlist_grid.set_games(wishlist_games)
            self.view_table.set_games(games)

            cur_idx = self.stack.currentIndex()
            if cur_idx == 4:
                self.view_yearbook.load_data()
            elif cur_idx == 5:
                self.view_genres.load_data()
            elif cur_idx == 6:
                self.view_platforms.load_data()
            elif cur_idx == 7:
                self.view_franchises.load_data()

            self.statusBar().showMessage(f"Total de jogos carregados: {len(games)}")
        except Exception as e:
            self.statusBar().showMessage(f"Erro de conexão com a API: {e}")

    def open_add_game_dialog(self):
        dialog = GameDialog(parent=self)
        if dialog.exec():
            self.refresh_all_data()

    def open_edit_game_dialog(self, game_data: dict):
        dialog = GameDialog(game_data=game_data, parent=self)
        if dialog.exec():
            self.refresh_all_data()
