"""Configurações: aparência, repositório de capas e informações do sistema (em abas)."""
import logging
import platform
import time

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton, QRadioButton,
    QScrollArea, QTabWidget, QVBoxLayout, QWidget,
)

from app_version import __version__
from frontend_desktop import preferences
from frontend_desktop.api_client.client import api_client
from frontend_desktop.styles.tokens import COLORS
from frontend_desktop.ui_helpers import set_button_icon, set_status

logger = logging.getLogger(__name__)

CARD_SIZE_OPTIONS = (
    ("small", "Pequeno (130px) — mais cards por linha"),
    ("medium", "Médio (170px) — padrão"),
    ("large", "Grande (230px) — capas em destaque"),
)
SCOPE_OPTIONS = (
    (preferences.SCOPE_COMPLETED, "Só jogos concluídos",
     "Contagens, capas e listas mostram apenas os jogos zerados e platinados."),
    (preferences.SCOPE_ALL, "Todos os jogos",
     "Mostra todos os jogos da categoria, com quantos foram zerados; a página da categoria ganha o filtro de status."),
)


class CoverFetcherThread(QThread):
    progress_updated = Signal(int, int, str, bool)  # current, total, game_title, success
    batch_finished = Signal(int, int)  # total, success_count

    def __init__(self, api_key: str = "", parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        try:
            games = api_client.get_games()
            missing = [g for g in games if not g.get("cover_image")]
            total = len(missing)
            success_count = 0

            for idx, g in enumerate(missing):
                if not self.is_running:
                    break

                gid = g.get("id")
                title = g.get("title", "")
                success = False

                try:
                    res = api_client.auto_cover_game(gid, self.api_key)
                    success = res.get("success", False)
                    if success:
                        success_count += 1
                except Exception as e:
                    logger.warning("Erro ao buscar capa para %s: %s", title, e)

                self.progress_updated.emit(idx + 1, total, title, success)
                # Pausa leve de 0.3s para evitar rate-limit e permitir cancelamento fluido
                time.sleep(0.3)

            self.batch_finished.emit(total, success_count)
        except Exception as e:
            logger.exception("Erro no worker de capas")
            self.batch_finished.emit(0, 0)


class SettingsView(QWidget):
    settings_changed = Signal()
    data_imported = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = preferences.settings()
        self.cover_thread = None
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setProperty("class", "settings-tabs")
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        self.tabs.addTab(self._scrollable(self._build_appearance_tab()), "Aparência")
        self.tabs.addTab(self._scrollable(self._build_covers_tab()), "Capas")
        self.tabs.addTab(self._scrollable(self._build_about_tab()), "Sobre")
        outer.addWidget(self.tabs)

    @staticmethod
    def _scrollable(content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content.setObjectName("settingsScrollContainer")
        scroll.setWidget(content)
        return scroll

    @staticmethod
    def _page() -> tuple:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 16, 16, 20)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignTop)
        return page, layout

    @staticmethod
    def _group(title: str, description: str = "") -> tuple:
        group = QGroupBox(title)
        group.setProperty("class", "settings-group")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        if description:
            desc = QLabel(description)
            desc.setWordWrap(True)
            desc.setProperty("class", "settings-desc")
            layout.addWidget(desc)
        return group, layout

    # --- Aparência ---
    def _build_appearance_tab(self) -> QWidget:
        page, layout = self._page()

        size_group, size_layout = self._group(
            "Tamanho dos cards", "Também dá para trocar pelo seletor P / M / G ao lado dos filtros das listas.")
        self.size_button_group = QButtonGroup(self)
        self.size_buttons = {}
        for size, text in CARD_SIZE_OPTIONS:
            rb = QRadioButton(text)
            self.size_button_group.addButton(rb)
            self.size_buttons[size] = rb
            size_layout.addWidget(rb)
            rb.clicked.connect(lambda _c=False, s=size: preferences.set_card_size(s))
        self.rb_small, self.rb_medium, self.rb_large = (self.size_buttons[k] for k in ("small", "medium", "large"))
        self._sync_card_size(preferences.card_size())
        preferences.notifier.card_size_changed.connect(self._sync_card_size)
        layout.addWidget(size_group)

        scope_group, scope_layout = self._group(
            "Páginas de Gêneros, Plataformas e Séries", "O que entra nas contagens, capas e listas dessas páginas.")
        self.scope_buttons = {}
        scope_group_buttons = QButtonGroup(self)
        current = preferences.category_scope()
        for scope, text, hint in SCOPE_OPTIONS:
            rb = QRadioButton(text)
            rb.setChecked(scope == current)
            scope_group_buttons.addButton(rb)
            self.scope_buttons[scope] = rb
            scope_layout.addWidget(rb)
            hint_label = QLabel(hint)
            hint_label.setWordWrap(True)
            hint_label.setProperty("class", "settings-hint")
            scope_layout.addWidget(hint_label)
            rb.clicked.connect(lambda _c=False, sc=scope: self.on_scope_changed(sc))
        layout.addWidget(scope_group)
        return page

    def _sync_card_size(self, size: str) -> None:
        btn = self.size_buttons.get(size)
        if btn and not btn.isChecked():
            btn.setChecked(True)

    def on_scope_changed(self, scope: str) -> None:
        if scope != preferences.category_scope():
            preferences.set_category_scope(scope)
            self.settings_changed.emit()

    # --- Capas ---
    def _build_covers_tab(self) -> QWidget:
        page, layout = self._page()
        sgdb_group, sgdb_layout = self._group(
            "Repositório de capas (Steam / SteamGridDB)",
            "A API pública da Steam é usada por padrão. Para capas de jogos de console e emuladores "
            "(Switch, 3DS, PS5...), informe sua API Key gratuita do SteamGridDB.",
        )
        key_layout = QHBoxLayout()
        self.input_sgdb_key = QLineEdit()
        self.input_sgdb_key.setPlaceholderText("Cole sua chave da API SteamGridDB aqui...")
        self.input_sgdb_key.setText(self.settings.value("steamgriddb_key", ""))
        self.input_sgdb_key.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        btn_save_key = QPushButton("Salvar chave")
        btn_save_key.setProperty("class", "cancel-btn")
        btn_save_key.setCursor(Qt.PointingHandCursor)
        btn_save_key.clicked.connect(self.save_steamgriddb_key)
        key_layout.addWidget(self.input_sgdb_key)
        key_layout.addWidget(btn_save_key)
        sgdb_layout.addLayout(key_layout)
        layout.addWidget(sgdb_group)

        batch_group, batch_layout = self._group(
            "Capas faltantes", "Busca, um jogo por vez, as capas de todos os jogos que ainda não têm uma.")
        batch_btn_layout = QHBoxLayout()
        self.btn_batch_covers = QPushButton("Buscar capas faltantes")
        set_button_icon(self.btn_batch_covers, "image", COLORS["on_accent"])
        self.btn_batch_covers.setProperty("class", "action-btn")
        self.btn_batch_covers.setCursor(Qt.PointingHandCursor)
        self.btn_batch_covers.clicked.connect(self.start_batch_cover_fetch)
        batch_btn_layout.addWidget(self.btn_batch_covers)

        self.btn_stop_covers = QPushButton("Parar busca")
        set_button_icon(self.btn_stop_covers, "pause", COLORS["text"])
        self.btn_stop_covers.setProperty("class", "cancel-btn")
        self.btn_stop_covers.setCursor(Qt.PointingHandCursor)
        self.btn_stop_covers.setVisible(False)
        self.btn_stop_covers.clicked.connect(self.stop_batch_cover_fetch)
        batch_btn_layout.addWidget(self.btn_stop_covers)
        batch_btn_layout.addStretch()
        batch_layout.addLayout(batch_btn_layout)

        self.cover_progress_bar = QProgressBar()
        self.cover_progress_bar.setVisible(False)
        self.cover_progress_bar.setTextVisible(True)
        batch_layout.addWidget(self.cover_progress_bar)

        self.lbl_cover_status = QLabel("")
        self.lbl_cover_status.setProperty("class", "card-meta")
        self.lbl_cover_status.setVisible(False)
        batch_layout.addWidget(self.lbl_cover_status)
        layout.addWidget(batch_group)
        return page

    # --- Sobre ---
    def _build_about_tab(self) -> QWidget:
        page, layout = self._page()
        about_group, about_layout = self._group("GameRoomLog")
        info_label = QLabel(
            f"<b>GameRoomLog</b> v{__version__}<br>"
            f"Ambiente: {platform.system()} {platform.release()}<br>"
            "Arquitetura: FastAPI (REST) + PySide6 (Qt6)<br>"
            "Gerenciamento de backlog, anuário gamer e integração com lojas e com o GameRoom Portátil."
        )
        info_label.setProperty("class", "settings-desc")
        about_layout.addWidget(info_label)
        layout.addWidget(about_group)
        return page

    def start_batch_cover_fetch(self):
        if self.cover_thread and self.cover_thread.isRunning():
            return

        api_key = self.settings.value("steamgriddb_key", "")
        self.cover_thread = CoverFetcherThread(api_key=api_key)
        self.cover_thread.progress_updated.connect(self.on_cover_progress)
        self.cover_thread.batch_finished.connect(self.on_cover_batch_finished)

        self.btn_batch_covers.setEnabled(False)
        self.btn_stop_covers.setVisible(True)
        self.cover_progress_bar.setValue(0)
        self.cover_progress_bar.setVisible(True)
        self.lbl_cover_status.setText("Preparando fila de busca de capas...")
        self.lbl_cover_status.setVisible(True)

        self.cover_thread.start()

    def stop_batch_cover_fetch(self):
        if self.cover_thread and self.cover_thread.isRunning():
            self.cover_thread.stop()
            self.lbl_cover_status.setText("Interrompendo busca de capas...")
            self.btn_stop_covers.setEnabled(False)

    def on_cover_progress(self, current: int, total: int, title: str, success: bool):
        if total > 0:
            pct = int((current / total) * 100)
            self.cover_progress_bar.setValue(pct)
            set_status(self.lbl_cover_status, "ok" if success else "error", f"[{current}/{total}] {title}")

    def on_cover_batch_finished(self, total: int, success_count: int):
        self.btn_batch_covers.setEnabled(True)
        self.btn_stop_covers.setVisible(False)
        self.btn_stop_covers.setEnabled(True)
        self.cover_progress_bar.setVisible(False)
        
        if total == 0:
            self.lbl_cover_status.setText("Todos os jogos já possuem capas cadastradas!")
        else:
            self.lbl_cover_status.setText(f"Busca finalizada: {success_count} capas obtidas de {total} jogos verificados.")
        
        # Um único refresh ao final do lote (e não um por capa baixada)
        self.data_imported.emit()

    def save_steamgriddb_key(self):
        key = self.input_sgdb_key.text().strip()
        self.settings.setValue("steamgriddb_key", key)
        QMessageBox.information(self, "Configurações", "Chave do SteamGridDB salva com sucesso!")
        self.settings_changed.emit()
