from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QFrame, QButtonGroup, QScrollArea
)
from PySide6.QtCore import Signal, Qt

class Sidebar(QWidget):
    navigation_changed = Signal(int)
    add_game_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarWidget")
        self.setFixedWidth(240)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 16, 12, 16)
        main_layout.setSpacing(8)

        # Cabeçalho do App
        title = QLabel("🎮 Game Room")
        title.setObjectName("appTitle")
        subtitle = QLabel("Organize seu Backlog")
        subtitle.setObjectName("appSubtitle")

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        # Botão Principal de Adicionar Jogo
        self.btn_add = QPushButton("+ Adicionar Jogo")
        self.btn_add.setObjectName("btnAddGame")
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.clicked.connect(self.add_game_requested.emit)
        main_layout.addWidget(self.btn_add)

        main_layout.addSpacing(10)

        # Scroll área interna para os botões do menu se a janela for pequena
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Grupo de Navegação
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        nav_items = [
            ("🕹️  Game Room", 0),
            ("📋  Fila de Espera", 1),
            ("🏆  Zerados", 2),
            ("👑  Platinados", 3),
            ("📊  Anuário", 4),
            ("🎨  Gêneros", 5),
            ("🎮  Plataformas", 6),
            ("👾  Séries / Franquias", 7),
            ("📑  Biblioteca (Tabela)", 8),
            ("⭐  Lista de Desejos", 9),
        ]

        self.nav_buttons = []
        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setProperty("class", "nav-btn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            if index == 0:
                btn.setChecked(True)
            self.button_group.addButton(btn, index)
            layout.addWidget(btn)
            self.nav_buttons.append(btn)

        layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        self.button_group.idClicked.connect(self.on_nav_clicked)

        # Versão no rodapé
        version_label = QLabel("v0.0.2 • Linux Native")
        version_label.setStyleSheet("color: #6b7280; font-size: 10px; text-align: center; padding-top: 6px;")
        main_layout.addWidget(version_label)

    def on_nav_clicked(self, nav_id: int):
        self.navigation_changed.emit(nav_id)

    def set_current_index(self, index: int):
        btn = self.button_group.button(index)
        if btn:
            btn.setChecked(True)
