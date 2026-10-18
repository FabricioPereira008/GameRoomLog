"""Sincronização com bibliotecas de lojas: encontra jogos fora do GameRoom e importa os escolhidos."""
import logging
from collections import Counter
from typing import Dict, List

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QDialog, QFrame, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QStackedWidget, QStyledItemDelegate, QTabWidget, QToolButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QGridLayout,
)

from frontend_desktop import icons, preferences
from frontend_desktop.api_client.client import api_client
from frontend_desktop.styles.tokens import COLORS
from frontend_desktop.ui_helpers import add_search_icon, set_button_icon, set_status
from frontend_desktop.views.dialogs.game_dialog import GameDialog
from frontend_desktop.workers import run_async

logger = logging.getLogger(__name__)

STORE_LABELS = {"heroic": "Heroic", "steam": "Steam", "epic": "Epic", "gog": "GOG", "amazon": "Amazon"}
# Cor de destaque de cada loja (selo na lista e chips de filtro)
STORE_COLORS = {"steam": "#66c0f4", "epic": "#d4d4d8", "gog": "#c084fc", "amazon": "#f59e0b"}
COL_TITLE, COL_STORE, COL_DEVELOPER, COL_HOURS = range(4)
ALL_STORES = ""


def store_label(store: str) -> str:
    return STORE_LABELS.get(store, store.capitalize())


def store_color(store: str) -> str:
    return STORE_COLORS.get(store, COLORS["text_muted"])


def import_prefill(cand: dict) -> dict:
    """Dados iniciais da tela de edição para um jogo vindo da loja (Digital/Disponível/PC)."""
    data = {
        "title": cand["title"],
        "status": "Disponível",
        "format": "Digital",
        "played_hours": cand.get("played_hours") or 0,
        "platform": {"name": "PC"},
    }
    if cand.get("developer"):
        data["developer"] = cand["developer"]
    return data


def finish_import(game: dict, cand: dict, cover_key: str = ""):
    """Vincula o jogo recém-salvo à loja e busca capa se não tiver; devolve o jogo se ganhou capa."""
    api_client.library_link(game["id"], cand["store"], cand["external_id"])
    if game.get("cover_image"):
        return None
    try:
        if api_client.auto_cover_game(game["id"], cover_key or None).get("success"):
            return api_client.get_game(game["id"])
    except Exception as exc:
        logger.warning("Falha ao buscar capa de %s: %s", game.get("title"), exc)
    return None


class StoreBadgeDelegate(QStyledItemDelegate):
    """Pinta a coluna "Loja" como um selo na cor da loja."""

    def paint(self, painter, option, index):
        store = index.data(Qt.UserRole + 1) or ""
        text = store_label(store) if store else ""
        super().paint(painter, option, index)  # fundo/seleção da linha
        if not text:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(store_color(store))
        fm = option.fontMetrics
        w, h = fm.horizontalAdvance(text) + 16, 20
        rect = QRectF(option.rect.x() + 4, option.rect.center().y() - h / 2 + 1, w, h)
        bg = QColor(color)
        bg.setAlpha(38)
        path = QPainterPath()
        path.addRoundedRect(rect, 5, 5)
        painter.fillPath(path, bg)
        painter.setPen(color)
        painter.drawText(rect, Qt.AlignCenter, text)
        painter.restore()

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.text = ""  # o texto vai no selo


class LibrarySyncView(QWidget):
    games_imported = Signal(list)  # jogos criados (dicts da API)
    games_updated = Signal(list)   # jogos que ganharam capa depois

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False
        self._ignored: List[dict] = []
        self._store = ALL_STORES
        self._init_ui()
        self._load_settings()

    # --- construção ---
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setProperty("class", "settings-tabs")
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        self.tabs.addTab(self._build_candidates_tab(), "Jogos encontrados")
        self.tabs.addTab(self._build_config_tab(), "Lojas")
        self.tabs.addTab(self._build_ignored_tab(), "Ignorados")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

    def _build_candidates_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 14, 0, 0)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.btn_scan = QPushButton("Buscar nas lojas")
        self.btn_scan.setProperty("class", "action-btn")
        self.btn_scan.setCursor(Qt.PointingHandCursor)
        set_button_icon(self.btn_scan, "refresh-cw", COLORS["on_accent"])
        self.btn_scan.clicked.connect(self.start_scan)
        top.addWidget(self.btn_scan)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filtrar por título ou desenvolvedora...")
        self.search_input.setProperty("class", "search-input")
        self.search_input.setClearButtonEnabled(True)
        add_search_icon(self.search_input)
        self.search_input.textChanged.connect(self.apply_filters)
        top.addWidget(self.search_input, 1)
        self.chk_played = QCheckBox("Só jogados")
        self.chk_played.setToolTip("Jogos com horas registradas na loja (só a Steam informa)")
        self.chk_played.toggled.connect(self.apply_filters)
        top.addWidget(self.chk_played)
        self.chk_show_all = QCheckBox("Incluir ferramentas e DLCs")
        self.chk_show_all.setToolTip("Vale para a próxima busca")
        top.addWidget(self.chk_show_all)
        layout.addLayout(top)

        # Chips por loja (com a contagem): filtram a lista
        self.store_bar = QHBoxLayout()
        self.store_bar.setSpacing(6)
        self.store_group = QButtonGroup(self)
        self.store_group.setExclusive(True)
        self.store_buttons: Dict[str, QToolButton] = {}
        self.store_bar.addStretch()
        layout.addLayout(self.store_bar)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setProperty("class", "status-muted")
        layout.addWidget(self.status_label)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_empty_state())
        self.tree = QTreeWidget()
        self.tree.setObjectName("syncTree")
        self.tree.setHeaderLabels(["Título", "Loja", "Desenvolvedora", "Horas jogadas"])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(COL_TITLE, Qt.AscendingOrder)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_TITLE, QHeaderView.Stretch)
        for col, width in ((COL_STORE, 100), (COL_DEVELOPER, 240), (COL_HOURS, 120)):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
            self.tree.setColumnWidth(col, width)
        self.tree.setItemDelegateForColumn(COL_STORE, StoreBadgeDelegate(self.tree))
        self.tree.itemChanged.connect(lambda *_: self._update_buttons())
        self.tree.itemDoubleClicked.connect(self._toggle_item)
        self.stack.addWidget(self.tree)
        layout.addWidget(self.stack, 1)

        bar = QFrame()
        bar.setProperty("class", "action-bar")
        bottom = QHBoxLayout(bar)
        bottom.setContentsMargins(14, 10, 14, 10)
        bottom.setSpacing(8)
        self.selection_label = QLabel("Nenhum jogo selecionado")
        self.selection_label.setProperty("class", "status-muted")
        bottom.addWidget(self.selection_label)
        self.btn_select_visible = QPushButton("Selecionar visíveis")
        self.btn_select_visible.clicked.connect(lambda: self._set_visible_checked(True))
        self.btn_clear = QPushButton("Limpar seleção")
        self.btn_clear.clicked.connect(lambda: self._set_all_checked(False))
        for b in (self.btn_select_visible, self.btn_clear):
            b.setProperty("class", "small-btn")
            b.setCursor(Qt.PointingHandCursor)
            bottom.addWidget(b)
        bottom.addStretch()
        self.btn_ignore = QPushButton("Ignorar")
        self.btn_ignore.setToolTip("Os jogos ignorados não aparecem nas próximas buscas")
        self.btn_ignore.setProperty("class", "cancel-btn")
        self.btn_ignore.setCursor(Qt.PointingHandCursor)
        self.btn_ignore.clicked.connect(self.ignore_selected)
        bottom.addWidget(self.btn_ignore)
        self.btn_import = QPushButton("Importar selecionados")
        self.btn_import.setProperty("class", "action-btn")
        self.btn_import.setCursor(Qt.PointingHandCursor)
        self.btn_import.clicked.connect(self.import_selected)
        bottom.addWidget(self.btn_import)
        layout.addWidget(bar)
        self._update_buttons()
        return tab

    def _build_empty_state(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)
        icon = QLabel()
        icon.setPixmap(icons.pixmap("refresh-cw", COLORS["text_dim"], 44))
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)
        title = QLabel("Encontre os jogos das suas lojas")
        title.setProperty("class", "section-header")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        text = QLabel("A busca lista os jogos da Steam, Epic, GOG e Amazon que ainda não estão no GameRoom.\n"
                      "Cada jogo escolhido abre a tela de informações antes de ser salvo.")
        text.setProperty("class", "settings-desc")
        text.setAlignment(Qt.AlignCenter)
        layout.addWidget(text)
        self.empty_label = text
        return box

    def _build_config_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 16, 16, 16)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignTop)

        steam = QGroupBox("Steam")
        steam.setProperty("class", "settings-group")
        grid = QGridLayout(steam)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        desc = QLabel(
            "Crie uma API key em <b>steamcommunity.com/dev/apikey</b> e informe o seu SteamID64. Nas configurações de "
            "privacidade do perfil, deixe os <b>detalhes dos jogos públicos</b>. A key fica salva só neste computador.")
        desc.setWordWrap(True)
        desc.setProperty("class", "settings-desc")
        grid.addWidget(desc, 0, 0, 1, 2)
        self.input_steam_key = QLineEdit()
        self.input_steam_key.setEchoMode(QLineEdit.Password)
        self.input_steam_id = QLineEdit()
        self.input_steam_id.setPlaceholderText("7656119...")
        grid.addWidget(QLabel("API key"), 1, 0)
        grid.addWidget(self.input_steam_key, 1, 1)
        grid.addWidget(QLabel("SteamID64"), 2, 0)
        grid.addWidget(self.input_steam_id, 2, 1)
        self.steam_state = QLabel("")
        grid.addWidget(self.steam_state, 3, 1)
        layout.addWidget(steam)

        heroic = QGroupBox("Epic, GOG e Amazon (Heroic Games Launcher)")
        heroic.setProperty("class", "settings-group")
        hgrid = QGridLayout(heroic)
        hgrid.setHorizontalSpacing(12)
        hgrid.setVerticalSpacing(10)
        hdesc = QLabel("Lidos do Heroic: faça login nas lojas e abra a biblioteca nele. A pasta é detectada "
                       "automaticamente; preencha só se estiver em outro lugar.")
        hdesc.setWordWrap(True)
        hdesc.setProperty("class", "settings-desc")
        hgrid.addWidget(hdesc, 0, 0, 1, 2)
        self.input_heroic_path = QLineEdit()
        self.input_heroic_path.setPlaceholderText("Automático (ex.: ~/.config/heroic)")
        hgrid.addWidget(QLabel("Pasta"), 1, 0)
        hgrid.addWidget(self.input_heroic_path, 1, 1)
        layout.addWidget(heroic)

        row = QHBoxLayout()
        self.btn_save = QPushButton("Salvar")
        self.btn_save.setProperty("class", "action-btn")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self.save_settings)
        row.addWidget(self.btn_save)
        self.config_status = QLabel("")
        row.addWidget(self.config_status, 1)
        layout.addLayout(row)
        return tab

    def _build_ignored_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 14, 0, 0)
        layout.setSpacing(10)
        info = QLabel("Jogos ignorados não aparecem nas próximas buscas. Selecione e desfaça para voltar a vê-los.")
        info.setProperty("class", "settings-desc")
        layout.addWidget(info)
        self.ignored_list = QListWidget()
        self.ignored_list.setObjectName("ignoredList")
        self.ignored_list.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.ignored_list, 1)
        self.btn_unignore = QPushButton("Desfazer ignorar")
        self.btn_unignore.setProperty("class", "cancel-btn")
        self.btn_unignore.setCursor(Qt.PointingHandCursor)
        self.btn_unignore.clicked.connect(self.unignore_selected)
        layout.addWidget(self.btn_unignore, 0, Qt.AlignRight)
        return tab

    # --- configurações ---
    def _load_settings(self):
        run_async(self, api_client.get_library_settings, self._on_settings_loaded, lambda _m: None)

    def _on_settings_loaded(self, cfg: dict):
        self.input_steam_id.setText(cfg.get("steam_id", ""))
        self.input_heroic_path.setText(cfg.get("heroic_path", ""))
        key_set = bool(cfg.get("steam_api_key_set"))
        self.input_steam_key.setPlaceholderText("(já salva — deixe vazio para manter)" if key_set else "")
        if key_set and cfg.get("steam_id"):
            set_status(self.steam_state, "ok", "Configurada")
        else:
            set_status(self.steam_state, "muted", "Falta a API key ou o SteamID64")

    def save_settings(self):
        payload: Dict[str, str] = {
            "steam_id": self.input_steam_id.text().strip(),
            "heroic_path": self.input_heroic_path.text().strip(),
        }
        key = self.input_steam_key.text().strip()
        if key:  # vazio mantém a key já salva
            payload["steam_api_key"] = key
        set_status(self.config_status, "muted", "Salvando...")
        run_async(self, api_client.save_library_settings, self._on_settings_saved,
                  lambda m: set_status(self.config_status, "error", f"Erro ao salvar: {m}"), payload)

    def _on_settings_saved(self, cfg: dict):
        self.input_steam_key.clear()
        self._on_settings_loaded(cfg)
        set_status(self.config_status, "ok", "Configurações salvas.")

    # --- scan ---
    def _set_busy(self, busy: bool):
        self._busy = busy
        self.btn_scan.setEnabled(not busy)
        self._update_buttons()

    def start_scan(self):
        if self._busy:
            return
        self._set_busy(True)
        set_status(self.status_label, "muted", "Buscando nas lojas...")
        run_async(self, api_client.library_scan, self._on_scan_done, self._on_scan_failed,
                  self.chk_show_all.isChecked())

    def _on_scan_failed(self, message: str):
        self._set_busy(False)
        set_status(self.status_label, "error", f"Erro ao buscar: {message}")

    def _rebuild_store_chips(self, counts: Counter):
        for btn in self.store_buttons.values():
            self.store_group.removeButton(btn)
            btn.deleteLater()
        self.store_buttons = {}
        total = sum(counts.values())
        entries = [(ALL_STORES, f"Todas  {total}")] + [(s, f"{store_label(s)}  {counts[s]}") for s in sorted(counts)]
        for i, (store, text) in enumerate(entries):
            btn = QToolButton()
            btn.setText(text)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("class", "store-chip")
            if store:
                btn.setStyleSheet(f"QToolButton:checked {{ color: {store_color(store)}; border-color: {store_color(store)}; }}")
            btn.clicked.connect(lambda _c=False, s=store: self.set_store_filter(s))
            self.store_group.addButton(btn)
            self.store_buttons[store] = btn
            self.store_bar.insertWidget(i, btn)
        if self._store not in self.store_buttons:
            self._store = ALL_STORES
        self.store_buttons[self._store].setChecked(True)

    def set_store_filter(self, store: str):
        self._store = store if store in self.store_buttons else ALL_STORES
        if self._store in self.store_buttons:
            self.store_buttons[self._store].setChecked(True)
        self.apply_filters()

    def _on_scan_done(self, data: dict):
        candidates = data.get("candidates", [])
        self.tree.setSortingEnabled(False)
        self.tree.clear()
        for cand in candidates:
            self.tree.addTopLevelItem(self._make_item(cand))
        self.tree.setSortingEnabled(True)
        self._rebuild_store_chips(Counter(c["store"] for c in candidates))
        self.stack.setCurrentWidget(self.tree if candidates else self.stack.widget(0))
        if not candidates:
            self.empty_label.setText("Nenhum jogo novo nas lojas: tudo já está no GameRoom (ou foi ignorado).")
        self.apply_filters()
        parts = [f"{len(candidates)} jogo(s) encontrado(s)"]
        if data.get("auto_linked"):
            parts.append(f"{data['auto_linked']} já cadastrado(s) foram vinculados automaticamente")
        errors = data.get("errors", [])
        kind = "error" if errors else "ok"
        text = ". ".join(parts) + "."
        if errors:
            text += " Problemas: " + "; ".join(f"{store_label(e['store'])}: {e['message']}" for e in errors)
        set_status(self.status_label, kind, text)
        self._set_busy(False)

    @staticmethod
    def _make_item(cand: dict) -> QTreeWidgetItem:
        title = cand["title"] + ("  (título ambíguo)" if cand.get("ambiguous") else "")
        hours = cand.get("played_hours")
        item = QTreeWidgetItem([title, store_label(cand["store"]), cand.get("developer") or "",
                                "" if hours is None else f"{hours:g} h"])
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(COL_TITLE, Qt.Unchecked)  # tudo desmarcado por padrão
        item.setData(COL_TITLE, Qt.UserRole, cand)
        item.setData(COL_STORE, Qt.UserRole + 1, cand["store"])
        item.setSizeHint(COL_TITLE, QSize(0, 34))
        if cand.get("ambiguous"):
            item.setToolTip(COL_TITLE, "O título coincide com mais de um jogo já cadastrado.")
            item.setForeground(COL_TITLE, QColor(COLORS["warning"]))
        return item

    def _toggle_item(self, item: QTreeWidgetItem, _column: int = 0):
        item.setCheckState(COL_TITLE, Qt.Unchecked if item.checkState(COL_TITLE) == Qt.Checked else Qt.Checked)

    # --- filtros e seleção ---
    def _items(self) -> List[QTreeWidgetItem]:
        return [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]

    def apply_filters(self, *_):
        text = self.search_input.text().strip().lower()
        only_played = self.chk_played.isChecked()
        for item in self._items():
            cand = item.data(COL_TITLE, Qt.UserRole)
            visible = (
                (text in cand["title"].lower() or text in (cand.get("developer") or "").lower())
                and (not self._store or cand["store"] == self._store)
                and (not only_played or (cand.get("played_hours") or 0) > 0)
            )
            item.setHidden(not visible)
        self._update_buttons()

    def _set_visible_checked(self, checked: bool):
        self.tree.blockSignals(True)
        for item in self._items():
            if not item.isHidden():
                item.setCheckState(COL_TITLE, Qt.Checked if checked else Qt.Unchecked)
        self.tree.blockSignals(False)
        self._update_buttons()

    def _set_all_checked(self, checked: bool):
        self.tree.blockSignals(True)
        for item in self._items():
            item.setCheckState(COL_TITLE, Qt.Checked if checked else Qt.Unchecked)
        self.tree.blockSignals(False)
        self._update_buttons()

    def checked_items(self) -> List[QTreeWidgetItem]:
        return [i for i in self._items() if i.checkState(COL_TITLE) == Qt.Checked]

    def _update_buttons(self):
        n = len(self.checked_items())
        self.btn_import.setText(f"Importar selecionados ({n})")
        self.btn_import.setEnabled(n > 0 and not self._busy)
        self.btn_ignore.setEnabled(n > 0 and not self._busy)
        visible = sum(1 for i in self._items() if not i.isHidden())
        self.selection_label.setText(
            f"{n} de {visible} selecionado(s)" if n else (f"{visible} jogo(s) na lista" if visible else "Nenhum jogo selecionado"))

    def _remove_items(self, items: List[QTreeWidgetItem]):
        for item in items:
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))
        self._update_buttons()

    # --- importar / ignorar ---
    @staticmethod
    def _payload(items: List[QTreeWidgetItem]) -> List[dict]:
        return [
            {k: v for k, v in item.data(COL_TITLE, Qt.UserRole).items() if k in ("store", "external_id", "title", "played_hours")}
            for item in items
        ]

    def import_selected(self):
        """Abre a tela de edição de cada jogo selecionado; só os que forem salvos entram no GameRoom."""
        items = self.checked_items()
        if not items or self._busy:
            return
        self._set_busy(True)
        key = preferences.settings().value("steamgriddb_key", "")
        imported = 0
        try:
            for index, item in enumerate(items, 1):
                cand = item.data(COL_TITLE, Qt.UserRole)
                set_status(self.status_label, "muted", f"Importando {index} de {len(items)}: {cand['title']}")
                game = self.edit_before_import(cand, index, len(items))
                if game is None:
                    if index < len(items) and not self.confirm_continue(len(items) - index):
                        break
                    continue
                imported += 1
                self._remove_items([item])
                self.games_imported.emit([game])
                run_async(self, finish_import, self._on_import_finished,
                          lambda m, g=game: self._on_link_failed(g, m), game, cand, key)
        finally:
            self._set_busy(False)
        set_status(self.status_label, "ok" if imported else "muted", f"{imported} jogo(s) importado(s).")

    def edit_before_import(self, cand: dict, index: int, total: int):
        """Tela de edição pré-preenchida; devolve o jogo salvo ou None se cancelada."""
        dialog = GameDialog(import_prefill(cand), self)
        dialog.setWindowTitle(f"Importar jogo ({index} de {total}) — {store_label(cand['store'])}")
        if cand["store"] == "steam" and not cand.get("developer"):
            # A Steam não manda a desenvolvedora na lista: busca na loja enquanto a tela está aberta
            run_async(dialog, api_client.library_details,
                      lambda details: dialog.suggest_developer(details.get("developer")), lambda _m: None,
                      cand["store"], cand["external_id"])
        if dialog.exec() == QDialog.Accepted and dialog.saved_game and not dialog.is_deleted:
            return dialog.saved_game
        return None

    def confirm_continue(self, remaining: int) -> bool:
        answer = QMessageBox.question(
            self, "Importação", f"Jogo não importado. Continuar com os próximos {remaining} jogo(s)?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        return answer == QMessageBox.Yes

    def _on_import_finished(self, updated):
        if updated:
            self.games_updated.emit([updated])

    def _on_link_failed(self, game: dict, message: str):
        set_status(self.status_label, "error",
                   f"“{game.get('title')}” foi salvo, mas não foi vinculado à loja: {message}")

    def ignore_selected(self):
        items = self.checked_items()
        if not items or self._busy:
            return
        self._set_busy(True)
        run_async(self, api_client.library_ignore, lambda _r: self._on_ignored(items),
                  self._on_scan_failed, self._payload(items))

    def _on_ignored(self, items: List[QTreeWidgetItem]):
        self._remove_items(items)
        self._set_busy(False)
        set_status(self.status_label, "ok", f"{len(items)} jogo(s) ignorado(s).")

    # --- ignorados ---
    def _on_tab_changed(self, index: int):
        if self.tabs.widget(index) is self.ignored_list.parentWidget():
            self.load_ignored()

    def load_ignored(self):
        run_async(self, api_client.library_ignored, self._on_ignored_loaded, lambda _m: None)

    def _on_ignored_loaded(self, rows: List[dict]):
        self._ignored = rows
        self.ignored_list.clear()
        for row in rows:
            item = QListWidgetItem(f"{row['title']}   ·   {store_label(row['store'])}")
            item.setData(Qt.UserRole, row["id"])
            item.setForeground(QColor(COLORS["text"]))
            self.ignored_list.addItem(item)
        if not rows:
            placeholder = QListWidgetItem("Nenhum jogo ignorado.")
            placeholder.setFlags(Qt.NoItemFlags)
            self.ignored_list.addItem(placeholder)

    def unignore_selected(self):
        items = [i for i in self.ignored_list.selectedItems() if i.data(Qt.UserRole) is not None]
        for item in items:
            run_async(self, api_client.library_unignore, lambda _ok, it=item: self._drop_ignored(it),
                      lambda _m: None, item.data(Qt.UserRole))

    def _drop_ignored(self, item: QListWidgetItem):
        row = self.ignored_list.row(item)
        if row >= 0:
            self.ignored_list.takeItem(row)
