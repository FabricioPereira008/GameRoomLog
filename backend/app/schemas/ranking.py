from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.schemas.game import GameResponse

MAX_RANKING_SIZE = 50
FILTER_FIELDS = ("genre_id", "franchise_id", "platform_id")


def _check_single_filter(model):
    chosen = [f for f in FILTER_FIELDS if getattr(model, f, None) is not None]
    if len(chosen) > 1:
        raise ValueError("Um ranking só pode ter um filtro (gênero, franquia ou plataforma)")
    return model


class RankingCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    max_size: int = Field(default=10, ge=1, le=MAX_RANKING_SIZE)
    genre_id: Optional[int] = None
    franchise_id: Optional[int] = None
    platform_id: Optional[int] = None

    _single_filter = model_validator(mode="after")(_check_single_filter)


class RankingUpdate(BaseModel):
    """Campos enviados são aplicados; para trocar o filtro, envie os três (os não usados como null)."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    max_size: Optional[int] = Field(default=None, ge=1, le=MAX_RANKING_SIZE)
    genre_id: Optional[int] = None
    franchise_id: Optional[int] = None
    platform_id: Optional[int] = None

    _single_filter = model_validator(mode="after")(_check_single_filter)


class RankingResponse(BaseModel):
    id: int
    name: str
    max_size: int
    position: int
    genre_id: Optional[int] = None
    franchise_id: Optional[int] = None
    platform_id: Optional[int] = None
    filter_type: Optional[str] = None   # "genre" | "franchise" | "platform"
    filter_label: Optional[str] = None  # nome do gênero/franquia/plataforma
    entries: List[GameResponse] = []    # na ordem (1º lugar primeiro)
    out_of_filter_ids: List[int] = []   # jogos que não casam mais com o filtro (ex.: gênero editado)

    model_config = ConfigDict(from_attributes=True)


class RankingEntriesRequest(BaseModel):
    game_ids: List[int] = Field(default_factory=list, max_length=MAX_RANKING_SIZE)


class RankingOrderRequest(BaseModel):
    ranking_ids: List[int]


class GameRankingPosition(BaseModel):
    ranking_id: int
    name: str
    position: int
