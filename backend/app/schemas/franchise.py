from pydantic import BaseModel, ConfigDict
from typing import Optional

class FranchiseBase(BaseModel):
    name: str

class FranchiseCreate(FranchiseBase):
    pass

class FranchiseUpdate(BaseModel):
    name: Optional[str] = None

class FranchiseResponse(FranchiseBase):
    id: int
    games_count: Optional[int] = 0
    model_config = ConfigDict(from_attributes=True)
