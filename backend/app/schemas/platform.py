from pydantic import BaseModel, ConfigDict
from typing import Optional

class PlatformBase(BaseModel):
    name: str
    icon_name: Optional[str] = None

class PlatformCreate(PlatformBase):
    pass

class PlatformUpdate(BaseModel):
    name: Optional[str] = None
    icon_name: Optional[str] = None

class PlatformResponse(PlatformBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
