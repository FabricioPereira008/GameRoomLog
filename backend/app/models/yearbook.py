from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class YearbookPick(Base):
    """Pódio do Anuário: os 3 melhores jogos de um ano, escolhidos pelo usuário (posição 1 a 3)."""
    __tablename__ = "yearbook_picks"

    year = Column(Integer, primary_key=True)
    position = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)

    game = relationship("Game")
