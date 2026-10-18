"""Provedor Heroic Games Launcher: lê (somente leitura) as bibliotecas Epic, GOG e Amazon que o Heroic já unificou.

Os arquivos são internos do Heroic e não têm contrato estável: qualquer divergência vira "sem jogos"
para aquela loja, nunca uma exceção. Só há dados se o usuário fez login e abriu a biblioteca no Heroic.
"""
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, List, Optional

from backend.app.services.library.base import LibraryEntry, LibraryProviderError
from backend.app.services.library.settings_store import load_settings

logger = logging.getLogger(__name__)

NON_GAME_EPIC_CATEGORIES = {"addons", "digitalextras"}


def candidate_dirs() -> List[Path]:
    home = Path.home()
    if sys.platform == "win32":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        return [appdata / "heroic"]
    config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    return [
        config / "heroic",
        home / ".var" / "app" / "com.heroicgameslauncher.hgl" / "config" / "heroic",
    ]


def find_heroic_dir(configured: str = "") -> Optional[Path]:
    paths = [Path(configured).expanduser()] if configured else candidate_dirs()
    return next((p for p in paths if p.is_dir()), None)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Não foi possível ler %s", path.name)
        return None


def _text(value) -> Optional[str]:
    return value.strip() or None if isinstance(value, str) else None


def _gog_entries(heroic: Path) -> Optional[List[LibraryEntry]]:
    data = _read_json(heroic / "store_cache" / "gog_library.json")
    if data is None:
        return None
    games = data.get("games") if isinstance(data, dict) else data
    entries = []
    for game in games if isinstance(games, list) else []:
        if not isinstance(game, dict):
            continue
        app_id, title = game.get("app_name"), (game.get("title") or "").strip()
        if not app_id or not title:
            continue
        is_dlc = bool((game.get("install") or {}).get("is_dlc"))
        entries.append(LibraryEntry("gog", str(app_id), title, None, not is_dlc, _text(game.get("developer"))))
    return entries


def _epic_entries(heroic: Path) -> Optional[List[LibraryEntry]]:
    folder = heroic / "legendaryConfig" / "legendary" / "metadata"
    if not folder.is_dir():
        return None
    entries = []
    for path in folder.glob("*.json"):
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        app_id, title = data.get("app_name"), (data.get("app_title") or "").strip()
        meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        if not app_id or not title:
            continue
        paths = {c.get("path") for c in meta.get("categories") or [] if isinstance(c, dict)}
        is_game = not meta.get("mainGameItem") and not (paths & NON_GAME_EPIC_CATEGORIES)
        entries.append(LibraryEntry("epic", str(app_id), title, None, is_game, _text(meta.get("developer"))))
    return entries


def _amazon_entries(heroic: Path) -> Optional[List[LibraryEntry]]:
    # Formato não verificado contra uma conta real: leitura defensiva.
    data = _read_json(heroic / "store_cache" / "nile_library.json")
    if data is None:
        return None
    items = data.get("library") or data.get("games") if isinstance(data, dict) else data
    entries = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        product = item.get("product") if isinstance(item.get("product"), dict) else {}
        app_id = item.get("app_name") or item.get("id") or product.get("id")
        title = (item.get("title") or product.get("title") or "").strip()
        if app_id and title:
            developer = _text(item.get("developer") or product.get("developer"))
            entries.append(LibraryEntry("amazon", str(app_id), title, developer=developer))
    return entries


class HeroicProvider:
    store = "heroic"

    def fetch(self) -> List[LibraryEntry]:
        heroic = find_heroic_dir(load_settings().heroic_path)
        if heroic is None:
            raise LibraryProviderError(
                "Heroic não encontrado. Instale-o ou informe a pasta de configuração nas configurações."
            )
        found, entries = False, []
        for reader in (_epic_entries, _gog_entries, _amazon_entries):
            result = reader(heroic)
            if result is not None:
                found = True
                entries.extend(result)
        if not found:
            raise LibraryProviderError(
                "Nenhuma biblioteca encontrada no Heroic. Faça login nas lojas e abra a biblioteca no Heroic."
            )
        return entries
