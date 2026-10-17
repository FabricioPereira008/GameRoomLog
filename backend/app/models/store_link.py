from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.game import get_utc_now


class GameStoreLink(Base):
    """Vincula um jogo do GameRoom ao seu identificador numa loja (Steam, Epic, GOG...)."""
    __tablename__ = "game_store_links"
    __table_args__ = (UniqueConstraint("store", "external_id", name="uq_store_link_store_external"),)

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    store = Column(String(30), nullable=False)
    external_id = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)

    game = relationship("Game", back_populates="store_links")


class IgnoredStoreGame(Base):
    """Jogo de loja que o usuário decidiu não importar; não reaparece nos próximos scans."""
    __tablename__ = "ignored_store_games"
    __table_args__ = (UniqueConstraint("store", "external_id", name="uq_ignored_store_external"),)

    id = Column(Integer, primary_key=True, index=True)
    store = Column(String(30), nullable=False)
    external_id = Column(String(100), nullable=False)
    title = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
