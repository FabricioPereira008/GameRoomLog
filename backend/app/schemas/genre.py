from pydantic import BaseModel, ConfigDict
from typing import Optional

class GenreBase(BaseModel):
    name: str
    color: Optional[str] = "#4f46e5"

class GenreCreate(GenreBase):
    pass

class GenreUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None

class GenreResponse(GenreBase):
    id: int
    games_count: Optional[int] = 0
    model_config = ConfigDict(from_attributes=True)
