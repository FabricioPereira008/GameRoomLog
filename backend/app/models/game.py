import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, 
    ForeignKey, Table, Text, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

def get_utc_now():
    return datetime.now(timezone.utc)

# Tabela associativa Many-to-Many entre Game e Genre
game_genres = Table(
    "game_genres",
    Base.metadata,
    Column("game_id", Integer, ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", Integer, ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)

class GameStatus(str, enum.Enum):
    DISPONIVEL = "Disponível"
    FILA = "Fila"
    PROXIMO = "Próximo"
    JOGANDO = "Jogando"
    PAUSADO = "Pausado"
    ZERADO = "Zerado"
    PLATINADO = "Platinado"
    DESISTI = "Desisti"
    WISHLIST = "Lista de Desejos"

class PlayType(str, enum.Enum):
    PRIMEIRA_JOGADA = "Primeira Jogada"
    REJOGADA = "Rejogada"

class GameFormat(str, enum.Enum):
    DIGITAL = "Digital"
    FISICO = "Físico"
    EMULADO = "Emulado"

class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    developer = Column(String(150), nullable=True)
    developer_id = Column(Integer, ForeignKey("developers.id"), nullable=True)
    
    # Chaves estrangeiras
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=True)
    franchise_id = Column(Integer, ForeignKey("franchises.id"), nullable=True)

    # Status e Imagens
    status = Column(SQLEnum(GameStatus), default=GameStatus.DISPONIVEL, nullable=False, index=True)
    cover_image = Column(String(300), nullable=True)
    
    # Tempo e Estimativas (salvos como float no banco, inteiros na UI)
    hltb_hours = Column(Float, nullable=True, default=0.0)
    played_hours = Column(Float, nullable=True, default=0.0)

    # Avaliação e Dificuldade (0-10)
    score = Column(Float, nullable=True)
    difficulty = Column(Float, nullable=True)

    # Datas
    finish_date = Column(Date, nullable=True)
    platinum_date = Column(Date, nullable=True)
    completion_year = Column(Integer, nullable=True, index=True)

    # Metadados adicionais
    play_type = Column(SQLEnum(PlayType), default=PlayType.PRIMEIRA_JOGADA, nullable=False)
    play_count = Column(Integer, default=1, nullable=False)
    format = Column(SQLEnum(GameFormat), default=GameFormat.DIGITAL, nullable=False)
    is_favorite = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=get_utc_now, nullable=False)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # Relacionamentos
    platform = relationship("Platform", back_populates="games")
    franchise = relationship("Franchise", back_populates="games")
    developer_rel = relationship("Developer", back_populates="games")
    genres = relationship("Genre", secondary="game_genres", back_populates="games")
