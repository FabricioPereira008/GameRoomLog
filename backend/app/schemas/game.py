from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date, datetime
from backend.app.models.game import GameStatus, PlayType, GameFormat
from backend.app.schemas.genre import GenreResponse
from backend.app.schemas.platform import PlatformResponse
from backend.app.schemas.franchise import FranchiseResponse
from backend.app.schemas.developer import DeveloperResponse

class GameBase(BaseModel):
    title: str
    developer: Optional[str] = None
    developer_id: Optional[int] = None
    platform_id: Optional[int] = None
    franchise_id: Optional[int] = None
    status: GameStatus = GameStatus.DISPONIVEL
    cover_image: Optional[str] = None
    hltb_hours: Optional[float] = 0.0
    played_hours: Optional[float] = 0.0
    score: Optional[float] = None
    difficulty: Optional[float] = None
    finish_date: Optional[date] = None
    platinum_date: Optional[date] = None
    completion_year: Optional[int] = None
    play_type: PlayType = PlayType.PRIMEIRA_JOGADA
    play_count: int = 1
    format: GameFormat = GameFormat.DIGITAL
    is_favorite: bool = False
    notes: Optional[str] = None

class GameCreate(GameBase):
    genre_ids: Optional[List[int]] = []

class GameUpdate(BaseModel):
    title: Optional[str] = None
    developer: Optional[str] = None
    developer_id: Optional[int] = None
    platform_id: Optional[int] = None
    franchise_id: Optional[int] = None
    status: Optional[GameStatus] = None
    cover_image: Optional[str] = None
    hltb_hours: Optional[float] = None
    played_hours: Optional[float] = None
    score: Optional[float] = None
    difficulty: Optional[float] = None
    finish_date: Optional[date] = None
    platinum_date: Optional[date] = None
    completion_year: Optional[int] = None
    play_type: Optional[PlayType] = None
    play_count: Optional[int] = None
    format: Optional[GameFormat] = None
    is_favorite: Optional[bool] = None
    notes: Optional[str] = None
    genre_ids: Optional[List[int]] = None

class GameResponse(GameBase):
    id: int
    created_at: datetime
    updated_at: datetime
    platform: Optional[PlatformResponse] = None
    franchise: Optional[FranchiseResponse] = None
    developer_rel: Optional[DeveloperResponse] = None
    genres: List[GenreResponse] = []

    model_config = ConfigDict(from_attributes=True)
