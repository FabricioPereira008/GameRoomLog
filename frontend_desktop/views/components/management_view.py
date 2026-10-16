import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QGridLayout, QFrame, QMessageBox, QInputDialog, QColorDialog, QSizePolicy
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor
from frontend_desktop.api_client.client import api_client
from frontend_desktop.workers import run_async
from frontend_desktop.ui_helpers import add_search_icon, make_color_dot, set_button_icon
from frontend_desktop.styles.tokens import COLORS

logger = logging.getLogger(__name__)

class ManageItemCard(QFrame):
    clicked = Signal(str, int)  # category_type, item_id
    edited = Signal()
    deleted = Signal()

    def __init__(self, category_type: str, item_data: dict, parent=None):
        super().__init__(parent)
        self.category_type = category_type
        self.item_data = item_data
        self.setProperty("class", "manage-card")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(230)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Cabeçalho do Card
        header = QHBoxLayout()
        name_label = QLabel(self.item_data.get("name", ""))
        name_label.setProperty("class", "manage-card-title")
        header.addWidget(name_label)
        header.addStretch()

        if self.category_type == "genre":
            color = self.item_data.get("color", "#4f46e5")
            header.addWidget(make_color_dot(color))

        layout.addLayout(header)

        # Contador de Jogos Zerados
        count = self.item_data.get("games_count", 0)
        count_label = QLabel(f"{count} {'jogo zerado' if count == 1 else 'jogos zerados'} · clique para ver")
        count_label.setProperty("class", "manage-card-count")
        layout.addWidget(count_label)


        # Botões de Ação
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_edit = QPushButton("Editar")

        set_button_icon(btn_edit, "pencil")
        btn_edit.setProperty("class", "small-btn")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.clicked.connect(self.on_edit)
        btn_layout.addWidget(btn_edit)

        btn_delete = QPushButton("Excluir")

        set_button_icon(btn_delete, "trash-2", COLORS["danger"])
        btn_delete.setProperty("class", "delete-btn")
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.clicked.connect(self.on_delete)
        btn_layout.addWidget(btn_delete)

        layout.addLayout(btn_layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.category_type, self.item_data["id"])
        super().mousePressEvent(event)

    def on_edit(self):
        item_id = self.item_data["id"]
        current_name = self.item_data["name"]

        name, ok = QInputDialog.getText(self, "Editar", "Novo nome:", text=current_name)
        if not ok or not name.strip():
            return

        try:
            if self.category_type == "genre":
                color = self.item_data.get("color", "#4f46e5")
                qcolor = QColorDialog.getColor(QColor(color), self, "Escolha a cor da tag")
                if qcolor.isValid():
                    color = qcolor.name()
                api_client.update_genre(item_id, name.strip(), color)
            elif self.category_type == "platform":
                api_client.update_platform(item_id, name.strip(), self.item_data.get("icon_name"))
            elif self.category_type == "franchise":
                api_client.update_franchise(item_id, name.strip())
            elif self.category_type == "developer":
                api_client.update_developer(item_id, name.strip())

            self.edited.emit()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao editar: {e}")

    def on_delete(self):
        item_id = self.item_data["id"]
        name = self.item_data["name"]
        count = self.item_data.get("games_count", 0)

        warn_text = f"Tem certeza que deseja excluir '{name}'?"
        if count > 0:
            warn_text += f"\n\nAtenção: Existem {count} jogos vinculados a este item."

        confirm = QMessageBox.question(
            self, "Confirmar Exclusão", warn_text, QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            try:
                if self.category_type == "genre":
                    api_client.delete_genre(item_id)
                elif self.category_type == "platform":
                    api_client.delete_platform(item_id)
                elif self.category_type == "franchise":
                    api_client.delete_franchise(item_id)
                elif self.category_type == "developer":
                    api_client.delete_developer(item_id)

                self.deleted.emit()
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao excluir: {e}")


class ManagementView(QWidget):
    category_selected = Signal(str, int)  # category_type, item_id
    data_changed = Signal()

    def __init__(self, category_type: str, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("managementView")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.category_type = category_type
        self.title = title
        self.items = []
        self.current_cols = 4
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Cabeçalho da Seção
        header = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(f"Buscar em {self.title.lower()}...")
        add_search_icon(self.search_input)
        self.search_input.setFixedWidth(280)
        self.search_input.textChanged.connect(self.render_items)
        header.addWidget(self.search_input)

        header.addStretch()

        self.btn_new = QPushButton(f"+ Novo(a) {self.title}")
        self.btn_new.setProperty("class", "action-btn")
        self.btn_new.setCursor(Qt.PointingHandCursor)
        self.btn_new.clicked.connect(self.on_create_new)
        header.addWidget(self.btn_new)

        layout.addLayout(header)

        # Scroll Area com Grid de Cards
        self.scroll = QScrollArea()
        self.scroll.setObjectName("managementScrollArea")
        self.scroll.setAttribute(Qt.WA_StyledBackground, True)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.container.setObjectName("managementScrollContainer")
        self.container.setAttribute(Qt.WA_StyledBackground, True)
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)


    def calculate_cols(self) -> int:
        available_width = self.scroll.width()
        if available_width <= 200:
            available_width = self.width()
        if available_width <= 200:
            available_width = 1200
        cols = max(2, (available_width - 32) // (250 + 16))
        return cols

    FETCHERS = {
        "genre": "get_genres",
        "platform": "get_platforms",
        "franchise": "get_franchises",
        "developer": "get_developers",
    }

    def load_data(self):
        """Busca os itens em background e renderiza ao terminar (descarta respostas antigas)."""
        fetcher = getattr(api_client, self.FETCHERS[self.category_type])
        self._load_seq = getattr(self, "_load_seq", 0) + 1
        seq = self._load_seq
        run_async(
            self, fetcher,
            lambda items: self._on_items_loaded(seq, items),
            lambda msg: logger.error("Erro ao carregar %s: %s", self.category_type, msg),
        )

    def _on_items_loaded(self, seq: int, items: list):
        if seq != self._load_seq:
            return
        self.items = items
        self.render_items()

    def render_items(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        search_term = self.search_input.text().lower().strip()
        filtered = [i for i in self.items if search_term in i.get("name", "").lower()]

        if not filtered:
            empty = QLabel(f"Nenhum registro encontrado em {self.title}.")
            empty.setProperty("class", "empty-state-text")
            self.grid_layout.addWidget(empty, 0, 0)
            return

        self.current_cols = self.calculate_cols()
        cols = self.current_cols
        for idx, itm in enumerate(filtered):
            card = ManageItemCard(self.category_type, itm)
            card.clicked.connect(self.category_selected.emit)
            card.edited.connect(self.on_item_changed)
            card.deleted.connect(self.on_item_changed)
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_cols = self.calculate_cols()
        if new_cols != self.current_cols:
            self.render_items()

    def on_item_changed(self):
        self.load_data()
        self.data_changed.emit()

    def on_create_new(self):
        name, ok = QInputDialog.getText(self, f"Novo(a) {self.title}", f"Nome:")
        if not ok or not name.strip():
            return

        try:
            if self.category_type == "genre":
                color = "#4f46e5"
                qcolor = QColorDialog.getColor(QColor(color), self, "Escolha a cor da tag")
                if qcolor.isValid():
                    color = qcolor.name()
                api_client.create_genre(name.strip(), color)
            elif self.category_type == "platform":
                api_client.create_platform(name.strip())
            elif self.category_type == "franchise":
                api_client.create_franchise(name.strip())
            elif self.category_type == "developer":
                api_client.create_developer(name.strip())

            self.load_data()
            self.data_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao criar: {e}")
