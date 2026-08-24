from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QFrame, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Signal, Qt
from frontend_desktop.views.components.game_grid import GameGrid
from frontend_desktop.api_client.client import api_client

class StatCard(QFrame):
    def __init__(self, title: str, value: str, icon: str = "🎮", parent=None):
        super().__init__(parent)
        self.setProperty("class", "stat-card")
        self.setFixedHeight(62)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Ícone em badge compacto
        icon_box = QFrame()
        icon_box.setProperty("class", "stat-icon-box")
        icon_box.setFixedSize(38, 38)
        icon_layout = QVBoxLayout(icon_box)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignCenter)
        
        icon_label = QLabel(icon)
        icon_label.setProperty("class", "yearbook-icon")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_layout.addWidget(icon_label)
        
        layout.addWidget(icon_box)

        # Informações de Valor e Rótulo
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(1)
        info_layout.setAlignment(Qt.AlignVCenter)

        self.val_label = QLabel(value)
        self.val_label.setProperty("class", "stat-value")
        info_layout.addWidget(self.val_label)

        title_label = QLabel(title)
        title_label.setProperty("class", "stat-label")
        info_layout.addWidget(title_label)

        layout.addLayout(info_layout)
        layout.addStretch()

    def set_value(self, val: str):
        self.val_label.setText(val)

class YearbookView(QWidget):
    game_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("yearbookView")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.current_year = 2026
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        # Scroll Area geral para a página do Anuário
        scroll = QScrollArea()
        scroll.setObjectName("yearbookScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setAttribute(Qt.WA_StyledBackground, True)

        container = QWidget()
        container.setObjectName("yearbookScrollContainer")
        container.setAttribute(Qt.WA_StyledBackground, True)

        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(12, 10, 12, 16)
        container_layout.setSpacing(14)
        container_layout.setAlignment(Qt.AlignTop)

        # 1. Cabeçalho do Anuário com Seletor de Ano
        header = QHBoxLayout()
        header.setContentsMargins(4, 0, 4, 0)
        
        header_title = QLabel("Resumo do Ano")
        header_title.setProperty("class", "section-header")
        header.addWidget(header_title)

        header.addStretch()

        year_label = QLabel("Ano:")
        year_label.setProperty("class", "yearbook-year")
        header.addWidget(year_label)

        self.year_combo = QComboBox()
        self.year_combo.setFixedWidth(100)
        self.year_combo.currentIndexChanged.connect(self.on_year_changed)
        header.addWidget(self.year_combo)

        container_layout.addLayout(header)

        # 2. Métricas / Stat Cards (Barra compacta com margens laterais)
        stats_layout = QHBoxLayout()
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(12)

        self.card_finished = StatCard("Jogos Zerados", "0", "🎮")
        self.card_platinums = StatCard("Platinas", "0", "🏆")
        self.card_hours = StatCard("Horas Jogadas", "0h", "⏱️")
        self.card_avg = StatCard("Média de Nota", "N/A", "⭐")

        stats_layout.addWidget(self.card_finished)
        stats_layout.addWidget(self.card_platinums)
        stats_layout.addWidget(self.card_hours)
        stats_layout.addWidget(self.card_avg)

        container_layout.addLayout(stats_layout)

        # 3. Seção Estruturada dos Jogos Finalizados (Sem vácuo vertical)
        self.games_section = QFrame()
        self.games_section.setObjectName("yearbookGamesSection")
        self.games_section.setProperty("class", "game-section-card")
        self.games_section.setAttribute(Qt.WA_StyledBackground, True)

        sec_layout = QVBoxLayout(self.games_section)
        sec_layout.setContentsMargins(14, 14, 14, 14)
        sec_layout.setSpacing(12)
        sec_layout.setAlignment(Qt.AlignTop)

        self.sub_label = QLabel("🏆 Jogos Finalizados")
        self.sub_label.setProperty("class", "section-header")
        sec_layout.addWidget(self.sub_label)

        self.game_grid = GameGrid()
        self.game_grid.game_selected.connect(self.game_selected.emit)
        sec_layout.addWidget(self.game_grid)

        container_layout.addWidget(self.games_section)

        # Adiciona stretch ao final para ancorar tudo no topo sem vácuo
        container_layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

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
            fin_count = summary.get("total_games_finished", 0)
            plat_count = summary.get("total_platinums", 0)
            hours_count = summary.get("total_hours_played", 0)
            avg = summary.get("average_score")

            self.card_finished.set_value(str(fin_count))
            self.card_platinums.set_value(str(plat_count))
            self.card_hours.set_value(f"{int(hours_count)}h")
            self.card_avg.set_value(f"{avg:.1f}/10" if avg is not None else "N/A")

            games = summary.get("games", [])
            self.sub_label.setText(f"🏆 Jogos Finalizados em {year} ({len(games)} {'jogo' if len(games) == 1 else 'jogos'})")
            self.game_grid.set_games(games)
        except Exception as e:
            print(f"Erro ao carregar dados do ano {year}:", e)
