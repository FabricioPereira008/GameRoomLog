from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import date, datetime
from backend.app.models.game import GameStatus, PlayType, GameFormat
from backend.app.schemas.genre import GenreResponse
from backend.app.schemas.platform import PlatformResponse
from backend.app.schemas.franchise import FranchiseResponse
from backend.app.schemas.developer import DeveloperResponse

class GameBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    developer: Optional[str] = None
    developer_id: Optional[int] = None
    platform_id: Optional[int] = None
    franchise_id: Optional[int] = None
    status: GameStatus = GameStatus.DISPONIVEL
    cover_image: Optional[str] = None
    hltb_hours: Optional[float] = Field(default=0.0, ge=0)
    played_hours: Optional[float] = Field(default=0.0, ge=0)
    score: Optional[float] = Field(default=None, ge=0, le=10)
    difficulty: Optional[float] = Field(default=None, ge=0, le=10)
    finish_date: Optional[date] = None
    platinum_date: Optional[date] = None
    completion_year: Optional[int] = None
    play_type: PlayType = PlayType.PRIMEIRA_JOGADA
    play_count: int = Field(default=1, ge=1)
    format: GameFormat = GameFormat.DIGITAL
    is_favorite: bool = False
    notes: Optional[str] = None

class GameCreate(GameBase):
    genre_ids: List[int] = Field(default_factory=list)

class GameUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    developer: Optional[str] = None
    developer_id: Optional[int] = None
    platform_id: Optional[int] = None
    franchise_id: Optional[int] = None
    status: Optional[GameStatus] = None
    cover_image: Optional[str] = None
    hltb_hours: Optional[float] = Field(default=None, ge=0)
    played_hours: Optional[float] = Field(default=None, ge=0)
    score: Optional[float] = Field(default=None, ge=0, le=10)
    difficulty: Optional[float] = Field(default=None, ge=0, le=10)
    finish_date: Optional[date] = None
    platinum_date: Optional[date] = None
    completion_year: Optional[int] = None
    play_type: Optional[PlayType] = None
    play_count: Optional[int] = Field(default=None, ge=1)
    format: Optional[GameFormat] = None
    is_favorite: Optional[bool] = None
    notes: Optional[str] = None
    genre_ids: Optional[List[int]] = None

class GameResponse(GameBase):
    # Respostas não revalidam limites: dados legados/importados podem estar fora da faixa
    title: str
    hltb_hours: Optional[float] = 0.0
    played_hours: Optional[float] = 0.0
    score: Optional[float] = None
    difficulty: Optional[float] = None
    play_count: int = 1
    id: int
    created_at: datetime
    updated_at: datetime
    platform: Optional[PlatformResponse] = None
    franchise: Optional[FranchiseResponse] = None
    developer_rel: Optional[DeveloperResponse] = None
    genres: List[GenreResponse] = []

    model_config = ConfigDict(from_attributes=True)
