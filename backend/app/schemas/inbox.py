"""Schemas do contrato com o app do portátil (docs/contracts) e da caixa de entrada."""
import datetime as dt
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

INBOX_FORMAT = "gameroom-inbox"
CATALOG_FORMAT = "gameroom-catalog"
INBOX_VERSION = 1
CATALOG_VERSION = 1

EventType = Literal["playing", "finished", "platinum"]


class InboxEventIn(BaseModel):
    """Um evento do pacote. Campos desconhecidos são ignorados (compatibilidade futura)."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=64)  # UUID gerado no app
    type: EventType
    title: str = Field(min_length=1, max_length=200)
    platform: Optional[str] = Field(default=None, max_length=100)
    game_id: Optional[int] = None  # do catálogo, quando o app o tiver
    date: Optional[dt.date] = None  # ausente: usa a data de created_at
    created_at: Optional[datetime] = None
    played_hours: Optional[float] = Field(default=None, ge=0)  # total acumulado, não incremento
    score: Optional[float] = Field(default=None, ge=0, le=10)
    difficulty: Optional[float] = Field(default=None, ge=0, le=10)
    notes: Optional[str] = Field(default=None, max_length=5000)


class InboxPackage(BaseModel):
    """Envelope do pacote. Eventos são validados um a um: um inválido não derruba os demais."""
    model_config = ConfigDict(extra="ignore")

    format: Literal["gameroom-inbox"]
    version: int = Field(ge=1)
    exported_at: Optional[datetime] = None
    events: List[Dict[str, Any]] = Field(max_length=5000)


class InboxImportResponse(BaseModel):
    received: int
    imported: int
    duplicates: int  # UUIDs já recebidos antes
    rejected: List[str]  # um aviso por evento inválido


class InboxEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str
    event_type: str
    title: str
    platform: Optional[str] = None
    game_id: Optional[int] = None
    event_date: date
    played_hours: Optional[float] = None
    score: Optional[float] = None
    difficulty: Optional[float] = None
    notes: Optional[str] = None


class PlatformMatch(BaseModel):
    platform_id: Optional[int] = None  # None: plataforma nova (será criada)
    name: str  # nome no GameRoom (ou o texto do app, se nova)
    similarity: int
    is_new: bool = False


class MatchCandidate(BaseModel):
    game_id: int
    title: str
    platform: Optional[str] = None
    status: str
    cover_image: Optional[str] = None
    similarity: int  # 0-100, após normalização
    platform_matches: bool
    current: Dict[str, Any]  # valores atuais dos campos que mudariam
    changes: Dict[str, Any]  # valores propostos (só os que mudam)
    # Rejogada de um jogo já concluído: jogo a criar, vinculado ao original (changes vale para o atual)
    replay: Optional[Dict[str, Any]] = None


class InboxGroup(BaseModel):
    """Eventos do mesmo jogo, em ordem cronológica, com os jogos candidatos."""
    key: str
    title: str
    platform: Optional[str] = None
    events: List[InboxEventOut]
    match: Literal["exact", "confirm", "none"]
    candidates: List[MatchCandidate]  # exact: o 1º é o vinculado; confirm: até 3 sugestões
    platform_match: Optional[PlatformMatch] = None
    new_game: Dict[str, Any]  # payload sugerido para criar o jogo, se nenhum candidato servir


class InboxPendingResponse(BaseModel):
    total_events: int
    groups: List[InboxGroup]


class InboxResolveRequest(BaseModel):
    event_ids: List[int] = Field(min_length=1)
    action: Literal["applied", "discarded"]
    game_id: Optional[int] = None  # jogo que recebeu os eventos (applied)


class InboxProposalRequest(BaseModel):
    event_ids: List[int] = Field(min_length=1)
    game_id: int


class InboxResolveResponse(BaseModel):
    resolved: int


class CatalogGame(BaseModel):
    id: int
    title: str
    platform: Optional[str] = None
    status: str


class CatalogResponse(BaseModel):
    format: str = CATALOG_FORMAT
    version: int = CATALOG_VERSION
    exported_at: datetime
    games: List[CatalogGame]
    platforms: List[str]
