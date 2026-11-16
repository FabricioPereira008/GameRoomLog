from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


def _utc_now():
    return datetime.now(timezone.utc)


class Ranking(Base):
    """Ranking pessoal (ex.: "Top 10 de todos os tempos"). Filtro opcional: um gênero, franquia ou plataforma."""
    __tablename__ = "rankings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    max_size = Column(Integer, nullable=False, default=10)
    position = Column(Integer, nullable=False, default=0)  # ordem na página de Favoritos
    genre_id = Column(Integer, ForeignKey("genres.id", ondelete="SET NULL"), nullable=True)
    franchise_id = Column(Integer, ForeignKey("franchises.id", ondelete="SET NULL"), nullable=True)
    platform_id = Column(Integer, ForeignKey("platforms.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=_utc_now, nullable=False)

    genre = relationship("Genre")
    franchise = relationship("Franchise")
    platform = relationship("Platform")
    entries = relationship("RankingEntry", order_by="RankingEntry.position",
                           cascade="all, delete-orphan", passive_deletes=True)


class RankingEntry(Base):
    """Posição de um jogo num ranking (1 = primeiro lugar)."""
    __tablename__ = "ranking_entries"
    __table_args__ = (UniqueConstraint("ranking_id", "game_id", name="uq_ranking_entries_game"),)

    ranking_id = Column(Integer, ForeignKey("rankings.id", ondelete="CASCADE"), primary_key=True)
    position = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)

    game = relationship("Game")
