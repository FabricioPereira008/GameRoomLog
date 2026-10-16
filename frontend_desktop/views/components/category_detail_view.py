import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea, QColorDialog, QMessageBox
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor
from frontend_desktop.views.components.game_grid import ScrollableGameGrid
from frontend_desktop.views.components.yearbook_view import StatCard
from frontend_desktop.api_client.client import api_client
from frontend_desktop.workers import run_async

logger = logging.getLogger(__name__)

class CategoryDetailView(QWidget):
    back_requested = Signal()
    game_selected = Signal(dict)
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("categoryDetailView")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.category_type = ""
        self.category_id = None
        self.category_data = {}
        self.init_ui()


    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # Barra Superior de Navegação (Voltar e Ações)
        top_bar = QHBoxLayout()
        self.btn_back = QPushButton("⬅ Voltar")
        self.btn_back.setProperty("class", "cancel-btn")
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.clicked.connect(self.back_requested.emit)
        top_bar.addWidget(self.btn_back)

        top_bar.addStretch()

        self.btn_edit_color = QPushButton("🎨 Alterar Cor da Tag")
        self.btn_edit_color.setProperty("class", "small-btn")
        self.btn_edit_color.setCursor(Qt.PointingHandCursor)
        self.btn_edit_color.setVisible(False)
        self.btn_edit_color.clicked.connect(self.on_change_color)
        top_bar.addWidget(self.btn_edit_color)

        main_layout.addLayout(top_bar)

        # Banner de Título da Categoria
        self.title_layout = QHBoxLayout()
        self.color_dot = QLabel()
        self.color_dot.setFixedSize(16, 16)
        self.color_dot.setVisible(False)
        
        self.title_label = QLabel("")
        self.title_label.setProperty("class", "view-title-xl")

        self.title_layout.addWidget(self.color_dot)
        self.title_layout.addWidget(self.title_label)
        self.title_layout.addStretch()
        main_layout.addLayout(self.title_layout)

        # Stat Cards (Total de Jogos Zerados e Total de Horas)
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)

        self.card_total_games = StatCard("Jogos Zerados", "0", "🏆")
        self.card_total_hours = StatCard("Horas Totais Jogadas", "0h", "⏱️")

        stats_layout.addWidget(self.card_total_games)
        stats_layout.addWidget(self.card_total_hours)
        stats_layout.addStretch()

        main_layout.addLayout(stats_layout)

        # Subtítulo da Lista de Jogos
        self.section_label = QLabel("🏆 Jogos Zerados / Platinados")
        self.section_label.setProperty("class", "section-header-small")
        main_layout.addWidget(self.section_label)


        # Grid de Cards dos Jogos
        self.game_grid = ScrollableGameGrid()
        self.game_grid.game_selected.connect(self.game_selected.emit)
        main_layout.addWidget(self.game_grid)

    DETAIL_FETCHERS = {
        "genre": ("get_genre_details", "{}"),
        "platform": ("get_platform_details", "🎮 {}"),
        "franchise": ("get_franchise_details", "👾 {}"),
    }

    def load_category(self, category_type: str, category_id: int):
        self.category_type = category_type
        self.category_id = category_id
        if category_type not in self.DETAIL_FETCHERS:
            self._on_category_loaded(category_type, category_id, {})
            return
        fetcher = getattr(api_client, self.DETAIL_FETCHERS[category_type][0])
        run_async(
            self, fetcher,
            lambda data: self._on_category_loaded(category_type, category_id, data),
            lambda msg: logger.error("Erro ao carregar detalhes da categoria: %s", msg),
            category_id,
        )

    def _on_category_loaded(self, category_type: str, category_id: int, data: dict):
        if (category_type, category_id) != (self.category_type, self.category_id):
            return  # usuário já navegou para outra categoria
        if category_type in self.DETAIL_FETCHERS:
            self.title_label.setText(self.DETAIL_FETCHERS[category_type][1].format(data.get("name")))
        is_genre = category_type == "genre"
        self.color_dot.setVisible(is_genre)
        self.btn_edit_color.setVisible(is_genre)
        if is_genre:
            color = data.get("color", "#4f46e5")
            self.color_dot.setStyleSheet(f"background-color: {color}; border-radius: 8px; border: 1px solid #ffffff66;")

        self.category_data = data
        self.card_total_games.set_value(str(data.get("total_games", 0)))
        self.card_total_hours.set_value(f"{data.get('total_hours_played', 0)}h")
        self.game_grid.set_games(data.get("games", []))

    def on_change_color(self):
        if self.category_type != "genre" or not self.category_id:
            return

        current_color = self.category_data.get("color", "#4f46e5")
        qcolor = QColorDialog.getColor(QColor(current_color), self, "Escolher Nova Cor do Gênero")
        if qcolor.isValid():
            new_hex = qcolor.name()
            try:
                api_client.update_genre(self.category_id, self.category_data.get("name"), new_hex)
                self.load_category(self.category_type, self.category_id)
                self.data_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Não foi possível atualizar a cor: {e}")
