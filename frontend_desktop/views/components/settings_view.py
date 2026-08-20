from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, QButtonGroup,
    QLineEdit, QPushButton, QFrame, QMessageBox, QGroupBox, QFileDialog, QCheckBox,
    QApplication
)
from PySide6.QtCore import Signal, Qt, QSettings
from frontend_desktop.api_client.client import api_client

class SettingsView(QWidget):
    settings_changed = Signal()
    data_imported = Signal()

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

        # --- SEÇÃO 1: IMPORTAÇÃO DO NOTION ---
        import_group = QGroupBox("Importação de Dados (Notion)")
        import_group.setProperty("class", "settings-group")
        import_layout = QVBoxLayout(import_group)
        import_layout.setSpacing(12)

        import_desc = QLabel(
            "Importe todo o seu catálogo de jogos diretamente da pasta exportada do Notion (CSV + Markdowns).<br>"
            "O sistema criará automaticamente as plataformas, gêneros, desenvolvedoras, franquias, "
            "vinculará as datas de zeramento/platina e importará as anotações das subpáginas."
        )
        import_desc.setWordWrap(True)
        import_desc.setProperty("class", "settings-desc")
        import_layout.addWidget(import_desc)

        self.chk_auto_covers = QCheckBox("Buscar capas automaticamente via Steam/SteamGridDB para os jogos importados")
        self.chk_auto_covers.setChecked(True)
        import_layout.addWidget(self.chk_auto_covers)

        btn_import = QPushButton("📦 Selecionar Pasta do Notion e Iniciar Importação")
        btn_import.setProperty("class", "action-btn")
        btn_import.setCursor(Qt.PointingHandCursor)
        btn_import.clicked.connect(self.on_import_notion)
        import_layout.addWidget(btn_import)

        main_layout.addWidget(import_group)

        # --- SEÇÃO 2: TAMANHO DOS CARDS ---
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

        # --- SEÇÃO 3: INTEGRAÇÃO STEAMGRIDDB ---
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

        # --- SEÇÃO 4: SOBRE O SISTEMA ---
        about_group = QGroupBox("Sobre o Sistema")
        about_group.setProperty("class", "settings-group")
        about_layout = QVBoxLayout(about_group)

        info_label = QLabel(
            "<b>GameRoomLog</b> v0.1.0<br>"
            "Ambiente: Linux (CachyOS KDE Plasma)<br>"
            "Arquitetura: FastAPI Backend (REST) + PySide6 Desktop (Qt6)<br>"
            "Desenvolvido sob medida para gerenciamento avançado de Backlog, Importação do Notion e Anuário Gamer."
        )
        info_label.setProperty("class", "settings-desc")
        about_layout.addWidget(info_label)

        main_layout.addWidget(about_group)
        main_layout.addStretch()

    def on_import_notion(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Selecione a Pasta Exportada do Notion (Game Room)",
            "/home/fabricio/Downloads"
        )
        if not folder:
            return

        auto_covers = self.chk_auto_covers.isChecked()

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            res = api_client.import_notion(folder, auto_fetch_covers=auto_covers)
            QApplication.restoreOverrideCursor()

            total = res.get("total_found", 0)
            imported = res.get("imported", 0)
            updated = res.get("updated", 0)
            queue = res.get("covers_queue_count", 0)
            errors = res.get("errors", [])

            msg = (
                f"<b>Importação do Notion Concluída!</b><br><br>"
                f"🎮 Total de jogos encontrados no CSV: <b>{total}</b><br>"
                f"✨ Novos jogos cadastrados: <b>{imported}</b><br>"
                f"🔄 Jogos já existentes atualizados: <b>{updated}</b><br>"
            )
            if auto_covers:
                msg += f"🖼️ Busca de capas em segundo plano: <b>{queue} jogos na fila</b><br>"

            if errors:
                msg += f"<br><small style='color: #f87171;'>Ocorreram {len(errors)} avisos não impeditivos.</small>"

            QMessageBox.information(self, "Sucesso", msg)
            self.data_imported.emit()
            self.settings_changed.emit()

        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Erro na Importação", f"Falha ao importar do Notion:\n\n{e}")

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
