from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Text
from backend.app.core.database import Base
from backend.app.models.game import get_utc_now


class InboxEvent(Base):
    """Evento recebido do app do portátil (contrato gameroom-inbox), aguardando revisão.

    Guardado mesmo depois de aplicado/descartado: o UUID impede que reimportações dupliquem.
    `game_id` não é FK: o jogo pode ter sido excluído depois que o catálogo foi exportado.
    """
    __tablename__ = "inbox_events"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(64), unique=True, nullable=False, index=True)
    event_type = Column(String(20), nullable=False)  # playing | finished | platinum
    title = Column(String(200), nullable=False)
    platform = Column(String(100), nullable=True)
    game_id = Column(Integer, nullable=True)
    event_date = Column(Date, nullable=False)
    device_created_at = Column(DateTime, nullable=True)
    played_hours = Column(Float, nullable=True)
    score = Column(Float, nullable=True)
    difficulty = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    status = Column(String(20), nullable=False, default="pending", index=True)  # pending | applied | discarded
    applied_game_id = Column(Integer, nullable=True)
    received_at = Column(DateTime, default=get_utc_now, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
