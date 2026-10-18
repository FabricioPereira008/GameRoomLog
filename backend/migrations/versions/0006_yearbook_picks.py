"""yearbook podium (top 3 games of a year)

Revision ID: 0006_yearbook_picks
Revises: 0005_remove_paused_dropped
Create Date: 2026-10-18 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0006_yearbook_picks'
down_revision = '0005_remove_paused_dropped'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('yearbook_picks',
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('game_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('year', 'position')
    )


def downgrade() -> None:
    op.drop_table('yearbook_picks')
