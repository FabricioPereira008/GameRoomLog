from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class GenreBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: Optional[str] = "#4f46e5"

class GenreCreate(GenreBase):
    pass

class GenreUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    color: Optional[str] = None

class GenreResponse(GenreBase):
    id: int
    games_count: Optional[int] = 0
    model_config = ConfigDict(from_attributes=True)
