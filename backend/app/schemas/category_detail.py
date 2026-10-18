from pydantic import BaseModel
from typing import List, Dict, Any, Literal, Optional

# Páginas de categoria: "completed" = só zerados/platinados (padrão), "all" = todos os jogos
CategoryScope = Literal["completed", "all"]
from backend.app.schemas.game import GameResponse

class CategoryDetailResponse(BaseModel):
    id: int
    name: str
    category_type: str  # 'genre', 'platform', 'franchise'
    color: Optional[str] = None
    icon_name: Optional[str] = None
    total_games: int
    completed_games: int = 0
    total_hours_played: float
    games: List[GameResponse] = []
