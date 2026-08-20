from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

class Platform(Base):
    __tablename__ = "platforms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    icon_name = Column(String(50), nullable=True)  # ex: pc, switch, 3ds, ps5

    games = relationship("Game", back_populates="platform")
