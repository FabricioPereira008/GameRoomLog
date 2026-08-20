from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from backend.app.schemas.game import GameResponse

class CategoryDetailResponse(BaseModel):
    id: int
    name: str
    category_type: str  # 'genre', 'platform', 'franchise'
    color: Optional[str] = None
    icon_name: Optional[str] = None
    total_games: int
    total_hours_played: float
    games: List[GameResponse] = []
