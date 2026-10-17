from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QComboBox, QSpinBox, QPushButton, QCompleter, QLineEdit
)
from PySide6.QtCore import Signal, Qt, QStringListModel, QTimer
from frontend_desktop.ui_helpers import set_button_icon

FIELD_DEBOUNCE_MS = 150


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
        """(texto em minúsculas, exato?) — texto vazio significa "sem filtro"."""
        if not self.isEnabled():  # bloqueado: mostra o nome da categoria, mas não filtra
            return "", False
        return self.text().strip().lower(), self._exact

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
    Componente retrátil de filtros avançados em tempo real (Gênero, Desenvolvedora, Plataforma, Franquia e HLTB).
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
        grid.addWidget(make_label("Tempo HLTB:"), 2, 0)
        
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

        # Botão Limpar
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.addStretch()
        
        self.btn_clear = QPushButton("Limpar filtros")
        
        set_button_icon(self.btn_clear, "x")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setProperty("class", "small-btn")
        self.btn_clear.clicked.connect(self.clear_filters)
        actions_layout.addWidget(self.btn_clear)

        grid.addLayout(actions_layout, 2, 2, 1, 2)

        # Conectar eventos de mudança para disparo em tempo real
        for _label, field in self._fields.values():
            field.changed.connect(self._on_any_change)
        self.combo_hltb_op.currentIndexChanged.connect(self._on_any_change)
        self.spin_hltb.valueChanged.connect(self._on_any_change)

        main_layout.addWidget(self.panel_frame)

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
                field.setText(locked[kind])
                field.setPlaceholderText(field.default_placeholder)
            else:
                if not field.isEnabled():
                    field.clear()
                field.setEnabled(True)

    def _on_any_change(self):
        self.update_button_badge()
        self.filters_changed.emit()

    def count_active_filters(self) -> int:
        count = sum(1 for _label, field in self._fields.values() if field.value()[0])
        if self.spin_hltb.value() > 0:
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
        self.spin_hltb.blockSignals(True)
        self.spin_hltb.setValue(0)
        self.spin_hltb.blockSignals(False)

        self._on_any_change()

    def build_matcher(self):
        """Lê o estado dos filtros uma única vez e devolve `game -> bool` (para filtrar listas grandes)."""
        gen, dev = self.combo_genre.value(), self.combo_dev.value()
        plat, fran = self.combo_plat.value(), self.combo_fran.value()
        target_hltb = self.spin_hltb.value()
        op = self.combo_hltb_op.currentText()
        at_least, at_most = "≥" in op, "≤" in op

        def name_of(value) -> str:
            return (value.get("name") if isinstance(value, dict) else str(value or "")).strip().lower()

        def hit(wanted: tuple, actual: str) -> bool:
            text, exact = wanted
            return actual == text if exact else text in actual

        def matcher(game: dict) -> bool:
            if gen[0] and not any(hit(gen, name_of(g)) for g in game.get("genres") or []):
                return False
            if dev[0] and not hit(dev, (game.get("developer") or "").strip().lower()):
                return False
            if plat[0] and not hit(plat, name_of(game.get("platform"))):
                return False
            if fran[0] and not hit(fran, name_of(game.get("franchise"))):
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
