from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QComboBox, QSpinBox, QPushButton, QCompleter, QLineEdit, QCheckBox
)
from PySide6.QtCore import Signal, Qt, QStringListModel, QTimer
from frontend_desktop import page_settings
from frontend_desktop.data_quality import is_incomplete
from frontend_desktop.text_search import fold_query
from frontend_desktop.ui_helpers import set_button_icon
from frontend_desktop.views import game_status as gs

FIELD_DEBOUNCE_MS = 150
STATUS_COMPLETED = "__concluidos__"  # opção "Zerados e platinados" do filtro de status


def is_replay(game: dict) -> bool:
    return bool(game.get("replay_of_id")) or game.get("play_type") == "Rejogada"


def was_replayed(game: dict) -> bool:
    """Faz parte de um jogo rejogado: é uma rejogada ou o original de alguma."""
    return is_replay(game) or bool(game.get("replays_count"))


class SuggestField(QLineEdit):
    """Campo de texto com sugestões: filtra por "contém" enquanto se digita; ao escolher uma sugestão o valor é exato.

    Vazio = sem filtro. `changed` é emitido com debounce quando o usuário digita (campo com foco) e na hora
    quando o texto é alterado por código.
    """
    changed = Signal()

    def __init__(self, placeholder: str, parent=None):
        super().__init__(parent)
        self.default_placeholder = placeholder
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.setProperty("class", "filter-combo")
        self._exact = False

        self.names_model = QStringListModel(self)
        completer = QCompleter(self.names_model, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.activated[str].connect(self._on_picked)
        self.setCompleter(completer)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(FIELD_DEBOUNCE_MS)
        self._debounce.timeout.connect(self.changed.emit)
        self.textEdited.connect(self._on_edited)
        self.textChanged.connect(self._on_text_changed)

    def set_names(self, names: list) -> None:
        self.names_model.setStringList(names)

    def value(self) -> tuple:
        """(texto normalizado — sem acentos/maiúsculas —, exato?) — texto vazio significa "sem filtro"."""
        if not self.isEnabled():  # bloqueado: mostra o nome da categoria, mas não filtra
            return "", False
        return fold_query(self.text()), self._exact

    def _on_edited(self, _text: str) -> None:
        self._exact = False

    def _on_picked(self, _text: str) -> None:
        self._exact = True
        self._debounce.stop()
        self.changed.emit()

    def _on_text_changed(self, _text: str) -> None:
        if not self.text():
            self._exact = False
        if self.hasFocus():
            self._debounce.start()
        else:
            self._debounce.stop()
            self.changed.emit()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if not self.text() and self.names_model.rowCount():
            self.completer().setCompletionPrefix("")
            self.completer().complete()  # campo vazio: abre a lista completa, como um dropdown

class FilterPanel(QWidget):
    """
    Componente retrátil de filtros avançados em tempo real (Gênero, Desenvolvedora, Plataforma, Franquia, HLTB,
    status — opcional — e só incompletos).
    """
    filters_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("filterPanelWrapper")
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        self.genres_list = []
        self.developers_list = []
        self.platforms_list = []
        self.franchises_list = []
        self._fields = {}  # kind -> (label, campo)
        self._page_fields = set(page_settings.FILTER_FIELDS)  # campos permitidos pela página (Configurações)
        self._status_allowed = False  # o status só existe nas páginas de categoria no modo "todos os jogos"

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # 1. Botão de Alternância de Filtros
        self.btn_toggle = QPushButton("Filtros")
        set_button_icon(self.btn_toggle, "sliders-horizontal")
        self.btn_toggle.setObjectName("btnToggleFilters")
        self.btn_toggle.setProperty("class", "filter-btn")
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.setChecked(False)
        self.btn_toggle.toggled.connect(self.on_toggle_panel)

        # 2. Painel Retrátil
        self.panel_frame = QFrame()
        self.panel_frame.setObjectName("filterPanelFrame")
        self.panel_frame.setProperty("class", "filter-panel-card")
        self.panel_frame.setAttribute(Qt.WA_StyledBackground, True)
        self.panel_frame.setVisible(False)

        grid = QGridLayout(self.panel_frame)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        def make_label(text):
            lbl = QLabel(text)
            lbl.setProperty("class", "filter-label")
            return lbl

        def add_field(kind, label_text, placeholder, row, col):
            label = make_label(label_text)
            field = SuggestField(placeholder)
            grid.addWidget(label, row, col)
            grid.addWidget(field, row, col + 1)
            self._fields[kind] = (label, field)
            return field

        # Linha 0: Gênero e Desenvolvedora
        self.combo_genre = add_field("genre", "Gênero:", "Todos os gêneros", 0, 0)
        self.combo_dev = add_field("developer", "Desenvolvedora:", "Todas as desenvolvedoras", 0, 2)

        # Linha 1: Plataforma e Franquia
        self.combo_plat = add_field("platform", "Plataforma:", "Todas as plataformas", 1, 0)
        self.combo_fran = add_field("franchise", "Franquia / Série:", "Todas as franquias", 1, 2)

        # Linha 2: Tempo HLTB e Botão Limpar
        self.hltb_label = make_label("Tempo HLTB:")
        grid.addWidget(self.hltb_label, 2, 0)
        
        hltb_layout = QHBoxLayout()
        hltb_layout.setContentsMargins(0, 0, 0, 0)
        hltb_layout.setSpacing(6)

        self.combo_hltb_op = QComboBox()
        self.combo_hltb_op.addItems(["≥ Maior ou igual a", "≤ Menor ou igual a"])
        self.combo_hltb_op.setProperty("class", "filter-combo")
        
        self.spin_hltb = QSpinBox()
        self.spin_hltb.setRange(0, 99999)
        self.spin_hltb.setSuffix(" h")
        self.spin_hltb.setSpecialValueText("Qualquer tempo")
        self.spin_hltb.setValue(0)
        self.spin_hltb.setProperty("class", "filter-spin")

        hltb_layout.addWidget(self.combo_hltb_op)
        hltb_layout.addWidget(self.spin_hltb)
        grid.addLayout(hltb_layout, 2, 1)

        # Status (só nas páginas de categoria no modo "todos os jogos")
        self.status_label = make_label("Status:")
        self.combo_status = QComboBox()
        self.combo_status.setProperty("class", "filter-combo")
        self.combo_status.addItem("Todos os status", "")
        self.combo_status.addItem("Zerados e platinados", STATUS_COMPLETED)
        for status in gs.ALL_STATUSES:
            self.combo_status.addItem(status, status)
        grid.addWidget(self.status_label, 2, 2)
        grid.addWidget(self.combo_status, 2, 3)

        # Linha 3: rejogados
        self.chk_replayed = QCheckBox("Só jogos rejogados")
        self.chk_replayed.setToolTip("Mostra todas as jogadas dos jogos rejogados: a original e as rejogadas.")
        self.chk_replayed.setCursor(Qt.PointingHandCursor)
        grid.addWidget(self.chk_replayed, 3, 0, 1, 2)

        # Linha 4: só incompletos e Limpar
        self.chk_incomplete = QCheckBox("Só jogos com dados faltando")
        self.chk_incomplete.setToolTip("Sem desenvolvedora, gênero, plataforma, capa ou HLTB; zerados também sem horas, nota ou data.")
        self.chk_incomplete.setCursor(Qt.PointingHandCursor)
        grid.addWidget(self.chk_incomplete, 4, 0, 1, 2)

        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.addStretch()

        self.btn_clear = QPushButton("Limpar filtros")

        set_button_icon(self.btn_clear, "x")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setProperty("class", "small-btn")
        self.btn_clear.clicked.connect(self.clear_filters)
        actions_layout.addWidget(self.btn_clear)

        grid.addLayout(actions_layout, 4, 2, 1, 2)

        # Conectar eventos de mudança para disparo em tempo real
        for _label, field in self._fields.values():
            field.changed.connect(self._on_any_change)
        self.combo_hltb_op.currentIndexChanged.connect(self._on_any_change)
        self.spin_hltb.valueChanged.connect(self._on_any_change)
        self.combo_status.currentIndexChanged.connect(self._on_any_change)
        self.chk_replayed.toggled.connect(self._on_any_change)
        self.chk_incomplete.toggled.connect(self._on_any_change)

        main_layout.addWidget(self.panel_frame)
        self._refresh_visibility()  # status começa escondido

    def set_status_filter_visible(self, visible: bool) -> None:
        """Mostra o filtro de status (se a página também permitir); escondido, ele é zerado e não filtra."""
        self._status_allowed = visible
        self._refresh_visibility()

    # --- campos visíveis (Configurações → Páginas) ---
    def bind_page(self, page: str) -> None:
        """Mostra só os campos escolhidos para `page` e acompanha mudanças nas Configurações."""
        self.set_visible_fields(page_settings.page_config(page).filters)
        page_settings.subscribe(page, self._on_page_config)

    def _on_page_config(self, config) -> None:
        self.set_visible_fields(config.filters)

    def set_visible_fields(self, fields) -> None:
        self._page_fields = set(fields)
        self._refresh_visibility()

    def _field_widgets(self, kind: str) -> tuple:
        if kind in self._fields:
            return self._fields[kind]
        return {
            "hltb": (self.hltb_label, self.combo_hltb_op, self.spin_hltb),
            "plays": (self.chk_replayed,),
            "status": (self.status_label, self.combo_status),
            "incomplete": (self.chk_incomplete,),
        }[kind]

    def is_field_visible(self, kind: str) -> bool:
        return kind in self._page_fields and (kind != "status" or self._status_allowed)

    def _reset_field(self, kind: str) -> bool:
        """Zera o campo (sem sinais); devolve True se ele estava filtrando."""
        if kind in self._fields:
            field = self._fields[kind][1]
            if not field.isEnabled() or not field.text():
                return False  # bloqueado pela página de categoria, ou já vazio
            field.blockSignals(True)
            field.clear()
            field._exact = False
            field.blockSignals(False)
            return True
        widget, active, reset = {
            "hltb": (self.spin_hltb, self.spin_hltb.value() > 0, lambda: self.spin_hltb.setValue(0)),
            "plays": (self.chk_replayed, self.chk_replayed.isChecked(), lambda: self.chk_replayed.setChecked(False)),
            "status": (self.combo_status, self.combo_status.currentIndex() > 0, lambda: self.combo_status.setCurrentIndex(0)),
            "incomplete": (self.chk_incomplete, self.chk_incomplete.isChecked(), lambda: self.chk_incomplete.setChecked(False)),
        }[kind]
        if active:
            widget.blockSignals(True)
            reset()
            widget.blockSignals(False)
        return active

    def _refresh_visibility(self) -> None:
        """Esconde os campos que a página não usa; campo escondido nunca filtra. Sem campos, some o botão."""
        cleared = False
        for kind in page_settings.FILTER_FIELDS:
            visible = self.is_field_visible(kind)
            for widget in self._field_widgets(kind):
                widget.setVisible(visible)
            if not visible:
                cleared = self._reset_field(kind) or cleared
        any_visible = any(self.is_field_visible(kind) for kind in page_settings.FILTER_FIELDS)
        self.btn_toggle.setVisible(any_visible)
        if not any_visible and self.btn_toggle.isChecked():
            self.btn_toggle.setChecked(False)
        if cleared:
            self._on_any_change()

    def on_toggle_panel(self, checked: bool):
        self.panel_frame.setVisible(checked)

    def set_options(self, genres: list, developers: list, platforms: list, franchises: list):
        self.genres_list = list(genres)
        self.developers_list = list(developers)
        self.platforms_list = list(platforms)
        self.franchises_list = list(franchises)

        def names_of(items):
            return [it.get("name") if isinstance(it, dict) else str(it) for it in items]

        self.combo_genre.set_names(names_of(self.genres_list))
        self.combo_dev.set_names(names_of(self.developers_list))
        self.combo_plat.set_names(names_of(self.platforms_list))
        self.combo_fran.set_names(names_of(self.franchises_list))

    def set_locked_filters(self, locked) -> None:
        """Bloqueia os filtros das dimensões em `locked` ({kind: nome}, kind em genre/developer/platform/franchise).

        Dentro da página de um gênero o filtro de gênero continua visível, mas desabilitado, mostrando o nome
        da categoria; ele é zerado e não conta como filtro ativo."""
        locked = dict(locked or {})
        for kind, (_label, field) in self._fields.items():
            if kind in locked:
                field.setEnabled(False)
                field.setClearButtonEnabled(False)  # sem o "x": não parece editável
                field.setText(locked[kind])
                field.setPlaceholderText(field.default_placeholder)
            else:
                if not field.isEnabled():
                    field.clear()
                field.setEnabled(True)
                field.setClearButtonEnabled(True)

    def _on_any_change(self):
        self.update_button_badge()
        self.filters_changed.emit()

    def count_active_filters(self) -> int:
        count = sum(1 for _label, field in self._fields.values() if field.value()[0])
        if self.spin_hltb.value() > 0:
            count += 1
        if self.combo_status.currentData():
            count += 1
        if self.chk_replayed.isChecked():
            count += 1
        if self.chk_incomplete.isChecked():
            count += 1
        return count

    def update_button_badge(self):
        active = self.count_active_filters()
        if active > 0:
            self.btn_toggle.setText(f"Filtros ({active})")
            self.btn_toggle.setProperty("class", "filter-btn filter-btn-active")
        else:
            self.btn_toggle.setText("Filtros")
            self.btn_toggle.setProperty("class", "filter-btn")
        self.btn_toggle.style().unpolish(self.btn_toggle)
        self.btn_toggle.style().polish(self.btn_toggle)

    def clear_filters(self):
        for _label, field in self._fields.values():
            if not field.isEnabled():
                continue  # filtro bloqueado pela página não é limpo
            field.blockSignals(True)
            field.clear()
            field._exact = False
            field.blockSignals(False)
        for widget, reset in ((self.spin_hltb, lambda: self.spin_hltb.setValue(0)),
                              (self.combo_status, lambda: self.combo_status.setCurrentIndex(0)),
                              (self.chk_replayed, lambda: self.chk_replayed.setChecked(False)),
                              (self.chk_incomplete, lambda: self.chk_incomplete.setChecked(False))):
            widget.blockSignals(True)
            reset()
            widget.blockSignals(False)

        self._on_any_change()

    def build_matcher(self):
        """Lê o estado dos filtros uma única vez e devolve `game -> bool` (para filtrar listas grandes)."""
        gen, dev = self.combo_genre.value(), self.combo_dev.value()
        plat, fran = self.combo_plat.value(), self.combo_fran.value()
        target_hltb = self.spin_hltb.value()
        op = self.combo_hltb_op.currentText()
        at_least, at_most = "≥" in op, "≤" in op
        status = self.combo_status.currentData() or ""  # escondido = sempre "Todos os status"
        only_replayed = self.chk_replayed.isChecked()
        only_incomplete = self.chk_incomplete.isChecked()

        def name_of(value) -> str:
            return fold_query(value.get("name") if isinstance(value, dict) else str(value or ""))

        def hit(wanted: tuple, actual: str) -> bool:
            text, exact = wanted
            return actual == text if exact else text in actual

        def matcher(game: dict) -> bool:
            if gen[0] and not any(hit(gen, name_of(g)) for g in game.get("genres") or []):
                return False
            if dev[0] and not hit(dev, fold_query(game.get("developer"))):
                return False
            if plat[0] and not hit(plat, name_of(game.get("platform"))):
                return False
            if fran[0] and not hit(fran, name_of(game.get("franchise"))):
                return False
            if status == STATUS_COMPLETED and game.get("status") not in (gs.ZERADO, gs.PLATINADO):
                return False
            if status and status != STATUS_COMPLETED and game.get("status") != status:
                return False
            if only_replayed and not was_replayed(game):
                return False
            if only_incomplete and not is_incomplete(game):
                return False
            if target_hltb > 0:
                hltb = float(game.get("hltb_hours") or 0.0)
                if at_least and hltb < target_hltb:
                    return False
                if at_most and (hltb == 0.0 or hltb > target_hltb):
                    return False
            return True

        return matcher

    def matches(self, game_data: dict) -> bool:
        """Verifica se o jogo atende a todos os critérios de filtro ativos."""
        return self.build_matcher()(game_data)
