from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QHeaderView, QLineEdit, QComboBox, QLabel
)
from PySide6.QtCore import Signal, Qt

class GameTable(QWidget):
    game_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.games = []
        self.filtered_games = []
        self.batch_size = 50
        self.rendered_count = 0
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

        self.count_label = QLabel("0 jogos")
        self.count_label.setProperty("class", "card-meta")
        filter_layout.addWidget(self.count_label)

        layout.addLayout(filter_layout)

        # Tabela com performance otimizada
        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "Jogo", "Status", "Gênero", "Plataforma", "Desenvolvedora", 
            "Ano", "Nota", "Dificuldade", "Horas HLTB", "Horas Jogadas", "Tipo"
        ])
        
        # Larguras de coluna pré-definidas (sem ResizeToContents custoso)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 11):
            header.setSectionResizeMode(col, QHeaderView.Interactive)

        col_widths = {
            1: 100, 2: 130, 3: 110, 4: 140, 5: 60,
            6: 60, 7: 75, 8: 80, 9: 80, 10: 120
        }
        for col, width in col_widths.items():
            self.table.setColumnWidth(col, width)

        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.itemDoubleClicked.connect(self.on_row_double_clicked)
        self.table.verticalScrollBar().valueChanged.connect(self.on_scroll)

        layout.addWidget(self.table)

    def set_games(self, games: list):
        self.games = list(games)
        self.apply_filter()

    def update_game(self, game_data: dict) -> bool:
        """Atualiza jogo na tabela in-place."""
        game_id = game_data.get("id")
        for i, g in enumerate(self.games):
            if g.get("id") == game_id:
                self.games[i] = game_data
                break
        for i, g in enumerate(self.filtered_games):
            if g.get("id") == game_id:
                self.filtered_games[i] = game_data
                if i < self.rendered_count:
                    self.update_row(i, game_data)
                return True
        return False

    def remove_game(self, game_id: int) -> bool:
        """Remove jogo da tabela in-place."""
        self.games = [g for g in self.games if g.get("id") != game_id]
        idx_in_filtered = -1
        for i, g in enumerate(self.filtered_games):
            if g.get("id") == game_id:
                idx_in_filtered = i
                break
        if idx_in_filtered != -1:
            self.filtered_games.pop(idx_in_filtered)
            if idx_in_filtered < self.rendered_count:
                self.table.removeRow(idx_in_filtered)
                self.rendered_count -= 1
                self.update_count_label()
            return True
        return False

    def insert_game(self, game_data: dict):
        """Insere jogo na tabela in-place."""
        self.games.insert(0, game_data)
        self.apply_filter()

    def update_row(self, row: int, game: dict):
        self.table.setItem(row, 0, QTableWidgetItem(game.get("title", "")))
        self.table.setItem(row, 1, QTableWidgetItem(game.get("status", "")))
        genres = ", ".join([gen.get("name") for gen in game.get("genres", [])])
        self.table.setItem(row, 2, QTableWidgetItem(genres))
        plat = game.get("platform", {}).get("name", "") if game.get("platform") else ""
        self.table.setItem(row, 3, QTableWidgetItem(plat))
        self.table.setItem(row, 4, QTableWidgetItem(game.get("developer") or ""))
        year = str(game.get("completion_year") or "")
        self.table.setItem(row, 5, QTableWidgetItem(year))
        score = str(game.get("score") or "")
        self.table.setItem(row, 6, QTableWidgetItem(score))
        diff = str(game.get("difficulty") or "")
        self.table.setItem(row, 7, QTableWidgetItem(diff))
        hltb = f"{int(game.get('hltb_hours'))}h" if game.get("hltb_hours") else ""
        self.table.setItem(row, 8, QTableWidgetItem(hltb))
        played = f"{int(game.get('played_hours'))}h" if game.get("played_hours") else ""
        self.table.setItem(row, 9, QTableWidgetItem(played))
        self.table.setItem(row, 10, QTableWidgetItem(game.get("play_type", "")))

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

        self.rendered_count = 0
        self.table.setRowCount(0)
        self.load_more_rows()

    def load_more_rows(self):
        total = len(self.filtered_games)
        if self.rendered_count >= total:
            self.update_count_label()
            return

        next_count = min(self.rendered_count + self.batch_size, total)
        batch = self.filtered_games[self.rendered_count:next_count]

        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)

        current_rows = self.table.rowCount()
        self.table.setRowCount(current_rows + len(batch))

        for idx, game in enumerate(batch):
            row = current_rows + idx
            self.update_row(row, game)

        self.rendered_count = next_count
        self.table.setUpdatesEnabled(True)
        self.update_count_label()

    def on_scroll(self, value: int):
        scroll_bar = self.table.verticalScrollBar()
        if value >= scroll_bar.maximum() * 0.75 or value >= scroll_bar.maximum() - 20:
            self.load_more_rows()

    def update_count_label(self):
        total = len(self.filtered_games)
        if self.rendered_count < total:
            self.count_label.setText(f"Exibindo {self.rendered_count} de {total} jogos (Role para carregar mais)")
        else:
            self.count_label.setText(f"{total} jogos encontrados")

    def on_row_double_clicked(self, item):
        row = item.row()
        if 0 <= row < len(self.filtered_games):
            self.game_selected.emit(self.filtered_games[row])
