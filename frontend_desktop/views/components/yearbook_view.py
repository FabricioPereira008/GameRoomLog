from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QFrame
)
from PySide6.QtCore import Signal, Qt
from frontend_desktop.views.components.game_grid import GameGrid
from frontend_desktop.api_client.client import api_client

class StatCard(QFrame):
    def __init__(self, title: str, value: str, icon: str = "🎮", parent=None):
        super().__init__(parent)
        self.setProperty("class", "stat-card")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 20px;")
        layout.addWidget(icon_label)

        self.val_label = QLabel(value)
        self.val_label.setProperty("class", "stat-value")
        layout.addWidget(self.val_label)

        title_label = QLabel(title)
        title_label.setProperty("class", "stat-label")
        layout.addWidget(title_label)

    def set_value(self, val: str):
        self.val_label.setText(val)

class YearbookView(QWidget):
    game_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_year = 2026
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Cabeçalho do Anuário com Seletor de Ano
        header = QHBoxLayout()
        title = QLabel("📊 Anuário Gamer")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #fffffe;")
        header.addWidget(title)

        header.addStretch()

        year_label = QLabel("Ano:")
        year_label.setStyleSheet("color: #94a1b2; font-weight: bold;")
        header.addWidget(year_label)

        self.year_combo = QComboBox()
        self.year_combo.setFixedWidth(100)
        self.year_combo.currentIndexChanged.connect(self.on_year_changed)
        header.addWidget(self.year_combo)

        layout.addLayout(header)

        # Métricas / Stat Cards
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)

        self.card_finished = StatCard("Jogos Zerados", "0", "🎮")
        self.card_platinums = StatCard("Platinas", "0", "🏆")
        self.card_hours = StatCard("Horas Jogadas", "0h", "⏱️")
        self.card_avg = StatCard("Média de Nota", "N/A", "⭐")

        stats_layout.addWidget(self.card_finished)
        stats_layout.addWidget(self.card_platinums)
        stats_layout.addWidget(self.card_hours)
        stats_layout.addWidget(self.card_avg)

        layout.addLayout(stats_layout)

        # Subtítulo da Lista
        sub_label = QLabel("Jogos Finalizados no Ano")
        sub_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #fffffe; margin-top: 10px;")
        layout.addWidget(sub_label)

        # Grid dos Jogos do Ano
        self.game_grid = GameGrid()
        self.game_grid.game_selected.connect(self.game_selected.emit)
        layout.addWidget(self.game_grid)

    def load_data(self):
        try:
            overall = api_client.get_overall_stats()
            available_years = overall.get("available_years", [])
            if not available_years:
                available_years = [2026, 2025]

            self.year_combo.blockSignals(True)
            self.year_combo.clear()
            for y in available_years:
                self.year_combo.addItem(str(y), y)
            self.year_combo.blockSignals(False)

            if available_years:
                self.load_year(available_years[0])
        except Exception as e:
            print("Erro ao carregar anuário:", e)

    def on_year_changed(self):
        year = self.year_combo.currentData()
        if year:
            self.load_year(year)

    def load_year(self, year: int):
        try:
            summary = api_client.get_yearbook(year)
            self.card_finished.set_value(str(summary.get("total_games_finished", 0)))
            self.card_platinums.set_value(str(summary.get("total_platinums", 0)))
            self.card_hours.set_value(f"{summary.get('total_hours_played', 0)}h")
            
            avg = summary.get("average_score")
            self.card_avg.set_value(f"{avg}/10" if avg is not None else "N/A")

            self.game_grid.set_games(summary.get("games", []))
        except Exception as e:
            print(f"Erro ao carregar dados do ano {year}:", e)
