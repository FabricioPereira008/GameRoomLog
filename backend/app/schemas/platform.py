from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional

class PlatformBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    icon_name: Optional[str] = None

class PlatformCreate(PlatformBase):
    pass

class PlatformUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    icon_name: Optional[str] = None

class PlatformResponse(PlatformBase):
    id: int
    games_count: Optional[int] = 0
    completed_count: int = 0  # zerados + platinados (igual a games_count no modo só concluídos)
    total_hours: float = 0.0
    cover_samples: List[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)
