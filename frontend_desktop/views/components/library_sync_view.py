"""Sincronização com bibliotecas de lojas: encontra jogos fora do GameRoom e importa os escolhidos."""
import logging
from typing import Dict, List

from PySide6.QtCore import Qt, QSettings, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from frontend_desktop.api_client.client import api_client
from frontend_desktop.styles.tokens import COLORS
from frontend_desktop.ui_helpers import add_search_icon, set_button_icon, set_status
from frontend_desktop.workers import run_async

logger = logging.getLogger(__name__)

STORE_LABELS = {"heroic": "Heroic", "steam": "Steam", "epic": "Epic", "gog": "GOG", "amazon": "Amazon"}
COL_TITLE, COL_STORE, COL_HOURS = range(3)


def store_label(store: str) -> str:
    return STORE_LABELS.get(store, store.capitalize())


def fetch_covers(games: List[dict], api_key: str) -> List[dict]:
    """Busca capas (uma a uma) dos jogos recém-importados; devolve os jogos que ganharam capa."""
    updated = []
    for game in games:
        try:
            if api_client.auto_cover_game(game["id"], api_key or None).get("success"):
                updated.append(api_client.get_game(game["id"]))
        except Exception as exc:
            logger.warning("Falha ao buscar capa de %s: %s", game.get("title"), exc)
    return updated


class LibrarySyncView(QWidget):
    games_imported = Signal(list)  # jogos criados (dicts da API)
    games_updated = Signal(list)   # jogos que ganharam capa depois

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False
        self._ignored: List[dict] = []
        self._init_ui()
        self._load_settings()

    # --- construção ---
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_candidates_tab(), "Jogos encontrados")
        self.tabs.addTab(self._build_config_tab(), "Configurações")
        self.tabs.addTab(self._build_ignored_tab(), "Ignorados")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

    def _build_candidates_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        top = QHBoxLayout()
        self.btn_scan = QPushButton("Buscar nas lojas")
        self.btn_scan.setProperty("class", "action-btn")
        self.btn_scan.setCursor(Qt.PointingHandCursor)
        set_button_icon(self.btn_scan, "refresh-cw", COLORS["on_accent"])
        self.btn_scan.clicked.connect(self.start_scan)
        top.addWidget(self.btn_scan)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filtrar por título...")
        add_search_icon(self.search_input)
        self.search_input.textChanged.connect(self.apply_filters)
        top.addWidget(self.search_input, 1)
        self.store_filter = QComboBox()
        self.store_filter.addItem("Todas as lojas", "")
        self.store_filter.currentIndexChanged.connect(self.apply_filters)
        top.addWidget(self.store_filter)
        self.chk_played = QCheckBox("Só jogados")
        self.chk_played.toggled.connect(self.apply_filters)
        top.addWidget(self.chk_played)
        self.chk_show_all = QCheckBox("Mostrar tudo (incluir ferramentas/DLCs)")
        top.addWidget(self.chk_show_all)
        layout.addLayout(top)

        self.status_label = QLabel("Clique em “Buscar nas lojas” para listar os jogos que ainda não estão no GameRoom.")
        self.status_label.setWordWrap(True)
        self.status_label.setProperty("class", "status-muted")
        layout.addWidget(self.status_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Título", "Loja", "Horas jogadas"])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(COL_TITLE, Qt.AscendingOrder)
        self.tree.setColumnWidth(COL_TITLE, 460)
        self.tree.itemChanged.connect(lambda *_: self._update_buttons())
        layout.addWidget(self.tree, 1)

        bottom = QHBoxLayout()
        self.btn_select_visible = QPushButton("Selecionar visíveis")
        self.btn_select_visible.clicked.connect(lambda: self._set_visible_checked(True))
        self.btn_clear = QPushButton("Limpar seleção")
        self.btn_clear.clicked.connect(lambda: self._set_all_checked(False))
        self.btn_ignore = QPushButton("Ignorar selecionados")
        self.btn_ignore.clicked.connect(self.ignore_selected)
        self.btn_import = QPushButton("Importar selecionados")
        self.btn_import.setProperty("class", "action-btn")
        self.btn_import.clicked.connect(self.import_selected)
        for b in (self.btn_select_visible, self.btn_clear, self.btn_ignore):
            b.setCursor(Qt.PointingHandCursor)
            bottom.addWidget(b)
        bottom.addStretch()
        self.btn_import.setCursor(Qt.PointingHandCursor)
        bottom.addWidget(self.btn_import)
        layout.addLayout(bottom)
        self._update_buttons()
        return tab

    def _build_config_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setAlignment(Qt.AlignTop)
        desc = QLabel(
            "<b>Steam</b>: crie uma API key em steamcommunity.com/dev/apikey e informe o seu SteamID64. "
            "Nas configurações de privacidade do perfil, deixe os <b>detalhes dos jogos públicos</b>.<br>"
            "A key fica salva apenas neste computador.<br><br>"
            "<b>Epic, GOG e Amazon</b>: lidos do Heroic Games Launcher (faça login nas lojas e abra a biblioteca nele). "
            "A pasta é detectada automaticamente; preencha só se estiver em outro lugar."
        )
        desc.setWordWrap(True)
        desc.setProperty("class", "settings-desc")
        layout.addWidget(desc)
        form = QFormLayout()
        self.input_steam_key = QLineEdit()
        self.input_steam_key.setEchoMode(QLineEdit.Password)
        self.input_steam_id = QLineEdit()
        self.input_steam_id.setPlaceholderText("7656119...")
        form.addRow("Steam API key", self.input_steam_key)
        form.addRow("SteamID64", self.input_steam_id)
        self.input_heroic_path = QLineEdit()
        self.input_heroic_path.setPlaceholderText("Automático (ex.: ~/.config/heroic)")
        form.addRow("Pasta do Heroic", self.input_heroic_path)
        layout.addLayout(form)
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
        info = QLabel("Jogos ignorados não aparecem nas próximas buscas.")
        info.setProperty("class", "settings-desc")
        layout.addWidget(info)
        self.ignored_list = QListWidget()
        self.ignored_list.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.ignored_list, 1)
        self.btn_unignore = QPushButton("Desfazer ignorar")
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
        self.input_steam_key.setPlaceholderText("(já salva — deixe vazio para manter)" if cfg.get("steam_api_key_set") else "")

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

    def _on_scan_done(self, data: dict):
        candidates = data.get("candidates", [])
        self.tree.setSortingEnabled(False)
        self.tree.clear()
        stores = sorted({c["store"] for c in candidates})
        self.store_filter.blockSignals(True)
        self.store_filter.clear()
        self.store_filter.addItem("Todas as lojas", "")
        for store in stores:
            self.store_filter.addItem(store_label(store), store)
        self.store_filter.blockSignals(False)
        for cand in candidates:
            self.tree.addTopLevelItem(self._make_item(cand))
        self.tree.setSortingEnabled(True)
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
        item = QTreeWidgetItem([title, store_label(cand["store"]), "" if hours is None else f"{hours:g} h"])
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(COL_TITLE, Qt.Unchecked)  # tudo desmarcado por padrão
        item.setData(COL_TITLE, Qt.UserRole, cand)
        if cand.get("ambiguous"):
            item.setToolTip(COL_TITLE, "O título coincide com mais de um jogo já cadastrado.")
        return item

    # --- filtros e seleção ---
    def _items(self) -> List[QTreeWidgetItem]:
        return [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]

    def apply_filters(self, *_):
        text = self.search_input.text().strip().lower()
        store = self.store_filter.currentData() or ""
        only_played = self.chk_played.isChecked()
        for item in self._items():
            cand = item.data(COL_TITLE, Qt.UserRole)
            visible = (
                text in cand["title"].lower()
                and (not store or cand["store"] == store)
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
        items = self.checked_items()
        if not items or self._busy:
            return
        self._set_busy(True)
        set_status(self.status_label, "muted", f"Importando {len(items)} jogo(s)...")
        run_async(self, api_client.library_import, lambda res: self._on_imported(items, res),
                  self._on_scan_failed, self._payload(items))

    def _on_imported(self, items: List[QTreeWidgetItem], result: dict):
        games = result.get("imported", [])
        self._remove_items(items)
        self._set_busy(False)
        set_status(self.status_label, "ok", f"{len(games)} jogo(s) importado(s). Buscando capas em segundo plano...")
        if not games:
            return
        self.games_imported.emit(games)
        key = QSettings("GameRoom", "GameRoomLog").value("steamgriddb_key", "")
        run_async(self, fetch_covers, self._on_covers_done, lambda _m: None, games, key)

    def _on_covers_done(self, updated: list):
        if updated:
            self.games_updated.emit(updated)
        set_status(self.status_label, "ok", f"Importação concluída ({len(updated)} capa(s) encontrada(s)).")

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
            item = QListWidgetItem(f"{row['title']}  —  {store_label(row['store'])}")
            item.setData(Qt.UserRole, row["id"])
            self.ignored_list.addItem(item)

    def unignore_selected(self):
        items = self.ignored_list.selectedItems()
        for item in items:
            run_async(self, api_client.library_unignore, lambda _ok, it=item: self._drop_ignored(it),
                      lambda _m: None, item.data(Qt.UserRole))

    def _drop_ignored(self, item: QListWidgetItem):
        row = self.ignored_list.row(item)
        if row >= 0:
            self.ignored_list.takeItem(row)
