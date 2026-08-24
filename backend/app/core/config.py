import sys
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

def get_base_data_dir() -> Path:
    """
    Retorna o diretório base para armazenamento de dados e banco SQLite.
    - Se GAMEROOM_DATA_DIR estiver definido: utiliza o caminho configurado.
    - Se estiver em execução compilada/empacotada (frozen/AppImage/.exe):
        * Linux: ~/.local/share/gameroomlog
        * Windows: %APPDATA%/GameRoomLog
        * macOS: ~/Library/Application Support/GameRoomLog
    - Se estiver em desenvolvimento local: utiliza o diretório backend do repositório.
    """
    if "GAMEROOM_DATA_DIR" in os.environ:
        p = Path(os.environ["GAMEROOM_DATA_DIR"]).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "GameRoomLog"
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support" / "GameRoomLog"
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "gameroomlog"
        base.mkdir(parents=True, exist_ok=True)
        return base

    return Path(__file__).resolve().parent.parent.parent

_BASE_DATA_DIR = get_base_data_dir()

class Settings(BaseSettings):
    PROJECT_NAME: str = "GameRoomLog API"
    VERSION: str = "0.2.4"
    API_V1_STR: str = "/api/v1"
    
    BASE_DIR: Path = _BASE_DATA_DIR
    DATABASE_URL: str = f"sqlite:///{_BASE_DATA_DIR}/gameroom.db"
    
    STORAGE_DIR: Path = _BASE_DATA_DIR / "storage"
    COVERS_DIR: Path = _BASE_DATA_DIR / "storage" / "covers"
    
    STEAMGRIDDB_API_KEY: str = ""
    
    model_config = SettingsConfigDict(case_sensitive=True)

settings = Settings()

# Garantir que o diretório de capas existe
settings.COVERS_DIR.mkdir(parents=True, exist_ok=True)
