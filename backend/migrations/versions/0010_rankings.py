"""personal rankings of favorite games

Revision ID: 0010_rankings
Revises: 0009_all_achievements
Create Date: 2026-11-16 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0010_rankings'
down_revision = '0009_all_achievements'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('rankings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('max_size', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('genre_id', sa.Integer(), nullable=True),
    sa.Column('franchise_id', sa.Integer(), nullable=True),
    sa.Column('platform_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['genre_id'], ['genres.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['franchise_id'], ['franchises.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['platform_id'], ['platforms.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_rankings_id'), 'rankings', ['id'], unique=False)
    op.create_table('ranking_entries',
    sa.Column('ranking_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('game_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['ranking_id'], ['rankings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('ranking_id', 'position'),
    sa.UniqueConstraint('ranking_id', 'game_id', name='uq_ranking_entries_game')
    )
    op.create_index(op.f('ix_ranking_entries_game_id'), 'ranking_entries', ['game_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ranking_entries_game_id'), table_name='ranking_entries')
    op.drop_table('ranking_entries')
    op.drop_index(op.f('ix_rankings_id'), table_name='rankings')
    op.drop_table('rankings')
