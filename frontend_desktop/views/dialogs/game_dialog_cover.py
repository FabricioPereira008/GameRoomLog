"""GameDialog: cartão da capa (busca automática, link, arquivo e recorte)."""
import os

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QFrame, QInputDialog, QLabel, QMessageBox, QPushButton

from frontend_desktop.api_client.client import api_client
from frontend_desktop.cover_loader import cover_loader
from frontend_desktop.ui_helpers import set_button_icon, set_status
from frontend_desktop.workers import run_async

COVER_PREVIEW_SIZE = (160, 240)
NO_COVER_TEXT = "Nenhuma imagem selecionada"


class CoverMixin:
    """Parte do GameDialog que cuida da capa; usa `cover_filename`, `input_title` e `_card` do diálogo."""

    def _build_cover_card(self) -> QFrame:
        """Capa: preview, busca automática, link, arquivo local e recorte."""
        card, grid = self._card("Capa")
        card.setFixedWidth(210)

        self.lbl_cover_preview = QLabel("Sem\ncapa")
        self.lbl_cover_preview.setFixedSize(*COVER_PREVIEW_SIZE)
        self.lbl_cover_preview.setProperty("class", "cover-preview")
        self.lbl_cover_preview.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.lbl_cover_preview, 0, 0, 1, 2, Qt.AlignHCenter)

        self.lbl_cover_status = QLabel("" if self.cover_filename else NO_COVER_TEXT)
        self.lbl_cover_status.setProperty("class", "status-muted")
        self.lbl_cover_status.setWordWrap(True)
        grid.addWidget(self.lbl_cover_status, 1, 0, 1, 2)

        self.btn_auto_cover = QPushButton("Buscar automático")
        set_button_icon(self.btn_auto_cover, "wand-sparkles")
        self.btn_auto_cover.setToolTip("Pesquisa e baixa a capa automaticamente pelo título do jogo")
        self.btn_auto_cover.clicked.connect(self.auto_search_cover)

        self.btn_url_cover = QPushButton("Link / URL…")
        set_button_icon(self.btn_url_cover, "link")
        self.btn_url_cover.clicked.connect(self.choose_cover_url)

        self.btn_select_cover = QPushButton("Arquivo…")
        set_button_icon(self.btn_select_cover, "folder-open")
        self.btn_select_cover.clicked.connect(self.choose_cover_image)

        self.btn_edit_cover = QPushButton("Ajustar recorte")
        set_button_icon(self.btn_edit_cover, "crop")
        self.btn_edit_cover.setVisible(False)
        self.btn_edit_cover.clicked.connect(self.open_image_cropper)

        for row, btn in enumerate((self.btn_auto_cover, self.btn_url_cover, self.btn_select_cover, self.btn_edit_cover), 2):
            btn.setProperty("class", "small-btn")
            grid.addWidget(btn, row, 0, 1, 2)
        return card

    def auto_search_cover(self):
        title = self.input_title.text().strip()
        if not title:
            QMessageBox.warning(self, "Aviso", "Digite o título do jogo antes de buscar a capa.")
            return

        self.btn_auto_cover.setEnabled(False)
        self.btn_auto_cover.setText("Buscando...")
        set_status(self.lbl_cover_status, "muted", "Pesquisando nos repositórios...")

        sgdb_key = QSettings("GameRoom", "GameRoomLog").value("steamgriddb_key", "")
        run_async(
            self, api_client.auto_search_cover,
            lambda filename: self._on_auto_cover_done(title, filename),
            lambda _msg: self._on_auto_cover_done(title, None),
            title, api_key=sgdb_key if sgdb_key else None,
        )

    def _on_auto_cover_done(self, title: str, filename):
        self.btn_auto_cover.setEnabled(True)
        self.btn_auto_cover.setText("Buscar automático")

        if filename:
            self.cover_filename = filename
            set_status(self.lbl_cover_status, "ok", f"Capa baixada com sucesso: {filename[:12]}...")
            self.update_cover_preview()
        else:
            set_status(self.lbl_cover_status, "error", "Capa não encontrada automaticamente.")
            QMessageBox.warning(
                self, "Não Encontrado",
                f"Não foi possível encontrar automaticamente uma capa para '{title}'.\nVocê pode colar o link direto da imagem pelo botão 'Link / URL'."
            )

    def choose_cover_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Imagem de Capa", "", "Imagens (*.png *.jpg *.jpeg *.webp)"
        )
        if file_path:
            filename = api_client.upload_cover(file_path)
            if filename:
                self.cover_filename = filename
                set_status(self.lbl_cover_status, "ok", f"Imagem: {filename[:12]}...")
                self.update_cover_preview()
                self.open_image_cropper()
            else:
                QMessageBox.warning(self, "Erro", "Não foi possível enviar a imagem.")

    def choose_cover_url(self):
        url, ok = QInputDialog.getText(self, "Importar Capa por URL", "Cole o link/URL da imagem:")
        if ok and url.strip():
            filename = api_client.upload_cover_url(url.strip())
            if filename:
                self.cover_filename = filename
                set_status(self.lbl_cover_status, "ok", f"Baixado: {filename[:12]}...")
                self.update_cover_preview()
                self.open_image_cropper()
            else:
                QMessageBox.warning(self, "Erro", "Não foi possível baixar a imagem do link fornecido.")

    def update_cover_preview(self):
        """Mostra a capa atual; o download/escala acontece em background (cover_loader)."""
        if not self.cover_filename:
            return
        if self.lbl_cover_status.text() == NO_COVER_TEXT:
            self.lbl_cover_status.setText("")
        pixmap = cover_loader.request(self.cover_filename, *COVER_PREVIEW_SIZE)
        if pixmap is not None:
            self.lbl_cover_preview.setPixmap(pixmap)
            self.btn_edit_cover.setVisible(True)

    def _on_cover_loaded(self, filename: str):
        if filename == self.cover_filename:
            self.update_cover_preview()

    def open_image_cropper(self):
        if not self.cover_filename:
            return
            
        storage_path = api_client.get_cover_path(self.cover_filename)
        if not storage_path:
            return


        from frontend_desktop.views.dialogs.image_cropper_dialog import ImageCropperDialog
        
        dialog = ImageCropperDialog(storage_path, self)
        if dialog.exec() == QDialog.Accepted and dialog.cropped_filepath:
            # Upload da imagem cortada para o servidor substituir a antiga logicamente
            crop_filename = api_client.upload_cover(dialog.cropped_filepath)
            if crop_filename:
                self.cover_filename = crop_filename
                self.update_cover_preview()
                set_status(self.lbl_cover_status, "ok", f"Recorte salvo: {crop_filename[:12]}...")
                
                # Cleanup: deletar temp file local se quiser
                try:
                    os.remove(dialog.cropped_filepath)
                except OSError:
                    pass
