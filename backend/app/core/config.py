import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "GameRoomLog API"
    VERSION: str = "0.1.1"
    API_V1_STR: str = "/api/v1"
    
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/gameroom.db"
    
    STORAGE_DIR: Path = BASE_DIR / "storage"
    COVERS_DIR: Path = BASE_DIR / "storage" / "covers"
    
    STEAMGRIDDB_API_KEY: str = ""
    
    model_config = SettingsConfigDict(case_sensitive=True)

settings = Settings()

# Garantir que o diretório de capas existe
settings.COVERS_DIR.mkdir(parents=True, exist_ok=True)
