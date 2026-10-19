import logging
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit, QPushButton, QLabel, QFileDialog,
    QCheckBox, QMessageBox, QScrollArea, QWidget, QInputDialog, QCompleter
)
from PySide6.QtCore import Qt, QDate, QSettings
from frontend_desktop.api_client.client import api_client
from frontend_desktop.workers import run_async
from frontend_desktop.cover_loader import cover_loader
from frontend_desktop.styles.tokens import COLORS
from frontend_desktop.text_search import fold
from frontend_desktop.ui_helpers import set_button_icon, set_status


logger = logging.getLogger(__name__)

COVER_PREVIEW_SIZE = (160, 240)
STATUSES = ["Disponível", "Fila", "Próximo", "Jogando", "Zerado", "Platinado", "Lista de Desejos"]
FORMATS = ["Digital", "Físico", "Emulado"]


NO_COVER_TEXT = "Nenhuma imagem selecionada"


def brief_label(brief: dict) -> str:
    """Rótulo de um jogo na escolha do original: "Hades (PC, 2020)"."""
    extra = [x for x in (brief.get("platform"), brief.get("completion_year")) if x]
    return f"{brief['title']} ({', '.join(str(x) for x in extra)})" if extra else brief["title"]


def replay_group(briefs: list, game_id, replay_of_id) -> list:
    """Jogadas do mesmo jogo (o original e as rejogadas vinculadas), da mais antiga para a mais recente."""
    root = replay_of_id or game_id
    if root is None:
        return []
    return sorted((b for b in briefs if b["id"] == root or b.get("replay_of_id") == root), key=lambda b: b["id"])


def describe_plays(group: list, current_id=None) -> str:
    """ "1ª: 2020 · Zerado · nota 9  |  2ª (esta): Jogando" """
    parts = []
    for number, play in enumerate(group, start=1):
        details = [str(play["completion_year"])] if play.get("completion_year") else []
        details.append(play.get("status") or "")
        if play.get("score") is not None:
            details.append(f"nota {play['score']:g}")
        mark = " (esta)" if play["id"] == current_id else ""
        parts.append(f"{number}ª{mark}: {' · '.join(d for d in details if d)}")
    return "  |  ".join(parts)


class OptionalDateEdit(QDateEdit):
    """Campo de data que começa vazio ("Selecione a data") e só assume um valor quando o usuário interage."""
    BLANK = QDate(1970, 1, 1)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd/MM/yyyy")
        self.setMinimumDate(self.BLANK)
        self.setSpecialValueText("Selecione a data")
        self.setDate(self.BLANK)

    def is_blank(self) -> bool:
        return self.date() == self.BLANK

    def date_or_none(self):
        return None if self.is_blank() else self.date()

    def set_optional_date(self, value) -> None:
        self.setDate(value if value is not None and value.isValid() else self.BLANK)

    def _start_today(self) -> bool:
        if self.is_blank():
            self.setDate(QDate.currentDate())
            return True
        return False

    def mousePressEvent(self, event):
        # o calendário abre no mês atual, não em 1970; o clique que preenche não conta como passo das setas
        self._skip_step = self._start_today()
        super().mousePressEvent(event)
        self._skip_step = False

    def stepBy(self, steps):
        if getattr(self, "_skip_step", False) or self._start_today():
            return
        super().stepBy(steps)

    def wheelEvent(self, event):
        if self.is_blank():
            event.ignore()  # rolar a página não deve preencher a data sem querer
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.setDate(self.BLANK)
            return
        super().keyPressEvent(event)


class GameDialog(QDialog):
    def __init__(self, game_data: dict = None, parent=None):
        super().__init__(parent)
        self.game_data = game_data or {}
        self.is_edit = bool(game_data and game_data.get("id"))
        self.cover_filename = self.game_data.get("cover_image")
        self.saved_game = None
        self.is_deleted = False
        self._briefs = None  # resumo dos jogos, carregado só quando o vínculo de rejogada é usado
        self._briefs_loading = False

        self.setWindowTitle("Editar Jogo" if self.is_edit else "Novo Jogo")
        self.setMinimumSize(820, 600)
        self.resize(900, 780)

        self.init_ui()
        cover_loader.loaded.connect(self._on_cover_loaded)
        self.load_options()

    def init_ui(self):
        self.setObjectName("gameDialog")
        self.setAttribute(Qt.WA_StyledBackground, True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        self._build_header(main_layout)

        scroll = QScrollArea()
        scroll.setObjectName("gameDialogScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setAttribute(Qt.WA_StyledBackground, True)

        container = QWidget()
        container.setObjectName("gameDialogContainer")
        container.setAttribute(Qt.WA_StyledBackground, True)
        body = QHBoxLayout(container)
        body.setContentsMargins(0, 0, 8, 0)
        body.setSpacing(16)

        body.addWidget(self._build_cover_card(), 0, Qt.AlignTop)
        right = QVBoxLayout()
        right.setSpacing(16)
        right.addWidget(self._build_identity_card())
        right.addWidget(self._build_progress_card())
        right.addWidget(self._build_play_card())
        right.addWidget(self._build_notes_card())
        right.addStretch()
        body.addLayout(right, 1)

        scroll.setWidget(container)
        main_layout.addWidget(scroll, 1)

        self._build_action_buttons(main_layout)

    # --- blocos reutilizáveis ---
    @staticmethod
    def _make_label(text: str) -> QLabel:
        """Label estilizado do formulário."""
        lbl = QLabel(text)
        lbl.setProperty("class", "form-label")
        return lbl

    @staticmethod
    def _field(label: str, widget, required: bool = False) -> QWidget:
        """Rótulo acima do campo; o conjunto pode ser mostrado/ocultado como uma unidade."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(GameDialog._make_label(f"{label} *" if required else label))
        if isinstance(widget, QWidget):
            lay.addWidget(widget)
        else:
            lay.addLayout(widget)
        return box

    @staticmethod
    def _card(title: str):
        """Cartão com título; devolve (frame, grid de 2 colunas)."""
        frame = QFrame()
        frame.setProperty("class", "form-card")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(18, 14, 18, 18)
        outer.setSpacing(12)
        heading = QLabel(title)
        heading.setProperty("class", "card-title")
        outer.addWidget(heading)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        outer.addLayout(grid)
        return frame, grid

    def _build_header(self, main_layout):
        title = QLabel("Editar jogo" if self.is_edit else "Novo jogo")
        title.setProperty("class", "view-title-large")
        subtitle = QLabel(
            "Altere as informações e salve." if self.is_edit
            else "Preencha os dados do jogo. Os campos com * são obrigatórios."
        )
        subtitle.setProperty("class", "settings-desc")
        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

    @staticmethod
    def _blank_combo(combo: QComboBox, placeholder: str) -> None:
        combo.setPlaceholderText(placeholder)
        combo.setCurrentIndex(-1)

    def _editable_combo(self, placeholder: str) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.lineEdit().setPlaceholderText(placeholder)
        return combo

    # --- cartões ---
    def _build_identity_card(self) -> QFrame:
        """Título, desenvolvedora, franquia, gênero, plataforma, status e formato."""
        card, grid = self._card("Identificação")

        self.input_title = QLineEdit()
        self.input_title.setPlaceholderText("Ex: The Legend of Zelda: Tears of the Kingdom")
        grid.addWidget(self._field("Título", self.input_title, required=True), 0, 0, 1, 2)

        self.combo_developer = self._editable_combo("Selecione ou digite…")
        grid.addWidget(self._field("Desenvolvedora", self.combo_developer), 1, 0)

        self.combo_franchise = self._editable_combo("Selecione ou digite…")
        grid.addWidget(self._field("Franquia / Série", self.combo_franchise), 1, 1)

        self.combo_genre = self._editable_combo("Selecione ou digite…")
        grid.addWidget(self._field("Gênero principal", self.combo_genre), 2, 0)

        self.combo_genre2 = self._editable_combo("Opcional")
        self.combo_genre2.setToolTip("Um segundo gênero que também descreve o jogo (ex.: Roguelike + Metroidvania).")
        grid.addWidget(self._field("Gênero secundário", self.combo_genre2), 2, 1)

        plat_layout = QHBoxLayout()
        plat_layout.setSpacing(6)
        self.combo_platform = QComboBox()
        self._blank_combo(self.combo_platform, "Selecione a plataforma…")
        btn_add_plat = QPushButton("+")
        btn_add_plat.setFixedWidth(34)
        btn_add_plat.setProperty("class", "small-btn")
        btn_add_plat.setToolTip("Adicionar nova plataforma")
        btn_add_plat.clicked.connect(self.add_new_platform)
        plat_layout.addWidget(self.combo_platform, 1)
        plat_layout.addWidget(btn_add_plat)
        grid.addWidget(self._field("Plataforma", plat_layout), 3, 0)

        self.combo_status = QComboBox()
        for s in STATUSES:
            self.combo_status.addItem(s, s)
        self._blank_combo(self.combo_status, "Selecione o status…")
        grid.addWidget(self._field("Status", self.combo_status, required=True), 3, 1)

        self.combo_format = QComboBox()
        self.combo_format.addItems(FORMATS)
        self._blank_combo(self.combo_format, "Selecione o formato…")
        grid.addWidget(self._field("Formato", self.combo_format), 4, 0)
        return card

    @staticmethod
    def _hours_spin() -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, 99999)
        spin.setSuffix(" h")
        spin.setSpecialValueText("—")  # 0 aparece como "não informado"
        return spin

    @staticmethod
    def _score_spin() -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0, 10)
        spin.setDecimals(1)
        spin.setSingleStep(0.5)
        spin.setSpecialValueText("Sem nota")
        return spin

    def _build_progress_card(self) -> QFrame:
        """Horas, avaliação e datas (os campos de conclusão só aparecem para Zerado/Platinado)."""
        card, grid = self._card("Progresso")

        self.spin_hltb = self._hours_spin()
        grid.addWidget(self._field("Duração estimada (HowLongToBeat)", self.spin_hltb), 0, 0)

        self.spin_played = self._hours_spin()
        self.field_played = self._field("Horas jogadas", self.spin_played)
        grid.addWidget(self.field_played, 0, 1)

        self.spin_score = self._score_spin()
        self.field_score = self._field("Nota (0–10)", self.spin_score)
        grid.addWidget(self.field_score, 1, 0)

        self.spin_diff = self._score_spin()
        self.field_diff = self._field("Dificuldade (0–10)", self.spin_diff)
        grid.addWidget(self.field_diff, 1, 1)

        self.date_finish = OptionalDateEdit()
        self.field_finish = self._field("Zerou em", self.date_finish)
        grid.addWidget(self.field_finish, 2, 0)

        self.date_plat = OptionalDateEdit()
        self.field_plat = self._field("Platinou em", self.date_plat)
        grid.addWidget(self.field_plat, 2, 1)

        self.combo_status.currentTextChanged.connect(self.on_status_changed)
        self.on_status_changed(self.combo_status.currentText())
        return card

    def _build_play_card(self) -> QFrame:
        """Rejogada e favorito."""
        card, grid = self._card("Jogada")

        self.chk_replay = QCheckBox("Esta é uma rejogada")
        self.chk_replay.toggled.connect(self.on_play_type_changed)
        grid.addWidget(self.chk_replay, 0, 0)

        self.spin_play_count = QSpinBox()
        self.spin_play_count.setRange(2, 99)
        self.spin_play_count.setSuffix("ª vez")
        self.field_play_count = self._field("Nº da jogada", self.spin_play_count)
        self.field_play_count.setVisible(False)
        grid.addWidget(self.field_play_count, 0, 1)

        self.combo_replay_of = self._editable_combo("Busque o registro da primeira jogada...")
        self.combo_replay_of.setToolTip("Liga esta jogada às anteriores do mesmo jogo; o registro antigo não muda.")
        self.combo_replay_of.currentIndexChanged.connect(self._on_replay_of_changed)
        self.field_replay_of = self._field("Rejogada de", self.combo_replay_of)
        self.field_replay_of.setVisible(False)
        grid.addWidget(self.field_replay_of, 1, 0, 1, 2)

        self.lbl_plays = QLabel("")
        self.lbl_plays.setWordWrap(True)
        self.lbl_plays.setProperty("class", "settings-desc")
        self.lbl_plays.setVisible(False)
        grid.addWidget(self.lbl_plays, 2, 0, 1, 2)

        self.chk_favorite = QCheckBox("Favorito")
        grid.addWidget(self.chk_favorite, 3, 0)
        return card

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

    def _build_notes_card(self) -> QFrame:
        card, grid = self._card("Anotações")
        self.input_notes = QTextEdit()
        self.input_notes.setPlaceholderText("Escreva aqui suas impressões, review ou dicas...")
        self.input_notes.setFixedHeight(90)
        grid.addWidget(self.input_notes, 0, 0, 1, 2)
        return card

    def _build_action_buttons(self, main_layout):
        btn_box = QHBoxLayout()
        if self.is_edit:
            self.btn_delete = QPushButton("Excluir jogo")
            set_button_icon(self.btn_delete, "trash-2", COLORS["danger"])
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
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self.save_game)
        btn_box.addWidget(self.btn_save)

        main_layout.addLayout(btn_box)

    def on_status_changed(self, status: str):
        is_finished = status in ("Zerado", "Platinado")
        for field in (self.field_played, self.field_score, self.field_diff, self.field_finish):
            field.setVisible(is_finished)
        self.field_plat.setVisible(status == "Platinado")

    def on_play_type_changed(self, *_):
        is_replay = self.chk_replay.isChecked()
        self.field_play_count.setVisible(is_replay)
        self.field_replay_of.setVisible(is_replay)
        if is_replay:
            self.load_briefs()
            if self._briefs is not None and self.combo_replay_of.currentIndex() < 0:
                self._suggest_original()

    # --- vínculo de rejogada ---
    def load_briefs(self):
        if self._briefs is not None or self._briefs_loading:
            return
        self._briefs_loading = True
        run_async(self, api_client.get_game_briefs, self.apply_briefs, self._on_briefs_failed)

    def _on_briefs_failed(self, message: str):
        self._briefs_loading = False
        logger.warning("Não foi possível carregar a lista de jogos para o vínculo de rejogada: %s", message)

    def apply_briefs(self, briefs: list):
        """Preenche a escolha do original (só registros que não são rejogadas) e o histórico de jogadas."""
        self._briefs_loading = False
        self._briefs = briefs
        own_id = self.game_data.get("id")
        originals = [b for b in briefs if b.get("replay_of_id") is None and b["id"] != own_id]
        self.combo_replay_of.blockSignals(True)
        self.combo_replay_of.clear()
        for brief in originals:
            self.combo_replay_of.addItem(brief_label(brief), brief["id"])
        completer = QCompleter([brief_label(b) for b in originals], self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.combo_replay_of.setCompleter(completer)
        self.combo_replay_of.setCurrentIndex(self.combo_replay_of.findData(self.game_data.get("replay_of_id")))
        self.combo_replay_of.blockSignals(False)
        if self.chk_replay.isChecked() and self.combo_replay_of.currentIndex() < 0:
            self._suggest_original()
        self._update_plays_label()

    def _suggest_original(self):
        """Rejogada nova: pré-seleciona o registro com o mesmo título (ignorando acentos e maiúsculas)."""
        title = fold(self.input_title.text().strip())
        if not title:
            return
        for i in range(self.combo_replay_of.count()):
            brief = next(b for b in self._briefs if b["id"] == self.combo_replay_of.itemData(i))
            if fold(brief["title"]) == title:
                self.combo_replay_of.setCurrentIndex(i)
                return

    def _on_replay_of_changed(self, *_):
        root = self.combo_replay_of.currentData()
        if root is not None and not self.is_edit and self._briefs is not None:
            plays = len(replay_group(self._briefs, None, root))
            self.spin_play_count.setValue(max(2, plays + 1))  # próxima jogada do grupo
        self._update_plays_label()

    def selected_replay_of(self):
        """id do original escolhido; sem a lista carregada, mantém o vínculo que o jogo já tinha."""
        if self.combo_replay_of.count() == 0:
            return self.game_data.get("replay_of_id")
        index = self.combo_replay_of.findText(self.combo_replay_of.currentText().strip(), Qt.MatchFixedString)
        return self.combo_replay_of.itemData(index) if index >= 0 else None

    def _update_plays_label(self):
        if self._briefs is None:
            return
        own_id = self.game_data.get("id")
        root = self.combo_replay_of.currentData() if self.chk_replay.isChecked() else None
        group = replay_group(self._briefs, own_id, root)
        self.lbl_plays.setText(f"Jogadas deste jogo — {describe_plays(group, own_id)}" if len(group) > 1 else "")
        self.lbl_plays.setVisible(len(group) > 1)

    def _wait_workers(self):
        for w in list(self.__dict__.get("_workers", ())):
            w.wait(5000)

    def done(self, result):
        self._wait_workers()
        super().done(result)

    @staticmethod
    def fetch_options() -> dict:
        """Busca as opções dos combos (roda fora da thread da UI)."""
        return {
            "developers": api_client.get_developers(),
            "platforms": api_client.get_platforms(),
            "franchises": api_client.get_franchises(),
            "genres": api_client.get_genres(),
        }

    def _set_editable_combo(self, combo, names: list):
        combo.clear()
        combo.addItems(names)
        combo.setCurrentIndex(-1)  # combo editável selecionaria o 1º item e o preencheria
        completer = QCompleter(names, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        combo.setCompleter(completer)

    def apply_options(self, options: dict):
        self._set_editable_combo(self.combo_developer, [d["name"] for d in options["developers"]])

        self.combo_platform.clear()
        self.combo_platform.addItem("Nenhuma", None)
        for p in options["platforms"]:
            self.combo_platform.addItem(p["name"], p["id"])
        self.combo_platform.setCurrentIndex(-1)

        self.franchises_list = options["franchises"]
        self._set_editable_combo(self.combo_franchise, [f["name"] for f in self.franchises_list])
        self.genres_list = options["genres"]
        self._set_editable_combo(self.combo_genre, [g["name"] for g in self.genres_list])
        self._set_editable_combo(self.combo_genre2, [g["name"] for g in self.genres_list])

    def load_options(self):
        """Carrega as opções em background e preenche o formulário ao terminar."""
        self.btn_save.setEnabled(False)
        run_async(self, self.fetch_options, self._on_options_loaded, self._on_options_failed)

    def _on_options_loaded(self, options: dict):
        self.apply_options(options)
        self.btn_save.setEnabled(True)
        self.populate_data()

    def _on_options_failed(self, message: str):
        logger.error("Erro ao carregar opções: %s", message)
        self.btn_save.setEnabled(True)
        self.populate_data()
        set_status(self.lbl_cover_status, "error", "Não foi possível carregar as listas (API offline?).")

    def populate_data(self):
        # Sem id também pode vir pré-preenchido (ex.: jogo novo vindo do app do portátil)
        if not self.game_data:
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
            # Sem id, procura pelo nome (ex.: "PC" na importação das lojas)
            idx = (self.combo_platform.findData(plat["id"]) if plat.get("id")
                   else self.combo_platform.findText(plat.get("name") or "", Qt.MatchFixedString))
            if idx >= 0:
                self.combo_platform.setCurrentIndex(idx)

        # Franchise
        fran = self.game_data.get("franchise")
        if fran:
            self.combo_franchise.setEditText(fran.get("name") or "")
        else:
            self.combo_franchise.setEditText("")

        # Genre
        names = [g.get("name") or "" for g in self.game_data.get("genres") or []] + ["", ""]
        self.combo_genre.setEditText(names[0])
        self.combo_genre2.setEditText(names[1])


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
            self.date_finish.set_optional_date(QDate.fromString(self.game_data["finish_date"], "yyyy-MM-dd"))
        if self.game_data.get("platinum_date"):
            self.date_plat.set_optional_date(QDate.fromString(self.game_data["platinum_date"], "yyyy-MM-dd"))

        self.on_status_changed(self.combo_status.currentText())


        # Play type e Play count
        is_replay = self.game_data.get("play_type") == "Rejogada"
        self.chk_replay.setChecked(is_replay)
        if is_replay:
            self.spin_play_count.setValue(max(2, int(self.game_data.get("play_count") or 2)))
        if self.game_data.get("replay_of_id") or self.game_data.get("replays_count"):
            self.load_briefs()  # mostra as outras jogadas do grupo

        self.combo_format.setCurrentText(self.game_data.get("format") or "Digital")
        self.chk_favorite.setChecked(bool(self.game_data.get("is_favorite")))
        self.input_notes.setText(self.game_data.get("notes") or "")

        self.update_cover_preview()

    def suggest_developer(self, name) -> None:
        """Preenche a desenvolvedora vinda da loja, sem sobrescrever o que já está no campo."""
        if not name or (self.game_data.get("developer") or "").strip():
            return
        self.game_data["developer"] = name  # caso as opções ainda estejam carregando
        if not self.combo_developer.currentText().strip():
            self.combo_developer.setEditText(name)

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

    @staticmethod
    def _find_id_by_name(items: list, name: str):
        for item in items:
            if item.get("name", "").strip().lower() == name.lower():
                return item["id"]
        return None

    def _build_payload(self, title: str) -> dict:
        """Lê o formulário (thread da UI) e monta o payload base, sem franquia/gênero."""
        is_replay = self.chk_replay.isChecked()
        payload = {
            "title": title,
            "developer": self.combo_developer.currentText().strip() or None,
            "status": self.combo_status.currentText(),
            "platform_id": self.combo_platform.currentData(),
            "hltb_hours": float(self.spin_hltb.value()),
            "played_hours": float(self.spin_played.value()),
            "score": round(self.spin_score.value(), 1) if self.spin_score.value() > 0 else None,
            "difficulty": round(self.spin_diff.value(), 1) if self.spin_diff.value() > 0 else None,
            "play_type": "Rejogada" if is_replay else "Primeira Jogada",
            "play_count": self.spin_play_count.value() if is_replay else 1,
            "replay_of_id": self.selected_replay_of() if is_replay else None,
            "is_favorite": self.chk_favorite.isChecked(),
            "notes": self.input_notes.toPlainText().strip() or None,
            "cover_image": self.cover_filename,
        }
        if self.combo_format.currentIndex() >= 0:  # sem escolha: mantém o padrão do servidor (Digital)
            payload["format"] = self.combo_format.currentText()

        st = payload["status"]
        finish, plat = self.date_finish.date_or_none(), self.date_plat.date_or_none()
        fmt = lambda d: d.toString("yyyy-MM-dd") if d else None
        if st == "Zerado":
            payload["finish_date"] = fmt(finish)
            payload["completion_year"] = finish.year() if finish else None
            payload["platinum_date"] = None
        elif st == "Platinado":
            payload["finish_date"] = fmt(finish)
            payload["platinum_date"] = fmt(plat)
            reference = plat or finish
            payload["completion_year"] = reference.year() if reference else None
        else:
            payload["finish_date"] = None
            payload["platinum_date"] = None
            payload["completion_year"] = None
        return payload

    @staticmethod
    def genre_names(texts: list) -> list:
        """Nomes de gênero preenchidos, sem repetir (sem diferenciar maiúsculas); no máximo dois."""
        names = []
        for text in texts:
            text = (text or "").strip()
            if text and text.lower() not in (n.lower() for n in names):
                names.append(text)
        return names[:2]

    @staticmethod
    def persist_game(game_id, payload: dict, fran_text: str, gen_texts: list,
                     franchises: list, genres: list) -> dict:
        """Resolve/cria franquia e gêneros (principal, secundário) e grava o jogo (roda fora da thread da UI)."""
        payload = dict(payload)

        franchise_id = None
        if fran_text:
            franchise_id = GameDialog._find_id_by_name(franchises, fran_text)
            if not franchise_id:
                try:
                    franchise_id = api_client.create_franchise(fran_text).get("id")
                except Exception as e:
                    logger.warning("Erro ao auto-criar franquia: %s", e)
        payload["franchise_id"] = franchise_id

        genre_ids = []
        for gen_text in GameDialog.genre_names(gen_texts):
            genre_id = GameDialog._find_id_by_name(genres, gen_text)
            if not genre_id:
                try:
                    genre_id = api_client.create_genre(gen_text).get("id")
                except Exception as e:
                    logger.warning("Erro ao auto-criar gênero: %s", e)
            if genre_id and genre_id not in genre_ids:
                genre_ids.append(genre_id)
        payload["genre_ids"] = genre_ids

        if game_id is not None:
            return api_client.update_game(game_id, payload)
        return api_client.create_game(payload)

    def _set_busy(self, busy: bool, save_text: str = "Salvar Jogo"):
        self.btn_save.setEnabled(not busy)
        self.btn_save.setText(save_text)
        self.btn_cancel.setEnabled(not busy)
        if self.is_edit:
            self.btn_delete.setEnabled(not busy)

    def save_game(self):
        title = self.input_title.text().strip()
        if not title:
            QMessageBox.warning(self, "Aviso", "O título do jogo é obrigatório.")
            return
        if self.combo_status.currentIndex() < 0:
            QMessageBox.warning(self, "Aviso", "Selecione o status do jogo.")
            return

        payload = self._build_payload(title)
        self._set_busy(True, "Salvando...")
        run_async(
            self, self.persist_game, self._on_game_saved, self._on_save_failed,
            self.game_data["id"] if self.is_edit else None,
            payload,
            self.combo_franchise.currentText().strip(),
            [self.combo_genre.currentText(), self.combo_genre2.currentText()],
            list(getattr(self, "franchises_list", [])),
            list(getattr(self, "genres_list", [])),
        )

    def _on_game_saved(self, saved_game: dict):
        self.saved_game = saved_game
        self.is_deleted = False
        self.accept()

    def _on_save_failed(self, message: str):
        self._set_busy(False)
        QMessageBox.critical(self, "Erro", f"Erro ao salvar jogo: {message}")

    def delete_game(self):
        confirm = QMessageBox.question(
            self, "Confirmar Exclusão",
            f"Tem certeza que deseja excluir '{self.game_data.get('title')}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self._set_busy(True)
            run_async(self, api_client.delete_game, self._on_game_deleted, self._on_delete_failed, self.game_data["id"])

    def _on_game_deleted(self, deleted: bool):
        if not deleted:
            self._on_delete_failed("o servidor não confirmou a exclusão")
            return
        self.saved_game = self.game_data
        self.is_deleted = True
        self.accept()

    def _on_delete_failed(self, message: str):
        self._set_busy(False)
        QMessageBox.critical(self, "Erro", f"Erro ao excluir jogo: {message}")
