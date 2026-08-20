from pydantic import BaseModel, ConfigDict
from typing import Optional

class GenreBase(BaseModel):
    name: str
    color: Optional[str] = "#4A5568"

class GenreCreate(GenreBase):
    pass

class GenreUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None

class GenreResponse(GenreBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
