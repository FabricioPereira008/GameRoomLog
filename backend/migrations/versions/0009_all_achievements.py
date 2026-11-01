"""100% with all achievements (games.all_achievements)

Revision ID: 0009_all_achievements
Revises: 0008_developer_from_relation
Create Date: 2026-11-01 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0009_all_achievements'
down_revision = '0008_developer_from_relation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD COLUMN simples (sem recriar `games`, que apagaria em cascata as linhas dependentes)
    op.add_column('games', sa.Column('all_achievements', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.execute("ALTER TABLE games DROP COLUMN all_achievements")
