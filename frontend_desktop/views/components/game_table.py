from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QHeaderView, QLineEdit, QComboBox, QLabel
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QBrush

class GameTable(QWidget):
    game_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.games = []
        self.filtered_games = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Barra de Filtro e Busca interna
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filtrar por nome ou desenvolvedora...")
        self.search_input.setObjectName("searchBar")
        self.search_input.textChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.search_input)

        self.status_filter = QComboBox()
        self.status_filter.addItem("Todos os Status", None)
        statuses = ["Jogando", "Fila", "Próximo", "Pausado", "Zerado", "Platinado", "Disponível", "Lista de Desejos", "Desisti"]
        for s in statuses:
            self.status_filter.addItem(s, s)
        self.status_filter.currentIndexChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.status_filter)

        layout.addLayout(filter_layout)

        # Tabela
        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "Jogo", "Status", "Gênero", "Plataforma", "Desenvolvedora", 
            "Ano", "Nota", "Dificuldade", "Horas HLTB", "Horas Jogadas", "Tipo"
        ])
        
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 11):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)

        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.itemDoubleClicked.connect(self.on_row_double_clicked)

        layout.addWidget(self.table)

    def set_games(self, games: list):
        self.games = games
        self.apply_filter()

    def apply_filter(self):
        search_text = self.search_input.text().lower().strip()
        status_filter = self.status_filter.currentData()

        self.filtered_games = []
        for g in self.games:
            title = g.get("title", "").lower()
            dev = (g.get("developer") or "").lower()
            status = g.get("status")

            if search_text and (search_text not in title and search_text not in dev):
                continue
            if status_filter and status != status_filter:
                continue

            self.filtered_games.append(g)

        self.render_table()

    def render_table(self):
        self.table.setRowCount(len(self.filtered_games))
        for row, game in enumerate(self.filtered_games):
            # 0: Jogo
            self.table.setItem(row, 0, QTableWidgetItem(game.get("title", "")))

            # 1: Status
            status_item = QTableWidgetItem(game.get("status", ""))
            self.table.setItem(row, 1, status_item)

            # 2: Gênero
            genres = ", ".join([gen.get("name") for gen in game.get("genres", [])])
            self.table.setItem(row, 2, QTableWidgetItem(genres))

            # 3: Plataforma
            plat = game.get("platform", {}).get("name", "") if game.get("platform") else ""
            self.table.setItem(row, 3, QTableWidgetItem(plat))

            # 4: Dev
            self.table.setItem(row, 4, QTableWidgetItem(game.get("developer") or ""))

            # 5: Ano
            year = str(game.get("completion_year") or "")
            self.table.setItem(row, 5, QTableWidgetItem(year))

            # 6: Nota
            score = str(game.get("score") or "")
            self.table.setItem(row, 6, QTableWidgetItem(score))

            # 7: Dificuldade
            diff = str(game.get("difficulty") or "")
            self.table.setItem(row, 7, QTableWidgetItem(diff))

            # 8: HLTB
            hltb = f"{game.get('hltb_hours')}h" if game.get("hltb_hours") else ""
            self.table.setItem(row, 8, QTableWidgetItem(hltb))

            # 9: Jogadas
            played = f"{game.get('played_hours')}h" if game.get("played_hours") else ""
            self.table.setItem(row, 9, QTableWidgetItem(played))

            # 10: Tipo
            self.table.setItem(row, 10, QTableWidgetItem(game.get("play_type", "")))

    def on_row_double_clicked(self, item):
        row = item.row()
        if 0 <= row < len(self.filtered_games):
            self.game_selected.emit(self.filtered_games[row])
