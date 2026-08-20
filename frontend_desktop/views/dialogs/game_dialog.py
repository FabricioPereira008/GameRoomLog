from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QDoubleSpinBox, QDateEdit, QTextEdit, QPushButton, QLabel, QFileDialog,
    QCheckBox, QMessageBox, QScrollArea, QWidget, QInputDialog
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QPixmap
from datetime import date
from frontend_desktop.api_client.client import api_client

class GameDialog(QDialog):
    def __init__(self, game_data: dict = None, parent=None):
        super().__init__(parent)
        self.game_data = game_data or {}
        self.is_edit = bool(game_data and game_data.get("id"))
        self.cover_filename = self.game_data.get("cover_image")

        self.setWindowTitle("Editar Jogo" if self.is_edit else "Novo Jogo")
        self.resize(550, 680)
        self.init_ui()
        self.load_options()
        self.populate_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # Scroll área para formulários longos
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        container = QWidget()
        form_layout = QFormLayout(container)
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # 1. Título
        self.input_title = QLineEdit()
        self.input_title.setPlaceholderText("Ex: The Legend of Zelda: Tears of the Kingdom")
        form_layout.addRow("Título *:", self.input_title)

        # 2. Desenvolvedora
        self.input_developer = QLineEdit()
        self.input_developer.setPlaceholderText("Ex: Nintendo EPD")
        form_layout.addRow("Desenvolvedora:", self.input_developer)

        # 3. Status
        self.combo_status = QComboBox()
        statuses = ["Disponível", "Fila", "Próximo", "Jogando", "Pausado", "Zerado", "Platinado", "Lista de Desejos", "Desisti"]
        for s in statuses:
            self.combo_status.addItem(s, s)
        form_layout.addRow("Status:", self.combo_status)

        # 4. Plataforma
        plat_layout = QHBoxLayout()
        self.combo_platform = QComboBox()
        btn_add_plat = QPushButton("+")
        btn_add_plat.setFixedWidth(30)
        btn_add_plat.setToolTip("Adicionar nova plataforma")
        btn_add_plat.clicked.connect(self.add_new_platform)
        plat_layout.addWidget(self.combo_platform)
        plat_layout.addWidget(btn_add_plat)
        form_layout.addRow("Plataforma:", plat_layout)

        # 5. Franquia
        fran_layout = QHBoxLayout()
        self.combo_franchise = QComboBox()
        btn_add_fran = QPushButton("+")
        btn_add_fran.setFixedWidth(30)
        btn_add_fran.setToolTip("Adicionar nova franquia")
        btn_add_fran.clicked.connect(self.add_new_franchise)
        fran_layout.addWidget(self.combo_franchise)
        fran_layout.addWidget(btn_add_fran)
        form_layout.addRow("Franquia / Série:", fran_layout)

        # 6. Gênero Principal
        gen_layout = QHBoxLayout()
        self.combo_genre = QComboBox()
        btn_add_gen = QPushButton("+")
        btn_add_gen.setFixedWidth(30)
        btn_add_gen.setToolTip("Adicionar novo gênero")
        btn_add_gen.clicked.connect(self.add_new_genre)
        gen_layout.addWidget(self.combo_genre)
        gen_layout.addWidget(btn_add_gen)
        form_layout.addRow("Gênero:", gen_layout)

        # 7. Horas (HLTB e Jogadas)
        hours_layout = QHBoxLayout()
        self.spin_hltb = QDoubleSpinBox()
        self.spin_hltb.setRange(0, 9999)
        self.spin_hltb.setSuffix(" h")
        
        self.spin_played = QDoubleSpinBox()
        self.spin_played.setRange(0, 9999)
        self.spin_played.setSuffix(" h")

        hours_layout.addWidget(QLabel("HLTB:"))
        hours_layout.addWidget(self.spin_hltb)
        hours_layout.addWidget(QLabel("Jogadas:"))
        hours_layout.addWidget(self.spin_played)
        form_layout.addRow("Tempo:", hours_layout)

        # 8. Nota e Dificuldade (0 a 10)
        score_layout = QHBoxLayout()
        self.spin_score = QDoubleSpinBox()
        self.spin_score.setRange(0, 10)
        self.spin_score.setSingleStep(0.5)
        self.spin_score.setSpecialValueText("Sem nota")

        self.spin_diff = QDoubleSpinBox()
        self.spin_diff.setRange(0, 10)
        self.spin_diff.setSingleStep(0.5)
        self.spin_diff.setSpecialValueText("Sem nota")

        score_layout.addWidget(QLabel("Nota (0-10):"))
        score_layout.addWidget(self.spin_score)
        score_layout.addWidget(QLabel("Dificuldade (0-10):"))
        score_layout.addWidget(self.spin_diff)
        form_layout.addRow("Avaliação:", score_layout)

        # 9. Datas (Finalização e Platina)
        dates_layout = QHBoxLayout()
        self.chk_finish_date = QCheckBox("Zerou em:")
        self.date_finish = QDateEdit(QDate.currentDate())
        self.date_finish.setCalendarPopup(True)
        self.date_finish.setEnabled(False)
        self.chk_finish_date.toggled.connect(self.date_finish.setEnabled)

        self.chk_plat_date = QCheckBox("Platinou em:")
        self.date_plat = QDateEdit(QDate.currentDate())
        self.date_plat.setCalendarPopup(True)
        self.date_plat.setEnabled(False)
        self.chk_plat_date.toggled.connect(self.date_plat.setEnabled)

        dates_layout.addWidget(self.chk_finish_date)
        dates_layout.addWidget(self.date_finish)
        dates_layout.addWidget(self.chk_plat_date)
        dates_layout.addWidget(self.date_plat)
        form_layout.addRow("Datas:", dates_layout)

        # 10. Tipo e Formato
        extra_layout = QHBoxLayout()
        self.combo_play_type = QComboBox()
        self.combo_play_type.addItems(["Primeira Jogada", "Rejogada"])

        self.combo_format = QComboBox()
        self.combo_format.addItems(["Digital", "Físico", "Emulado"])

        self.chk_favorite = QCheckBox("⭐ Favorito")

        extra_layout.addWidget(self.combo_play_type)
        extra_layout.addWidget(self.combo_format)
        extra_layout.addWidget(self.chk_favorite)
        form_layout.addRow("Detalhes:", extra_layout)

        # 11. Imagem de Capa
        cover_layout = QHBoxLayout()
        self.btn_select_cover = QPushButton("Escolher Imagem de Capa...")
        self.btn_select_cover.clicked.connect(self.choose_cover_image)
        self.lbl_cover_status = QLabel("Nenhuma imagem selecionada" if not self.cover_filename else "Capa definida")
        self.lbl_cover_status.setStyleSheet("color: #72757e;")
        cover_layout.addWidget(self.btn_select_cover)
        cover_layout.addWidget(self.lbl_cover_status)
        form_layout.addRow("Capa:", cover_layout)

        # 12. Anotações / Review
        self.input_notes = QTextEdit()
        self.input_notes.setPlaceholderText("Escreva aqui suas impressões, review ou dicas do jogo...")
        self.input_notes.setFixedHeight(90)
        form_layout.addRow("Anotações:", self.input_notes)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Botões de Ação
        btn_box = QHBoxLayout()
        if self.is_edit:
            self.btn_delete = QPushButton("🗑️ Excluir Jogo")
            self.btn_delete.setStyleSheet("background-color: #e53e3e; color: white; border-radius: 6px; padding: 8px 12px;")
            self.btn_delete.clicked.connect(self.delete_game)
            btn_box.addWidget(self.btn_delete)

        btn_box.addStretch()

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setProperty("class", "cancel-btn")
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Salvar Jogo")
        self.btn_save.setProperty("class", "action-btn")
        self.btn_save.clicked.connect(self.save_game)
        btn_box.addWidget(self.btn_save)

        main_layout.addLayout(btn_box)

    def load_options(self):
        try:
            # Plataformas
            self.combo_platform.clear()
            self.combo_platform.addItem("Nenhuma", None)
            for p in api_client.get_platforms():
                self.combo_platform.addItem(p["name"], p["id"])

            # Franquias
            self.combo_franchise.clear()
            self.combo_franchise.addItem("Nenhuma", None)
            for f in api_client.get_franchises():
                self.combo_franchise.addItem(f["name"], f["id"])

            # Gêneros
            self.combo_genre.clear()
            self.combo_genre.addItem("Nenhum", None)
            for g in api_client.get_genres():
                self.combo_genre.addItem(g["name"], g["id"])
        except Exception as e:
            print("Erro ao carregar opções:", e)

    def populate_data(self):
        if not self.is_edit:
            return

        self.input_title.setText(self.game_data.get("title", ""))
        self.input_developer.setText(self.game_data.get("developer") or "")
        
        status = self.game_data.get("status")
        if status:
            idx = self.combo_status.findText(status)
            if idx >= 0:
                self.combo_status.setCurrentIndex(idx)

        # Platform
        plat = self.game_data.get("platform")
        if plat:
            idx = self.combo_platform.findData(plat.get("id"))
            if idx >= 0:
                self.combo_platform.setCurrentIndex(idx)

        # Franchise
        fran = self.game_data.get("franchise")
        if fran:
            idx = self.combo_franchise.findData(fran.get("id"))
            if idx >= 0:
                self.combo_franchise.setCurrentIndex(idx)

        # Genre
        genres = self.game_data.get("genres", [])
        if genres:
            idx = self.combo_genre.findData(genres[0].get("id"))
            if idx >= 0:
                self.combo_genre.setCurrentIndex(idx)

        self.spin_hltb.setValue(self.game_data.get("hltb_hours") or 0.0)
        self.spin_played.setValue(self.game_data.get("played_hours") or 0.0)

        if self.game_data.get("score") is not None:
            self.spin_score.setValue(self.game_data.get("score"))
        if self.game_data.get("difficulty") is not None:
            self.spin_diff.setValue(self.game_data.get("difficulty"))

        if self.game_data.get("finish_date"):
            fdate = QDate.fromString(self.game_data["finish_date"], "yyyy-MM-dd")
            if fdate.isValid():
                self.date_finish.setDate(fdate)
                self.chk_finish_date.setChecked(True)

        if self.game_data.get("platinum_date"):
            pdate = QDate.fromString(self.game_data["platinum_date"], "yyyy-MM-dd")
            if pdate.isValid():
                self.date_plat.setDate(pdate)
                self.chk_plat_date.setChecked(True)

        self.combo_play_type.setCurrentText(self.game_data.get("play_type", "Primeira Jogada"))
        self.combo_format.setCurrentText(self.game_data.get("format", "Digital"))
        self.chk_favorite.setChecked(bool(self.game_data.get("is_favorite")))
        self.input_notes.setText(self.game_data.get("notes") or "")

    def choose_cover_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Imagem de Capa", "", "Imagens (*.png *.jpg *.jpeg *.webp)"
        )
        if file_path:
            filename = api_client.upload_cover(file_path)
            if filename:
                self.cover_filename = filename
                self.lbl_cover_status.setText(f"✓ Imagem carregada: {filename[:15]}...")
                self.lbl_cover_status.setStyleSheet("color: #2cb67d;")
            else:
                QMessageBox.warning(self, "Erro", "Não foi possível enviar a imagem.")

    def add_new_platform(self):
        name, ok = QInputDialog.getText(self, "Nova Plataforma", "Nome da plataforma:")
        if ok and name.strip():
            created = api_client.create_platform(name.strip())
            self.combo_platform.addItem(created["name"], created["id"])
            self.combo_platform.setCurrentIndex(self.combo_platform.count() - 1)

    def add_new_franchise(self):
        name, ok = QInputDialog.getText(self, "Nova Franquia", "Nome da franquia/série:")
        if ok and name.strip():
            created = api_client.create_franchise(name.strip())
            self.combo_franchise.addItem(created["name"], created["id"])
            self.combo_franchise.setCurrentIndex(self.combo_franchise.count() - 1)

    def add_new_genre(self):
        name, ok = QInputDialog.getText(self, "Novo Gênero", "Nome do gênero:")
        if ok and name.strip():
            created = api_client.create_genre(name.strip())
            self.combo_genre.addItem(created["name"], created["id"])
            self.combo_genre.setCurrentIndex(self.combo_genre.count() - 1)

    def save_game(self):
        title = self.input_title.text().strip()
        if not title:
            QMessageBox.warning(self, "Aviso", "O título do jogo é obrigatório.")
            return

        payload = {
            "title": title,
            "developer": self.input_developer.text().strip() or None,
            "status": self.combo_status.currentText(),
            "platform_id": self.combo_platform.currentData(),
            "franchise_id": self.combo_franchise.currentData(),
            "hltb_hours": self.spin_hltb.value(),
            "played_hours": self.spin_played.value(),
            "score": self.spin_score.value() if self.spin_score.value() > 0 else None,
            "difficulty": self.spin_diff.value() if self.spin_diff.value() > 0 else None,
            "play_type": self.combo_play_type.currentText(),
            "format": self.combo_format.currentText(),
            "is_favorite": self.chk_favorite.isChecked(),
            "notes": self.input_notes.toPlainText().strip() or None,
            "cover_image": self.cover_filename
        }

        genre_id = self.combo_genre.currentData()
        payload["genre_ids"] = [genre_id] if genre_id else []

        if self.chk_finish_date.isChecked():
            payload["finish_date"] = self.date_finish.date().toString("yyyy-MM-dd")
            payload["completion_year"] = self.date_finish.date().year()
        else:
            payload["finish_date"] = None
            payload["completion_year"] = None

        if self.chk_plat_date.isChecked():
            payload["platinum_date"] = self.date_plat.date().toString("yyyy-MM-dd")
        else:
            payload["platinum_date"] = None

        try:
            if self.is_edit:
                api_client.update_game(self.game_data["id"], payload)
            else:
                api_client.create_game(payload)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar jogo: {e}")

    def delete_game(self):
        confirm = QMessageBox.question(
            self, "Confirmar Exclusão",
            f"Tem certeza que deseja excluir '{self.game_data.get('title')}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            try:
                api_client.delete_game(self.game_data["id"])
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao excluir jogo: {e}")
