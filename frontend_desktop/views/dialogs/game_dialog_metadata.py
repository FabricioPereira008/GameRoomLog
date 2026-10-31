"""GameDialog: botão "Buscar dados" (desenvolvedora, franquia, gêneros, plataforma e duração)."""
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QDialog, QMessageBox, QPushButton

from frontend_desktop.ui_helpers import set_button_icon
from frontend_desktop.views.dialogs.metadata_preview_dialog import MetadataPreviewDialog


def igdb_credentials() -> dict:
    """Credenciais da IGDB salvas nas Configurações (vazio = o backend usa o .env ou só a Steam)."""
    settings = QSettings("GameRoom", "GameRoomLog")
    creds = {key: (settings.value(key, "") or "").strip() for key in ("igdb_client_id", "igdb_client_secret")}
    return creds if all(creds.values()) else {}


class MetadataMixin:
    """Parte do GameDialog que busca dados do jogo; usa os campos do cartão Identificação e `spin_hltb`."""

    def _build_metadata_button(self) -> QPushButton:
        self.btn_fetch_data = QPushButton("Buscar dados")
        set_button_icon(self.btn_fetch_data, "search")
        self.btn_fetch_data.setProperty("class", "cancel-btn")
        self.btn_fetch_data.setCursor(Qt.PointingHandCursor)
        self.btn_fetch_data.setToolTip("Busca desenvolvedora, franquia, gêneros, plataforma e duração "
                                       "(IGDB / Steam / HowLongToBeat)")
        self.btn_fetch_data.clicked.connect(self.fetch_game_data)
        return self.btn_fetch_data

    def current_metadata_values(self) -> dict:
        return {
            "developer": self.combo_developer.currentText().strip(),
            "franchise": self.combo_franchise.currentText().strip(),
            "genre": self.combo_genre.currentText().strip(),
            "genre2": self.combo_genre2.currentText().strip(),
            "platform": self.combo_platform.currentText().strip() if self.combo_platform.currentData() else "",
            "hltb_hours": self.spin_hltb.value(),
        }

    def fetch_game_data(self):
        title = self.input_title.text().strip()
        if not title:
            QMessageBox.warning(self, "Aviso", "Digite o título do jogo antes de buscar os dados.")
            return
        dialog = MetadataPreviewDialog(title, self.current_metadata_values(), igdb_credentials(), parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.apply_metadata(dialog.chosen)

    def apply_metadata(self, chosen: dict):
        for field, combo in (("developer", self.combo_developer), ("franchise", self.combo_franchise),
                             ("genre", self.combo_genre), ("genre2", self.combo_genre2)):
            if chosen.get(field):
                combo.setEditText(chosen[field])
        if chosen.get("platform"):
            idx = self.combo_platform.findText(chosen["platform"], Qt.MatchFixedString)
            if idx >= 0:
                self.combo_platform.setCurrentIndex(idx)
        if chosen.get("hltb_hours"):
            self.spin_hltb.setValue(round(float(chosen["hltb_hours"])))
