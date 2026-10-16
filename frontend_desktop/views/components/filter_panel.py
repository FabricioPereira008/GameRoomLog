from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QComboBox, QSpinBox, QPushButton, QCompleter, QSizePolicy
)
from PySide6.QtCore import Signal, Qt, QStringListModel
from frontend_desktop.ui_helpers import set_button_icon

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

        def setup_editable_combo(placeholder):
            combo = QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.NoInsert)
            combo.lineEdit().setPlaceholderText(placeholder)
            combo.setProperty("class", "filter-combo")
            return combo

        # Linha 0: Gênero e Desenvolvedora
        grid.addWidget(make_label("Gênero:"), 0, 0)
        self.combo_genre = setup_editable_combo("(Todos os Gêneros)")
        grid.addWidget(self.combo_genre, 0, 1)

        grid.addWidget(make_label("Desenvolvedora:"), 0, 2)
        self.combo_dev = setup_editable_combo("(Todas as Desenvolvedoras)")
        grid.addWidget(self.combo_dev, 0, 3)

        # Linha 1: Plataforma e Franquia
        grid.addWidget(make_label("Plataforma:"), 1, 0)
        self.combo_plat = setup_editable_combo("(Todas as Plataformas)")
        grid.addWidget(self.combo_plat, 1, 1)

        grid.addWidget(make_label("Franquia / Série:"), 1, 2)
        self.combo_fran = setup_editable_combo("(Todas as Franquias)")
        grid.addWidget(self.combo_fran, 1, 3)

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
        self.combo_genre.currentTextChanged.connect(self._on_any_change)
        self.combo_dev.currentTextChanged.connect(self._on_any_change)
        self.combo_plat.currentTextChanged.connect(self._on_any_change)
        self.combo_fran.currentTextChanged.connect(self._on_any_change)
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

        def populate(combo, items, default_label):
            cur_text = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(default_label, "")
            names = [it.get("name") if isinstance(it, dict) else str(it) for it in items]
            combo.addItems(names)
            
            # O completer é criado uma vez por combo; depois só a lista de nomes é atualizada
            names_model = getattr(combo, "_names_model", None)
            if names_model is None:
                names_model = QStringListModel(self)
                combo._names_model = names_model
                completer = QCompleter(names_model, self)
                completer.setCaseSensitivity(Qt.CaseInsensitive)
                completer.setFilterMode(Qt.MatchContains)
                combo.setCompleter(completer)
            names_model.setStringList(names)

            # Restaura texto se possível
            idx = combo.findText(cur_text)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setEditText(cur_text)
            combo.blockSignals(False)

        populate(self.combo_genre, self.genres_list, "(Todos os Gêneros)")
        populate(self.combo_dev, self.developers_list, "(Todas as Desenvolvedoras)")
        populate(self.combo_plat, self.platforms_list, "(Todas as Plataformas)")
        populate(self.combo_fran, self.franchises_list, "(Todas as Franquias)")

    def _on_any_change(self):
        self.update_button_badge()
        self.filters_changed.emit()

    def count_active_filters(self) -> int:
        count = 0
        gen = self.combo_genre.currentText().strip()
        if gen and not gen.startswith("("):
            count += 1
        dev = self.combo_dev.currentText().strip()
        if dev and not dev.startswith("("):
            count += 1
        plat = self.combo_plat.currentText().strip()
        if plat and not plat.startswith("("):
            count += 1
        fran = self.combo_fran.currentText().strip()
        if fran and not fran.startswith("("):
            count += 1
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
        self.combo_genre.blockSignals(True)
        self.combo_dev.blockSignals(True)
        self.combo_plat.blockSignals(True)
        self.combo_fran.blockSignals(True)
        self.spin_hltb.blockSignals(True)

        self.combo_genre.setCurrentIndex(0)
        self.combo_dev.setCurrentIndex(0)
        self.combo_plat.setCurrentIndex(0)
        self.combo_fran.setCurrentIndex(0)
        self.spin_hltb.setValue(0)

        self.combo_genre.blockSignals(False)
        self.combo_dev.blockSignals(False)
        self.combo_plat.blockSignals(False)
        self.combo_fran.blockSignals(False)
        self.spin_hltb.blockSignals(False)

        self._on_any_change()

    def build_matcher(self):
        """Lê o estado dos filtros uma única vez e devolve `game -> bool` (para filtrar listas grandes)."""
        def active(combo):
            value = combo.currentText().strip()
            return value.lower() if value and not value.startswith("(") else ""

        gen, dev = active(self.combo_genre), active(self.combo_dev)
        plat, fran = active(self.combo_plat), active(self.combo_fran)
        target_hltb = self.spin_hltb.value()
        op = self.combo_hltb_op.currentText()
        at_least, at_most = "≥" in op, "≤" in op

        def name_of(value) -> str:
            return (value.get("name") if isinstance(value, dict) else str(value or "")).strip().lower()

        def matcher(game: dict) -> bool:
            if gen and not any(name_of(g) == gen for g in game.get("genres") or []):
                return False
            if dev and (game.get("developer") or "").strip().lower() != dev:
                return False
            if plat and name_of(game.get("platform")) != plat:
                return False
            if fran and name_of(game.get("franchise")) != fran:
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
