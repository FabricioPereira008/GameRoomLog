from pydantic import BaseModel, ConfigDict
from typing import Optional

class DeveloperBase(BaseModel):
    name: str

class DeveloperCreate(DeveloperBase):
    pass

class DeveloperUpdate(BaseModel):
    name: Optional[str] = None

class DeveloperResponse(DeveloperBase):
    id: int
    games_count: Optional[int] = 0
    model_config = ConfigDict(from_attributes=True)
