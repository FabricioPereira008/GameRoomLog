"""Configuração local das lojas (Steam key/ID...), em JSON no diretório de dados, só legível pelo usuário."""
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.app.core.config import settings


@dataclass
class LibrarySettings:
    steam_api_key: str = ""
    steam_id: str = ""


def settings_path() -> Path:
    return settings.BASE_DIR / "library_settings.json"


def load_settings() -> LibrarySettings:
    try:
        raw = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return LibrarySettings()
    if not isinstance(raw, dict):
        return LibrarySettings()
    return LibrarySettings(
        steam_api_key=str(raw.get("steam_api_key") or ""),
        steam_id=str(raw.get("steam_id") or ""),
    )


def save_settings(value: LibrarySettings) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Cria o arquivo já com 0600 (no Windows o modo é ignorado)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(asdict(value), fh)
