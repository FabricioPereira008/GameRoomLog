"""Abas das Configurações que não dependem do backend: Páginas (personalização) e Atalhos."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout,
    QWidget,
)

from frontend_desktop import page_settings
from frontend_desktop.page_settings import FILTER_FIELDS, PAGES, SORT_CRITERIA, PageConfig
from frontend_desktop.shortcuts import GROUPS, SHORTCUTS


def settings_page() -> tuple:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(8, 16, 16, 20)
    layout.setSpacing(20)
    layout.setAlignment(Qt.AlignTop)
    return page, layout


def settings_group(title: str, description: str = "") -> tuple:
    group = QGroupBox(title)
    group.setProperty("class", "settings-group")
    layout = QVBoxLayout(group)
    layout.setSpacing(10)
    if description:
        desc = QLabel(description)
        desc.setWordWrap(True)
        desc.setProperty("class", "settings-desc")
        layout.addWidget(desc)
    return group, layout


def restore_button(on_click) -> QHBoxLayout:
    """Linha com o botão "Restaurar padrões" alinhado à direita (um por aba)."""
    row = QHBoxLayout()
    row.addStretch()
    button = QPushButton("Restaurar padrões")
    button.setProperty("class", "small-btn")
    button.setCursor(Qt.PointingHandCursor)
    button.clicked.connect(on_click)
    row.addWidget(button)
    return row


class PagesSettingsTab(QWidget):
    """Configurações → Páginas: por página, os critérios de ordenação e os campos do Filtro visíveis.

    Uma página por vez (seletor no topo); cada mudança é salva e vale na hora (page_settings)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        self._init_ui()
        self.load_page(self.current_page)

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        page, layout = settings_page()
        outer.addWidget(page)

        intro, intro_layout = settings_group(
            "Personalizar páginas",
            "Escolha o que aparece em cada página: os critérios de ordenação e os campos do painel de Filtros. "
            "A ordenação padrão é a que a página usa ao abrir o app; trocar a ordenação na própria página vale "
            "até fechar o app.",
        )
        row = QHBoxLayout()
        row.addWidget(QLabel("Página:"))
        self.combo_page = QComboBox()
        for key, spec in PAGES.items():
            self.combo_page.addItem(spec.title, key)
        self.combo_page.currentIndexChanged.connect(lambda *_: self.load_page(self.current_page))
        row.addWidget(self.combo_page, 1)
        intro_layout.addLayout(row)
        layout.addWidget(intro)

        self.sort_group, sort_layout = settings_group(
            "Ordenação", "Critérios que aparecem no seletor da página (pelo menos um). Com um só, fica apenas o "
                         "botão de direção.")
        self.sort_checks_layout = QVBoxLayout()
        sort_layout.addLayout(self.sort_checks_layout)
        self.sort_checks = {}
        default_row = QHBoxLayout()
        default_row.addWidget(QLabel("Padrão:"))
        self.combo_default = QComboBox()
        self.combo_default.currentIndexChanged.connect(self._on_default_changed)
        default_row.addWidget(self.combo_default, 1)
        self.combo_direction = QComboBox()
        self.combo_direction.currentIndexChanged.connect(self._save)
        default_row.addWidget(self.combo_direction, 1)
        sort_layout.addLayout(default_row)
        layout.addWidget(self.sort_group)

        self.filter_group, filter_layout = settings_group(
            "Filtros", "Campos que aparecem no painel de Filtros da página. Sem nenhum, o botão Filtros some.")
        self.filter_checks_layout = QVBoxLayout()
        filter_layout.addLayout(self.filter_checks_layout)
        self.filter_checks = {}
        layout.addWidget(self.filter_group)

        layout.addLayout(restore_button(self.restore_defaults))

    @property
    def current_page(self) -> str:
        return self.combo_page.currentData()

    @staticmethod
    def _clear(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()  # some já; deleteLater só destrói no próximo ciclo de eventos
                item.widget().deleteLater()

    def load_page(self, page: str) -> None:
        """Monta as caixas de seleção da página e preenche com a configuração salva."""
        self._loading = True
        spec, config = PAGES[page], page_settings.page_config(page)
        self._clear(self.sort_checks_layout)
        self.sort_checks = {}
        for key in spec.sorts:
            check = QCheckBox(SORT_CRITERIA[key].label)
            check.setChecked(key in config.sorts)
            check.toggled.connect(self._on_sorts_changed)
            self.sort_checks[key] = check
            self.sort_checks_layout.addWidget(check)
        self.sort_group.setVisible(bool(spec.sorts))  # Game Room: as faixas têm ordem própria

        self._clear(self.filter_checks_layout)
        self.filter_checks = {}
        for key in spec.filters:
            label = FILTER_FIELDS[key]
            if key == "status":
                label += " (só no modo \"Todos os jogos\" da aba Aparência)"
            check = QCheckBox(label)
            check.setChecked(key in config.filters)
            check.toggled.connect(self._save)
            self.filter_checks[key] = check
            self.filter_checks_layout.addWidget(check)
        self._fill_defaults(config)
        self._loading = False

    def _fill_defaults(self, config: PageConfig) -> None:
        was_loading, self._loading = self._loading, True
        self.combo_default.clear()
        for key in config.sorts:
            self.combo_default.addItem(SORT_CRITERIA[key].label, key)
        self.combo_default.setCurrentIndex(self.combo_default.findData(config.default_sort))
        self._fill_directions(config.default_sort, config.default_descending)
        # O último critério marcado não pode ser desmarcado
        for check in self.sort_checks.values():
            check.setEnabled(not (check.isChecked() and len(config.sorts) == 1))
            check.setToolTip("Pelo menos um critério precisa ficar visível." if not check.isEnabled() else "")
        self._loading = was_loading

    def _fill_directions(self, sort_key, descending: bool) -> None:
        self.combo_direction.clear()
        if sort_key is None:
            return
        criterion = SORT_CRITERIA[sort_key]
        self.combo_direction.addItem(criterion.direction_label(False), False)
        self.combo_direction.addItem(criterion.direction_label(True), True)
        self.combo_direction.setCurrentIndex(1 if descending else 0)

    def _on_sorts_changed(self, *_):
        self._save()

    def _on_default_changed(self, *_):
        if self._loading:
            return
        key = self.combo_default.currentData()
        self._loading = True
        self._fill_directions(key, SORT_CRITERIA[key].descending if key else False)  # direção inicial do critério
        self._loading = False
        self._save()

    def config_from_ui(self) -> PageConfig:
        return PageConfig(
            tuple(k for k, c in self.sort_checks.items() if c.isChecked()),
            self.combo_default.currentData(),
            bool(self.combo_direction.currentData()),
            tuple(k for k, c in self.filter_checks.items() if c.isChecked()),
        )

    def _save(self, *_):
        if self._loading:
            return
        saved = page_settings.set_page_config(self.current_page, self.config_from_ui())
        self._fill_defaults(saved)  # o padrão pode ter mudado (ex.: critério padrão desmarcado)

    def restore_defaults(self):
        confirm = QMessageBox.question(
            self, "Restaurar padrões",
            "Voltar a ordenação e os filtros de todas as páginas ao padrão?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        page_settings.reset_all()
        self.load_page(self.current_page)


class ShortcutsTab(QWidget):
    """Configurações → Atalhos: só consulta, gerada do registro em frontend_desktop/shortcuts.py."""

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        page, layout = settings_page()
        outer.addWidget(page)
        self.key_labels = []
        for group_name in GROUPS:
            group, group_layout = settings_group(group_name)
            grid = QGridLayout()
            grid.setHorizontalSpacing(16)
            grid.setVerticalSpacing(10)
            grid.setColumnStretch(1, 1)
            for row, item in enumerate(s for s in SHORTCUTS if s.group == group_name):
                key = QLabel(item.keys)
                key.setProperty("class", "shortcut-key")
                key.setAlignment(Qt.AlignCenter)
                key.setMinimumWidth(72)  # mesma coluna nos dois grupos
                desc = QLabel(item.description)
                desc.setProperty("class", "shortcut-desc")
                desc.setWordWrap(True)
                grid.addWidget(key, row, 0, Qt.AlignLeft)
                grid.addWidget(desc, row, 1)
                self.key_labels.append(key)
            group_layout.addLayout(grid)
            layout.addWidget(group)
