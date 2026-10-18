"""ordered genres per game (primary + secondary)

Revision ID: 0004_genre_position
Revises: 0003_inbox_events
Create Date: 2026-10-17 22:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0004_genre_position'
down_revision = '0003_inbox_events'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('game_genres', schema=None) as batch_op:
        batch_op.add_column(sa.Column('position', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('game_genres', schema=None) as batch_op:
        batch_op.drop_column('position')
