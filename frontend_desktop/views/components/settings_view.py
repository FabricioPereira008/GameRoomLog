import json
import logging
import platform
from app_version import __version__
import time
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, QButtonGroup,
    QLineEdit, QPushButton, QFrame, QMessageBox, QGroupBox, QFileDialog, QCheckBox,
    QApplication, QProgressBar, QScrollArea, QSpinBox
)
from PySide6.QtCore import Signal, Qt, QSettings, QThread
from frontend_desktop.api_client.client import api_client
from frontend_desktop.styles.tokens import COLORS
from frontend_desktop.ui_helpers import set_button_icon, set_status
from frontend_desktop.views.dialogs.inbox_review_dialog import InboxReviewDialog
from frontend_desktop.workers import run_async

logger = logging.getLogger(__name__)

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
    game_saved = Signal(dict, bool, object)  # jogo, é novo, status anterior (caixa de entrada do portátil)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("GameRoom", "GameRoomLog")
        self.cover_thread = None
        self.init_ui()

    def init_ui(self):
        # Conteúdo rolável: em janelas baixas os grupos não são espremidos
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName("settingsScrollContainer")
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(8, 8, 16, 20)
        main_layout.setSpacing(20)
        main_layout.setAlignment(Qt.AlignTop)

        title = QLabel("Configurações")
        title.setProperty("class", "view-title-large")
        main_layout.addWidget(title)

        # --- SEÇÃO 1: IMPORTAÇÃO DO NOTION ---
        import_group = QGroupBox("Importação de Dados (Notion)")
        import_group.setProperty("class", "settings-group")
        import_layout = QVBoxLayout(import_group)
        import_layout.setSpacing(12)

        import_desc = QLabel(
            "Importe todo o seu catálogo de jogos diretamente da pasta exportada do Notion (CSV).<br>"
            "O sistema criará automaticamente as plataformas, gêneros, desenvolvedoras, franquias "
            "e vinculará as datas de zeramento e platina."
        )
        import_desc.setWordWrap(True)
        import_desc.setProperty("class", "settings-desc")
        import_layout.addWidget(import_desc)

        self.chk_auto_covers = QCheckBox("Iniciar busca automática de capas após importar")
        self.chk_auto_covers.setChecked(True)
        import_layout.addWidget(self.chk_auto_covers)

        btn_import = QPushButton("Selecionar pasta do Notion e importar")
        set_button_icon(btn_import, "upload", COLORS["on_accent"])
        btn_import.setProperty("class", "action-btn")
        btn_import.setCursor(Qt.PointingHandCursor)
        btn_import.clicked.connect(self.on_import_notion)
        import_layout.addWidget(btn_import)

        main_layout.addWidget(import_group)

        main_layout.addWidget(self._build_portable_group())

        # --- SEÇÃO 2: REPOSITÓRIO E BUSCA DE CAPAS EM LOTE ---
        sgdb_group = QGroupBox("Repositório de Capas (Steam / SteamGridDB)")
        sgdb_group.setProperty("class", "settings-group")
        sgdb_layout = QVBoxLayout(sgdb_group)
        sgdb_layout.setSpacing(12)

        sgdb_desc = QLabel(
            "A API pública da Steam é usada por padrão. Para capas de jogos de console e emuladores (Switch, 3DS, PS5, etc.), "
            "insira sua API Key gratuita do SteamGridDB.<br>"
            "Use o botão abaixo para <b>buscar capas faltantes em lote</b> de forma sequencial sem sobrecarregar."
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

        # Controles de Busca em Lote
        batch_btn_layout = QHBoxLayout()
        self.btn_batch_covers = QPushButton("Buscar capas faltantes em lote")
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

        sgdb_layout.addLayout(batch_btn_layout)

        # Progresso da busca
        self.cover_progress_bar = QProgressBar()
        self.cover_progress_bar.setVisible(False)
        self.cover_progress_bar.setTextVisible(True)
        sgdb_layout.addWidget(self.cover_progress_bar)

        self.lbl_cover_status = QLabel("")
        self.lbl_cover_status.setProperty("class", "card-meta")
        self.lbl_cover_status.setVisible(False)
        sgdb_layout.addWidget(self.lbl_cover_status)

        main_layout.addWidget(sgdb_group)

        # --- SEÇÃO 3: TAMANHO DOS CARDS ---
        size_group = QGroupBox("Tamanho de Exibição dos Cards")
        size_group.setProperty("class", "settings-group")
        size_layout = QVBoxLayout(size_group)
        size_layout.setSpacing(10)

        self.size_button_group = QButtonGroup(self)
        
        self.rb_small = QRadioButton("Pequeno (130px) — Mais cards visíveis por linha")
        self.rb_medium = QRadioButton("Médio (170px) — Padrão balanceado")
        self.rb_large = QRadioButton("Grande (230px) — Capas em destaque")

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

        # --- SEÇÃO 4: SOBRE O SISTEMA ---
        about_group = QGroupBox("Sobre o Sistema")
        about_group.setProperty("class", "settings-group")
        about_layout = QVBoxLayout(about_group)

        info_label = QLabel(
            f"<b>GameRoomLog</b> v{__version__}<br>"
            f"Ambiente: {platform.system()} {platform.release()}<br>"
            "Arquitetura: FastAPI Backend (REST) + PySide6 Desktop (Qt6)<br>"
            "Desenvolvido sob medida para gerenciamento avançado de Backlog, Importação do Notion e Anuário Gamer."
        )
        info_label.setProperty("class", "settings-desc")
        about_layout.addWidget(info_label)

        main_layout.addWidget(about_group)
        main_layout.addStretch()

    def _build_portable_group(self) -> QGroupBox:
        group = QGroupBox("App do Portátil")
        group.setProperty("class", "settings-group")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        desc = QLabel(
            "Importe os jogos que você registrou no app Android (arquivo <i>.json</i> exportado por ele). "
            "Cada evento passa por uma revisão antes de alterar o GameRoom; reimportar o mesmo arquivo não duplica nada.<br>"
            "O catálogo exportado permite que o app sugira os títulos e plataformas já cadastrados aqui."
        )
        desc.setWordWrap(True)
        desc.setProperty("class", "settings-desc")
        layout.addWidget(desc)

        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("Semelhança mínima para sugerir um jogo:"))
        self.spin_inbox_threshold = QSpinBox()
        self.spin_inbox_threshold.setRange(50, 100)
        self.spin_inbox_threshold.setSuffix("%")
        self.spin_inbox_threshold.setValue(self.inbox_threshold)
        self.spin_inbox_threshold.valueChanged.connect(lambda v: self.settings.setValue("inbox_threshold", v))
        threshold_row.addWidget(self.spin_inbox_threshold)
        threshold_row.addStretch()
        layout.addLayout(threshold_row)

        buttons = QHBoxLayout()
        self.btn_inbox_import = QPushButton("Importar eventos do portátil...")
        set_button_icon(self.btn_inbox_import, "upload", COLORS["on_accent"])
        self.btn_inbox_import.setProperty("class", "action-btn")
        self.btn_inbox_import.setCursor(Qt.PointingHandCursor)
        self.btn_inbox_import.clicked.connect(self.on_inbox_import)
        buttons.addWidget(self.btn_inbox_import)

        self.btn_inbox_review = QPushButton("Revisar pendentes")
        self.btn_inbox_review.setProperty("class", "cancel-btn")
        self.btn_inbox_review.setEnabled(False)
        self.btn_inbox_review.clicked.connect(self.open_inbox_review)
        buttons.addWidget(self.btn_inbox_review)

        self.btn_export_catalog = QPushButton("Exportar catálogo para o portátil...")
        self.btn_export_catalog.setProperty("class", "cancel-btn")
        self.btn_export_catalog.clicked.connect(self.on_export_catalog)
        buttons.addWidget(self.btn_export_catalog)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.lbl_inbox_status = QLabel("")
        self.lbl_inbox_status.setWordWrap(True)
        layout.addWidget(self.lbl_inbox_status)
        return group

    @property
    def inbox_threshold(self) -> int:
        try:
            return int(self.settings.value("inbox_threshold", 85))
        except (TypeError, ValueError):
            return 85

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_inbox_count()

    def refresh_inbox_count(self):
        run_async(self, api_client.inbox_pending, self._on_inbox_count, lambda _msg: None, self.inbox_threshold)

    def _on_inbox_count(self, data: dict):
        total = data.get("total_events", 0)
        self.btn_inbox_review.setText(f"Revisar pendentes ({total})" if total else "Revisar pendentes")
        self.btn_inbox_review.setEnabled(total > 0)

    def on_inbox_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecione o arquivo exportado pelo app do portátil", str(Path.home() / "Downloads"),
            "Eventos do portátil (*.json);;Todos os arquivos (*)",
        )
        if not path:
            return
        try:
            package = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "Arquivo inválido", f"Não foi possível ler o arquivo:\n\n{e}")
            return
        if not isinstance(package, dict) or package.get("format") != "gameroom-inbox":
            QMessageBox.critical(self, "Arquivo inválido", "Este arquivo não foi exportado pelo app do portátil.")
            return
        self.btn_inbox_import.setEnabled(False)
        run_async(self, api_client.inbox_import, self._on_inbox_imported, self._on_inbox_import_failed, package)

    def _on_inbox_imported(self, res: dict):
        self.btn_inbox_import.setEnabled(True)
        imported, duplicates, rejected = res.get("imported", 0), res.get("duplicates", 0), res.get("rejected", [])
        parts = [f"{imported} evento(s) novo(s)"]
        if duplicates:
            parts.append(f"{duplicates} já recebido(s) antes")
        if rejected:
            parts.append(f"{len(rejected)} inválido(s)")
        set_status(self.lbl_inbox_status, "error" if rejected else "ok", "Importação: " + ", ".join(parts) + ".")
        if rejected:
            QMessageBox.warning(self, "Eventos ignorados", "Alguns eventos não puderam ser lidos:\n\n" + "\n".join(rejected[:20]))
        self.refresh_inbox_count()
        if imported:
            self.open_inbox_review()

    def _on_inbox_import_failed(self, message: str):
        self.btn_inbox_import.setEnabled(True)
        QMessageBox.critical(self, "Erro na importação", f"Falha ao importar os eventos do portátil:\n\n{message}")

    def open_inbox_review(self):
        dialog = InboxReviewDialog(self.inbox_threshold, self)
        dialog.game_saved.connect(self.game_saved)
        dialog.exec()
        if dialog.applied_count:
            set_status(self.lbl_inbox_status, "ok", f"{dialog.applied_count} jogo(s) atualizado(s) pela caixa de entrada.")
        self.refresh_inbox_count()

    def on_export_catalog(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar catálogo para o portátil", str(Path.home() / "gameroom-catalog.json"), "JSON (*.json)",
        )
        if not path:
            return
        self.btn_export_catalog.setEnabled(False)
        run_async(self, api_client.inbox_catalog, lambda data: self._on_catalog_loaded(path, data),
                  self._on_catalog_failed)

    def _on_catalog_loaded(self, path: str, data: dict):
        self.btn_export_catalog.setEnabled(True)
        try:
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            self._on_catalog_failed(str(e))
            return
        set_status(self.lbl_inbox_status, "ok", f"Catálogo com {len(data.get('games', []))} jogos salvo em {path}.")

    def _on_catalog_failed(self, message: str):
        self.btn_export_catalog.setEnabled(True)
        set_status(self.lbl_inbox_status, "error", f"Falha ao exportar o catálogo: {message}")

    def on_import_notion(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Selecione a Pasta Exportada do Notion (Game Room)",
            str(Path.home() / "Downloads")
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
                f"Total de jogos encontrados no CSV: <b>{total}</b><br>"
                f"Novos jogos cadastrados: <b>{imported}</b><br>"
                f"Jogos já existentes atualizados: <b>{updated}</b><br>"
            )
            if auto_covers and queue > 0:
                msg += f"Busca de capas iniciada em lote para <b>{queue} jogos</b>.<br>"

            if errors:
                msg += f"<br><small>Ocorreram {len(errors)} avisos não impeditivos.</small>"

            QMessageBox.information(self, "Sucesso", msg)
            self.data_imported.emit()

            if auto_covers:
                self.start_batch_cover_fetch()

        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Erro na Importação", f"Falha ao importar do Notion:\n\n{e}")

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
