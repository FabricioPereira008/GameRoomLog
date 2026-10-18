from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from backend.app.schemas.game import GameResponse


class CountItem(BaseModel):
    name: str
    count: int
    hours: float = 0.0
    color: Optional[str] = None  # gêneros


class YearbookSummary(BaseModel):
    year: int
    total_games_finished: int
    total_platinums: int
    total_hours_played: float
    total_hltb_hours: float
    average_score: Optional[float] = None
    games: List[GameResponse] = []
    # Detalhes do ano
    previous_year_finished: Optional[int] = None  # para comparar com o ano anterior
    monthly_finished: List[int] = Field(default_factory=lambda: [0] * 12)  # jan..dez (jogos com data)
    genres: List[CountItem] = []       # principal e secundário contam
    platforms: List[CountItem] = []    # contagem e horas
    developers: List[CountItem] = []   # top 5
    franchises: List[CountItem] = []   # top 5
    average_difficulty: Optional[float] = None
    average_hours: Optional[float] = None
    replays: int = 0
    longest_game: Optional[GameResponse] = None
    best_game: Optional[GameResponse] = None
    hardest_game: Optional[GameResponse] = None
    # Pódio: escolhido pelo usuário ou, sem escolha, sugerido pela nota
    top3: List[GameResponse] = []
    top3_custom: bool = False


class Top3Request(BaseModel):
    game_ids: List[int] = Field(default_factory=list, max_length=3)  # na ordem (1º, 2º, 3º); vazio = sugestão

class StatusCounts(BaseModel):
    jogando: int = 0
    proximos: int = 0
    fila: int = 0
    zerados: int = 0
    platinados: int = 0
    disponivel: int = 0
    wishlist: int = 0
    total: int = 0

class OverallStats(BaseModel):
    status_counts: StatusCounts
    total_hours: float
    available_years: List[int]
