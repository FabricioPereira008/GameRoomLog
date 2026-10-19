import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QGridLayout, QFrame, QMessageBox, QInputDialog, QColorDialog, QSizePolicy, QToolButton, QMenu
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor
from frontend_desktop.api_client.client import api_client
from frontend_desktop.text_search import fold, fold_query
from frontend_desktop.workers import run_async
from frontend_desktop.ui_helpers import add_search_icon
from frontend_desktop.views.components.cover_mosaic import CoverMosaic
from frontend_desktop.preferences import SCOPE_ALL, SCOPE_COMPLETED, category_scope

logger = logging.getLogger(__name__)

def card_count_text(item: dict, scope: str) -> str:
    """"3 jogos · 40h" (só concluídos) ou "30 jogos · 4 zerados · 40h" (todos); horas são as dos concluídos."""
    count = item.get("games_count", 0) or 0
    hours = item.get("total_hours", 0) or 0
    text = f"{count} {'jogo' if count == 1 else 'jogos'}"
    if scope == SCOPE_ALL:
        done = item.get("completed_count", 0) or 0
        text += f" · {done} {'zerado' if done == 1 else 'zerados'}"
    if hours:
        text += f" · {hours:g}h"
    return text


class ManageItemCard(QFrame):
    """Card de uma categoria. Coleta nome/cor/confirmação; a chamada à API fica com a ManagementView
    (o card é recriado após cada mudança, então não pode ser dono de threads)."""
    clicked = Signal(str, int)  # category_type, item_id
    edit_requested = Signal(dict, dict)  # item, campos novos ({"name", "color"?})
    delete_requested = Signal(dict)

    def __init__(self, category_type: str, item_data: dict, parent=None, scope: str = SCOPE_COMPLETED):
        super().__init__(parent)
        self.category_type = category_type
        self.item_data = item_data
        self.scope = scope
        self.setProperty("class", "manage-card")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(230)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 12)
        layout.setSpacing(10)

        # Capa em mosaico (jogos do item); gênero ganha faixa de cor e plataforma, um selo de ícone
        is_genre = self.category_type == "genre"
        is_platform = self.category_type == "platform"
        self.mosaic = CoverMosaic(
            self.item_data.get("cover_samples") or [],
            title=self.item_data.get("name", ""),
            accent_color=self.item_data.get("color", "#4f46e5") if is_genre else None,
            badge_icon=("monitor" if self.item_data.get("icon_name") == "pc" else "gamepad-2") if is_platform else None,
        )
        layout.addWidget(self.mosaic)

        # Editar/Excluir ficam num menu "⋯" que só aparece no hover (também no clique direito)
        self.menu_btn = QToolButton()
        self.menu_btn.setText("⋯")
        self.menu_btn.setProperty("class", "card-menu-btn")
        self.menu_btn.setCursor(Qt.PointingHandCursor)
        self.menu_btn.setFixedSize(30, 26)
        self.menu_btn.setPopupMode(QToolButton.InstantPopup)
        self.menu = QMenu(self.menu_btn)
        self.menu.addAction("Editar", self.on_edit)
        self.menu.addAction("Excluir", self.on_delete)
        self.menu_btn.setMenu(self.menu)
        self.mosaic.set_corner_widget(self.menu_btn)
        self.menu_btn.setVisible(False)

        info = QVBoxLayout()
        info.setContentsMargins(8, 0, 8, 0)
        info.setSpacing(2)
        name_label = QLabel(self.item_data.get("name", ""))
        name_label.setProperty("class", "manage-card-title")
        name_label.setToolTip(self.item_data.get("name", ""))
        info.addWidget(name_label)

        text = card_count_text(self.item_data, self.scope)
        count_label = QLabel(text)
        count_label.setProperty("class", "manage-card-count")
        info.addWidget(count_label)
        layout.addLayout(info)

    def enterEvent(self, event):
        self.menu_btn.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.menu.isVisible():
            self.menu_btn.setVisible(False)
        super().leaveEvent(event)

    def contextMenuEvent(self, event):
        self.menu.exec(event.globalPos())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.category_type, self.item_data["id"])
        super().mousePressEvent(event)

    def on_edit(self):
        name, ok = QInputDialog.getText(self, "Editar", "Novo nome:", text=self.item_data["name"])
        if not ok or not name.strip():
            return
        fields = {"name": name.strip()}
        if self.category_type == "genre":
            color = self.item_data.get("color", "#4f46e5")
            qcolor = QColorDialog.getColor(QColor(color), self, "Escolha a cor da tag")
            fields["color"] = qcolor.name() if qcolor.isValid() else color
        self.edit_requested.emit(self.item_data, fields)

    def on_delete(self):
        name = self.item_data["name"]
        count = self.item_data.get("games_count", 0)
        warn_text = f"Tem certeza que deseja excluir '{name}'?"
        if count > 0:
            warn_text += f"\n\nAtenção: Existem {count} jogos vinculados a este item."
        confirm = QMessageBox.question(self, "Confirmar Exclusão", warn_text, QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self.delete_requested.emit(self.item_data)


def update_category(category_type: str, item: dict, fields: dict):
    """Grava a edição de uma categoria (roda fora da thread da UI)."""
    item_id, name = item["id"], fields["name"]
    if category_type == "genre":
        return api_client.update_genre(item_id, name, fields.get("color") or item.get("color", "#4f46e5"))
    if category_type == "platform":
        return api_client.update_platform(item_id, name, item.get("icon_name"))
    return getattr(api_client, f"update_{category_type}")(item_id, name)


def delete_category(category_type: str, item_id: int):
    return getattr(api_client, f"delete_{category_type}")(item_id)


def create_category(category_type: str, name: str, color: str = ""):
    if category_type == "genre":
        return api_client.create_genre(name, color or "#4f46e5")
    return getattr(api_client, f"create_{category_type}")(name)


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
        self.scope = category_scope()
        run_async(
            self, fetcher,
            lambda items: self._on_items_loaded(seq, items),
            lambda msg: logger.error("Erro ao carregar %s: %s", self.category_type, msg),
            self.scope,
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

        search_term = fold_query(self.search_input.text())
        filtered = [i for i in self.items if search_term in fold(i.get("name"))]

        if not filtered:
            empty = QLabel(f"Nenhum registro encontrado em {self.title}.")
            empty.setProperty("class", "empty-state-text")
            self.grid_layout.addWidget(empty, 0, 0)
            return

        self.current_cols = self.calculate_cols()
        cols = self.current_cols
        for idx, itm in enumerate(filtered):
            card = ManageItemCard(self.category_type, itm, scope=getattr(self, "scope", SCOPE_COMPLETED))
            card.clicked.connect(self.category_selected.emit)
            card.edit_requested.connect(self.on_edit_requested)
            card.delete_requested.connect(self.on_delete_requested)
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_cols = self.calculate_cols()
        if new_cols != self.current_cols:
            self.render_items()

    def on_item_changed(self, *_):
        self.load_data()
        self.data_changed.emit()

    def _on_failed(self, action: str, message: str):
        QMessageBox.critical(self, "Erro", f"Falha ao {action}: {message}")

    def on_edit_requested(self, item: dict, fields: dict):
        run_async(self, update_category, self.on_item_changed, lambda m: self._on_failed("editar", m),
                  self.category_type, item, fields)

    def on_delete_requested(self, item: dict):
        run_async(self, delete_category, self.on_item_changed, lambda m: self._on_failed("excluir", m),
                  self.category_type, item["id"])

    def on_create_new(self):
        name, ok = QInputDialog.getText(self, f"Novo(a) {self.title}", "Nome:")
        if not ok or not name.strip():
            return
        color = ""
        if self.category_type == "genre":
            qcolor = QColorDialog.getColor(QColor("#4f46e5"), self, "Escolha a cor da tag")
            color = qcolor.name() if qcolor.isValid() else "#4f46e5"
        run_async(self, create_category, self.on_item_changed, lambda m: self._on_failed("criar", m),
                  self.category_type, name.strip(), color)
