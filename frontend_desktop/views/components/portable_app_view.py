"""App do portátil (Android): importar eventos, revisar a caixa de entrada e exportar o catálogo."""
import json
import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from frontend_desktop import preferences
from frontend_desktop.api_client.client import api_client
from frontend_desktop.styles.tokens import COLORS
from frontend_desktop.ui_helpers import set_button_icon, set_status
from frontend_desktop.views.dialogs.inbox_review_dialog import InboxReviewDialog
from frontend_desktop.workers import run_async

logger = logging.getLogger(__name__)


class PortableAppView(QWidget):
    game_saved = Signal(dict, bool, object)  # jogo, é novo, status anterior

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = preferences.settings()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 16, 20)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignTop)
        layout.addWidget(self._build_portable_group())

    def _build_portable_group(self) -> QGroupBox:
        group = QGroupBox("Caixa de entrada do GameRoom Portátil")
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
        self.spin_inbox_threshold.valueChanged.connect(self._save_inbox_threshold)
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

    def _save_inbox_threshold(self, value: int):
        self.settings.setValue("inbox_threshold", value)

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
