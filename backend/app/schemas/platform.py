from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

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
    model_config = ConfigDict(from_attributes=True)
