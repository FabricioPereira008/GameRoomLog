from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.game import GameResponse


class LibraryEntryBase(BaseModel):
    store: str = Field(min_length=1, max_length=30)
    external_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)


class ScanRequest(BaseModel):
    stores: Optional[List[str]] = None  # None = todas as lojas registradas
    include_all: bool = False  # True desativa o filtro de itens que não são jogos


class Candidate(LibraryEntryBase):
    played_hours: Optional[float] = None
    ambiguous: bool = False  # título bate com mais de um jogo já cadastrado


class StoreError(BaseModel):
    store: str
    message: str


class ScanResponse(BaseModel):
    candidates: List[Candidate]
    auto_linked: int
    errors: List[StoreError]


class ImportItem(LibraryEntryBase):
    played_hours: Optional[float] = Field(default=None, ge=0)


class ImportRequest(BaseModel):
    items: List[ImportItem] = Field(min_length=1)


class ImportResponse(BaseModel):
    imported: List[GameResponse]
    skipped: int  # já vinculados anteriormente


class LinkRequest(BaseModel):
    game_id: int
    store: str = Field(min_length=1, max_length=30)
    external_id: str = Field(min_length=1, max_length=100)


class LinkResponse(LinkRequest):
    model_config = ConfigDict(from_attributes=True)
    id: int


class IgnoreRequest(BaseModel):
    items: List[LibraryEntryBase] = Field(min_length=1)


class IgnoredResponse(LibraryEntryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class LibrarySettingsResponse(BaseModel):
    steam_api_key_set: bool  # a key nunca é devolvida
    steam_id: str
    heroic_path: str = ""


class LibrarySettingsUpdate(BaseModel):
    steam_api_key: Optional[str] = Field(default=None, max_length=200)  # None mantém; "" apaga
    steam_id: Optional[str] = Field(default=None, max_length=40)
    heroic_path: Optional[str] = Field(default=None, max_length=500)
