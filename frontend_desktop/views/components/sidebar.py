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
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(240)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 14, 12, 14)
        main_layout.setSpacing(6)

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

        main_layout.addSpacing(6)

        # Scroll área interna para os botões do menu
        scroll = QScrollArea()
        scroll.setObjectName("sidebarScrollArea")
        scroll.setWidgetResizable(True)
        
        scroll_content = QWidget()
        scroll_content.setObjectName("sidebarNavContainer")
        scroll_content.setAttribute(Qt.WA_StyledBackground, True)
        
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)


        # Grupo de Navegação
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        nav_items = [
            ("🕹️  Game Room", 0),
            ("📋  Fila de Espera", 1),
            ("🟢  Disponíveis", 2),
            ("🏆  Zerados", 3),
            ("👑  Platinados", 4),
            ("📊  Anuário", 5),
            ("🎨  Gêneros", 6),
            ("🎮  Plataformas", 7),
            ("👾  Séries / Franquias", 8),
            ("📑  Biblioteca (Tabela)", 9),
            ("⭐  Lista de Desejos", 10),
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

        # Botão de Configurações fixo na parte inferior
        self.btn_settings = QPushButton("⚙️  Configurações")
        self.btn_settings.setProperty("class", "nav-btn")
        self.btn_settings.setCheckable(True)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.button_group.addButton(self.btn_settings, 11)
        main_layout.addWidget(self.btn_settings)

        self.button_group.idClicked.connect(self.on_nav_clicked)

        # Versão no rodapé
        version_label = QLabel("v0.2.3 • Linux Native")
        version_label.setObjectName("appVersion")
        main_layout.addWidget(version_label)

    def on_nav_clicked(self, nav_id: int):
        self.navigation_changed.emit(nav_id)

    def set_current_index(self, index: int):
        btn = self.button_group.button(index)
        if btn:
            btn.setChecked(True)
