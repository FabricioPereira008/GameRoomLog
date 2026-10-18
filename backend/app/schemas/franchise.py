from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional

class FranchiseBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)

class FranchiseCreate(FranchiseBase):
    pass

class FranchiseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)

class FranchiseResponse(FranchiseBase):
    id: int
    games_count: Optional[int] = 0
    completed_count: int = 0  # zerados + platinados (igual a games_count no modo só concluídos)
    total_hours: float = 0.0
    cover_samples: List[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)
