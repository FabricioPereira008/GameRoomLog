from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QGridLayout, QFrame, QMessageBox, QInputDialog, QColorDialog
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor
from frontend_desktop.api_client.client import api_client

class ManageItemCard(QFrame):
    edited = Signal()
    deleted = Signal()

    def __init__(self, category_type: str, item_data: dict, parent=None):
        super().__init__(parent)
        self.category_type = category_type  # 'genre', 'platform', 'franchise', 'developer'
        self.item_data = item_data
        self.setProperty("class", "manage-card")
        self.setFixedWidth(260)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Cabeçalho do Card
        header = QHBoxLayout()
        name_label = QLabel(self.item_data.get("name", ""))
        name_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        header.addWidget(name_label)
        header.addStretch()

        if self.category_type == "genre":
            color = self.item_data.get("color", "#4A5568")
            color_dot = QLabel("   ")
            color_dot.setStyleSheet(f"background-color: {color}; border-radius: 6px; border: 1px solid #ffffff44;")
            header.addWidget(color_dot)

        layout.addLayout(header)

        # Contador de Jogos
        count = self.item_data.get("games_count", 0)
        count_label = QLabel(f"🎮 {count} {'jogo cadastrado' if count == 1 else 'jogos cadastrados'}")
        count_label.setStyleSheet("color: #9ca3af; font-size: 12px;")
        layout.addWidget(count_label)

        # Botões de Ação
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_edit = QPushButton("✏️ Editar")
        btn_edit.setProperty("class", "small-btn")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.clicked.connect(self.on_edit)
        btn_layout.addWidget(btn_edit)

        btn_delete = QPushButton("🗑️ Excluir")
        btn_delete.setProperty("class", "delete-btn")
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.clicked.connect(self.on_delete)
        btn_layout.addWidget(btn_delete)

        layout.addLayout(btn_layout)

    def on_edit(self):
        item_id = self.item_data["id"]
        current_name = self.item_data["name"]

        name, ok = QInputDialog.getText(self, "Editar", "Novo nome:", text=current_name)
        if not ok or not name.strip():
            return

        try:
            if self.category_type == "genre":
                color = self.item_data.get("color", "#4A5568")
                # Opção de trocar cor
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
    data_changed = Signal()

    def __init__(self, category_type: str, title: str, parent=None):
        super().__init__(parent)
        self.category_type = category_type  # 'genre', 'platform', 'franchise', 'developer'
        self.title = title
        self.items = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Cabeçalho da Seção
        header = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(f"🔍 Buscar em {self.title.lower()}...")
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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        self.container = QWidget()
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(14)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        scroll.setWidget(self.container)
        layout.addWidget(scroll)

    def load_data(self):
        try:
            if self.category_type == "genre":
                self.items = api_client.get_genres()
            elif self.category_type == "platform":
                self.items = api_client.get_platforms()
            elif self.category_type == "franchise":
                self.items = api_client.get_franchises()
            elif self.category_type == "developer":
                self.items = api_client.get_developers()
            self.render_items()
        except Exception as e:
            print(f"Erro ao carregar {self.category_type}:", e)

    def render_items(self):
        # Limpar grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        search_term = self.search_input.text().lower().strip()
        filtered = [i for i in self.items if search_term in i.get("name", "").lower()]

        if not filtered:
            empty = QLabel(f"Nenhum registro encontrado em {self.title}.")
            empty.setStyleSheet("color: #9ca3af; font-size: 13px; padding: 20px;")
            self.grid_layout.addWidget(empty, 0, 0)
            return

        cols = 3
        for idx, itm in enumerate(filtered):
            card = ManageItemCard(self.category_type, itm)
            card.edited.connect(self.on_item_changed)
            card.deleted.connect(self.on_item_changed)
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)

    def on_item_changed(self):
        self.load_data()
        self.data_changed.emit()

    def on_create_new(self):
        name, ok = QInputDialog.getText(self, f"Novo(a) {self.title}", f"Nome:")
        if not ok or not name.strip():
            return

        try:
            if self.category_type == "genre":
                color = "#4A5568"
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
