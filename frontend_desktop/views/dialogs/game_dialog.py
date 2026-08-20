from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit, QPushButton, QLabel, QFileDialog,
    QCheckBox, QMessageBox, QScrollArea, QWidget, QInputDialog, QCompleter
)
from PySide6.QtCore import Qt, QDate, QSettings
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
        self.resize(600, 720)
        self.init_ui()
        self.load_options()
        self.populate_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # Scroll área vertical (desabilitando scroll horizontal)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        container = QWidget()
        form_layout = QFormLayout(container)
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # Helper para estilizar labels do formulário
        def make_label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setProperty("class", "form-label")
            return lbl

        # 1. Título
        self.input_title = QLineEdit()
        self.input_title.setPlaceholderText("Ex: The Legend of Zelda: Tears of the Kingdom")
        form_layout.addRow(make_label("Título *:"), self.input_title)

        # 2. Desenvolvedora (Combobox Editável com Autocomplete)
        self.combo_developer = QComboBox()
        self.combo_developer.setEditable(True)
        self.combo_developer.setInsertPolicy(QComboBox.NoInsert)
        self.combo_developer.lineEdit().setPlaceholderText("Selecione ou digite a desenvolvedora...")
        form_layout.addRow(make_label("Desenvolvedora:"), self.combo_developer)

        # 3. Status
        self.combo_status = QComboBox()
        statuses = ["Disponível", "Fila", "Próximo", "Jogando", "Pausado", "Zerado", "Platinado", "Lista de Desejos", "Desisti"]
        for s in statuses:
            self.combo_status.addItem(s, s)
        form_layout.addRow(make_label("Status:"), self.combo_status)

        # 4. Plataforma
        plat_layout = QHBoxLayout()
        plat_layout.setSpacing(6)
        self.combo_platform = QComboBox()
        btn_add_plat = QPushButton("+")
        btn_add_plat.setFixedWidth(32)
        btn_add_plat.setProperty("class", "small-btn")
        btn_add_plat.setToolTip("Adicionar nova plataforma")
        btn_add_plat.clicked.connect(self.add_new_platform)
        plat_layout.addWidget(self.combo_platform)
        plat_layout.addWidget(btn_add_plat)
        form_layout.addRow(make_label("Plataforma:"), plat_layout)

        # 5. Franquia / Série
        fran_layout = QHBoxLayout()
        fran_layout.setSpacing(6)
        self.combo_franchise = QComboBox()
        btn_add_fran = QPushButton("+")
        btn_add_fran.setFixedWidth(32)
        btn_add_fran.setProperty("class", "small-btn")
        btn_add_fran.setToolTip("Adicionar nova franquia")
        btn_add_fran.clicked.connect(self.add_new_franchise)
        fran_layout.addWidget(self.combo_franchise)
        fran_layout.addWidget(btn_add_fran)
        form_layout.addRow(make_label("Franquia / Série:"), fran_layout)

        # 6. Gênero
        gen_layout = QHBoxLayout()
        gen_layout.setSpacing(6)
        self.combo_genre = QComboBox()
        btn_add_gen = QPushButton("+")
        btn_add_gen.setFixedWidth(32)
        btn_add_gen.setProperty("class", "small-btn")
        btn_add_gen.setToolTip("Adicionar novo gênero")
        btn_add_gen.clicked.connect(self.add_new_genre)
        gen_layout.addWidget(self.combo_genre)
        gen_layout.addWidget(btn_add_gen)
        form_layout.addRow(make_label("Gênero:"), gen_layout)

        # 7. Horas (Inteiros)
        hours_layout = QHBoxLayout()
        hours_layout.setSpacing(8)
        self.spin_hltb = QSpinBox()
        self.spin_hltb.setRange(0, 99999)
        self.spin_hltb.setSuffix(" h")
        
        self.spin_played = QSpinBox()
        self.spin_played.setRange(0, 99999)
        self.spin_played.setSuffix(" h")

        hours_layout.addWidget(QLabel("HLTB:"))
        hours_layout.addWidget(self.spin_hltb)
        hours_layout.addWidget(QLabel("Jogadas:"))
        hours_layout.addWidget(self.spin_played)
        form_layout.addRow(make_label("Tempo:"), hours_layout)

        # 8. Avaliação (0.0 a 10.0 com 1 decimal)
        score_layout = QHBoxLayout()
        score_layout.setSpacing(8)
        self.spin_score = QDoubleSpinBox()
        self.spin_score.setRange(0, 10)
        self.spin_score.setDecimals(1)
        self.spin_score.setSingleStep(0.1)
        self.spin_score.setSpecialValueText("Sem nota")

        self.spin_diff = QDoubleSpinBox()
        self.spin_diff.setRange(0, 10)
        self.spin_diff.setDecimals(1)
        self.spin_diff.setSingleStep(0.1)
        self.spin_diff.setSpecialValueText("Sem nota")

        score_layout.addWidget(QLabel("Nota (0-10):"))
        score_layout.addWidget(self.spin_score)
        score_layout.addWidget(QLabel("Dificuldade (0-10):"))
        score_layout.addWidget(self.spin_diff)
        form_layout.addRow(make_label("Avaliação:"), score_layout)

        # 9. Datas (Finalização e Platina)
        dates_layout = QHBoxLayout()
        dates_layout.setSpacing(8)
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
        form_layout.addRow(make_label("Datas:"), dates_layout)

        # 10. Tipo de Jogada e Campo Condicional de Rejogada
        play_layout = QHBoxLayout()
        play_layout.setSpacing(8)
        self.combo_play_type = QComboBox()
        self.combo_play_type.addItems(["Primeira Jogada", "Rejogada"])
        self.combo_play_type.currentIndexChanged.connect(self.on_play_type_changed)

        self.lbl_play_count = QLabel("Nº da Jogada:")
        self.spin_play_count = QSpinBox()
        self.spin_play_count.setRange(2, 99)
        self.spin_play_count.setSuffix("ª Vez")
        self.spin_play_count.setValue(2)

        self.lbl_play_count.setVisible(False)
        self.spin_play_count.setVisible(False)

        play_layout.addWidget(self.combo_play_type)
        play_layout.addWidget(self.lbl_play_count)
        play_layout.addWidget(self.spin_play_count)
        play_layout.addStretch()
        form_layout.addRow(make_label("Tipo de Jogada:"), play_layout)

        # 11. Formato e Favorito
        format_layout = QHBoxLayout()
        format_layout.setSpacing(12)
        self.combo_format = QComboBox()
        self.combo_format.addItems(["Digital", "Físico", "Emulado"])
        self.chk_favorite = QCheckBox("⭐ Favorito")
        format_layout.addWidget(self.combo_format)
        format_layout.addWidget(self.chk_favorite)
        format_layout.addStretch()
        form_layout.addRow(make_label("Formato:"), format_layout)

        # 12. Imagem de Capa (Arquivo Local, Link/URL ou Busca Automática)
        cover_layout = QHBoxLayout()
        cover_layout.setSpacing(6)

        self.btn_auto_cover = QPushButton("🤖 Buscar Automático")
        self.btn_auto_cover.setProperty("class", "small-btn")
        self.btn_auto_cover.setToolTip("Pesquisa e baixa a capa automaticamente pelo título do jogo")
        self.btn_auto_cover.clicked.connect(self.auto_search_cover)

        self.btn_url_cover = QPushButton("🔗 Link / URL...")
        self.btn_url_cover.setProperty("class", "small-btn")
        self.btn_url_cover.clicked.connect(self.choose_cover_url)

        self.btn_select_cover = QPushButton("📁 Arquivo...")
        self.btn_select_cover.setProperty("class", "small-btn")
        self.btn_select_cover.clicked.connect(self.choose_cover_image)

        cover_layout.addWidget(self.btn_auto_cover)
        cover_layout.addWidget(self.btn_url_cover)
        cover_layout.addWidget(self.btn_select_cover)
        form_layout.addRow(make_label("Capa do Jogo:"), cover_layout)

        # Status da Capa
        self.lbl_cover_status = QLabel("Nenhuma imagem" if not self.cover_filename else f"✓ Imagem: {self.cover_filename}")
        self.lbl_cover_status.setStyleSheet("color: #2cb67d; font-size: 11px;")
        form_layout.addRow("", self.lbl_cover_status)

        # 13. Anotações
        self.input_notes = QTextEdit()
        self.input_notes.setPlaceholderText("Escreva aqui suas impressões, review ou dicas...")
        self.input_notes.setFixedHeight(85)
        form_layout.addRow(make_label("Anotações:"), self.input_notes)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Botões de Ação
        btn_box = QHBoxLayout()
        if self.is_edit:
            self.btn_delete = QPushButton("🗑️ Excluir Jogo")
            self.btn_delete.setProperty("class", "delete-btn")
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

    def on_play_type_changed(self):
        is_replay = self.combo_play_type.currentText() == "Rejogada"
        self.lbl_play_count.setVisible(is_replay)
        self.spin_play_count.setVisible(is_replay)

    def load_options(self):
        try:
            # Desenvolvedoras
            self.combo_developer.clear()
            devs = api_client.get_developers()
            dev_names = [d["name"] for d in devs]
            self.combo_developer.addItems(dev_names)
            completer = QCompleter(dev_names, self)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            self.combo_developer.setCompleter(completer)

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
        self.combo_developer.setEditText(self.game_data.get("developer") or "")

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

        # Horas
        self.spin_hltb.setValue(int(self.game_data.get("hltb_hours") or 0))
        self.spin_played.setValue(int(self.game_data.get("played_hours") or 0))

        # Avaliações
        if self.game_data.get("score") is not None:
            self.spin_score.setValue(float(self.game_data.get("score")))
        if self.game_data.get("difficulty") is not None:
            self.spin_diff.setValue(float(self.game_data.get("difficulty")))

        # Datas
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

        # Play type e Play count
        play_type = self.game_data.get("play_type", "Primeira Jogada")
        self.combo_play_type.setCurrentText(play_type)
        if play_type == "Rejogada":
            self.spin_play_count.setValue(self.game_data.get("play_count", 2))
        self.on_play_type_changed()

        self.combo_format.setCurrentText(self.game_data.get("format", "Digital"))
        self.chk_favorite.setChecked(bool(self.game_data.get("is_favorite")))
        self.input_notes.setText(self.game_data.get("notes") or "")

    def auto_search_cover(self):
        title = self.input_title.text().strip()
        if not title:
            QMessageBox.warning(self, "Aviso", "Digite o título do jogo antes de buscar a capa.")
            return

        self.btn_auto_cover.setEnabled(False)
        self.btn_auto_cover.setText("Buscando...")
        self.lbl_cover_status.setText("Pesquisando nos repositórios...")

        sgdb_key = QSettings("GameRoom", "GameRoomLog").value("steamgriddb_key", "")
        filename = api_client.auto_search_cover(title, api_key=sgdb_key if sgdb_key else None)

        self.btn_auto_cover.setEnabled(True)
        self.btn_auto_cover.setText("🤖 Buscar Automático")

        if filename:
            self.cover_filename = filename
            self.lbl_cover_status.setText(f"✓ Capa baixada com sucesso: {filename[:12]}...")
            self.lbl_cover_status.setStyleSheet("color: #2cb67d;")
            QMessageBox.information(self, "Sucesso", f"Capa para '{title}' encontrada e salva com sucesso!")
        else:
            self.lbl_cover_status.setText("Capa não encontrada automaticamente.")
            self.lbl_cover_status.setStyleSheet("color: #f87171;")
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
                self.lbl_cover_status.setText(f"✓ Imagem: {filename[:12]}...")
                self.lbl_cover_status.setStyleSheet("color: #2cb67d;")
            else:
                QMessageBox.warning(self, "Erro", "Não foi possível enviar a imagem.")

    def choose_cover_url(self):
        url, ok = QInputDialog.getText(self, "Importar Capa por URL", "Cole o link/URL da imagem:")
        if ok and url.strip():
            filename = api_client.upload_cover_url(url.strip())
            if filename:
                self.cover_filename = filename
                self.lbl_cover_status.setText(f"✓ Baixado: {filename[:12]}...")
                self.lbl_cover_status.setStyleSheet("color: #2cb67d;")
                QMessageBox.information(self, "Sucesso", "Imagem baixada e salva com sucesso!")
            else:
                QMessageBox.warning(self, "Erro", "Não foi possível baixar a imagem do link fornecido.")

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

        play_type = self.combo_play_type.currentText()
        play_count = self.spin_play_count.value() if play_type == "Rejogada" else 1

        payload = {
            "title": title,
            "developer": self.combo_developer.currentText().strip() or None,
            "status": self.combo_status.currentText(),
            "platform_id": self.combo_platform.currentData(),
            "franchise_id": self.combo_franchise.currentData(),
            "hltb_hours": float(self.spin_hltb.value()),
            "played_hours": float(self.spin_played.value()),
            "score": round(self.spin_score.value(), 1) if self.spin_score.value() > 0 else None,
            "difficulty": round(self.spin_diff.value(), 1) if self.spin_diff.value() > 0 else None,
            "play_type": play_type,
            "play_count": play_count,
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
