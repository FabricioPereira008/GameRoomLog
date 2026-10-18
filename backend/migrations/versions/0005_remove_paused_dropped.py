"""remove the Pausado and Desisti statuses

Revision ID: 0005_remove_paused_dropped
Revises: 0004_genre_position
Create Date: 2026-10-18 10:00:00.000000
"""
from alembic import op


revision = '0005_remove_paused_dropped'
down_revision = '0004_genre_position'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Pausado continuava na fila de espera; Desisti volta a ser um jogo disponível
    op.execute("UPDATE games SET status = 'FILA' WHERE status = 'PAUSADO'")
    op.execute("UPDATE games SET status = 'DISPONIVEL' WHERE status = 'DESISTI'")


def downgrade() -> None:
    pass  # os status antigos não são recriados
