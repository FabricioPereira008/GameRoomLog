from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, QButtonGroup,
    QLineEdit, QPushButton, QFrame, QMessageBox, QGroupBox
)
from PySide6.QtCore import Signal, Qt, QSettings

class SettingsView(QWidget):
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("GameRoom", "GameRoomLog")
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(20)
        main_layout.setAlignment(Qt.AlignTop)

        title = QLabel("⚙️ Configurações do Aplicativo")
        title.setProperty("class", "view-title-large")
        main_layout.addWidget(title)

        # --- SEÇÃO 1: TAMANHO DOS CARDS ---
        size_group = QGroupBox("Tamanho de Exibição dos Cards")
        size_group.setProperty("class", "settings-group")
        size_layout = QVBoxLayout(size_group)
        size_layout.setSpacing(10)

        self.size_button_group = QButtonGroup(self)
        
        self.rb_small = QRadioButton("Pequeno (165px) — Mais cards visíveis por linha")
        self.rb_medium = QRadioButton("Médio (215px) — Padrão balanceado")
        self.rb_large = QRadioButton("Grande (270px) — Capas em destaque")

        self.size_button_group.addButton(self.rb_small, 0)
        self.size_button_group.addButton(self.rb_medium, 1)
        self.size_button_group.addButton(self.rb_large, 2)

        size_layout.addWidget(self.rb_small)
        size_layout.addWidget(self.rb_medium)
        size_layout.addWidget(self.rb_large)

        current_size = self.settings.value("card_size", "medium")
        if current_size == "small":
            self.rb_small.setChecked(True)
        elif current_size == "large":
            self.rb_large.setChecked(True)
        else:
            self.rb_medium.setChecked(True)

        self.size_button_group.idClicked.connect(self.on_size_changed)
        main_layout.addWidget(size_group)

        # --- SEÇÃO 2: INTEGRAÇÃO STEAMGRIDDB ---
        sgdb_group = QGroupBox("Repositório de Capas (SteamGridDB)")
        sgdb_group.setProperty("class", "settings-group")
        sgdb_layout = QVBoxLayout(sgdb_group)
        sgdb_layout.setSpacing(10)

        sgdb_desc = QLabel(
            "A API pública da Steam é usada por padrão. Para buscar automaticamente capas de jogos exclusivos de consoles (Switch, 3DS, PS5, Emuladores), insira sua API Key gratuita do SteamGridDB."
        )
        sgdb_desc.setWordWrap(True)
        sgdb_desc.setProperty("class", "settings-desc")
        sgdb_layout.addWidget(sgdb_desc)

        key_layout = QHBoxLayout()
        self.input_sgdb_key = QLineEdit()
        self.input_sgdb_key.setPlaceholderText("Cole sua chave da API SteamGridDB aqui...")
        self.input_sgdb_key.setText(self.settings.value("steamgriddb_key", ""))
        self.input_sgdb_key.setEchoMode(QLineEdit.PasswordEchoOnEdit)

        btn_save_key = QPushButton("Salvar Chave")
        btn_save_key.setProperty("class", "action-btn")
        btn_save_key.clicked.connect(self.save_steamgriddb_key)

        key_layout.addWidget(self.input_sgdb_key)
        key_layout.addWidget(btn_save_key)
        sgdb_layout.addLayout(key_layout)

        main_layout.addWidget(sgdb_group)

        # --- SEÇÃO 3: SOBRE O SISTEMA ---
        about_group = QGroupBox("Sobre o Sistema")
        about_group.setProperty("class", "settings-group")
        about_layout = QVBoxLayout(about_group)

        info_label = QLabel(
            "<b>GameRoomLog</b> v0.0.4<br>"
            "Ambiente: Linux (CachyOS KDE Plasma)<br>"
            "Arquitetura: FastAPI Backend (REST) + PySide6 Desktop (Qt6)<br>"
            "Desenvolvido sob medida para gerenciamento avançado de Backlog e Anuário Gamer."
        )
        info_label.setProperty("class", "settings-desc")
        about_layout.addWidget(info_label)

        main_layout.addWidget(about_group)
        main_layout.addStretch()

    def on_size_changed(self, button_id: int):
        size_map = {0: "small", 1: "medium", 2: "large"}
        chosen = size_map.get(button_id, "medium")
        self.settings.setValue("card_size", chosen)
        self.settings_changed.emit()

    def save_steamgriddb_key(self):
        key = self.input_sgdb_key.text().strip()
        self.settings.setValue("steamgriddb_key", key)
        QMessageBox.information(self, "Configurações", "Chave do SteamGridDB salva com sucesso!")
        self.settings_changed.emit()
