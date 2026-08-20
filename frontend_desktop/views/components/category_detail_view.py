from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea
)
from PySide6.QtCore import Signal, Qt
from frontend_desktop.views.components.game_grid import GameGrid
from frontend_desktop.views.components.yearbook_view import StatCard
from frontend_desktop.api_client.client import api_client

class CategoryDetailView(QWidget):
    back_requested = Signal()
    game_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.category_type = ""
        self.category_id = None
        self.category_data = {}
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # Barra Superior de Navegação (Voltar)
        top_bar = QHBoxLayout()
        self.btn_back = QPushButton("⬅ Voltar")
        self.btn_back.setProperty("class", "cancel-btn")
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.clicked.connect(self.back_requested.emit)
        top_bar.addWidget(self.btn_back)

        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # Banner de Título da Categoria
        self.title_label = QLabel("")
        self.title_label.setStyleSheet("font-size: 24px; font-weight: 800; color: #ffffff;")
        main_layout.addWidget(self.title_label)

        # Stat Cards (Total de Jogos e Total de Horas)
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)

        self.card_total_games = StatCard("Jogos na Categoria", "0", "🎮")
        self.card_total_hours = StatCard("Horas Totais Jogadas", "0h", "⏱️")

        stats_layout.addWidget(self.card_total_games)
        stats_layout.addWidget(self.card_total_hours)
        stats_layout.addStretch()

        main_layout.addLayout(stats_layout)

        # Subtítulo da Lista de Jogos
        section_label = QLabel("Jogos Cadastrados")
        section_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff; margin-top: 8px;")
        main_layout.addWidget(section_label)

        # Grid de Cards dos Jogos
        self.game_grid = GameGrid()
        self.game_grid.game_selected.connect(self.game_selected.emit)
        main_layout.addWidget(self.game_grid)

    def load_category(self, category_type: str, category_id: int):
        self.category_type = category_type
        self.category_id = category_id
        try:
            if category_type == "genre":
                data = api_client.get_genre_details(category_id)
                self.title_label.setText(f"🎨 {data.get('name')}")
            elif category_type == "platform":
                data = api_client.get_platform_details(category_id)
                self.title_label.setText(f"🎮 {data.get('name')}")
            elif category_type == "franchise":
                data = api_client.get_franchise_details(category_id)
                self.title_label.setText(f"👾 {data.get('name')}")
            else:
                data = {}

            self.category_data = data
            self.card_total_games.set_value(str(data.get("total_games", 0)))
            self.card_total_hours.set_value(f"{data.get('total_hours_played', 0)}h")
            self.game_grid.set_games(data.get("games", []))
        except Exception as e:
            print("Erro ao carregar detalhes da categoria:", e)
