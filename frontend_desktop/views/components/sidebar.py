from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QFrame, QButtonGroup
)
from PySide6.QtCore import Signal, Qt

class Sidebar(QWidget):
    navigation_changed = Signal(int)  # 0: Game Room, 1: Fila, 2: Zerados, 3: Anuário, 4: Biblioteca, 5: Wishlist
    add_game_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarWidget")
        self.setFixedWidth(230)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(8)

        # Cabeçalho do App
        title = QLabel("🎮 Game Room")
        title.setObjectName("appTitle")
        subtitle = QLabel("Organize seu Backlog")
        subtitle.setObjectName("appSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Botão Principal de Adicionar Jogo
        self.btn_add = QPushButton("+ Adicionar Jogo")
        self.btn_add.setObjectName("btnAddGame")
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.clicked.connect(self.add_game_requested.emit)
        layout.addWidget(self.btn_add)

        layout.addSpacing(16)

        # Grupo de Navegação
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        nav_items = [
            ("🕹️  Game Room", 0),
            ("📋  Fila de Espera", 1),
            ("🏆  Zerados & Platinas", 2),
            ("📊  Anuário", 3),
            ("📑  Biblioteca (Tabela)", 4),
            ("⭐  Lista de Desejos", 5),
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

        self.button_group.idClicked.connect(self.on_nav_clicked)

        layout.addStretch()

        # Versão no rodapé
        version_label = QLabel("v0.0.1 • Linux Native")
        version_label.setStyleSheet("color: #72757e; font-size: 10px; text-align: center;")
        layout.addWidget(version_label)

    def on_nav_clicked(self, nav_id: int):
        self.navigation_changed.emit(nav_id)

    def set_current_index(self, index: int):
        btn = self.button_group.button(index)
        if btn:
            btn.setChecked(True)
