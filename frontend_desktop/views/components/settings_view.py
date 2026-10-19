"""Configurações: aparência, repositório de capas e informações do sistema (em abas)."""
import logging
import platform
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QProgressBar,
    QPushButton, QRadioButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget,
)

from app_version import __version__
from frontend_desktop import preferences
from frontend_desktop.api_client.client import api_client
from frontend_desktop.styles.tokens import COLORS
from frontend_desktop.ui_helpers import set_button_icon, set_status
from frontend_desktop.workers import run_async

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
        except Exception:
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
        self.tabs.addTab(self._scrollable(self._build_backup_tab()), "Backup")
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
        preferences.subscribe_card_size(self._sync_card_size)
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

        cleanup_group, cleanup_layout = self._group(
            "Capas sem uso",
            "Capas trocadas ou de jogos excluídos ficam ocupando espaço. A limpeza apaga as que nenhum jogo usa "
            "(as guardadas nos backups continuam lá) e também esvazia o cache local delas.",
        )
        cleanup_row = QHBoxLayout()
        self.btn_cleanup_covers = QPushButton("Limpar capas sem uso")
        self.btn_cleanup_covers.setProperty("class", "cancel-btn")
        self.btn_cleanup_covers.setCursor(Qt.PointingHandCursor)
        self.btn_cleanup_covers.setEnabled(False)
        self.btn_cleanup_covers.clicked.connect(self.on_cleanup_covers)
        cleanup_row.addWidget(self.btn_cleanup_covers)
        cleanup_row.addStretch()
        cleanup_layout.addLayout(cleanup_row)
        self.lbl_cleanup_status = QLabel("")
        self.lbl_cleanup_status.setWordWrap(True)
        cleanup_layout.addWidget(self.lbl_cleanup_status)
        layout.addWidget(cleanup_group)
        return page

    @staticmethod
    def format_size(size_bytes: int) -> str:
        mb = (size_bytes or 0) / (1024 * 1024)
        return f"{mb:,.1f} MB".replace(",", "X").replace(".", ",").replace("X", ".")

    def load_orphan_covers(self):
        run_async(self, api_client.orphan_covers, self._on_orphans_loaded,
                  lambda msg: set_status(self.lbl_cleanup_status, "error", f"Não foi possível verificar: {msg}"))

    def _on_orphans_loaded(self, data: dict):
        count = data.get("count") or 0
        self.btn_cleanup_covers.setEnabled(count > 0)
        if count:
            set_status(self.lbl_cleanup_status, "muted",
                       f"{count} capa(s) sem uso, ocupando {self.format_size(data.get('bytes'))}.")
        else:
            set_status(self.lbl_cleanup_status, "muted", "Nenhuma capa sem uso.")

    def on_cleanup_covers(self):
        confirm = QMessageBox.question(
            self, "Limpar capas sem uso", "Apagar as capas que nenhum jogo usa?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self.btn_cleanup_covers.setEnabled(False)
        run_async(self, self.cleanup_covers, self._on_covers_cleaned,
                  lambda msg: set_status(self.lbl_cleanup_status, "error", f"Falha na limpeza: {msg}"))

    @staticmethod
    def cleanup_covers() -> dict:
        """Limpa no servidor e depois o cache local (roda fora da thread da interface)."""
        result = api_client.cleanup_covers()
        in_use = {g.get("cover_image") for g in api_client.get_games()}
        result["cache_removed"] = api_client.prune_cover_cache(in_use)
        return result

    def _on_covers_cleaned(self, result: dict):
        set_status(self.lbl_cleanup_status, "ok",
                   f"{result.get('removed', 0)} capa(s) apagada(s), {self.format_size(result.get('freed_bytes'))} "
                   f"liberados; {result.get('cache_removed', 0)} removida(s) do cache local.")

    # --- Backup ---
    def _build_backup_tab(self) -> QWidget:
        page, layout = self._page()
        group, group_layout = self._group(
            "Cópias de segurança",
            "Uma cópia do banco e das capas é feita automaticamente ao abrir o app (no máximo uma por dia) e as "
            "10 mais recentes são mantidas. Ao restaurar, o estado atual também é guardado antes, então dá para "
            "desfazer. Para guardar fora deste computador, exporte um backup (.zip) e importe-o quando precisar.",
        )
        self.backup_list = QListWidget()
        self.backup_list.setObjectName("backupList")
        self.backup_list.setMinimumHeight(260)
        self.backup_list.currentItemChanged.connect(lambda *_: self._update_backup_buttons())
        group_layout.addWidget(self.backup_list)

        row = QHBoxLayout()
        self.btn_backup_now = QPushButton("Fazer backup agora")
        self.btn_backup_now.setProperty("class", "cancel-btn")
        self.btn_backup_now.setCursor(Qt.PointingHandCursor)
        self.btn_backup_now.clicked.connect(self.on_backup_now)
        row.addWidget(self.btn_backup_now)
        self.btn_restore = QPushButton("Restaurar selecionado")
        self.btn_restore.setProperty("class", "action-btn")
        self.btn_restore.setCursor(Qt.PointingHandCursor)
        self.btn_restore.clicked.connect(self.on_restore)
        row.addWidget(self.btn_restore)
        row.addStretch()
        self.btn_export = QPushButton("Exportar selecionado…")
        self.btn_export.setProperty("class", "cancel-btn")
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setToolTip("Salva o backup selecionado e as capas num arquivo .zip")
        self.btn_export.clicked.connect(self.on_export)
        row.addWidget(self.btn_export)
        self.btn_import = QPushButton("Importar…")
        self.btn_import.setProperty("class", "cancel-btn")
        self.btn_import.setCursor(Qt.PointingHandCursor)
        self.btn_import.setToolTip("Adiciona à lista um backup .zip exportado antes (depois é só restaurá-lo)")
        self.btn_import.clicked.connect(self.on_import)
        row.addWidget(self.btn_import)
        group_layout.addLayout(row)

        self.lbl_backup_status = QLabel("")
        self.lbl_backup_status.setWordWrap(True)
        self.lbl_backup_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        group_layout.addWidget(self.lbl_backup_status)
        layout.addWidget(group)
        self._update_backup_buttons()
        return page

    def showEvent(self, event):
        super().showEvent(event)
        self.load_backups()
        self.load_orphan_covers()

    def load_backups(self, select: Optional[str] = None):
        run_async(self, api_client.list_backups, lambda data: self._on_backups_loaded(data, select),
                  lambda msg: set_status(self.lbl_backup_status, "error", f"Não foi possível listar os backups: {msg}"))

    @staticmethod
    def describe_backup(info: dict) -> str:
        created = str(info.get("created_at", "")).replace("T", " ")[:16]
        try:
            date_part, time_part = created.split(" ")
            y, m, d = date_part.split("-")
            created = f"{d}/{m}/{y} {time_part}"
        except ValueError:
            pass
        games = info.get("games_count")
        size_kb = (info.get("size_bytes") or 0) / 1024
        parts = [created, info.get("reason_label", "")]
        if games is not None:
            parts.append(f"{games} jogos")
        parts.append(f"{size_kb:,.0f} KB".replace(",", "."))
        return "   ·   ".join(p for p in parts if p)

    def _on_backups_loaded(self, data: dict, select: Optional[str] = None):
        self.backup_list.clear()
        for info in data.get("backups", []):
            item = QListWidgetItem(self.describe_backup(info))
            item.setData(Qt.UserRole, info["name"])
            self.backup_list.addItem(item)
            if info["name"] == select:
                self.backup_list.setCurrentItem(item)
        if not self.backup_list.count():
            set_status(self.lbl_backup_status, "muted", "Nenhum backup ainda.")
        elif data.get("folder") and select is None:
            set_status(self.lbl_backup_status, "muted", f"Pasta: {data['folder']}")
        self._update_backup_buttons()

    def _update_backup_buttons(self):
        selected = self.backup_list.currentItem() is not None
        self.btn_restore.setEnabled(selected)
        self.btn_export.setEnabled(selected)

    def on_backup_now(self):
        self.btn_backup_now.setEnabled(False)
        run_async(self, api_client.create_backup, self._on_backup_created, self._on_backup_failed)

    def _on_backup_created(self, info: dict):
        self.btn_backup_now.setEnabled(True)
        self.load_backups()
        set_status(self.lbl_backup_status, "ok", f"Backup criado: {self.describe_backup(info)}")

    def _on_backup_failed(self, message: str):
        self.btn_backup_now.setEnabled(True)
        self.btn_import.setEnabled(True)
        self._update_backup_buttons()
        set_status(self.lbl_backup_status, "error", f"Falha: {message}")

    def on_restore(self):
        item = self.backup_list.currentItem()
        if item is None:
            return
        confirm = QMessageBox.question(
            self, "Restaurar backup",
            f"Restaurar o banco para:\n\n{item.text()}\n\nO estado atual será guardado como um novo backup antes.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self.btn_restore.setEnabled(False)
        run_async(self, api_client.restore_backup, self._on_restored, self._on_backup_failed, item.data(Qt.UserRole))

    def _on_restored(self, result: dict):
        self.load_backups(select=result.get("restored"))
        message = f"Banco restaurado. O estado anterior foi guardado em {result.get('safety_backup')}."
        if result.get("covers_restored"):
            message += f" {result['covers_restored']} capa(s) recuperada(s)."
        set_status(self.lbl_backup_status, "ok", message)
        self.data_imported.emit()  # recarrega todas as telas

    def on_export(self):
        item = self.backup_list.currentItem()
        if item is None:
            return
        name = item.data(Qt.UserRole)
        suggested = str(Path.home() / (name.removesuffix(".db") + ".zip"))
        path, _ = QFileDialog.getSaveFileName(self, "Exportar backup", suggested, "Backup do GameRoom (*.zip)")
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        self.btn_export.setEnabled(False)
        set_status(self.lbl_backup_status, "muted", "Exportando…")
        run_async(self, api_client.export_backup, self._on_exported, self._on_backup_failed, name, path)

    def _on_exported(self, path: str):
        self._update_backup_buttons()
        set_status(self.lbl_backup_status, "ok", f"Backup exportado para {path}")

    def on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar backup", str(Path.home()), "Backup do GameRoom (*.zip)")
        if not path:
            return
        self.btn_import.setEnabled(False)
        set_status(self.lbl_backup_status, "muted", "Importando…")
        run_async(self, api_client.import_backup, self._on_backup_imported, self._on_backup_failed, path)

    def _on_backup_imported(self, info: dict):
        self.btn_import.setEnabled(True)
        self.load_backups(select=info["name"])
        set_status(self.lbl_backup_status, "ok",
                   f"Backup importado: {self.describe_backup(info)}. Ele está selecionado na lista; "
                   "clique em \"Restaurar selecionado\" para usá-lo.")

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
