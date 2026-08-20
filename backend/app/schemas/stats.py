from pydantic import BaseModel
from typing import List, Dict, Optional
from backend.app.schemas.game import GameResponse

class YearbookSummary(BaseModel):
    year: int
    total_games_finished: int
    total_platinums: int
    total_hours_played: float
    total_hltb_hours: float
    average_score: Optional[float] = None
    games: List[GameResponse] = []

class StatusCounts(BaseModel):
    jogando: int = 0
    proximos: int = 0
    fila: int = 0
    pausados: int = 0
    zerados: int = 0
    platinados: int = 0
    disponivel: int = 0
    desisti: int = 0
    wishlist: int = 0
    total: int = 0

class OverallStats(BaseModel):
    status_counts: StatusCounts
    total_hours: float
    available_years: List[int]
